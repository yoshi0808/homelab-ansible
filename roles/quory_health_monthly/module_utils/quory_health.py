"""Pure quory health classification and serialization helpers.

Issues are 3-tuples ``[level, code, detail]``. ``code`` is a stable
machine-facing string used for classification and label lookup (issue_text);
``detail`` carries the dynamic, human-facing values (current value, delta,
comparison source) so a truncated or generic-sounding code is never the only
thing a reader sees.
"""
import json
import re
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))
COUNTERS = ("media_errors", "num_err_log_entries")


def integer(value):
    if isinstance(value, bool):
        raise ValueError("boolean is not a counter")
    if isinstance(value, int) and value >= 0:
        return value
    if isinstance(value, str) and re.fullmatch(r"\d+", value):
        return int(value)
    raise ValueError("invalid nonnegative integer")


def parse_df_percent(raw_value):
    """Only trust df's own use% field; never recompute from a different denominator."""
    match = re.fullmatch(r"(\d{1,3})%", (raw_value or "").strip())
    if not match:
        return None
    value = int(match[1])
    return value if 0 <= value <= 100 else None


def filesystem(raw, name, warning, critical, growth_warning_points, prior=None, history_error=False):
    if not isinstance(raw, dict) or "error" in raw:
        detail = raw.get("error", "missing_observation") if isinstance(raw, dict) else "missing_observation"
        if isinstance(raw, dict) and raw.get("error") == "not_mounted":
            detail = "not_mounted (actual_mount=" + str(raw.get("actual_mount")) + ")"
        return {"name": name, "collection": "error",
                "issues": [["UNKNOWN", name + ": filesystem observation unavailable", str(detail)]]}
    use_percent = parse_df_percent(raw.get("use_percent_raw"))
    if use_percent is None:
        return {"name": name, "collection": "error",
                "issues": [["UNKNOWN", name + ": df usage percent unparsable",
                            "raw=" + str(raw.get("use_percent_raw"))]]}
    size = integer(raw["size_bytes"])
    used = integer(raw["used_bytes"])
    avail = integer(raw["avail_bytes"])
    out = {"name": name, "collection": "ok", "mountpoint": raw["mountpoint"], "source": raw["source"],
           "fstype": raw["fstype"], "size_bytes": size, "used_bytes": used, "avail_bytes": avail,
           "use_percent": use_percent, "comparison": "baseline", "delta": {}}
    delta_percent = None
    comparison_note = ""
    if history_error:
        out["comparison"] = "history_corrupt"
        comparison_note = "（履歴破損のため比較不能）"
    elif prior is not None and prior.get("collection") == "ok":
        delta_percent = use_percent - prior["use_percent"]
        out["delta"] = {"used_bytes": used - prior["used_bytes"], "use_percent": delta_percent}
        out["comparison_source"] = prior["comparison_source"]
        out["comparison"] = "compared"
        comparison_note = "（前回{}%→今回{}%、{:+d}pt、比較元 {} ({})）".format(
            prior["use_percent"], use_percent, delta_percent,
            prior["comparison_source"]["report_id"], display_time(prior["comparison_source"]["collected_at"]))
    issues = []
    if use_percent >= critical:
        issues.append(["CRITICAL", name + ": filesystem usage threshold", str(use_percent) + "%" + comparison_note])
    elif use_percent >= warning:
        issues.append(["WARNING", name + ": filesystem usage threshold", str(use_percent) + "%" + comparison_note])
    if delta_percent is not None and delta_percent >= growth_warning_points and use_percent < critical:
        issues.append(["WARNING", name + ": usage grew notably since last comparison", comparison_note.strip("（）")])
    out["issues"] = issues
    return out


