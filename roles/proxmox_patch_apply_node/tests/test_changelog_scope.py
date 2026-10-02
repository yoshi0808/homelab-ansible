#!/usr/bin/env python3
"""Local fixture test for apply changelog CVE scoping (AC1--AC5)."""

import json
import os
import pathlib
import subprocess
import tempfile


REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
COLLECTOR = REPO_ROOT / "roles/proxmox_patch_apply_node/files/proxmox-patch-changelog-collect.py"

CHANGELOGS = {
    "openssl": """openssl (3.5.7-1~deb13u3) unstable; urgency=medium

  * Current security fix (CVE-2026-1001)

 -- Maintainer <maintainer@example.invalid>  Fri, 03 Oct 2026 00:00:00 +0000

openssl (3.5.7-1~deb13u2) unstable; urgency=medium

  * Installed-version entry (CVE-2025-2001)

 -- Maintainer <maintainer@example.invalid>  Thu, 02 Oct 2025 00:00:00 +0000

openssl (1.0.0-1) unstable; urgency=low

  * Historical entry (CVE-2006-2937, CVE-2007-0001, CVE-2008-0001)

 -- Maintainer <maintainer@example.invalid>  Wed, 01 Oct 2025 00:00:00 +0000
""",
    "multi": """multi (3.0-1) unstable; urgency=medium

  * Newest change (CVE-2026-3001)

 -- Maintainer <maintainer@example.invalid>  Fri, 03 Oct 2026 00:00:00 +0000

multi (2.0-1) unstable; urgency=medium

  * Intermediate change (CVE-2026-2001)

 -- Maintainer <maintainer@example.invalid>  Thu, 02 Oct 2026 00:00:00 +0000

multi (1.0-1) unstable; urgency=medium

  * Installed-version entry (CVE-2025-1001)

 -- Maintainer <maintainer@example.invalid>  Wed, 01 Oct 2025 00:00:00 +0000
""",
    "newpkg": """newpkg (1.0-1) unstable; urgency=medium

  * New install fix (CVE-2026-4001)

 -- Maintainer <maintainer@example.invalid>  Fri, 03 Oct 2026 00:00:00 +0000

newpkg (0.1-1) unstable; urgency=low

  * Historical newpkg fix (CVE-2006-4001)

 -- Maintainer <maintainer@example.invalid>  Thu, 02 Oct 2025 00:00:00 +0000
""",
    "missing": """missing (3.0-1) unstable; urgency=medium

  * Fallback latest (CVE-2026-5001)

 -- Maintainer <maintainer@example.invalid>  Fri, 03 Oct 2026 00:00:00 +0000

missing (2.0-1) unstable; urgency=low

  * Historical fallback (CVE-2006-5001, CVE-2007-5001)

 -- Maintainer <maintainer@example.invalid>  Thu, 02 Oct 2025 00:00:00 +0000
""",
    "many": """many (2.0-1) unstable; urgency=medium

  * Many CVEs (CVE-2026-0001, CVE-2026-0002, CVE-2026-0003, CVE-2026-0004, CVE-2026-0005, CVE-2026-0006, CVE-2026-0007)

 -- Maintainer <maintainer@example.invalid>  Fri, 03 Oct 2026 00:00:00 +0000

many (1.0-1) unstable; urgency=low

  * Installed entry (CVE-2006-0001)

 -- Maintainer <maintainer@example.invalid>  Thu, 02 Oct 2025 00:00:00 +0000
""",
}


def main():
    with tempfile.TemporaryDirectory() as tempdir:
        temp = pathlib.Path(tempdir)
        apt = temp / "apt"
        apt.write_text(
            "#!/bin/sh\n"
            "if [ \"$1\" = changelog ]; then\n"
            "  case \"$2\" in\n"
            + "".join(
                f"  {package}) cat <<'EOF'\n{changelog}EOF\n;;\n"
                for package, changelog in CHANGELOGS.items())
            + "  esac\nfi\n",
            encoding="utf-8")
        apt.chmod(0o755)
        simulation = "\n".join([
            "Inst openssl [3.5.7-1~deb13u2] (3.5.7-1~deb13u3 repo)",
            "Inst multi [1.0-1] (3.0-1 repo)",
            "Inst newpkg (1.0-1 repo)",
            "Inst missing [1.5-1] (10.0-1 repo)",
            "Inst many [1.0-1] (2.0-1 repo)",
        ])
        environment = os.environ | {"PATH": f"{temp}{os.pathsep}{os.environ['PATH']}"}
        result = subprocess.run(
            ["python3", str(COLLECTOR), "--limit", "10", "--timeout", "30", "--cve-limit", "5"],
            input=simulation,
            capture_output=True,
            check=True,
            text=True,
            env=environment,
        )
    records = {record["package"]: record for record in json.loads(result.stdout)}
    assert records["openssl"]["cves"] == ["CVE-2026-1001"], records["openssl"]
    assert records["multi"]["cves"] == ["CVE-2026-2001", "CVE-2026-3001"], records["multi"]
    assert records["newpkg"]["cves"] == ["CVE-2026-4001"], records["newpkg"]
    assert records["missing"]["cves"] == ["CVE-2026-5001"], records["missing"]
    assert "CVE範囲未確定: 最新項目のみ" in records["missing"]["summary"], records["missing"]
    assert records["many"]["cves"] == [f"CVE-2026-000{number}" for number in range(1, 6)], records["many"]
    assert records["many"]["cve_overflow"] == 2, records["many"]
    print("PASS: changelog CVE scope AC1--AC5")


if __name__ == "__main__":
    main()
