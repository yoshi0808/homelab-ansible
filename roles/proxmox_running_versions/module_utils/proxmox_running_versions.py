"""Pure page rendering and local apply-report lookup for running versions."""
import json
import re
from pathlib import Path


NODES = ("pve1", "pve2")
VERSION_KEYS = (
    "kernel", "kernel_pkg", "kernel_installed", "pve_manager",
    "pve_qemu_kvm_installed", "collected_at",
)
APPLY_KEYS = ("last_apply_at", "last_apply_result", "reboot_done")
REPORT_NAME = re.compile(r"^(\d{8}T\d{6})_(pve[12])_apply\.json$")
NOTE = "pve_qemu_kvm_installed はパッケージのインストール版であり、稼働中VMのQEMUの版ではない"


def latest_apply(directory, node):
    """Read only the newest correctly named report for one node, or unknown."""
    unknown = {key: "unknown" for key in APPLY_KEYS}
    try:
        candidates = []
        for path in Path(directory).glob("*_{}_apply.json".format(node)):
            match = REPORT_NAME.fullmatch(path.name)
            if match and match.group(2) == node:
                candidates.append((match.group(0), path))
        if not candidates:
            return unknown
        _, path = max(candidates)
        value = json.loads(path.read_text(encoding="utf-8"))
        timestamp = value["run_timestamp"]
        result = value["result"]
        reboot = value["reboot_done"]
        if not isinstance(timestamp, str) or result not in ("SUCCESS", "FAILED") or not isinstance(reboot, bool):
            return unknown
        return {"last_apply_at": timestamp, "last_apply_result": result,
                "reboot_done": str(reboot).lower()}
    except (OSError, ValueError, KeyError, TypeError):
        return unknown


def normalize(observations, apply_report_dir):
    """Fail closed per node and return fixed-key, fixed-order page data."""
    nodes = {}
    for node in NODES:
        observed = observations.get(node, {})
        status = observed.get("status") if isinstance(observed, dict) else None
        if status == "unreachable":
            nodes[node] = {"node": node, "status": "unreachable"}
        elif (isinstance(observed, dict) and observed.get("ok") is True
              and isinstance(observed.get("values"), dict)
              and all(isinstance(observed["values"].get(key), str) and observed["values"][key]
                      for key in VERSION_KEYS)):
            nodes[node] = {"node": node, "status": "ok"}
            nodes[node].update(observed["values"])
        else:
            nodes[node] = {"node": node, "status": "error"}
        if nodes[node]["status"] != "ok":
            nodes[node].update({key: "unknown" for key in VERSION_KEYS})
        nodes[node].update(latest_apply(apply_report_dir, node))
    statuses = [nodes[node]["status"] for node in NODES]
    overall = "ok" if all(status == "ok" for status in statuses) else (
        "error" if all(status != "ok" for status in statuses) else "partial"
    )
    has_execution_error = "error" in statuses or overall == "error"
    return nodes, overall, has_execution_error


def node_block(node):
    keys = ("node", "status") + VERSION_KEYS + APPLY_KEYS
    return "\n".join("{}: {}".format(key, node[key]) for key in keys)


def header_block(state, updated_at, status):
    return "\n".join((
        "state: " + state,
        "updated_at: " + updated_at,
        "status: " + status,
        "note: " + NOTE,
    ))


def render_complete(nodes, updated_at, overall):
    return "\n\n".join((header_block("complete", updated_at, overall),
                            node_block(nodes["pve1"]), node_block(nodes["pve2"])))
