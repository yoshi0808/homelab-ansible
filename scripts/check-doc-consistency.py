#!/usr/bin/env python3
"""Detect transcription drift between a normative source and a place that
copies its value, for the three relationships identified in
docs/ai/reviews/norm_drift_mechanical_check/2026-08-01_001_survey.md (only
the three judged "①機械比較できる": both sides are the same structured
vocabulary, so an exact-match comparison is meaningful and PASS/FAIL, not
just presence/absence).

This check does not fix drift; it only blocks a commit that introduces or
leaves drift standing (see
docs/ai/reviews/norm_drift_mechanical_check/2026-08-01_002_requirement.md
§1). It found zero drift in all three relationships at the time it was
written; its value is catching the *next* one before it merges, because the
first check (#1, playbook tester-gate vs the README catalog) had already
drifted 12 entries out of sync once, and neither the closing review nor the
Auditor pass for that project caught it.

Checks
------
1. playbook `# tester-gate:` header  <->  playbooks/README.md catalog tables
2. `.claude/agents/<role>.md` frontmatter `model:`/`effort:`  <->
   docs/ai/roles/coordinator.md "モデル・effort配分" table
3. Markdown internal links (normative layer only, explicit allowlist -
   see _is_normative_markdown)  <-> existence of the linked file

Design notes
------------
- Reads file content from the *git index* (`git show :<path>`), not the
  working tree, for the same reason scripts/check-staged-yaml.py and the
  vault-header check in scripts/git-pre-commit-check.sh do: what gets
  committed is the index, and a repo-wide check like this one must reflect
  the tree as it will exist right after this commit, not whatever happens to
  be lying around unstaged in the working copy.
- Every check refuses to report PASS when its own input set turned out to be
  empty (raises AnalysisError instead of returning zero findings). A broken
  table parser or an empty glob naturally produces "0 compared -> 0
  mismatches -> exit 0", which is exactly the false confidence this script
  exists to prevent (requirement §3).
- Standard library only (argparse, posixpath, re, subprocess, sys,
  dataclasses, pathlib) - no ansible-core, no third-party packages, no
  network access. Safe to run on every commit.

Usage
-----
    check-doc-consistency.py [--repo-root PATH]

Exit status: 0 if all three checks find zero drift, 1 if any check finds
drift, 2 if a check's input set is empty (analysis itself is broken/blocked)
or a file the check depends on cannot be read.
"""
import argparse
import posixpath
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path


class AnalysisError(Exception):
    """The input set for a check was empty or unparsable.

    Raised instead of letting a check fall through to "0 compared -> 0
    mismatches -> PASS", per requirement §3.
    """


@dataclass
class CheckResult:
    name: str
    findings: list = field(default_factory=list)
    compared: int = 0

    @property
    def ok(self):
        return not self.findings


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


def git_ls_files(repo_root, patterns=None):
    """List tracked paths (as they stand in the index) matching patterns.

    No patterns means every tracked path. Uses the index (what `git add` has
    staged), not the working tree, so an untracked scratch file never enters
    the comparison and a staged deletion is correctly treated as gone.
    """
    args = ["ls-files"]
    if patterns:
        args += ["--"] + list(patterns)
    result = _run_git(repo_root, args)
    if result.returncode != 0:
        raise RuntimeError(
            "git ls-files failed (cwd={}): {}".format(repo_root, result.stderr.strip())
        )
    return [line for line in result.stdout.split("\n") if line]


def read_index_content(repo_root, path):
    """Return the staged (index) content of path, or None if unreadable."""
    result = _run_git(repo_root, ["show", ":" + path])
    if result.returncode != 0:
        return None
    return result.stdout


# ---------------------------------------------------------------------------
# generic Markdown pipe-table parsing
# ---------------------------------------------------------------------------


def _split_row(line):
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    return [cell.strip() for cell in stripped.split("|")]


def _is_separator_row(cells):
    return all(re.fullmatch(r":?-{1,}:?", cell) for cell in cells if cell != "") and any(
        cell != "" for cell in cells
    )


