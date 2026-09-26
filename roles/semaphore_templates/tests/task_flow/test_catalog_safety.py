#!/usr/bin/env python3
"""Static AC1/AC2 checks for the Semaphore template catalog.

These checks intentionally inspect only the three named surveys: the catalog
also contains UN-SAFE update and rollback surveys whose choices must remain
unchanged.
"""
from pathlib import Path


CATALOG = Path(__file__).resolve().parents[2] / "defaults" / "main.yml"


def survey_block(text: str, legacy_name: str) -> str:
    marker = f'legacy_name: "{legacy_name}"'
    start = text.index(marker)
    end = text.find("\n  - playbook:", start + len(marker))
    return text[start:] if end == -1 else text[start:end]


def main() -> int:
    text = CATALOG.read_text(encoding="utf-8")
    manual = survey_block(text, "UN-SAFE:Proxmox patch apply (Manual)")
    safe_check = survey_block(text, "SAFE:Prometheus update check")
    update = survey_block(text, "UN-SAFE:Prometheus update(Manual)")
    rollback = survey_block(text, "UNSAFE:Prometheus rollback(Manual)")
    failures = []

    confirm_lines = manual.splitlines()
    confirm_index = next(i for i, line in enumerate(confirm_lines) if "proxmox_patch_apply_manual_confirm" in line)
    confirm_line = confirm_lines[confirm_index]
    confirm_survey = "\n".join(confirm_lines[confirm_index:confirm_index + 3])
    if "required: true" not in confirm_line or "type: enum" not in confirm_line:
        failures.append("manual confirmation survey must remain a required enum")
    if "default_value" in confirm_survey:
        failures.append("manual confirmation survey must not have a default_value")
    if "MAINTENANCE_REQUIRED" not in manual or "MAJOR_UPGRADE_DETECTED" not in manual:
        failures.append("manual confirmation survey lost a required choice")
    if "values: [{ name: inspect, value: inspect }]" not in safe_check:
        failures.append("SAFE Prometheus check must expose inspect as its only choice")
    for label, block in (("update", update), ("rollback", rollback)):
        if all(choice in block for choice in ("inspect", "update", "rollback")):
            continue
        failures.append(f"UN-SAFE Prometheus {label} survey was changed")

    if failures:
        print("FAILED:")
        for failure in failures:
            print(f" - {failure}")
        return 1
    print("OK: manual confirmation has no default; SAFE Prometheus is inspect-only")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