def memory(raw, warning_percent, critical_percent, drop_warning_points, swap_growth_warning_bytes,
          prior=None, history_error=False):
    required = ("MemTotal", "MemAvailable", "SwapTotal", "SwapFree")
    if not isinstance(raw, dict) or any(k not in raw for k in required):
        return {"collection": "error", "issues": [["UNKNOWN", "memory observation unavailable", ""]]}
    total = integer(raw["MemTotal"])
    available = integer(raw["MemAvailable"])
    swap_total = integer(raw["SwapTotal"])
    swap_free = integer(raw["SwapFree"])
    if swap_free > swap_total:
        raise ValueError("swap free exceeds total")
    if total <= 0:
        raise ValueError("non-positive memory total")
    swap_used = swap_total - swap_free
    available_percent = round(available * 100 / total, 2)
    out = {"collection": "ok", "total_bytes": total, "available_bytes": available,
           "available_percent": available_percent, "swap_total_bytes": swap_total,
           "swap_used_bytes": swap_used, "comparison": "baseline", "delta": {}}
    drop_points, swap_growth = None, None
    comparison_note, swap_note = "", ""
    if history_error:
        out["comparison"] = "history_corrupt"
        comparison_note = swap_note = "（履歴破損のため比較不能）"
    elif prior is not None and prior.get("collection") == "ok":
        drop_points = prior["available_percent"] - available_percent
        swap_growth = swap_used - prior["swap_used_bytes"]
        out["delta"] = {"available_bytes": available - prior["available_bytes"],
                        "available_percent": -drop_points, "swap_used_bytes": swap_growth}
        out["comparison_source"] = prior["comparison_source"]
        out["comparison"] = "compared"
        source_text = "比較元 {} ({})".format(
            prior["comparison_source"]["report_id"], display_time(prior["comparison_source"]["collected_at"]))
        comparison_note = "（前回{}%→今回{}%、{:+.2f}pt、{}）".format(
            prior["available_percent"], available_percent, -drop_points, source_text)
        # swap has its own prior/current/delta — it must never be read off the
        # unrelated memory-available comparison_note (AC3: 現在値・前回値・
        # 差分・比較元をswap自身の値で示す。available%と桁も単位も別物)。
        swap_note = "（前回 {} bytes→今回 {} bytes、{:+d} bytes、{}）".format(
            prior["swap_used_bytes"], swap_used, swap_growth, source_text)
    issues = []
    if available_percent <= critical_percent:
        issues.append(["CRITICAL", "memory available threshold", str(available_percent) + "%" + comparison_note])
    elif available_percent <= warning_percent:
        issues.append(["WARNING", "memory available threshold", str(available_percent) + "%" + comparison_note])
    if drop_points is not None and drop_points >= drop_warning_points and available_percent > critical_percent:
        issues.append(["WARNING", "memory available dropped notably since last comparison",
                      comparison_note.strip("（）")])
    if swap_growth is not None and swap_growth >= swap_growth_warning_bytes:
        issues.append(["WARNING", "swap usage grew notably since last comparison",
                      str(swap_used) + " bytes" + swap_note])
    out["issues"] = issues
    return out


