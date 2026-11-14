"""Pure rendering and report parsing for the Proxmox Watch v2 page."""
import datetime
import json
import re
from pathlib import Path


NODES = ("pve1", "pve2", "quory", "authy", "monnie")
PVE_NODES = ("pve1", "pve2")
NODE_KEYS = (
    "node", "status", "os", "role", "repo", "kernel_running",
    "kernel_installed", "kernel_reboot_required", "services_restart_required",
    "last_apply_at", "last_apply_result", "reboot_required", "reboot_done",
    "last_apply_upgraded", "vms_on_old_qemu", "pve_manager", "collected_at",
    "package_count",
)
APPLY_KEYS = ("last_apply_at", "last_apply_result", "reboot_required", "reboot_done")
REPORT_NAME = re.compile(r"^(\d{8}T\d{6})_(pve[12])_apply\.json$")
ISO8601_OFFSET = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:[+-]\d{2}:?\d{2}|Z)$")
APPLY_TIMESTAMP = re.compile(r"^\d{8}T\d{6}$")
KERNEL_ENTITY = re.compile(r"^proxmox-kernel-[0-9][^- ]*(?:\.[0-9]+)*-[^- ]+-pve(?:-signed)?$")
PVE_FIXED_PACKAGES = {"apt", "openssh-server", "libssl3t64", "libc6", "zlib1g", "corosync", "systemd", "sudo"}
UBUNTU_FIXED_PACKAGES = {"apt", "openssh-server", "corosync-qnetd", "libssl3t64", "libc6", "zlib1g", "systemd", "sudo"}
PACKAGE_BLOCK_LIMIT = 1900
NODE_BLOCK_LIMIT = 1900
SERVICE_LINE_LIMIT = 20
UPGRADE_LINE_LIMIT = 40


def unknown_apply():
    return {key: "unknown" for key in APPLY_KEYS}


def apply_timestamp_to_iso8601(timestamp):
    """Convert the patch role's JST basic timestamp to page-format ISO 8601."""
    if not isinstance(timestamp, str):
        return None
    if APPLY_TIMESTAMP.fullmatch(timestamp):
        parsed = datetime.datetime.strptime(timestamp, "%Y%m%dT%H%M%S")
        return parsed.replace(tzinfo=datetime.timezone(datetime.timedelta(hours=9))).isoformat(timespec="seconds")
    if ISO8601_OFFSET.fullmatch(timestamp):
        parsed = datetime.datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        return parsed.astimezone(datetime.timezone(datetime.timedelta(hours=9))).isoformat(timespec="seconds")
    return None


def latest_apply(directory, node):
    """Read the newest valid local apply report, preserving its facts."""
    unknown = unknown_apply()
    try:
        candidates = []
        for path in Path(directory).glob("*_{}_apply.json".format(node)):
            match = REPORT_NAME.fullmatch(path.name)
            if match and match.group(2) == node:
                candidates.append((match.group(1), path))
        if not candidates:
            return unknown
        _, path = max(candidates)
        value = json.loads(path.read_text(encoding="utf-8"))
        timestamp, result, done = value["run_timestamp"], value["result"], value["reboot_done"]
        trigger = value.get("reboot_trigger")
        timestamp = apply_timestamp_to_iso8601(timestamp)
        if timestamp is None:
            return unknown
        if result not in ("SUCCESS", "FAILED") or not isinstance(done, bool):
            return unknown
        if trigger == "none":
            required = "false"
        elif isinstance(trigger, str) and (trigger == "reboot-required-file" or trigger.startswith("kernel-version-mismatch:")):
            required = "true"
        else:
            required = "unknown"
        return {"last_apply_at": timestamp, "last_apply_result": result,
                "reboot_required": required, "reboot_done": str(done).lower()}
    except (OSError, ValueError, KeyError, TypeError):
        return unknown


def is_kernel_entity(name):
    """Exclude only versioned PVE kernel images, not kernel meta packages."""
    return bool(KERNEL_ENTITY.fullmatch(name))


def package_lines(records, is_pve):
    """Select package rows and render installed/candidate versions."""
    fixed = PVE_FIXED_PACKAGES if is_pve else UBUNTU_FIXED_PACKAGES
    selected = []
    for record in records:
        if not isinstance(record, dict):
            continue
        name, installed, candidate = record.get("name"), record.get("installed"), record.get("candidate")
        if not isinstance(name, str) or not isinstance(installed, str) or not installed:
            continue
        if is_pve:
            include = (bool(record.get("proxmox_origin")) or name in fixed) and not is_kernel_entity(name)
        else:
            include = name in fixed or name in {"linux-image-generic", "linux-image-virtual", "linux-image-aws", "linux-image-gke"}
        if not include:
            continue
        line = "{}: {}".format(name, installed)
        if isinstance(candidate, str) and candidate and candidate != installed:
            line += " (candidate {})".format(candidate)
        selected.append(line)
    return sorted(set(selected))