def extract_pipe_tables(content):
    """Split content into contiguous blocks of `|`-led lines.

    Each block is one Markdown table (header + optional separator + data
    rows), returned as a list of raw (unsplit) lines. Tables are extracted
    per contiguous block rather than tracked with file-wide state, so one
    table's column layout can never leak into an unrelated table elsewhere
    in the same file.
    """
    blocks = []
    current = []
    for line in content.split("\n"):
        if line.strip().startswith("|"):
            current.append(line)
        else:
            if current:
                blocks.append(current)
                current = []
    if current:
        blocks.append(current)
    return blocks


def _strip_cell_markup(text):
    """Strip Markdown emphasis/code markers (`**bold**`, `` `code` ``) from a cell."""
    return re.sub(r"[`*]", "", text).strip()


def _extract_link_target(cell):
    m = re.search(r"\]\(([^)]+)\)", cell)
    if not m:
        return None
    return m.group(1).strip()


def find_table(content, required_header_substrings):
    """Return (header_cells, data_rows) for the first table whose header row
    contains every string in required_header_substrings (case-insensitive,
    substring match against markup-stripped cell text), or None.
    """
    for block in extract_pipe_tables(content):
        if not block:
            continue
        header_cells = [_strip_cell_markup(c).lower() for c in _split_row(block[0])]
        if all(any(req in cell for cell in header_cells) for req in required_header_substrings):
            data_lines = block[1:]
            if data_lines and _is_separator_row(_split_row(data_lines[0])):
                data_lines = data_lines[1:]
            return _split_row(block[0]), data_lines
    return None


# ---------------------------------------------------------------------------
# check 1: playbook tester-gate <-> playbooks/README.md
# ---------------------------------------------------------------------------

_TESTER_GATE_RE = re.compile(r"^#\s*tester-gate:\s*(\S+)", re.MULTILINE)
_VALID_GATES = {
    "safe-readonly",
    "role-guarded",
    "risk-accepted",
    "check-mode-native",
    "dry-run-aware",
}


def _find_tester_gate(content):
    m = _TESTER_GATE_RE.search(content)
    return m.group(1) if m else None


def check_playbook_tester_gate(repo_root):
    findings = []

    playbook_paths = git_ls_files(repo_root, ["playbooks/*.yml"])
    if not playbook_paths:
        raise AnalysisError("check1: 'git ls-files playbooks/*.yml' returned no files")
    playbook_set = set(playbook_paths)

    readme_path = "playbooks/README.md"
    readme_content = read_index_content(repo_root, readme_path)
    if readme_content is None:
        raise AnalysisError("check1: cannot read index content of {}".format(readme_path))

    actual_gate = {}
    for path in playbook_paths:
        content = read_index_content(repo_root, path)
        if content is None:
            findings.append("check1: cannot read index content of {}".format(path))
            continue
        actual_gate[path] = _find_tester_gate(content)
        if actual_gate[path] is None:
            findings.append("check1: {} has no '# tester-gate:' header".format(path))

    catalog_rows = []
    for block in extract_pipe_tables(readme_content):
        header_cells = [_strip_cell_markup(c).lower() for c in _split_row(block[0])]
        if not header_cells or "playbook" not in header_cells[0]:
            continue
        gate_idx = next((i for i, c in enumerate(header_cells) if "tester-gate" in c), None)
        if gate_idx is None:
            continue
        data_lines = block[1:]
        if data_lines and _is_separator_row(_split_row(data_lines[0])):
            data_lines = data_lines[1:]
        for line in data_lines:
            cells = _split_row(line)
            if len(cells) <= gate_idx:
                findings.append(
                    "check1: {}: malformed catalog row (too few columns): {!r}".format(
                        readme_path, line.strip()
                    )
                )
                continue
            catalog_rows.append((cells[0], _strip_cell_markup(cells[gate_idx])))

    if not catalog_rows:
        raise AnalysisError(
            "check1: no catalog table rows parsed from {} (table format changed?)".format(
                readme_path
            )
        )

    listed = set()
    for link_cell, gate_value in catalog_rows:
        target = _extract_link_target(link_cell)
        if target is None:
            findings.append(
                "check1: {}: catalog row's first column has no Markdown link: {!r}".format(
                    readme_path, link_cell
                )
            )
            continue
        resolved = posixpath.normpath(posixpath.join("playbooks", target))
        listed.add(resolved)
        if resolved not in playbook_set:
            findings.append(
                "check1: {}: row links to '{}', which is not among playbooks/*.yml".format(
                    readme_path, resolved
                )
            )
            continue
        header_value = actual_gate.get(resolved)
        if header_value is not None and header_value != gate_value:
            findings.append(
                "check1: {}: tester-gate mismatch for {} (header='{}', README='{}')".format(
                    readme_path, resolved, header_value, gate_value
                )
            )

    for path in sorted(playbook_set - listed):
        findings.append("check1: {} is not listed in {}".format(path, readme_path))

    return CheckResult("check1", findings, compared=len(playbook_set) + len(catalog_rows))