def device_health(device, prior, history_error, baseline, wear_warning, wear_critical, entry_issues):
    namespace = device.get("namespace", "unknown")
    identity = device.get("identity") or {}
    health = device.get("health") or {}
    if identity.get("rc") != 0 or health.get("rc") != 0:
        reason = "tool_unavailable" if identity.get("rc") == -1 or health.get("rc") == -1 else "command_failed"
        entry_issues.append(["UNKNOWN", namespace + ": NVMe health unavailable", reason])
        return {"id": namespace, "namespace": namespace, "health_status": "UNKNOWN", "reason": reason,
                "values": {}, "comparison": "unavailable", "delta": {}}
    identity_json = identity["json"]
    health_json = health["json"]
    serial, model = (identity_json[k].strip() for k in ("sn", "mn"))
    if not serial or not model:
        raise ValueError("missing identity")
    key = json.dumps([serial, model], ensure_ascii=False)
    values = {k: integer(health_json[k]) for k in
              (*COUNTERS, "critical_warning", "temperature", "avail_spare", "spare_thresh", "percent_used")}
    out = {"id": key, "namespace": namespace, "serial": serial, "model": model, "values": values,
           "temperature_c": round(values["temperature"] - 273.15, 2), "health_status": "OK",
           "reason": "", "comparison": "baseline", "delta": {}}
    if history_error:
        out["comparison"] = "history_corrupt"
    elif key in prior:
        previous = prior[key]["values"]
        out["comparison_source"] = prior[key].get("comparison_source") or {
            k: baseline[k] for k in ("report_id", "collected_at")}
        delta = {k: values[k] - integer(previous[k]) for k in COUNTERS}
        out["delta"] = delta
        out["comparison"] = "reset_suspected" if any(v < 0 for v in delta.values()) else "compared"
        if any(v < 0 for v in delta.values()):
            entry_issues.append(["WARNING", serial + ": counter reset suspected", ""])
        if delta["num_err_log_entries"] > 0:
            entry_issues.append(["WARNING", serial + ": error log count increased",
                                "+" + str(delta["num_err_log_entries"])])
    elif prior:
        out["comparison"] = "replacement_or_added"
        entry_issues.append(["WARNING", serial + ": device replacement/addition", ""])
    if values["critical_warning"] or values["media_errors"] or values["avail_spare"] < values["spare_thresh"]:
        out["health_status"] = "CRITICAL"
        entry_issues.append(["CRITICAL", serial + ": NVMe health warning/media errors/spare", ""])
    if values["percent_used"] >= wear_warning:
        level = "CRITICAL" if values["percent_used"] >= wear_critical else "WARNING"
        if level == "CRITICAL":
            out["health_status"] = "CRITICAL"
        elif out["health_status"] == "OK":
            out["health_status"] = "WARNING"
        entry_issues.append([level, serial + ": endurance used threshold", str(values["percent_used"]) + "%"])
    return out