def capped_lines(lines, limit):
    values = list(lines)
    return values if len(values) <= limit else values[:limit] + ["(+{} more)".format(len(values) - limit)]


def package_blocks(lines):
    """Split below Notion's 2,000-character rich-text content limit."""
    if not lines:
        return []
    groups, current = [], []
    for line in lines:
        if current and len("\n".join(current + [line])) > PACKAGE_BLOCK_LIMIT:
            groups.append(current)
            current = [line]
        else:
            current.append(line)
    if current:
        groups.append(current)
    return ["\n".join(["part: {}/{}".format(index, len(groups))] + group)
            for index, group in enumerate(groups, start=1)]


def upgraded_after(history, timestamp):
    """Extract apt upgrades after latest apply from current and rotated history."""
    if not isinstance(history, str) or timestamp == "unknown":
        return "unknown"
    try:
        threshold = datetime.datetime.fromisoformat(timestamp.replace("Z", "+00:00")).replace(tzinfo=None)
        upgrades = []
        saw_history_entry = False
        for entry in re.split(r"\n\s*\n", history):
            started = re.search(r"^Start-Date:\s*(.+)$", entry, re.MULTILINE)
            changed = re.search(r"^Upgrade:\s*(.+)$", entry, re.MULTILINE)
            if not started:
                continue
            saw_history_entry = True
            if not changed:
                continue
            started_at = datetime.datetime.strptime(started.group(1).strip(), "%Y-%m-%d  %H:%M:%S")
            if started_at < threshold:
                continue
            for package, old, new in re.findall(r"([\w.+-]+)(?::[\w-]+)? \(([^,()]+), ([^)]+)\)", changed.group(1)):
                upgrades.append("{} {}->{}".format(package, old.strip(), new.strip()))
        if history.strip() and not saw_history_entry:
            return "unknown"
        values = capped_lines(sorted(set(upgrades)), UPGRADE_LINE_LIMIT)
        return ", ".join(values) if values else "none"
    except (TypeError, ValueError):
        return "unknown"


def _services(values):
    raw = values.get("services") if isinstance(values, dict) else None
    if raw is None or not isinstance(raw, list):
        return "unknown"
    lines = []
    for item in raw:
        if not isinstance(item, dict) or not isinstance(item.get("library"), str):
            return "unknown"
        processes = item.get("processes")
        if not isinstance(processes, list) or not all(isinstance(value, str) for value in processes):
            return "unknown"
        # A proc comm/unit can be unexpectedly long; reserve room for the
        # fixed node keys before the later per-library line-count cap.
        process_values = [value[:80] for value in sorted(processes)]
        shown = process_values[:10]
        if len(process_values) > len(shown):
            shown.append("(+{} more)".format(len(process_values) - len(shown)))
        lines.append("{} -> {}".format(item["library"][:160], ", ".join(shown)))
    if not lines:
        return "none"
    rendered = capped_lines(sorted(lines), SERVICE_LINE_LIMIT)
    return "count={}; {}".format(len(lines), rendered[0]) + ("\n" + "\n".join(rendered[1:]) if len(rendered) > 1 else "")


def _unknown_node(node, role, status):
    result = {"node": node, "status": status, "role": role}
    for key in NODE_KEYS:
        if key not in result:
            result[key] = 0 if key == "package_count" else "unknown"
    return result