# ---------------------------------------------------------------------------
# check 2: agent frontmatter <-> docs/ai/roles/coordinator.md
# ---------------------------------------------------------------------------


def _parse_frontmatter_model_effort(content):
    lines = content.split("\n")
    if not lines or lines[0].strip() != "---":
        return None, None
    model = effort = None
    for line in lines[1:]:
        if line.strip() == "---":
            break
        m = re.match(r"^model:\s*(\S+)\s*$", line)
        if m:
            model = m.group(1)
        m = re.match(r"^effort:\s*(\S+)\s*$", line)
        if m:
            effort = m.group(1)
    return model, effort


def check_agent_model_effort(repo_root):
    findings = []

    agent_paths = git_ls_files(repo_root, [".claude/agents/*.md"])
    if not agent_paths:
        raise AnalysisError("check2: 'git ls-files .claude/agents/*.md' returned no files")

    agent_info = {}
    for path in agent_paths:
        content = read_index_content(repo_root, path)
        if content is None:
            findings.append("check2: cannot read index content of {}".format(path))
            continue
        role = Path(path).stem.lower()
        model, effort = _parse_frontmatter_model_effort(content)
        if model is None or effort is None:
            findings.append(
                "check2: {}: frontmatter missing model:/effort: (model={!r}, effort={!r})".format(
                    path, model, effort
                )
            )
        agent_info[role] = (model, effort, path)

    routing_path = "docs/ai/roles/coordinator.md"
    routing_content = read_index_content(repo_root, routing_path)
    if routing_content is None:
        raise AnalysisError("check2: cannot read index content of {}".format(routing_path))

    table = find_table(routing_content, ["role", "model", "effort"])
    if table is None:
        raise AnalysisError(
            "check2: could not find a table with Role/model/effort columns in {}".format(
                routing_path
            )
        )
    header_cells, data_lines = table
    header_lower = [_strip_cell_markup(c).lower() for c in header_cells]
    role_idx = 0
    model_idx = header_lower.index("model")
    effort_idx = header_lower.index("effort")

    table_info = {}
    for line in data_lines:
        cells = _split_row(line)
        if len(cells) <= max(role_idx, model_idx, effort_idx):
            findings.append(
                "check2: {}: malformed table row (too few columns): {!r}".format(
                    routing_path, line.strip()
                )
            )
            continue
        role = _strip_cell_markup(cells[role_idx]).lower()
        if not role:
            continue
        table_info[role] = (
            _strip_cell_markup(cells[model_idx]),
            _strip_cell_markup(cells[effort_idx]),
        )

    if not table_info:
        raise AnalysisError(
            "check2: model/effort table in {} parsed to zero data rows".format(routing_path)
        )

    agent_roles = set(agent_info.keys())
    table_roles = set(table_info.keys())

    for role in sorted(agent_roles - table_roles):
        findings.append(
            "check2: .claude/agents/{}.md has no corresponding row in {}".format(
                role, routing_path
            )
        )
    for role in sorted(table_roles - agent_roles):
        findings.append(
            "check2: {}: row '{}' has no corresponding .claude/agents/{}.md".format(
                routing_path, role, role
            )
        )

    for role in sorted(agent_roles & table_roles):
        agent_model, agent_effort, agent_path = agent_info[role]
        table_model, table_effort = table_info[role]
        if agent_model != table_model:
            findings.append(
                "check2: model mismatch for {}: {}='{}', {}='{}'".format(
                    role, agent_path, agent_model, routing_path, table_model
                )
            )
        if agent_effort != table_effort:
            findings.append(
                "check2: effort mismatch for {}: {}='{}', {}='{}'".format(
                    role, agent_path, agent_effort, routing_path, table_effort
                )
            )

    return CheckResult("check2", findings, compared=len(agent_roles) + len(table_roles))