def build_report(observations, report_id, collected_at, baseline=None, previous=None, fs_warning=80,
                  fs_critical=90, mem_warning=15, mem_critical=5, wear_warning=80, wear_critical=100,
                  fs_growth_warning_points=10, mem_drop_warning_points=10,
                  swap_growth_warning_bytes=104857600, history_error=False):
    now = datetime.fromisoformat(collected_at)
    if now.utcoffset() is None:
        raise ValueError("timestamp needs timezone")
    hosts, issues = {}, []
    prior_hosts = (baseline or {}).get("hosts", {})
    previous = previous or {}
    for host, raw in observations.items():
        entry = {"collection": "ok", "filesystems": {}, "memory": {}, "devices": [],
                 "nvme_transport_observed": None, "issues": []}
        hosts[host] = entry
        ok = isinstance(raw, dict) and raw.get("schema_version") == 1
        if not ok:
            entry["issues"].append(["UNKNOWN", "collection incomplete", "missing_or_invalid_schema"])
        else:
            previous_full = previous.get(host)
            previous_entry = previous_full["hosts"][host] if previous_full else {}
            previous_source = ({"report_id": previous_full["report_id"],
                                "collected_at": previous_full["collected_at"]} if previous_full else None)
            prior_devices = {d["id"]: d for d in prior_hosts.get(host, {}).get("devices", [])}

            fs = {}
            for name in ("root", "efi"):
                prior_fs = previous_entry.get("filesystems", {}).get(name)
                if prior_fs is not None and prior_fs.get("collection") == "ok":
                    prior_fs = dict(prior_fs, comparison_source=previous_source)
                try:
                    fs[name] = filesystem(raw.get("filesystems", {}).get(name), name, fs_warning, fs_critical,
                                          fs_growth_warning_points, prior_fs, history_error)
                except (KeyError, ValueError, TypeError) as exc:
                    fs[name] = {"name": name, "collection": "error",
                                "issues": [["UNKNOWN", name + ": collection incomplete", type(exc).__name__]]}
                entry["issues"].extend(fs[name]["issues"])
                if fs[name]["collection"] != "ok":
                    ok = False
            entry["filesystems"] = fs

            prior_mem = previous_entry.get("memory")
            if prior_mem is not None and prior_mem.get("collection") == "ok":
                prior_mem = dict(prior_mem, comparison_source=previous_source)
            try:
                mem = memory(raw.get("memory"), mem_warning, mem_critical, mem_drop_warning_points,
                            swap_growth_warning_bytes, prior_mem, history_error)
            except (KeyError, ValueError, TypeError) as exc:
                mem = {"collection": "error",
                       "issues": [["UNKNOWN", "memory: collection incomplete", type(exc).__name__]]}
            entry["memory"] = mem
            entry["issues"].extend(mem["issues"])
            if mem["collection"] != "ok":
                ok = False

            # lsblk_valid is decided by the collector, which is the only side that
            # actually parses lsblk's JSON shape (blockdevices present, rows
            # well-formed) — trust that single source rather than re-guessing
            # validity from rc/json-type here, which previously let rc=0 with an
            # empty or malformed payload pass as "zero NVMe devices, healthy".
            if not raw.get("lsblk_valid"):
                lsblk = raw.get("lsblk") if isinstance(raw.get("lsblk"), dict) else {}
                entry["issues"].append(["UNKNOWN", "NVMe device enumeration unavailable",
                                        lsblk.get("error", "lsblk_invalid")])
                ok = False
            else:
                entry["nvme_transport_observed"] = bool(raw.get("nvme_transport_observed"))
                seen = set()
                for device in raw.get("devices", []):
                    try:
                        out = device_health(device, prior_devices, history_error, baseline, wear_warning,
                                            wear_critical, entry["issues"])
                    except (KeyError, ValueError, TypeError) as exc:
                        namespace = device.get("namespace", "unknown") if isinstance(device, dict) else "unknown"
                        out = {"id": namespace, "namespace": namespace, "health_status": "UNKNOWN",
                               "reason": "invalid_observation", "values": {}, "comparison": "unavailable",
                               "delta": {}}
                        entry["issues"].append(["UNKNOWN", namespace + ": NVMe observation invalid",
                                                type(exc).__name__])
                        ok = False
                    if out["id"] in seen and out.get("reason", "") == "":
                        entry["issues"].append(["UNKNOWN", out["namespace"] + ": duplicate physical identity", ""])
                        ok = False
                    else:
                        seen.add(out["id"])
                    entry["devices"].append(out)
        entry["collection"] = "ok" if ok else "error"
        host_levels = {"OK": 0, "WARNING": 1, "CRITICAL": 2, "UNKNOWN": 3}
        entry["health"] = max((i[0] for i in entry["issues"]), key=host_levels.get, default="OK")
        issues.extend([[level, host + ": " + code, detail] for level, code, detail in entry["issues"]])
    if not hosts:
        issues.append(["UNKNOWN", "empty target list", ""])
    if history_error:
        issues.append(["UNKNOWN", "history corrupt; comparison unavailable", ""])
    levels = {"OK": 0, "WARNING": 1, "CRITICAL": 2, "UNKNOWN": 3}
    health = max((i[0] for i in issues), key=levels.get, default="OK")
    return {"schema_version": 1, "report_id": report_id, "collected_at": collected_at,
            "month": now.astimezone(JST).strftime("%Y-%m"), "hosts": hosts, "issues": issues,
            "health": health,
            "collection": "ok" if hosts and all(h["collection"] == "ok" for h in hosts.values()) else "error",
            "comparison_source": {k: baseline.get(k) for k in ("report_id", "collected_at")} if baseline else None,
            "history_error": history_error}


HEALTH_LABELS = {
    "OK": "問題なし",
    "WARNING": "要確認",
    "CRITICAL": "異常",
    "UNKNOWN": "判定不能",
}

ISSUE_LABELS = {
    "filesystem observation unavailable": "ファイルシステムの観測が取得できません",
    "df usage percent unparsable": "dfの使用率が解釈できません",
    "filesystem usage threshold": "ファイルシステム使用率が基準値以上です",
    "usage grew notably since last comparison": "使用率が前回より大きく増加しました",
    "memory observation unavailable": "メモリの観測が取得できません",
    "memory available threshold": "メモリ空き容量が基準値以下です",
    "memory available dropped notably since last comparison": "メモリ空き容量が前回より大きく減少しました",
    "swap usage grew notably since last comparison": "swap使用量が前回より大きく増加しました",
    "memory: collection incomplete": "メモリ収集データが不完全です",
    "NVMe device enumeration unavailable": "NVMeデバイス一覧が取得できません",
    "NVMe health unavailable": "NVMe健康情報を取得できません",
    "NVMe observation invalid": "NVMe観測データが不正です",
    "duplicate physical identity": "同一の物理デバイスが重複して観測されました",
    "counter reset suspected": "カウンターが減少しました（リセットまたは交換の可能性）",
    "error log count increased": "NVMe error-logの累積数が増加しました",
    "device replacement/addition": "前回にないデバイスです（交換または追加の可能性）",
    "NVMe health warning/media errors/spare": "NVMeの警告、media error、予備領域を確認してください",
    "endurance used threshold": "NVMe消耗率が基準値以上です",
    "empty target list": "点検対象hostがありません",
    "history corrupt; comparison unavailable": "保存履歴が壊れているため前回比較できません",
    "collection incomplete": "収集データが不完全です",
}


