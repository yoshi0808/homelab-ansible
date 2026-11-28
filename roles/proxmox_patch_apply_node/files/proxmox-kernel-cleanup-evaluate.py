#!/usr/bin/env python3
"""Parse old-kernel observations; this helper never changes host state."""

import json
import re
import sys

KERNEL_RE = re.compile(r"^proxmox-kernel-(.+-pve)-signed$")
ACTION_RE = re.compile(r"^(Remv|Purg|Inst|Conf)\s+(\S+)")


def version_key(value):
    # Only compare the numeric ABI format we understand. Guessing an order for
    # a new format could select the wrong newest kernel.
    match = re.fullmatch(r"([0-9]+)\.([0-9]+)\.([0-9]+)-([0-9]+)-pve", value)
    if not match:
        raise ValueError("unsupported kernel version format: " + value)
    return tuple(int(part) for part in match.groups())


def parse_package_list(text):
    records = []
    for line in text.splitlines():
        if not line.strip():
            continue
        fields = line.split("\t")
        if len(fields) != 3 or not fields[0] or not fields[1]:
            raise ValueError("malformed dpkg-query record: " + line)
        match = KERNEL_RE.match(fields[1])
        records.append({"status": fields[0][:2], "name": fields[1], "version": fields[2],
                        "kernel": match.group(1) if match else "", "is_kernel": bool(match)})
    if not records:
        raise ValueError("dpkg-query returned no package records")
    return records


def parse_boot_tool(text):
    section = None
    seen = set()
    kernels = []
    for raw in text.splitlines():
        line = raw.strip()
        if line == "Manually selected kernels:":
            section, seen = "manual", seen | {"manual"}
        elif line == "Automatically selected kernels:":
            section, seen = "automatic", seen | {"automatic"}
        elif not line:
            continue
        elif section is None:
            # `proxmox-boot-tool status / kernel list` is commonly captured
            # together.  Only the two labelled list sections are input.
            continue
        elif line not in {"None", "None."}:
            if not re.fullmatch(r"[0-9][0-9A-Za-z.+:~_-]*-pve", line):
                raise ValueError("unparseable kernel entry: " + line)
            kernels.append(line)
    if seen != {"manual", "automatic"} or not kernels:
        raise ValueError("proxmox-boot-tool selected-kernel set is empty or incomplete")
    return sorted(set(kernels), key=version_key)


def evaluate_inventory(running_kernel, package_text, boot_text):
    packages = parse_package_list(package_text)
    selected = parse_boot_tool(boot_text)
    installed = [p for p in packages if p["is_kernel"] and p["status"] == "ii"]
    known = {p["kernel"] for p in installed}
    if running_kernel not in known:
        raise ValueError("running kernel is not an installed signed kernel")
    latest = max(known, key=version_key)
    if running_kernel != latest:
        raise ValueError("running kernel is not the newest installed signed kernel")
    keep = sorted(set(selected + [running_kernel]), key=version_key)
    if not set(keep).issubset(known):
        raise ValueError("selected kernel is not installed")
    target_records = [p for p in packages if p["is_kernel"] and p["status"] in {"ii", "rc"}
                      and p["kernel"] not in keep]
    targets = [p["name"] for p in target_records]
    return {"running_kernel": running_kernel, "latest_kernel": latest, "keep_kernels": keep,
            "installed_kernels": sorted(known, key=version_key), "targets": sorted(targets),
            "target_kernels": sorted({p["kernel"] for p in target_records}, key=version_key),
            "protected_packages": protected_packages(packages)}


def protected_packages(packages):
    return sorted(p["name"] for p in packages if p["status"] == "ii" and
                  re.fullmatch(r"proxmox-(kernel-[0-9]+\.[0-9]+|default-kernel|ve)", p["name"]))


def evaluate_post_inventory(package_text, targets):
    """Observe actual purge progress independently of boot-tool validation."""
    packages = parse_package_list(package_text)
    remaining = {p["name"] for p in packages if p["status"] not in {"un", "pn"}}
    return {"removed": sorted(set(targets) - remaining),
            "installed_kernels": sorted(p["kernel"] for p in packages
                                        if p["is_kernel"] and p["status"] == "ii"),
            "protected_packages": protected_packages(packages)}


def parse_apt_simulation(text):
    if not text.strip():
        raise ValueError("apt simulation output is empty")
    actions = {"Remv": [], "Purg": [], "Inst": [], "Conf": []}
    for line in text.splitlines():
        match = ACTION_RE.match(line)
        if match:
            actions[match.group(1)].append(match.group(2))
        elif re.match(r"^(Remv|Purg|Inst|Conf)\b", line):
            raise ValueError("unparseable apt action: " + line)
    return actions


def validate_simulations(targets, dpkg_rc, dpkg_output, apt_rc, apt_output):
    if dpkg_rc != 0 or not dpkg_output.strip():
        return {"valid": False, "reason": "dpkg simulation failed or returned empty output"}
    if apt_rc != 0:
        return {"valid": False, "reason": "apt simulation failed"}
    try:
        actions = parse_apt_simulation(apt_output)
    except ValueError as exc:
        return {"valid": False, "reason": str(exc)}
    if set(actions["Remv"] + actions["Purg"]) != set(targets):
        return {"valid": False, "reason": "apt simulation remove/purge set differs from targets"}
    if actions["Inst"] or actions["Conf"]:
        return {"valid": False, "reason": "apt simulation proposes installs or configuration"}
    return {"valid": True, "reason": "validated", "apt_actions": actions}


def main():
    payload = json.load(sys.stdin)
    if payload.get("mode", "inventory") == "inventory":
        try:
            result = evaluate_inventory(payload["running_kernel"], payload["package_text"], payload["boot_text"])
        except ValueError as exc:
            # Unsupported formats need attention every week, rather than a
            # SUCCESS notification for a cleanup that can never run.
            result = {"status": "aborted" if str(exc).startswith("unsupported kernel") else "skipped",
                      "reason": str(exc)}
    elif payload["mode"] == "post":
        result = evaluate_post_inventory(payload["package_text"], payload["targets"])
    else:
        result = validate_simulations(payload["targets"], payload["dpkg_rc"], payload["dpkg_output"],
                                      payload["apt_rc"], payload["apt_output"])
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