def normalize(observations, apply_report_dir, node_roles):
    """Fail closed, adding every fixed key and package block deterministically."""
    nodes = {}
    for node in NODES:
        role = node_roles.get(node) if isinstance(node_roles, dict) else None
        if not isinstance(role, str) or not role:
            nodes[node] = _unknown_node(node, "unknown", "error")
            continue
        observed = observations.get(node, {}) if isinstance(observations, dict) else {}
        if isinstance(observed, dict) and observed.get("status") == "unreachable":
            nodes[node] = _unknown_node(node, role, "unreachable")
            continue
        values = observed.get("values") if isinstance(observed, dict) and observed.get("ok") is True else None
        required = ("os", "kernel_running", "kernel_installed", "kernel_reboot_required", "packages", "collected_at")
        valid = isinstance(values, dict) and all(key in values for key in required)
        if not valid or not isinstance(values["os"], str) or not values["os"].startswith(("debian-", "ubuntu-")):
            nodes[node] = _unknown_node(node, role, "error")
            continue
        if not all(isinstance(values[key], str) and values[key] for key in ("kernel_running", "kernel_installed", "collected_at")):
            nodes[node] = _unknown_node(node, role, "error")
            continue
        if values["kernel_reboot_required"] not in ("true", "false") or not ISO8601_OFFSET.fullmatch(values["collected_at"]):
            nodes[node] = _unknown_node(node, role, "error")
            continue
        is_pve = node in PVE_NODES
        lines = package_lines(values["packages"], is_pve)
        if not lines:
            nodes[node] = _unknown_node(node, role, "error")
            continue
        result = {"node": node, "status": "ok", "role": role, "os": values["os"],
                  "repo": values.get("repo", "unknown") if is_pve else "n/a",
                  "kernel_running": values["kernel_running"], "kernel_installed": values["kernel_installed"],
                  "kernel_reboot_required": values["kernel_reboot_required"],
                  "services_restart_required": _services(values),
                  "pve_manager": values.get("pve_manager", "unknown") if is_pve else "n/a",
                  "vms_on_old_qemu": values.get("vms_on_old_qemu", "unknown") if is_pve else "n/a",
                  "collected_at": values["collected_at"], "package_lines": lines, "package_count": len(lines)}
        if is_pve:
            apply = latest_apply(apply_report_dir, node)
            result.update(apply)
            result["last_apply_upgraded"] = upgraded_after(values.get("apt_history"), apply["last_apply_at"])
        else:
            result.update({key: "n/a" for key in APPLY_KEYS})
            result["last_apply_upgraded"] = "n/a"
        nodes[node] = result
    statuses = [nodes[node]["status"] for node in NODES]
    pve_unavailable = all(nodes[node]["status"] != "ok" for node in PVE_NODES)
    execution_error = "error" in statuses or pve_unavailable or all(status != "ok" for status in statuses)
    overall = "ok" if all(status == "ok" for status in statuses) else ("error" if execution_error else "partial")
    return nodes, overall, execution_error


def _entries_with_total(value, separator):
    """Recover displayed entries and their original count from a capped value."""
    if value in ("none", "unknown", "n/a"):
        return [], 0
    entries = value.split(separator)
    extra = 0
    if entries and re.fullmatch(r"\(\+\d+ more\)", entries[-1]):
        extra = int(entries.pop()[2:-6])
    return entries, len(entries) + extra


def _fit_value(entries, total, separator, keep):
    if not entries:
        return None
    shown = entries[:keep]
    remaining = total - len(shown)
    if remaining:
        shown.append("(+{} more)".format(remaining))
    return separator.join(shown)


def node_block(node):
    """Keep each node code block below Notion's rich-text content limit."""
    rendered = dict(node)
    services, service_total = _entries_with_total(rendered["services_restart_required"], "\n")
    upgrades, upgrade_total = _entries_with_total(rendered["last_apply_upgraded"], ", ")
    service_keep, upgrade_keep = len(services), len(upgrades)
    while True:
        if services:
            rendered["services_restart_required"] = _fit_value(services, service_total, "\n", service_keep)
        if upgrades:
            rendered["last_apply_upgraded"] = _fit_value(upgrades, upgrade_total, ", ", upgrade_keep)
        text = "\n".join("{}: {}".format(key, rendered[key]) for key in NODE_KEYS)
        if len(text) <= NODE_BLOCK_LIMIT:
            return text
        if service_keep:
            service_keep -= 1
            continue
        if upgrade_keep:
            upgrade_keep -= 1
            continue
        raise ValueError("node_block_too_large")


def header_block(state, updated_at, status):
    return "\n".join(("schema_version: 2", "state: " + state, "updated_at: " + updated_at,
                      "status: " + status, "node_count: 5"))


def render_blocks(nodes, updated_at, overall, state="complete"):
    blocks = [header_block(state, updated_at, overall)]
    for name in NODES:
        blocks.append(node_block(nodes[name]))
        blocks.extend(package_blocks(nodes[name].get("package_lines", [])))
    return blocks


def render_complete(nodes, updated_at, overall):
    return "\n\n".join(render_blocks(nodes, updated_at, overall))
