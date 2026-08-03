#!/usr/bin/env python3
"""Warn (never block) that a staged change likely needs a deployment run, and
separately block a commit that leaves the deployment-drift catalog pointing
at a playbook that does not exist.

Background
----------
`docs/ai/context/operations/code-delivery-to-production.md` §2 describes a
structural gap: fixing a role's `files/` payload in this repo does not, by
itself, update the deployed copy on quory/ansy. Until now nothing in this
repo told the person committing that a deployment step is now owed.
`roles/deployment_drift_check` catalogs exactly the `copy`-deployed files
this repo tracks (`roles/deployment_drift_check/defaults/main.yml`,
`deployment_drift_check_files`), each with the role-verified playbook that
restores it (`playbook:`, added alongside this script — see
docs/ai/reviews/deploy_awareness/2026-08-04_002_implement.md for which
catalog entries were deliberately left without one and why: R1-a forbids
naming a playbook that does not actually restore the state) and, where the
role delegates the actual deployment to a different host than the one the
finding is about (`delegate_to` from a `hosts: quory` play — verified with
`--list-hosts`; R9, 2026-08-04), an optional `run_host:` naming the host
that must actually be passed to `-l`. When `run_host:` is absent, the
finding's own host is correct and is used instead.

This script has two independent jobs that must not be conflated (per
requirement R4/R5 — "判定の性質が異なる. スクリプト内で明示的に分けて書く"):

  R4 (advisory, never blocks): a staged path matches a catalog `files[].src`
     -> print the entry's `playbook` and the host that must be passed to
     `-l` (the entry's `run_host` if set, else its `hosts`) so the committer
     knows a deployment is now owed, and knows the command that will
     actually reach it. Exit code from this half is always 0 — the deploy
     step comes *after* the commit, so blocking here would demand an
     impossible ordering.

  R6 (advisory, never blocks, separate heading): a staged path is under
     `roles/<role>/templates/` and `playbooks/<role>_setup.yml` exists ->
     print a rougher "may need deployment" notice. Template-rendered
     deployables (Tier 2) have no content-drift detector at all (unlike the
     `copy` files R4 covers), so this commit-time guess is the only signal
     that exists for them. It is explicitly a guess, not a catalog-verified
     fact, hence the separate heading.

  R5 (blocking): every catalog `playbook:` value (across
     deployment_drift_check_files / _units / _forced_command_keys) must name
     a file that exists in this repo. A stale/renamed reference here is a
     purely in-repo inconsistency the committer can fix in the same commit,
     and left standing it hands a future drift notification a "fix" command
     that 404s.

Reads catalog and tracked-file state from the git INDEX (`git show
:<path>`, `git ls-files`), not the working tree — same convention as
scripts/check-doc-consistency.py and scripts/check-staged-yaml.py: what gets
committed is the index.

Usage: check-deploy-needed.py [--repo-root PATH]
Exit status: 0 unless R5 finds a catalog playbook: reference that does not
exist among tracked files (then 1). 2 on a setup/analysis problem (not a
git working tree, catalog unreadable/unparsable).
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print(
        "ERROR: python3 yaml module (PyYAML) not found; cannot parse the "
        "deployment_drift_check catalog",
        file=sys.stderr,
    )
    sys.exit(2)


CATALOG_PATH = "roles/deployment_drift_check/defaults/main.yml"

# Sections of the catalog whose entries may carry a `playbook:` field.
# deployment_drift_check_report_dirs / _hosts_file are deliberately excluded
# from this list at the *catalog* level (no playbook restores them, per the
# requirement) rather than being filtered here, but iterating them too would
# be harmless (entry.get("playbook") is simply always falsy for those).
PLAYBOOK_BEARING_SECTIONS = (
    "deployment_drift_check_files",
    "deployment_drift_check_units",
    "deployment_drift_check_forced_command_keys",
)

_ROLE_TEMPLATE_RE = re.compile(r"^roles/([^/]+)/templates/")


# ---------------------------------------------------------------------------
# git index access
# ---------------------------------------------------------------------------


def _run_git(repo_root, args):
    return subprocess.run(
        ["git"] + args,
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def git_ls_files(repo_root):
    """Tracked (staged) paths as a set, per the index."""
    result = _run_git(repo_root, ["ls-files"])
    if result.returncode != 0:
        raise RuntimeError("git ls-files failed: {}".format(result.stderr.strip()))
    return {line for line in result.stdout.split("\n") if line}


def git_staged_paths(repo_root):
    """Paths staged as added/copied/modified/renamed, per the index vs HEAD."""
    result = _run_git(
        repo_root, ["diff", "--cached", "--name-only", "--diff-filter=ACMR"]
    )
    if result.returncode != 0:
        raise RuntimeError(
            "git diff --cached failed: {}".format(result.stderr.strip())
        )
    return [line for line in result.stdout.split("\n") if line]


def read_index_content(repo_root, path):
    result = _run_git(repo_root, ["show", ":" + path])
    if result.returncode != 0:
        return None
    return result.stdout


def load_catalog(repo_root):
    content = read_index_content(repo_root, CATALOG_PATH)
    if content is None:
        raise RuntimeError(
            "cannot read staged content of {} (not tracked / not staged?)".format(
                CATALOG_PATH
            )
        )
    try:
        data = yaml.safe_load(content)
    except yaml.YAMLError as exc:
        raise RuntimeError("{}: invalid YAML: {}".format(CATALOG_PATH, exc))
    if not isinstance(data, dict):
        raise RuntimeError("{}: did not parse to a mapping".format(CATALOG_PATH))
    return data


# ---------------------------------------------------------------------------
# R4: catalog `files[].src` staged -> advisory "deployment owed" notice
# ---------------------------------------------------------------------------


def check_r4(catalog, staged_paths):
    # 対象は `deployment_drift_check_files` だけである。他のsectionは repo 内の
    # src を持たない(unitやauthorized_keysはtemplate配備で、stagedパスと突き
    # 合わせられる元ファイルが無い)ため、ここで見ても一致しようがない。
    # **`playbook:` を持つが `src` を持たない種別を将来足すときは、この前提が
    # 崩れていないか確かめること** — R5(check_r5)は全section を見ており、
    # 対象範囲が意図的に異なる。
    staged_set = set(staged_paths)
    files = catalog.get("deployment_drift_check_files") or []
    hits = []
    for entry in files:
        if entry.get("src") in staged_set and entry.get("playbook"):
            hits.append(entry)
    return hits


# ---------------------------------------------------------------------------
# R5: every catalog `playbook:` must name a file that exists (blocking)
# ---------------------------------------------------------------------------


def check_r5(catalog, tracked_paths):
    errors = []
    for section_name in PLAYBOOK_BEARING_SECTIONS:
        entries = catalog.get(section_name) or []
        for entry in entries:
            playbook = entry.get("playbook")
            if not playbook:
                continue
            if playbook not in tracked_paths:
                label = entry.get("src") or entry.get("name") or entry.get("path") or "?"
                errors.append(
                    "{}: entry '{}' の playbook '{}' はrepoに存在しません "
                    "(git ls-files に無い)".format(section_name, label, playbook)
                )
    return errors


# ---------------------------------------------------------------------------
# R6: staged roles/<role>/templates/* with a matching *_setup.yml -> rough
# advisory notice, kept visually separate from R4's catalog-verified notice.
# ---------------------------------------------------------------------------


def check_r6(staged_paths, tracked_paths):
    hits = []
    seen_roles = set()
    for path in staged_paths:
        m = _ROLE_TEMPLATE_RE.match(path)
        if not m:
            continue
        role = m.group(1)
        if role in seen_roles:
            continue
        playbook = "playbooks/{}_setup.yml".format(role)
        if playbook in tracked_paths:
            seen_roles.add(role)
            hits.append((role, playbook))
    return hits


# ---------------------------------------------------------------------------
# entrypoint
# ---------------------------------------------------------------------------


def _default_repo_root():
    # Mirrors scripts/check-doc-consistency.py's convention: repo root is the
    # parent of scripts/, not whatever the caller's cwd happens to be.
    return Path(__file__).resolve().parent.parent


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Repository root to check (default: parent of this script's "
        "directory). Must be a git working tree (git ls-files/git show/"
        "git diff --cached are used to read the index).",
    )
    args = parser.parse_args(argv)
    repo_root = args.repo_root.resolve() if args.repo_root else _default_repo_root()

    if not repo_root.is_dir():
        print("ERROR: --repo-root {} is not a directory".format(repo_root))
        return 2
    if not (repo_root / ".git").exists():
        print("ERROR: {} has no .git (not a git working tree)".format(repo_root))
        return 2

    try:
        staged_paths = git_staged_paths(repo_root)
        tracked_paths = git_ls_files(repo_root)
        catalog = load_catalog(repo_root)
    except RuntimeError as exc:
        print("ERROR: {}".format(exc))
        return 2

    exit_code = 0

    # R4: advisory, catalog-verified, never blocks.
    r4_hits = check_r4(catalog, staged_paths)
    if r4_hits:
        print("[check-deploy-needed] 配備が要る変更(カタログ一致):")
        for entry in r4_hits:
            # run_host (R9): the host that must actually be passed to `-l`
            # for delegate_to-based entries. Falls back to the entry's own
            # `hosts` (joined) when absent -- same fallback evaluate.yml /
            # report.yml use for the Slack "直し方" line and the JSON
            # report's `run_host` field, so all three consumers agree.
            target = entry.get("run_host") or ", ".join(entry.get("hosts") or [])
            print("  配備が要る: `{}`({})".format(entry["playbook"], target))

    # R6: advisory, rough guess, never blocks — printed under a distinct
    # heading from R4 so the two confidence levels are never confused.
    r6_hits = check_r6(staged_paths, tracked_paths)
    if r6_hits:
        print(
            "[check-deploy-needed] 配備が要る可能性(Tier 2: template配備物、"
            "内容検査の対象外、推定です):"
        )
        for role, playbook in r6_hits:
            print("  配備が要る可能性: `{}`(role={})".format(playbook, role))

    # R5: blocking, independent of what is staged this commit (it validates
    # the whole catalog every time, since a stale reference could have been
    # introduced by any earlier commit that this pre-commit run never saw).
    r5_errors = check_r5(catalog, tracked_paths)
    if r5_errors:
        print("[check-deploy-needed] カタログのplaybook実在チェック: FAIL")
        for err in r5_errors:
            print("  ERROR: " + err)
        exit_code = 1

    return exit_code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