def issue_text(code):
    """Translate a known machine-facing issue code while retaining identity prefixes."""
    for known, label in ISSUE_LABELS.items():
        if code == known:
            return label
        suffix = ": " + known
        if code.endswith(suffix):
            return code[:-len(suffix)] + ": " + label
    return code


def format_issue(item):
    level, code, detail = item
    text = HEALTH_LABELS.get(level, level) + "：" + issue_text(code)
    return text + "（" + detail + "）" if detail else text


def sorted_issues(report):
    """Put uncertainty and failures before warnings without changing stored JSON."""
    priority = {"UNKNOWN": 0, "CRITICAL": 1, "WARNING": 2, "OK": 3}
    return sorted(report.get("issues", []), key=lambda item: priority.get(item[0], 0))


def comparison_text(device):
    state = device["comparison"]
    if state == "unavailable":
        return "健康情報が取得できないため比較不能"
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


def display_time(value):
    """Render a stored offset-aware time for a human reader."""
    if not value:
        return "記録なし"
    return datetime.fromisoformat(value).astimezone(JST).strftime("%Y-%m-%d %H:%M JST")


def short_summary(report):
    """Compact Japanese Slack summary. Report ID/host are always shown; CRITICAL and
    UNKNOWN items are never dropped for length — only WARNING items are capped."""
    health = HEALTH_LABELS.get(report.get("health"), "判定不能")
    hosts = "、".join(report.get("hosts", {}).keys()) or "対象なし"
    header = "[" + health + "] 対象: " + hosts + " / Report ID: " + str(report.get("report_id", ""))
    if report.get("collection") != "ok":
        lead = "収集または比較が完了していません"
    elif report.get("health") == "OK":
        lead = "異常は見つかりませんでした"
    else:
        lead = "確認が必要です"
    ordered = sorted_issues(report)
    urgent = [item for item in ordered if item[0] in ("UNKNOWN", "CRITICAL")]
    warning = [item for item in ordered if item[0] == "WARNING"]
    shown_warning = warning[:3]
    parts = [header, lead] + [format_issue(item) for item in urgent] + [format_issue(item) for item in shown_warning]
    if len(warning) > len(shown_warning):
        parts.append("ほか(WARNING) " + str(len(warning) - len(shown_warning)) + "件")
    return " / ".join(parts)