# ---------------------------------------------------------------------------
# check 3: Markdown internal links (normative layer only, explicit allowlist)
# ---------------------------------------------------------------------------

_LINK_RE = re.compile(r"\[[^\]\n]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
_SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.\-]*:")

# requirement §2 検査#3「対象の決め方」(2026-08-01改訂) を機械可読な形にしたもの。
# An exclude-list (all *.md minus docs/ai/reviews/) was tried first and
# rejected: it grows every time a new kind of non-normative file shows up,
# and a missed exclusion becomes an unfixable finding (docs/ai/reviews/ is
# historical record and scripts/tests/ fixtures deliberately contain a
# permanently-broken link - see 2026-08-01_003_implement.md §6/§8 for the
# incident that forced this change). An allowlist fails safe instead: a
# newly-added directory is simply not scanned until someone deliberately
# adds it here, rather than becoming a surprise false positive.
_NORMATIVE_EXACT_PATHS = frozenset({"CLAUDE.md", "AGENTS.md", "playbooks/README.md"})
_NORMATIVE_PREFIXES = (
    "docs/ai/policies/",
    "docs/ai/context/",
    "docs/ai/roles/",
    "docs/ai/memory/",
    "docs/ai/adr/",
    "docs/ai/prompts/",
    "skills/",
    "roles/",
    ".claude/agents/",
)


def _is_normative_markdown(path):
    """Is `path` in the check3 scan scope (requirement §2 検査#3)?

    Deliberately reimplemented with plain string/posixpath operations
    instead of a `git ls-files <pattern>` glob: git's pathspec glob (and
    Python's fnmatch, which it resembles here) matches `*` across `/`
    boundaries, so `git ls-files 'docs/ai/*.md'` returns all 1025 Markdown
    files anywhere under docs/ai/ (947 of them under docs/ai/reviews/), not
    just the ~8 direct children the requirement's "直下" means. That
    mismatch was caught by re-deriving this count independently rather than
    trusting the glob call site - see 2026-08-01_003_implement.md §2.7.
    """
    if not path.endswith(".md"):
        return False
    if path in _NORMATIVE_EXACT_PATHS:
        return True
    if posixpath.dirname(path) == "docs/ai":
        return True
    return path.startswith(_NORMATIVE_PREFIXES)


# A code span's closing delimiter must be a run of exactly as many backticks
# as the opening one (CommonMark rule) - matched here with a backreference
# to the opening run, plus a trailing (?!`) so we don't stop one backtick
# short of the true closing run. `re.sub(r"`+[^`\n]*?`+", ...)` (the
# original, simpler version of this) doesn't track run length: it treated
# `` `[example](...)` `` (a double-backtick span deliberately used to quote
# text that itself contains literal single backticks) as ending at the
# FIRST single backtick it found, which is the opening backtick of the
# quoted text, leaving "[example](...)" outside the stripped region and
# reported as a broken link. Confirmed with a full-repo run (`git init &&
# git add -A` over a copy of the whole tree, index-based like production) -
# see 2026-08-01_003_implement.md §2.4/§6.
_CODE_SPAN_RE = re.compile(r"(`+)(.+?)\1(?!`)")


