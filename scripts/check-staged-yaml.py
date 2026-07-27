#!/usr/bin/env python3
"""Validate that staged YAML files parse as YAML.

Checks the content staged in the git index (`git show :<path>`), not the
working tree, since that is what the commit will actually contain. The
vault-header check in `scripts/git-pre-commit-check.sh` uses the same
`git show :<path>` approach for the same reason. This exists because
`ansible-playbook --syntax-check` does not validate the contents of
dynamically included task files (`include_tasks`/`include_role`), so a
broken YAML file reachable only via a dynamic include can pass syntax-check
and still crash every caller at runtime. Checking every staged YAML file
(not just ones believed to be dynamically included) avoids having to
maintain that include graph here, which would itself be a source of gaps.

Only syntax is checked (can this be parsed as YAML at all), via
`yaml.compose_all()`, which builds the node graph without constructing
Python objects. That deliberately accepts Ansible/YAML custom tags such as
`!vault` without needing a constructor registered for them, and correctly
handles multi-document files (`---` separated) and empty files (zero
documents, not an error).

Usage: check-staged-yaml.py <path> [<path> ...]
Exit status: 0 if every given path is valid (or skipped), 1 if any path
contains invalid YAML.
"""
import subprocess
import sys

try:
    import yaml
except ImportError:
    # This is the sole pre-commit defense against broken dynamic-include
    # YAML (ansible-playbook --syntax-check does not look inside
    # include_tasks/include_role targets); staying silent here would mean
    # the gate quietly stops protecting anything. Since ansible-core itself
    # depends on PyYAML, any host that can run ansible-playbook already has
    # it, so this should not trigger in practice.
    print(
        "ERROR: python3 yaml module (PyYAML) not found; "
        "cannot run staged YAML syntax check",
        file=sys.stderr,
    )
    sys.exit(1)


def staged_modes(paths):
    """Return {path: git index mode} for the given paths (e.g. '120000' for a symlink).

    A single batched `git ls-files -s` call, not one per path, since this
    runs on every commit and the file list can be large.
    """
    if not paths:
        return {}
    result = subprocess.run(
        ["git", "ls-files", "-s", "--"] + paths,
        capture_output=True,
        text=True,
        check=False,
    )
    modes = {}
    for line in result.stdout.splitlines():
        # format: "<mode> <object> <stage>\t<path>"
        meta, _, path = line.partition("\t")
        fields = meta.split()
        if fields and path:
            modes[path] = fields[0]
    return modes


def staged_content(path):
    """Return the staged (index) content of path, or None if it can't be read."""
    result = subprocess.run(
        ["git", "show", ":" + path],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        return None
    return result.stdout


def check_file(path, content):
    """Return an error message string, or None if content is valid YAML."""
    try:
        for _ in yaml.compose_all(content, Loader=yaml.SafeLoader):
            pass
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        if mark is not None:
            location = "line {}, column {}".format(mark.line + 1, mark.column + 1)
        else:
            location = "location unknown"
        detail = "\n".join("  " + line for line in str(exc).splitlines())
        return "ERROR: {}: invalid YAML ({})\n{}".format(path, location, detail)
    return None


def main(paths):
    modes = staged_modes(paths)
    ok = True

    for path in paths:
        # Symlinks (e.g. shared vars files linked from elsewhere) have blob
        # content that is a target path string, not YAML; skip them.
        if modes.get(path) == "120000":
            continue

        content = staged_content(path)
        if content is None:
            # Do not fail the commit on a git-tooling gap (e.g. the path
            # vanished between listing and check); say so and move on.
            print("WARNING: could not read staged content for {}; skipped".format(path))
            continue

        error = check_file(path, content)
        if error is not None:
            print(error)
            ok = False

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
