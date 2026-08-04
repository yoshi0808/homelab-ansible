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

A third, unrelated job was added 2026-08-05 (requirement
docs/ai/reviews/precommit_checks_extension/2026-08-05_001_requirement.md,
R1). It shares this script's git-index plumbing and "advisory, never
blocks" pattern but reads a different catalog entirely
(`roles/semaphore_templates/defaults/main.yml`'s `semaphore_templates_catalog`,
not the `deployment_drift_check` catalog R4/R5/R6 read) and answers a
different question ("does this new playbook have a Semaphore template?" not
"was a deployment-tracked file just changed?"):

  R1 (advisory, never blocks): a newly *added* `playbooks/*.yml` (git status
     A, not M — an existing playbook being edited already has its button
     situation decided, per the requirement's non-goal) has no catalog entry
     naming it under `playbook:` -> warn, and say what fixes it. Deliberately
     Added-only: including renames would need extra logic to avoid
     double-warning on an entry the catalog already has under the old name
     (OQ1), so renames are out of scope. No exclude list is kept for
     import_playbook-only / one-off playbooks that legitimately have no
     button (OQ2) — advisory-only means the cost of a false positive here is
     low, and an exclude list would itself rot.

R2 of the same requirement (staged-list retrieval unification) also touches
this file: see git_staged_paths() below.

Usage: check-deploy-needed.py [--repo-root PATH] [--staged-paths PATH|-]
Exit status: 0 unless R5 finds a catalog playbook: reference that does not
exist among tracked files (then 1). 2 on a setup/analysis problem (not a
git working tree, catalog unreadable/unparsable, a quoted/unsafe staged
path when this script derives the staged list itself).
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


def git_staged_paths(repo_root, given=None):
    """Paths staged as added/copied/modified/renamed, per the index vs HEAD.

    R2 (docs/ai/reviews/precommit_checks_extension/2026-08-05_001_requirement.md):
    "staged とは何か" used to have two independent implementations — this
    function re-running `git diff --cached`, and
    scripts/git-pre-commit-check.sh's own `git -c core.quotepath=false diff
    --cached --name-only --diff-filter=ACMR`, whose fail-closed handling of
    still-quoted paths (a name containing a literal newline/quote/backslash)
    the Python side never shared. That gate now has one definition.

    When `given` is not None (the normal pre-commit path: the shell script
    passes its own already-computed, already-quoted-path-checked list via
    `--staged-paths`), it is used as-is — this function does not ask git
    again, so there is exactly one place that decides what "staged" means
    for that run.

    When `given` is None (this script invoked standalone, as the fixture
    harness in scripts/tests/fixtures/deploy_needed/ does), fall back to
    asking git directly, but with the identical safety handling: `-c
    core.quotepath=false` (so non-ASCII paths are not octal-escaped and
    hidden from every consumer below — see the same comment in
    git-pre-commit-check.sh) and fail-closed if a path still comes back
    quoted despite that setting.
    """
    if given is not None:
        return list(given)
    result = _run_git(
        repo_root,
        [
            "-c",
            "core.quotepath=false",
            "diff",
            "--cached",
            "--name-only",
            "--diff-filter=ACMR",
        ],
    )
    if result.returncode != 0:
        raise RuntimeError(
            "git diff --cached failed: {}".format(result.stderr.strip())
        )
    paths = [line for line in result.stdout.split("\n") if line]
    quoted = [p for p in paths if p.startswith('"')]
    if quoted:
        raise RuntimeError(
            "staged path(s) cannot be safely checked (still quoted after "
            "core.quotepath=false): {}. These names likely contain a "
            "newline, quote, or backslash. Rename before committing.".format(
                ", ".join(quoted)
            )
        )
    return paths


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
# R1 (2026-08-05 requirement, unrelated to R4/R5/R6 above): a newly added
# playbooks/*.yml with no roles/semaphore_templates catalog entry -> advisory
# ---------------------------------------------------------------------------

SEMAPHORE_TEMPLATES_CATALOG_PATH = "roles/semaphore_templates/defaults/main.yml"


def git_added_playbooks(repo_root):
    """Newly staged (git status Added only) `playbooks/*.yml` paths.

    Deliberately narrower than git_staged_paths()'s ACMR: --diff-filter=A
    excludes Modified (an existing playbook's button situation is already
    decided, non-goal per the requirement) and Renamed (OQ1 — including
    renames would need extra logic to avoid double-warning on an entry the
    catalog already has under the old name; out of scope here).

    The rename exclusion only holds when git *detects* the change as a
    rename. A rename combined with a large enough content rewrite in the
    same commit falls under git's rename-detection similarity threshold
    (50% by default) and is reported as Deleted + Added, so the new path
    arrives here as genuinely added and the advisory fires even though the
    old name had a catalog entry (independent review, 2026-08-05,
    reproduced). That false positive is accepted: this check never blocks,
    and raising the recall of a rename heuristic is not worth the extra
    logic. Do not "fix" it by widening --diff-filter — that reintroduces
    the double-warning this exclusion exists to avoid.

    Applies the same `-c core.quotepath=false` convention as
    git-pre-commit-check.sh, but unlike git_staged_paths()'s fail-closed
    behavior, a path that still comes back quoted is simply skipped: this
    whole check is advisory-only and must never block a commit (requirement
    §3 non-goal), and in the real pre-commit flow the shell wrapper has
    already refused to commit any quoted path before this script ever runs.
    """
    result = _run_git(
        repo_root,
        [
            "-c",
            "core.quotepath=false",
            "diff",
            "--cached",
            "--name-status",
            "--diff-filter=A",
            "--",
            "playbooks/*.yml",
        ],
    )
    if result.returncode != 0:
        return []
    added = []
    for line in result.stdout.split("\n"):
        if not line:
            continue
        status, _, path = line.partition("\t")
        if status != "A" or not path or path.startswith('"'):
            continue
        added.append(path)
    return added


def load_semaphore_templates_catalog(repo_root):
    """The set of `playbook:` values in semaphore_templates_catalog.

    Returns None (not an empty set) when the catalog cannot be read or
    parsed. The caller must treat that as "cannot judge, say nothing" — not
    "catalog is empty, warn about every added playbook" (noise) and not
    "block the commit" (this check never blocks, unlike R5's handling of the
    unrelated deployment_drift_check catalog).
    """
    content = read_index_content(repo_root, SEMAPHORE_TEMPLATES_CATALOG_PATH)
    if content is None:
        return None
    try:
        data = yaml.safe_load(content)
    except yaml.YAMLError:
        return None
    if not isinstance(data, dict):
        return None
    entries = data.get("semaphore_templates_catalog")
    if not isinstance(entries, list):
        return None
    return {
        entry.get("playbook")
        for entry in entries
        if isinstance(entry, dict) and entry.get("playbook")
    }


def check_new_playbook_catalog_advisory(repo_root):
    """R1: newly added playbooks/*.yml with no matching catalog entry.

    Advisory only, never blocks (requirement §3 non-goal) — a playbook that
    is only ever import_playbook'd, or a one-off manual tool, legitimately
    has no template, and this script cannot tell the two cases apart (OQ2).
    """
    catalog_playbooks = load_semaphore_templates_catalog(repo_root)
    if catalog_playbooks is None:
        return []
    added = git_added_playbooks(repo_root)
    return sorted(p for p in added if p not in catalog_playbooks)


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
    parser.add_argument(
        "--staged-paths",
        default=None,
        metavar="PATH|-",
        help="Newline-separated list of staged paths to use as-is (R2: "
        "'staged' 一覧の取得を1箇所にする), read from PATH or, if '-', from "
        "stdin. This is how scripts/git-pre-commit-check.sh passes its own "
        "already-computed, already-quoted-path-checked staged list so this "
        "script does not re-derive it. When omitted, falls back to asking "
        "git directly (used by the standalone fixture harness).",
    )
    args = parser.parse_args(argv)
    repo_root = args.repo_root.resolve() if args.repo_root else _default_repo_root()

    if not repo_root.is_dir():
        print("ERROR: --repo-root {} is not a directory".format(repo_root))
        return 2
    if not (repo_root / ".git").exists():
        print("ERROR: {} has no .git (not a git working tree)".format(repo_root))
        return 2

    given_staged_paths = None
    if args.staged_paths is not None:
        try:
            if args.staged_paths == "-":
                raw = sys.stdin.read()
            else:
                raw = Path(args.staged_paths).read_text(encoding="utf-8")
        except OSError as exc:
            print("ERROR: could not read --staged-paths {}: {}".format(args.staged_paths, exc))
            return 2
        given_staged_paths = [line for line in raw.split("\n") if line]

    try:
        staged_paths = git_staged_paths(repo_root, given_staged_paths)
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

    # R1 (2026-08-05 requirement, unrelated catalog): advisory, never blocks
    # — does not touch exit_code. Uses its own git call, not staged_paths
    # above, since it needs Added-only status (ACMR does not distinguish).
    new_playbook_hits = check_new_playbook_catalog_advisory(repo_root)
    if new_playbook_hits:
        print(
            "[check-deploy-needed] 新規playbookにSemaphoreボタンがありません"
            "(助言、commitは通ります):"
        )
        for pb in new_playbook_hits:
            print("  `{}`".format(pb))
        print(
            "  → roles/semaphore_templates/defaults/main.yml の "
            "semaphore_templates_catalog へ playbook: エントリを足し、"
            "reconcile(semaphore_templates roleの適用)を流すとボタンになります。"
        )
        print(
            "  他のplaybookからimport_playbookされるだけ、または単発の手動用で"
            "ボタンが不要なら、このまま無視して構いません。"
        )

    return exit_code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
