"""Pure storage report classification and serialization helpers."""
import json
import re
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))
COUNTERS = ("media_errors", "num_err_log_entries")


def scan_timestamp(value):
    """Parse the collector's LC_ALL=C date without controller locale state."""
    match = re.fullmatch(
        r"(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+([A-Za-z]{3})\s+(\d{1,2})\s+"
        r"(\d{2}):(\d{2}):(\d{2})\s+(\d{4})", value)
    if not match:
        raise ValueError('invalid scrub timestamp')
    months = 'Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec'.split()
    month = months.index(match[2]) + 1
    return datetime(int(match[7]), month, int(match[3]), int(match[4]),
                    int(match[5]), int(match[6]), tzinfo=JST)


def integer(value):
    if isinstance(value, bool):
        raise ValueError("boolean is not a counter")
    if isinstance(value, int) and value >= 0:
        return value
    if isinstance(value, str) and re.fullmatch(r"\d+", value):
        return int(value)
    raise ValueError("invalid nonnegative integer")


def zfs(text, now, stale_days):
    pools = []
    for section in re.split(r"(?m)^\s*pool:\s*", text)[1:]:
        name = section.splitlines()[0].strip()
        state = re.search(r"(?m)^\s*state:\s*(\S+)", section)
        scan = re.search(r"(?m)^\s*scan:\s*(.*)", section)
        config = re.search(r"config:\s*\n(.*?)\nerrors:", section, re.S)
        if not state or not scan or not config:
            raise ValueError("unrecognized zpool status")
        rows = []
        for line in config[1].splitlines():
            match = re.fullmatch(r"\s*(\S+)\s+(\S+)\s+(\d+)\s+(\d+)\s+(\d+)\s*", line)
            if match:
                rows.append(dict(zip(("name", "state", "read", "write", "cksum"),
                                     [match[1], match[2], *map(int, match.group(3, 4, 5))])))
        if not rows:
            raise ValueError("missing pool config rows")
        issues = []
        if state[1] != "ONLINE" or any(r["state"] != "ONLINE" or
                                         r["read"] + r["write"] + r["cksum"] for r in rows):
            issues.append(["CRITICAL", "pool/vdev state or IO errors"])
        if not re.search(r"(?m)^errors:\s*No known data errors\s*$", section):
            issues.append(["CRITICAL", "ZFS data errors reported"])
        scrub = {"raw": scan[1], "completed_at": None}
        completed = re.fullmatch(r"scrub repaired (\S+) in .+ with (\d+) errors on (.+)", scan[1])
        if completed:
            stamp = scan_timestamp(completed[3])
            if stamp > now:
                raise ValueError("future scrub timestamp")
            scrub.update(completed_at=stamp.isoformat(), repaired=completed[1], errors=int(completed[2]))
            if int(completed[2]):
                issues.append(["CRITICAL", "scrub errors"])
            if completed[1] not in ("0", "0B"):
                issues.append(["WARNING", "scrub repaired data"])
            if (now - stamp).total_seconds() > stale_days * 86400:
                issues.append(["WARNING", "scrub result stale"])
        elif "in progress" in scan[1] or scan[1] == "none requested" or scan[1].startswith("resilvered "):
            issues.append(["WARNING", "scrub completion unavailable or scan in progress"])
        else:
            raise ValueError("unrecognized scan result")
        pools.append({"name": name, "state": state[1], "vdevs": rows, "scrub": scrub, "issues": issues})
    if not pools:
        raise ValueError("no pools observed")
    return pools


