#!/usr/bin/env python3
"""Collect version facts only; status and publication belong to Ansible."""
import datetime
import json
import re
import subprocess
import sys
from zoneinfo import ZoneInfo


# R2: <ABI> must start with a digit. This excludes helper/meta and arbitrary
# similarly named packages even if they happen to end in -pve.
KERNEL_PACKAGE = re.compile(r"^proxmox-kernel-[0-9][^ ]*-pve(?:-signed)?$")
PVE_MANAGER = re.compile(r"^pve-manager/([^/\s]+)")


class CollectionError(Exception):
    """An expected command or format failure, safe to expose as a code."""


def run(*argv):
    result = subprocess.run(argv, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        raise CollectionError("command_failed")
    return result.stdout.strip()


def installed_kernel_version(rows):
    """Return the newest installed bootable kernel using dpkg's comparator."""
    candidates = []
    for row in rows.splitlines():
        fields = row.split()
        if len(fields) != 3:
            continue
        status, package, version = fields
        if status == "ii" and KERNEL_PACKAGE.fullmatch(package):
            candidates.append(version)
    if not candidates:
        raise CollectionError("kernel_candidates_missing")
    newest = candidates[0]
    for candidate in candidates[1:]:
        compared = subprocess.run(
            ["dpkg", "--compare-versions", candidate, "gt", newest], check=False
        )
        if compared.returncode == 0:
            newest = candidate
        elif compared.returncode != 1:
            raise CollectionError("version_compare_failed")
    return newest


def collect():
    kernel = run("uname", "-r")
    owner = run("dpkg-query", "-S", "/boot/vmlinuz-" + kernel)
    package = owner.rsplit(": ", 1)[0]
    if not package:
        raise CollectionError("kernel_owner_invalid")
    kernel_pkg = run("dpkg-query", "-W", "-f=${Version}", package)
    kernel_rows = run(
        "dpkg-query", "-W", "-f=${db:Status-Abbrev} ${Package} ${Version}\\n", "proxmox-kernel-*"
    )
    manager_raw = run("pveversion")
    manager_match = PVE_MANAGER.match(manager_raw)
    if not manager_match:
        raise CollectionError("pve_manager_invalid")
    qemu = run("dpkg-query", "-W", "-f=${db:Status-Abbrev} ${Version}", "pve-qemu-kvm")
    qemu_fields = qemu.split()
    if len(qemu_fields) != 2 or qemu_fields[0] != "ii" or not qemu_fields[1]:
        raise CollectionError("pve_qemu_kvm_invalid")
    return {
        "kernel": kernel,
        "kernel_pkg": kernel_pkg,
        "kernel_installed": installed_kernel_version(kernel_rows),
        "pve_manager": manager_match.group(1),
        "pve_qemu_kvm_installed": qemu_fields[1],
        "collected_at": datetime.datetime.now(ZoneInfo("Asia/Tokyo")).strftime("%Y-%m-%dT%H:%M:%S%z"),
    }


def main():
    try:
        print(json.dumps({"ok": True, "values": collect()}))
    except CollectionError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
    except (OSError, ValueError, UnicodeError):
        print(json.dumps({"ok": False, "error": "collection_invalid"}))


if __name__ == "__main__":
    main()