def _strip_code_regions(content):
    """Blank out fenced code blocks and inline code spans.

    Link-like text inside a code span is a literal example, not a live
    link (e.g. `` `[Repository Context](...)` `` in
    skills/document-norm-review/SKILL.md, illustrating link-vs-prose
    duplication, not a real link with target "..."). Checking it as a real
    link is exactly the false positive requirement §4/AC2 forbids.
    """
    out_lines = []
    in_fence = False
    for line in content.split("\n"):
        stripped = line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
            out_lines.append("")
            continue
        if in_fence:
            out_lines.append("")
            continue
        out_lines.append(_CODE_SPAN_RE.sub(" ", line))
    return "\n".join(out_lines)


def _resolve_link_target(source_path, target):
    """Return the repo-relative path a Markdown link target resolves to, or
    None if the target is not an internal file reference to check (external
    URL, mailto, pure same-page anchor).
    """
    target = target.strip()
    if not target:
        return None
    if _SCHEME_RE.match(target):
        return None
    if target.startswith("#"):
        return None
    path_part = target.split("#", 1)[0]
    if not path_part:
        return None
    if path_part.startswith("/"):
        return posixpath.normpath(path_part.lstrip("/"))
    base_dir = posixpath.dirname(source_path)
    return posixpath.normpath(posixpath.join(base_dir, path_part))


def check_internal_links(repo_root):
    findings = []

    all_tracked = set(git_ls_files(repo_root))
    if not all_tracked:
        raise AnalysisError("check3: 'git ls-files' returned no tracked files at all")

    md_paths = sorted(p for p in all_tracked if _is_normative_markdown(p))
    if not md_paths:
        raise AnalysisError(
            "check3: zero files matched the normative-layer allowlist "
            "(_is_normative_markdown/_NORMATIVE_PREFIXES likely broken)"
        )

    checked = 0
    for path in md_paths:
        content = read_index_content(repo_root, path)
        if content is None:
            findings.append("check3: cannot read index content of {}".format(path))
            continue
        cleaned = _strip_code_regions(content)
        for m in _LINK_RE.finditer(cleaned):
            resolved = _resolve_link_target(path, m.group(1))
            if resolved is None:
                continue
            checked += 1
            if resolved not in all_tracked:
                line_no = cleaned.count("\n", 0, m.start()) + 1
                findings.append(
                    "check3: {}:{}: link target '{}' does not resolve to a tracked file "
                    "(resolved: {})".format(path, line_no, m.group(1), resolved)
                )

    if checked == 0:
        raise AnalysisError(
            "check3: zero internal links found to check across {} files "
            "(link regex likely broken)".format(len(md_paths))
        )

    return CheckResult("check3", findings, compared=checked)


# ---------------------------------------------------------------------------
# entrypoint
# ---------------------------------------------------------------------------


def _default_repo_root():
    # Mirrors the convention used by the sibling shell scripts in this
    # directory (scripts/git-pre-commit-check.sh): repo root is the parent
    # of scripts/, not whatever the caller's cwd happens to be.
    return Path(__file__).resolve().parent.parent


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Repository root to check (default: parent of this script's directory). "
        "Must be a git working tree (git ls-files/git show are used to read the index).",
    )
    args = parser.parse_args(argv)
    repo_root = args.repo_root.resolve() if args.repo_root else _default_repo_root()

    if not repo_root.is_dir():
        print("ERROR: --repo-root {} is not a directory".format(repo_root))
        return 2
    if not (repo_root / ".git").exists():
        print("ERROR: {} has no .git (not a git working tree)".format(repo_root))
        return 2

    checks = [
        check_playbook_tester_gate,
        check_agent_model_effort,
        check_internal_links,
    ]

    overall_ok = True
    for check in checks:
        try:
            result = check(repo_root)
        except AnalysisError as exc:
            print("ERROR: {}".format(exc))
            print("ERROR: analysis input was empty/unparsable - treating as failure, not PASS.")
            return 2
        except RuntimeError as exc:
            print("ERROR: {}".format(exc))
            return 2

        if result.ok:
            print("[{}] OK ({} compared)".format(result.name, result.compared))
        else:
            overall_ok = False
            print(
                "[{}] FAIL ({} compared, {} mismatch(es))".format(
                    result.name, result.compared, len(result.findings)
                )
            )
            for finding in result.findings:
                print("  " + finding)

    return 0 if overall_ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
