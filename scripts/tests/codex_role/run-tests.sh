#!/usr/bin/env bash
# Offline acceptance checks for scripts/codex-role.sh. The fake Codex binary
# lives under /tmp for the duration of this test; no real Codex CLI is run.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
WRAPPER="$REPO_ROOT/scripts/codex-role.sh"
CHECKER="$REPO_ROOT/scripts/check-doc-consistency.py"
WORKDIR="$(mktemp -d /tmp/codex-role-tests.XXXXXX)"
cleanup() { rm -rf -- "$WORKDIR"; }
trap cleanup EXIT

FAKE_CODEX="$WORKDIR/fake-codex"
STATE_DIR="$WORKDIR/state"
CAPTURE_ARGS="$WORKDIR/args"
CAPTURE_PROMPT="$WORKDIR/prompt"
CAPTURE_CWD="$WORKDIR/cwd"
CALLER_DIR="$WORKDIR/outside-repo"
mkdir -p "$CALLER_DIR"

cat > "$FAKE_CODEX" <<'FAKE'
#!/usr/bin/env bash
set -euo pipefail
: "${FAKE_CODEX_ARGS_CAPTURE:?}"
: "${FAKE_CODEX_PROMPT_CAPTURE:?}"
: "${FAKE_CODEX_CWD_CAPTURE:?}"
args=("$@")
last_index=$((${#args[@]} - 1))
if [[ "${args[$last_index]}" != "-" ]]; then
    echo "fake codex: prompt must be explicit '-' argument" >&2
    exit 64
fi
printf '%s\n' "$@" > "$FAKE_CODEX_ARGS_CAPTURE"
printf '%s\n' "$PWD" > "$FAKE_CODEX_CWD_CAPTURE"
cat > "$FAKE_CODEX_PROMPT_CAPTURE"
output=""
while (($#)); do
    if [[ "$1" == "-o" ]]; then
        output="$2"
        break
    fi
    shift
done
[[ -n "$output" ]] && printf 'fake final message\n' > "$output"
printf 'model: fake\nsandbox: fake\nsession id: %s\n' "${FAKE_CODEX_SESSION_ID:-fake-session}"
if [[ -n "${FAKE_CODEX_SECOND_SESSION_ID:-}" ]]; then
    printf 'session id: %s\n' "$FAKE_CODEX_SECOND_SESSION_ID"
fi
exit "${FAKE_CODEX_EXIT_STATUS:-0}"
FAKE
chmod 700 "$FAKE_CODEX"

export CODEX_ROLE_CODEX_BINARY="$FAKE_CODEX"
export CODEX_ROLE_STATE_DIR="$STATE_DIR"
export FAKE_CODEX_ARGS_CAPTURE="$CAPTURE_ARGS"
export FAKE_CODEX_PROMPT_CAPTURE="$CAPTURE_PROMPT"
export FAKE_CODEX_CWD_CAPTURE="$CAPTURE_CWD"
export FAKE_CODEX_EXIT_STATUS=0
export FAKE_CODEX_SECOND_SESSION_ID=""

fail=0

expect() {
    if ! "$@"; then
        echo "FAIL: $*" >&2
        fail=1
    fi
}

expect_contains() {
    local file="$1" expected="$2"
    if ! grep -Fqx -- "$expected" "$file"; then
        echo "FAIL: $file lacks exact line: $expected" >&2
        fail=1
    fi
}

expect_prompt_contains() {
    local expected="$1"
    if ! grep -Fq -- "$expected" "$CAPTURE_PROMPT"; then
        echo "FAIL: prompt lacks: $expected" >&2
        fail=1
    fi
}

expect_not_called() {
    if [[ -e "$CAPTURE_ARGS" ]]; then
        echo "FAIL: fake Codex was called for invalid input" >&2
        fail=1
    fi
}

expect_exit_64() {
    local actual="$1" label="$2"
    if [[ "$actual" -ne 64 ]]; then
        echo "FAIL: $label exited $actual, expected script rejection 64" >&2
        fail=1
    fi
}

run_role() {
    local session="$1"
    shift
    rm -f -- "$CAPTURE_ARGS" "$CAPTURE_PROMPT" "$CAPTURE_CWD"
    (
        cd "$CALLER_DIR"
        FAKE_CODEX_SESSION_ID="$session" "$WRAPPER" "$@"
    )
}

# AC1/AC1b: all roles pass their model/effort/sandbox contract and inject the
# correct role document. The fake rejects a missing terminal '-' prompt
# argument, and its recorded cwd proves an external caller is normalized to
# the repository root. New sessions are also recorded under the test state.
run_role implementer-session implementer --output "$WORKDIR/implementer-final" <<'EOF'
Implement the accepted requirement.
EOF
expect_contains "$CAPTURE_ARGS" "-m"
expect_contains "$CAPTURE_ARGS" "gpt-5.6-terra"
expect_contains "$CAPTURE_ARGS" "model_reasoning_effort=medium"
expect_contains "$CAPTURE_ARGS" "-s"
expect_contains "$CAPTURE_ARGS" "workspace-write"
expect_contains "$CAPTURE_ARGS" "sandbox_workspace_write.network_access=false"
expect_prompt_contains "docs/ai/roles/implementer.md"
expect test "$(<"$CAPTURE_CWD")" = "$REPO_ROOT"
expect test -f "$WORKDIR/implementer-final"
expect test "$(<"$STATE_DIR/implementer-session")" = $'implementer\tmedium'

# --output is resolved before the wrapper changes to REPO_ROOT. A relative
# destination therefore remains under the external caller, not the repo.
RELATIVE_OUTPUT="relative-output.md"
run_role relative-output-session implementer --output "$RELATIVE_OUTPUT" <<'EOF'
Verify caller-relative output.
EOF
expect_contains "$CAPTURE_ARGS" "$CALLER_DIR/$RELATIVE_OUTPUT"
expect test -f "$CALLER_DIR/$RELATIVE_OUTPUT"
expect test ! -e "$REPO_ROOT/$RELATIVE_OUTPUT"

PROMPT_FILE="$WORKDIR/request.md"
printf 'Review the plan.\n' > "$PROMPT_FILE"
run_role reviewer-session plan-reviewer --prompt "$PROMPT_FILE" --output "$WORKDIR/reviewer-final"
expect_contains "$CAPTURE_ARGS" "gpt-5.6-sol"
expect_contains "$CAPTURE_ARGS" "model_reasoning_effort=medium"
expect_contains "$CAPTURE_ARGS" "read-only"
expect_prompt_contains "docs/ai/roles/reviewer.md"
expect test "$(<"$STATE_DIR/reviewer-session")" = $'plan-reviewer\tmedium'

CASE_DIR="docs/ai/reviews/codex_exec_roles"
START_AT="$CASE_DIR/2026-10-12_001_requirement.md"
CASE_DIR_INPUT="$CASE_DIR/../codex_exec_roles"
START_AT_INPUT="$CASE_DIR/../codex_exec_roles/2026-10-12_001_requirement.md"
run_role auditor-session auditor --case-dir "$CASE_DIR_INPUT" --start-at "$START_AT_INPUT" --output "$WORKDIR/auditor-final"
expect_contains "$CAPTURE_ARGS" "gpt-5.6-sol"
expect_contains "$CAPTURE_ARGS" "model_reasoning_effort=medium"
expect_contains "$CAPTURE_ARGS" "read-only"
expect_prompt_contains "docs/ai/roles/auditor.md"
expect_prompt_contains "監査対象の案件フォルダ: $CASE_DIR"
expect_prompt_contains "読み始める場所: $START_AT"
if grep -Fq -- "$CASE_DIR_INPUT" "$CAPTURE_PROMPT"; then
    echo "FAIL: Auditor prompt contains caller-supplied, unnormalized path" >&2
    fail=1
fi
expect test "$(<"$STATE_DIR/auditor-session")" = $'auditor\tmedium'

# AC1 resume: Implementer and plan-reviewer re-pass every value, including
# sandbox through -c because resume has no -s.
run_role ignored implementer --resume implementer-session --output "$WORKDIR/resume-implementer" <<'EOF'
Continue the work.
EOF
expect_contains "$CAPTURE_ARGS" "resume"
expect_contains "$CAPTURE_ARGS" "model_reasoning_effort=medium"
expect_contains "$CAPTURE_ARGS" "sandbox_mode=\"workspace-write\""
expect_contains "$CAPTURE_ARGS" "sandbox_workspace_write.network_access=false"
expect test "$(<"$CAPTURE_CWD")" = "$REPO_ROOT"
if grep -Fqx -- "-s" "$CAPTURE_ARGS"; then
    echo "FAIL: resume used unsupported -s" >&2
    fail=1
fi

run_role ignored plan-reviewer --resume reviewer-session --output "$WORKDIR/resume-reviewer" <<'EOF'
Continue the review.
EOF
expect_contains "$CAPTURE_ARGS" "sandbox_mode=\"read-only\""

# Implementer alone can raise effort.
run_role high-session implementer --effort high --output "$WORKDIR/high-final" <<'EOF'
Complex implementation.
EOF
expect_contains "$CAPTURE_ARGS" "model_reasoning_effort=high"
expect test "$(<"$STATE_DIR/high-session")" = $'implementer\thigh'
run_role ignored implementer --resume high-session --output "$WORKDIR/resume-high" <<'EOF'
Continue high-effort implementation.
EOF
expect_contains "$CAPTURE_ARGS" "model_reasoning_effort=high"
expect_contains "$CAPTURE_ARGS" "sandbox_workspace_write.network_access=false"

# A failed new Codex session is still resumable when it emitted an id. The
# wrapper must preserve Codex's non-script exit status after recording it.
export FAKE_CODEX_EXIT_STATUS=73
set +e
run_role failed-session implementer --output "$WORKDIR/failed-final" <<'EOF'
Fail after creating a session.
EOF
failed_status=$?
set -e
export FAKE_CODEX_EXIT_STATUS=0
expect test "$failed_status" -eq 73
expect test "$(<"$STATE_DIR/failed-session")" = $'implementer\tmedium'

# Only the first session id line belongs to Codex's header. Later output may
# be arbitrary command output and must not reject or replace the recording.
export FAKE_CODEX_SECOND_SESSION_ID=second-session
run_role first-session implementer --output "$WORKDIR/first-final" <<'EOF'
Emit a second id-shaped output line.
EOF
export FAKE_CODEX_SECOND_SESSION_ID=""
expect test "$(<"$STATE_DIR/first-session")" = $'implementer\tmedium'
expect test ! -e "$STATE_DIR/second-session"

# AC2 and AC4b: all invalid inputs fail before the fake is invoked.
rm -f -- "$CAPTURE_ARGS" "$CAPTURE_PROMPT"
set +e
"$WRAPPER" unknown --output "$WORKDIR/invalid" </dev/null
invalid_status=$?
set -e
if [[ "$invalid_status" -eq 0 ]]; then
    echo "FAIL: unknown role succeeded" >&2
    fail=1
fi
expect_exit_64 "$invalid_status" "unknown role"
expect_not_called

rm -f -- "$CAPTURE_ARGS" "$CAPTURE_PROMPT"
set +e
"$WRAPPER" implementer --output "$WORKDIR/empty" </dev/null
empty_status=$?
set -e
if [[ "$empty_status" -eq 0 ]]; then
    echo "FAIL: empty request succeeded" >&2
    fail=1
fi
expect_exit_64 "$empty_status" "empty request"
expect_not_called

rm -f -- "$CAPTURE_ARGS" "$CAPTURE_PROMPT"
set +e
printf ' \t \n' | "$WRAPPER" implementer --output "$WORKDIR/whitespace"
whitespace_status=$?
set -e
if [[ "$whitespace_status" -eq 0 ]]; then
    echo "FAIL: whitespace-only request succeeded" >&2
    fail=1
fi
expect_exit_64 "$whitespace_status" "whitespace-only request"
expect_not_called

rm -f -- "$CAPTURE_ARGS" "$CAPTURE_PROMPT"
set +e
"$WRAPPER" implementer --resume absent-session --output "$WORKDIR/missing" </dev/null
missing_status=$?
set -e
if [[ "$missing_status" -eq 0 ]]; then
    echo "FAIL: unrecorded resume succeeded" >&2
    fail=1
fi
expect_exit_64 "$missing_status" "unrecorded resume"
expect_not_called

rm -f -- "$CAPTURE_ARGS" "$CAPTURE_PROMPT"
set +e
"$WRAPPER" plan-reviewer --resume implementer-session --output "$WORKDIR/wrong-role" </dev/null
wrong_role_status=$?
set -e
if [[ "$wrong_role_status" -eq 0 ]]; then
    echo "FAIL: cross-role resume succeeded" >&2
    fail=1
fi
expect_exit_64 "$wrong_role_status" "cross-role resume"
expect_not_called

rm -f -- "$CAPTURE_ARGS" "$CAPTURE_PROMPT"
if "$WRAPPER" auditor --prompt "$PROMPT_FILE" --case-dir "$CASE_DIR" --start-at "$START_AT" --output "$WORKDIR/auditor-prompt"; then
    echo "FAIL: Auditor accepted free-form prompt" >&2
    fail=1
fi
expect_not_called

rm -f -- "$CAPTURE_ARGS" "$CAPTURE_PROMPT"
if "$WRAPPER" auditor --resume auditor-session --case-dir "$CASE_DIR" --start-at "$START_AT" --output "$WORKDIR/auditor-resume"; then
    echo "FAIL: Auditor resume succeeded" >&2
    fail=1
fi
expect_not_called

# AC4c: default is the fixed /usr/bin path; even an explicit ~/.agents/
# override is rejected before invocation.
expect grep -Fqx 'CODEX_BINARY_DEFAULT="/usr/bin/codex"' "$WRAPPER"
AGENT_HOME="$WORKDIR/home"
mkdir -p "$AGENT_HOME/.agents/bin"
cp "$FAKE_CODEX" "$AGENT_HOME/.agents/bin/codex"
rm -f -- "$CAPTURE_ARGS" "$CAPTURE_PROMPT"
if HOME="$AGENT_HOME" CODEX_ROLE_CODEX_BINARY="$AGENT_HOME/.agents/bin/codex" \
    CODEX_ROLE_STATE_DIR="$STATE_DIR" "$WRAPPER" implementer --output "$WORKDIR/shim" </dev/null; then
    echo "FAIL: ~/.agents/ override succeeded" >&2
    fail=1
fi
expect_not_called

# AC3: exercise the index-reading check's comparison function with staged
# content supplied by a test double. The table's 現在のCLI cell intentionally
# differs from no script value and is therefore not part of the comparison.
if ! python3 - "$CHECKER" "$WRAPPER" <<'PY'
import importlib.util
import sys
from pathlib import Path

checker_path = Path(sys.argv[1])
wrapper = Path(sys.argv[2]).read_text(encoding="utf-8")
spec = importlib.util.spec_from_file_location("doc_check", checker_path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

table = """| Role / 工程 | 現在のCLI | 起動時指定 | 既定段 |
|---|---|---|---|
| Implementer | rewritten freely | gpt-5.6-terra | medium |
| 計画Reviewer | ignored | gpt-5.6-sol | medium |
| Auditor | ignored | gpt-5.6-sol | medium |
"""

def result_for(script):
    sources = {
        "scripts/codex-role.sh": script,
        "docs/ai/roles/coordinator.md": table,
    }
    module.read_index_content = lambda _root, path: sources.get(path)
    return module.check_codex_role_model_effort(Path("/index-fixture"))

assert result_for(wrapper).ok
for role, value in (("implementer", "gpt-0"), ("plan-reviewer", "gpt-0"), ("auditor", "gpt-0")):
    broken = wrapper.replace('[{}]="{}"'.format(role, "gpt-5.6-terra" if role == "implementer" else "gpt-5.6-sol"), '[{}]="{}"'.format(role, value), 1)
    findings = result_for(broken).findings
    assert any("model mismatch for " + role in finding for finding in findings), findings
for role in ("implementer", "plan-reviewer", "auditor"):
    broken = wrapper.replace('[{}]="medium"'.format(role), '[{}]="high"'.format(role), 1)
    findings = result_for(broken).findings
    assert any("effort mismatch for " + role in finding for finding in findings), findings
PY
then
    echo "FAIL: check4 did not detect every role/model and role/effort mismatch" >&2
    fail=1
fi

if [[ "$fail" -eq 0 ]]; then
    echo "OK: codex-role AC1, AC1b, AC2, AC3, AC4b, AC4c, and review regressions passed with fake Codex"
fi
exit "$fail"
