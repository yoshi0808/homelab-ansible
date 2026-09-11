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


HEALTH_LABELS = {
    "OK": "問題なし",
    "WARNING": "要確認",
    "CRITICAL": "異常",
    "UNKNOWN": "判定不能",
}

ISSUE_LABELS = {
    "pool/vdev state or IO errors": "ZFSプールまたは構成デバイスの状態・I/Oエラーを確認してください",
    "ZFS data errors reported": "ZFSがデータエラーを報告しています",
    "scrub errors": "scrubでエラーが報告されています",
    "scrub repaired data": "scrubでデータ修復が行われました",
    "scrub result stale": "前回scrubから日数が経過しています",
    "scrub completion unavailable or scan in progress": "scrub完了履歴がないか、現在処理中です",
    "counter reset suspected": "カウンターが減少しました（リセットまたは交換の可能性）",
    "error log count increased": "NVMe error-logの累積数が増加しました",
    "device replacement/addition": "前回にないデバイスです（交換または追加の可能性）",
    "NVMe health warning/media errors/spare": "NVMeの警告、media error、予備領域を確認してください",
    "endurance used threshold": "NVMe消耗率が基準値以上です",
    "empty target list": "点検対象hostがありません",
    "history corrupt; comparison unavailable": "保存履歴が壊れているため前回比較できません",
}


def display_time(value):
    """Render a stored offset-aware time for a human reader."""
    if not value:
        return "記録なし"
    return datetime.fromisoformat(value).astimezone(JST).strftime("%Y-%m-%d %H:%M JST")


def issue_text(reason):
    """Translate known machine-facing issue codes while retaining identity prefixes."""
    for code, label in ISSUE_LABELS.items():
        if reason == code:
            return label
        suffix = ": " + code
        if reason.endswith(suffix):
            return reason[:-len(suffix)] + ": " + label
    if "collection incomplete:" in reason:
        prefix, detail = reason.split("collection incomplete:", 1)
        return prefix + "収集データが不完全です（" + detail.strip() + "）"
    return reason


def sorted_issues(report):
    """Put uncertainty and failures before warnings without changing stored JSON."""
    priority = {"UNKNOWN": 0, "CRITICAL": 1, "WARNING": 2, "OK": 3}
    return sorted(report.get("issues", []), key=lambda item: priority.get(item[0], 0))


def comparison_text(device):
    state = device["comparison"]
    if state == "baseline":
        return "初回基準値として記録"
    if state == "history_corrupt":
        return "履歴破損のため比較不能"
    if state == "replacement_or_added":
        return "前回にないデバイス（交換または追加の可能性）"
    delta = device.get("delta", {})
    detail = "media error {:+d} / error-log {:+d}".format(
        delta.get("media_errors", 0), delta.get("num_err_log_entries", 0))
    if state == "reset_suspected":
        return "カウンター減少（リセットまたは交換の可能性）: " + detail
    return "前回比: " + detail


def short_summary(report):
    """Return a compact Japanese summary suitable for Slack."""
    health = HEALTH_LABELS.get(report.get("health"), "判定不能")
    if report.get("collection") != "ok":
        lead = "収集または比較が完了していません（" + health + "）"
    elif report.get("health") == "OK":
        lead = "異常は見つかりませんでした"
    else:
        lead = "確認が必要です（" + health + "）"
    issues = [HEALTH_LABELS.get(level, level) + "：" + issue_text(reason)
              for level, reason in sorted_issues(report)]
    if not issues:
        return lead
    shown = issues[:3]
    if len(issues) > 3:
        shown.append("ほか" + str(len(issues) - 3) + "件")
    return lead + " / " + " / ".join(shown)


def markdown(report):
    healthy_hosts = sum(data["collection"] == "ok" for data in report["hosts"].values())
    lines = ["# ストレージ月次点検 " + report["month"], "", "## 結論",
             "**" + short_summary(report).split(" / ", 1)[0] + "**",
             "- 総合判定: " + HEALTH_LABELS.get(report["health"], "判定不能") +
             "（" + report["health"] + "）",
             "- 収集結果: " + str(healthy_hosts) + "/" + str(len(report["hosts"])) + "台で成功",
             "- 観測日時: " + display_time(report["collected_at"]), "", "## 対応・未確認事項"]
    lines += ["- [" + HEALTH_LABELS.get(level, level) + "] " + issue_text(reason)
              for level, reason in sorted_issues(report)] or ["- 対応はありません"]
    lines += ["", "## 前回比較"]
    if report["history_error"]:
        lines.append("保存履歴が壊れているため比較できません。今回値を正常値として扱わないでください。")
    elif report["comparison_source"]:
        lines.append("比較元: " + display_time(report["comparison_source"]["collected_at"]))
    else:
        lines.append("初回点検のため前回比較はありません。今回値を今後の基準として記録しました。")
    for host, data in report["hosts"].items():
        lines += ["", "## " + host,
                  "収集: " + ("成功" if data["collection"] == "ok" else "失敗・判定不能")]
        for pool in data["pools"]:
            scrub = pool["scrub"]
            pool_state = "正常（ONLINE）" if pool["state"] == "ONLINE" else "異常（" + pool["state"] + "）"
            lines += ["", "### ZFS " + pool["name"], "- プール状態: " + pool_state]
            if scrub.get("completed_at"):
                age = (datetime.fromisoformat(report["collected_at"]) -
                       datetime.fromisoformat(scrub["completed_at"])).days
                lines += ["- 最終scrub: " + display_time(scrub["completed_at"]) +
                          "（" + str(age) + "日前）",
                          "- scrub結果: 修復 " + str(scrub.get("repaired", "不明")) +
                          " / エラー " + str(scrub.get("errors", "不明")) + "件"]
            else:
                lines.append("- scrub結果: 完了日時を確認できません（" + scrub["raw"] + "）")
            lines.append("- 構成デバイス:")
            for vdev in pool["vdevs"]:
                vdev_state = "正常" if vdev["state"] == "ONLINE" else "異常（" + vdev["state"] + "）"
                lines.append("  - " + vdev["name"] + ": " + vdev_state +
                             " / 読み取りエラー " + str(vdev["read"]) +
                             " / 書き込みエラー " + str(vdev["write"]) +
                             " / チェックサムエラー " + str(vdev["cksum"]))
        for number, device in enumerate(data["devices"], 1):
            values = device["values"]
            lines += ["", "### NVMe " + str(number) + "（" + device["model"] + "）",
                      "- 温度: " + str(device["temperature_c"]) + " °C",
                      "- 消耗率: " + str(values["percent_used"]) + "%",
                      "- 予備領域: " + str(values["avail_spare"]) +
                      "%（警告基準 " + str(values["spare_thresh"]) + "%）",
                      "- 重大警告: " + ("なし" if values["critical_warning"] == 0 else
                                      "あり（" + str(values["critical_warning"]) + "）"),
                      "- メディアエラー累積: " + str(values["media_errors"]) + "件",
                      "- エラーログ累積: " + str(values["num_err_log_entries"]) + "件",
                      "- 比較: " + comparison_text(device)]
    lines += ["", "## 詳細情報", "- Report ID: " + report["report_id"]]
    if report["comparison_source"]:
        lines.append("- 比較元Report ID: " + str(report["comparison_source"]["report_id"]))
    for host, data in report["hosts"].items():
        for device in data["devices"]:
            lines.append("- " + host + " / " + device["model"] + ": serial " + device["serial"] +
                         " / vdev " + device["vdev"] + " / device " + device["namespace"])
    return "\n".join(lines) + "\n"
