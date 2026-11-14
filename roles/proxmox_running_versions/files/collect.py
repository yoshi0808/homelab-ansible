#!/usr/bin/env python3
"""Collect OS/package observations only; classification belongs to Ansible."""
import datetime
import gzip
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from zoneinfo import ZoneInfo


PVE_KERNEL = re.compile(r"^proxmox-kernel-[0-9].*-pve(?:-signed)?$")
UBUNTU_KERNEL = re.compile(r"^linux-image-[0-9].*$")
PVE_MANAGER = re.compile(r"^pve-manager/([^/\s]+)", re.MULTILINE)


class CollectionError(Exception):
    """An expected failure represented as a static, non-secret code."""


def run(*argv):
    result = subprocess.run(argv, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        raise CollectionError("command_failed")
    return result.stdout


def newer(left, right):
    result = subprocess.run(["dpkg", "--compare-versions", left, "gt", right], check=False)
    if result.returncode not in (0, 1):
        raise CollectionError("version_compare_failed")
    return result.returncode == 0


def installed_kernel_version(rows, is_pve):
    matcher = PVE_KERNEL if is_pve else UBUNTU_KERNEL
    candidates = []
    for row in rows.splitlines():
        fields = row.split("\t")
        if len(fields) != 3:
            continue
        status, package, version = fields[0].strip(), fields[1].split(":", 1)[0], fields[2]
        if status == "ii" and matcher.fullmatch(package):
            candidates.append(version)
    if not candidates:
        raise CollectionError("kernel_candidates_missing")
    result = candidates[0]
    for candidate in candidates[1:]:
        if newer(candidate, result):
            result = candidate
    return result


def os_release():
    values = {}
    try:
        for line in Path("/etc/os-release").read_text(encoding="utf-8").splitlines():
            if "=" in line:
                key, value = line.split("=", 1)
                values[key] = value.strip().strip('"')
    except OSError as exc:
        raise CollectionError("os_release_unreadable") from exc
    if values.get("ID") not in ("debian", "ubuntu") or not values.get("VERSION_ID"):
        raise CollectionError("os_unsupported")
    return values["ID"] + "-" + values["VERSION_ID"], values["ID"] == "debian"


def installed_packages():
    rows = run("dpkg-query", "-W", "-f=${db:Status-Abbrev}\t${binary:Package}\t${Version}\n", "*")
    result = []
    for row in rows.splitlines():
        fields = row.split("\t")
        if len(fields) == 3 and fields[0].strip() == "ii":
            result.append((fields[1].split(":", 1)[0], fields[2]))
    if not result:
        raise CollectionError("packages_missing")
    return result


def parse_policy(text, installed):
    """Identify candidate/install versions offered by a Proxmox apt origin."""
    result = {name: {"name": name, "installed": version, "candidate": "", "proxmox_origin": False}
              for name, version in installed}
    current, version = None, None
    for line in text.splitlines():
        if line and not line.startswith((" ", "\t")) and line.endswith(":") and line[:-1].split(":", 1)[0] in result:
            current, version = line[:-1].split(":", 1)[0], None
            continue
        if current not in result:
            continue
        match = re.match(r"\s*Installed:\s*(\S+)", line)
        if match:
            continue
        match = re.match(r"\s*Candidate:\s*(\S+)", line)
        if match:
            result[current]["candidate"] = "" if match.group(1) == "(none)" else match.group(1)
            continue
        match = re.match(r"\s*(?:\*\*\*\s*)?(\S+)(?:\s+\d+)?\s*$", line)
        if match and not line.lstrip().startswith(("http", "file:")):
            version = match.group(1)
            continue
        if version and "proxmox" in line.lower() and version in (result[current]["installed"], result[current]["candidate"]):
            result[current]["proxmox_origin"] = True
    return list(result.values())


def package_records(installed):
    names = [name for name, _ in installed]
    # apt-cache reads existing metadata only; it never runs apt update.
    policy = run("apt-cache", "policy", *names)
    return parse_policy(policy, installed)


def stale_libraries():
    """Match homelab-stale-libs: deleted mappings excluding volatile paths."""
    excluded = ("/memfd:", "/dev/", "/tmp/", "/var/tmp/", "/run/")
    result = defaultdict(set)
    try:
        entries = list(os.scandir("/proc"))
    except OSError as exc:
        raise CollectionError("proc_unreadable") from exc
    for entry in entries:
        if not entry.name.isdecimal():
            continue
        try:
            name = Path("/proc", entry.name, "comm").read_text(encoding="utf-8", errors="replace").strip()
            cgroup = Path("/proc", entry.name, "cgroup").read_text(encoding="utf-8", errors="replace")
            unit_match = re.search(r"([^/]+\.service)(?:$|/)", cgroup, re.MULTILINE)
            process = "{}({})".format(name, unit_match.group(1)) if unit_match else name
            for line in Path("/proc", entry.name, "maps").read_text(encoding="utf-8", errors="surrogateescape").splitlines():
                fields = line.split(maxsplit=5)
                if len(fields) < 6 or not fields[5].endswith(" (deleted)"):
                    continue
                library = fields[5][:-10]
                if library.startswith("/") and not library.startswith(excluded):
                    result[library].add(process)
        except OSError:
            continue
    return [{"library": library, "processes": sorted(processes)} for library, processes in sorted(result.items())]


def history(paths=None):
    """Read current and rotated apt history; optional paths are test-only input."""
    parts = []
    paths = paths or (Path("/var/log/apt/history.log.1.gz"), Path("/var/log/apt/history.log"))
    for path in paths:
        try:
            if path.suffix == ".gz":
                parts.append(gzip.open(path, "rt", encoding="utf-8", errors="replace").read())
            else:
                parts.append(path.read_text(encoding="utf-8", errors="replace"))
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise CollectionError("apt_history_unreadable") from exc
    return "\n\n".join(parts)


def old_qemu_vmids(qm_list, process_rows, executable_by_pid):
    """Return running VMIDs whose QEMU executable was replaced after start."""
    try:
        running = set()
        for row in qm_list.splitlines()[1:]:
            fields = row.split()
            if len(fields) >= 3 and fields[0].isdigit() and fields[2] == "running":
                running.add(fields[0])
        process_vmids = {}
        for row in process_rows.splitlines():
            fields = row.strip().split(maxsplit=1)
            if len(fields) != 2 or not fields[0].isdigit():
                continue
            match = re.search(r"(?:^|\s)-id\s+(\d+)(?:\s|$)", fields[1])
            if match and match.group(1) in running:
                process_vmids[match.group(1)] = fields[0]
        if set(process_vmids) != running:
            raise CollectionError("qemu_process_missing")
        old = []
        for vmid, pid in process_vmids.items():
            executable = executable_by_pid[pid]
            if not isinstance(executable, str):
                raise CollectionError("qemu_executable_invalid")
            if executable.endswith(" (deleted)"):
                old.append(vmid)
        return "{}{}".format(len(old), " ({})".format(",".join(sorted(old, key=int))) if old else "")
    except (CollectionError, KeyError, TypeError, ValueError):
        return "unknown"


def running_qemu_executables():
    """Observe running QEMU executable links without interpreting package versions."""
    qm_list = run("qm", "list")
    process_rows = run("ps", "-eo", "pid=,args=")
    executable_by_pid = {}
    for row in process_rows.splitlines():
        fields = row.strip().split(maxsplit=1)
        if len(fields) != 2 or not fields[0].isdigit():
            continue
        if not re.search(r"(?:^|\s)-id\s+\d+(?:\s|$)", fields[1]):
            continue
        try:
            executable_by_pid[fields[0]] = os.readlink("/proc/{}/exe".format(fields[0]))
        except OSError as exc:
            raise CollectionError("qemu_executable_unreadable") from exc
    return old_qemu_vmids(qm_list, process_rows, executable_by_pid)


def pve_values():
    values = {"pve_manager": "unknown", "repo": "unknown", "vms_on_old_qemu": "unknown"}
    try:
        manager = PVE_MANAGER.search(run("pveversion"))
        values["pve_manager"] = manager.group(1) if manager else "unknown"
    except CollectionError:
        pass
    try:
        repositories = set()
        for line in run("apt-cache", "policy").lower().splitlines():
            if "proxmox.com/debian/pve" not in line:
                continue
            if "pve-enterprise" in line:
                repositories.add("enterprise")
            if "pve-no-subscription" in line:
                repositories.add("no-subscription")
            if "pvetest" in line:
                repositories.add("test")
        values["repo"] = ",".join(sorted(repositories)) if repositories else "unknown"
    except CollectionError:
        pass
    try:
        values["vms_on_old_qemu"] = running_qemu_executables()
    except CollectionError:
        pass
    return values


def collect(role):
    os_name, _ = os_release()
    is_pve = role == "pve"
    kernel = run("uname", "-r").strip()
    owner = run("dpkg-query", "-S", "/boot/vmlinuz-" + kernel).strip().rsplit(": ", 1)[0]
    if not owner:
        raise CollectionError("kernel_owner_invalid")
    running_version = run("dpkg-query", "-W", "-f=${Version}", owner).strip()
    kernel_rows = run("dpkg-query", "-W", "-f=${db:Status-Abbrev}\t${Package}\t${Version}\n", "*")
    installed = installed_packages()
    values = {
        "os": os_name,
        "kernel_running": kernel,
        "kernel_installed": installed_kernel_version(kernel_rows, is_pve),
        "kernel_reboot_required": str(Path("/run/reboot-required").exists() or newer(installed_kernel_version(kernel_rows, is_pve), running_version)).lower(),
        "packages": package_records(installed),
        "collected_at": datetime.datetime.now(ZoneInfo("Asia/Tokyo")).isoformat(timespec="seconds"),
    }
    try:
        values["services"] = stale_libraries()
    except CollectionError:
        values["services"] = None
    if is_pve:
        values.update(pve_values())
        try:
            values["apt_history"] = history()
        except CollectionError:
            values["apt_history"] = None
    return values


def main():
    if len(sys.argv) != 2:
        print(json.dumps({"ok": False, "error": "role_required"}))
        return
    try:
        print(json.dumps({"ok": True, "values": collect(sys.argv[1])}))
    except CollectionError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
    except (OSError, ValueError, UnicodeError):
        print(json.dumps({"ok": False, "error": "collection_invalid"}))


if __name__ == "__main__":
    main()