def markdown(report):
    healthy_hosts = sum(data["collection"] == "ok" for data in report["hosts"].values())
    lines = ["# quoryヘルス月次点検 " + report["month"], "", "## 結論",
             "**" + HEALTH_LABELS.get(report["health"], "判定不能") + "**",
             "- Report ID: " + report["report_id"],
             "- 対象: " + "、".join(report["hosts"].keys()),
             "- 総合判定: " + HEALTH_LABELS.get(report["health"], "判定不能") +
             "（" + report["health"] + "）",
             "- 収集結果: " + str(healthy_hosts) + "/" + str(len(report["hosts"])) + "台で成功",
             "- 観測日時: " + display_time(report["collected_at"]), "", "## 対応・未確認事項"]
    lines += ["- [" + HEALTH_LABELS.get(level, level) + "] " + issue_text(code) +
              (" — " + detail if detail else "")
              for level, code, detail in sorted_issues(report)] or ["- 対応はありません"]
    lines += ["", "## 前回比較"]
    if report["history_error"]:
        lines.append("保存履歴が壊れているため比較できません。今回値を正常値として扱わないでください。")
    elif report["comparison_source"]:
        lines.append("デバイス比較元: " + display_time(report["comparison_source"]["collected_at"]))
    else:
        lines.append("初回点検のため前回比較はありません。今回値を今後の基準として記録しました。")
    for host, data in report["hosts"].items():
        lines += ["", "## " + host,
                  "収集: " + ("成功" if data["collection"] == "ok" else "失敗・判定不能（部分的に収集できた値は以下に記載）")]
        for name, fs in data["filesystems"].items():
            if fs["collection"] != "ok":
                lines += ["", "### " + name, "- 収集失敗: " +
                          "; ".join(issue_text(c) + ("(" + d + ")" if d else "") for _, c, d in fs["issues"])]
                continue
            lines += ["", "### " + name + "（" + fs["mountpoint"] + "）",
                      "- 種別: " + fs["fstype"],
                      "- 総量: " + str(fs["size_bytes"]) + " bytes",
                      "- 使用量: " + str(fs["used_bytes"]) + " bytes",
                      "- 空き: " + str(fs["avail_bytes"]) + " bytes",
                      "- 使用率(df): " + str(fs["use_percent"]) + "%"]
            if fs["comparison"] == "compared":
                lines.append("- 前回比: 使用率 {:+d}pt / 使用量 {:+d} bytes（比較元 {} {}）".format(
                    fs["delta"]["use_percent"], fs["delta"]["used_bytes"],
                    fs["comparison_source"]["report_id"], display_time(fs["comparison_source"]["collected_at"])))
            elif fs["comparison"] == "history_corrupt":
                lines.append("- 前回比: 履歴破損のため比較不能")
            else:
                lines.append("- 前回比: 初回基準値として記録")
        mem = data["memory"]
        if mem["collection"] == "ok":
            lines += ["", "### メモリ・swap",
                      "- メモリ総量: " + str(mem["total_bytes"]) + " bytes",
                      "- メモリ空き(available): " + str(mem["available_bytes"]) +
                      " bytes（" + str(mem["available_percent"]) + "%）",
                      "- swap総量: " + str(mem["swap_total_bytes"]) + " bytes",
                      "- swap使用量: " + str(mem["swap_used_bytes"]) + " bytes"]
            if mem["comparison"] == "compared":
                lines.append("- 前回比: メモリ空き {:+.2f}pt / swap使用量 {:+d} bytes（比較元 {} {}）".format(
                    mem["delta"]["available_percent"], mem["delta"]["swap_used_bytes"],
                    mem["comparison_source"]["report_id"], display_time(mem["comparison_source"]["collected_at"])))
            elif mem["comparison"] == "history_corrupt":
                lines.append("- 前回比: 履歴破損のため比較不能")
            else:
                lines.append("- 前回比: 初回基準値として記録")
        else:
            lines += ["", "### メモリ・swap", "- 収集失敗"]
        transport = {True: "あり", False: "なし", None: "不明（取得不能）"}[data["nvme_transport_observed"]]
        lines += ["", "### NVMe", "- transport観測: " + transport]
        if not data["devices"] and data["nvme_transport_observed"] is False:
            lines.append("- 対象デバイスなし")
        elif not data["devices"]:
            lines.append("- デバイス一覧を取得できませんでした")
        for number, device in enumerate(data["devices"], 1):
            if device["health_status"] == "UNKNOWN" and not device["values"]:
                lines += ["", "#### NVMe " + str(number) + "（" + device["namespace"] + "）",
                          "- 健康情報: 取得不能（" + device["reason"] + "）"]
                continue
            values = device["values"]
            lines += ["", "#### NVMe " + str(number) + "（" + device["model"] + "）",
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
        lines.append("- デバイス比較元Report ID: " + str(report["comparison_source"]["report_id"]))
    for host, data in report["hosts"].items():
        for device in data["devices"]:
            if device.get("serial"):
                lines.append("- " + host + " / " + device["model"] + ": serial " + device["serial"] +
                             " / device " + device["namespace"])
    return "\n".join(lines) + "\n"