def build_report(observations, report_id, collected_at, baseline=None, stale_days=35,
                 wear_warning=80, wear_critical=100, history_error=False):
    now = datetime.fromisoformat(collected_at)
    if now.utcoffset() is None:
        raise ValueError("timestamp needs timezone")
    hosts, issues = {}, []
    prior_hosts = (baseline or {}).get("hosts", {})
    for host, raw in observations.items():
        entry = {"collection": "error", "devices": [], "pools": [], "issues": []}
        hosts[host] = entry
        try:
            if raw.get("schema_version") != 1 or raw["zpool"]["rc"] != 0:
                raise ValueError("missing or failed collection")
            entry["pools"] = zfs(raw["zpool"]["stdout"], now, stale_days)
            for pool in entry["pools"]:
                entry["issues"].extend(pool["issues"])
            if not raw["devices"]:
                raise ValueError("no physical devices")
            prior = {d["id"]: d for d in prior_hosts.get(host, {}).get("devices", [])}
            seen = set()
            for device in raw["devices"]:
                identity = device["identity"]
                health = device["health"]
                if identity["rc"] != 0 or health["rc"] != 0:
                    raise ValueError("NVMe command failed")
                serial, model = (identity["json"][k].strip() for k in ("sn", "mn"))
                if not serial or not model:
                    raise ValueError("missing identity")
                key = json.dumps([host, serial, model], ensure_ascii=False)
                if key in seen:
                    raise ValueError("duplicate physical identity")
                seen.add(key)
                source = health["json"]
                values = {k: integer(source[k]) for k in
                          (*COUNTERS, "critical_warning", "temperature", "avail_spare",
                           "spare_thresh", "percent_used")}
                out = {"id": key, "serial": serial, "model": model, "vdev": device["vdev"],
                       "namespace": device["namespace"], "values": values,
                       "temperature_c": round(values["temperature"] - 273.15, 2),
                       "comparison": "baseline", "delta": {}}
                if history_error:
                    out["comparison"] = "history_corrupt"
                elif key in prior:
                    previous = prior[key]["values"]
                    out['comparison_source'] = prior[key].get('comparison_source') or {
                        k: baseline[k] for k in ('report_id', 'collected_at')}
                    delta = {k: values[k] - integer(previous[k]) for k in COUNTERS}
                    out["delta"] = delta
                    out["comparison"] = "reset_suspected" if any(v < 0 for v in delta.values()) else "compared"
                    if any(v < 0 for v in delta.values()):
                        entry["issues"].append(["WARNING", serial + ": counter reset suspected"])
                    if delta["num_err_log_entries"] > 0:
                        entry["issues"].append(["WARNING", serial + ": error log count increased"])
                elif prior:
                    out["comparison"] = "replacement_or_added"
                    entry["issues"].append(["WARNING", serial + ": device replacement/addition"])
                if values["critical_warning"] or values["media_errors"] or values["avail_spare"] < values["spare_thresh"]:
                    entry["issues"].append(["CRITICAL", serial + ": NVMe health warning/media errors/spare"])
                if values["percent_used"] >= wear_warning:
                    entry["issues"].append(["CRITICAL" if values["percent_used"] >= wear_critical else "WARNING",
                                            serial + ": endurance used threshold"])
                entry["devices"].append(out)
            entry["collection"] = "ok"
        except (KeyError, ValueError, TypeError, AttributeError) as exc:
            entry["issues"].append(["UNKNOWN", "collection incomplete: " + type(exc).__name__])
        issues.extend([[level, host + ": " + reason] for level, reason in entry["issues"]])
    if not hosts:
        issues.append(["UNKNOWN", "empty target list"])
    if history_error:
        issues.append(["UNKNOWN", "history corrupt; comparison unavailable"])
    levels = {"OK": 0, "WARNING": 1, "CRITICAL": 2, "UNKNOWN": 3}
    health = max((i[0] for i in issues), key=levels.get, default="OK")
    return {"schema_version": 1, "report_id": report_id, "collected_at": collected_at,
            "month": now.astimezone(JST).strftime("%Y-%m"), "hosts": hosts, "issues": issues,
            "health": health, "collection": "ok" if hosts and all(h["collection"] == "ok" for h in hosts.values()) else "error",
            "comparison_source": {k: baseline.get(k) for k in ("report_id", "collected_at")} if baseline else None,
            "history_error": history_error}


def markdown(report):
    lines = ["# ストレージ月次点検 " + report["month"], "",
             "Report: " + report["report_id"], "観測: " + report["collected_at"],
             "健康状態: " + report["health"] + " / 収集: " + report["collection"],
             "比較元: " + json.dumps(report["comparison_source"], ensure_ascii=False), "", "## 対応・未確認事項"]
    lines += ["- " + level + ": " + reason for level, reason in report["issues"]] or ["- なし"]
    for host, data in report["hosts"].items():
        lines += ["", "## " + host, "収集: " + data["collection"]]
        for pool in data["pools"]:
            lines += ["### Pool " + pool["name"], "状態: " + pool["state"],
                      "Scrub: " + json.dumps(pool["scrub"], ensure_ascii=False),
                      "Vdev: " + json.dumps(pool["vdevs"], ensure_ascii=False)]
        for device in data["devices"]:
            lines += ["### NVMe " + device["serial"], json.dumps(device, ensure_ascii=False, indent=2)]
    return "\n".join(lines) + "\n"
