"""Tests roles/dev_investigate/files/recovery-investigate-dispatch-quory.sh
directly (the real bash script, not a copy), covering:

- the 4 new Operator Request Channel arms (arity, request-id/cursor format,
  and that a syntactically valid command reaches `exec` rather than being
  denied) -- requirement §18.1 "forced commandのarity、改行、余分な引数、
  allowlist外拒否"
- non-regression of a sample of the pre-existing 25 arms (§10.3, §18.1
  "既存dev-investigate全操作の非回帰") -- run locally on whatever host this
  test executes on (never quory), using only arms whose commands are
  generic system tools with no quory-specific path (df/free/uptime/ss/
  journalctl), so nothing here depends on quory-only state.

The script is invoked as a plain subprocess with SSH_ORIGINAL_COMMAND set
in the environment -- exactly how sshd would set it for a forced command,
minus the SSH transport itself. No real host is touched: this only ever
runs `bash <path-to-the-repo-copy-of-the-script>` locally.
"""

import os
import subprocess
import unittest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
_DISPATCHER_PATH = os.path.join(
    _REPO_ROOT, "roles", "dev_investigate", "files", "recovery-investigate-dispatch-quory.sh"
)


def run_dispatch(original_command, timeout=5):
    env = dict(os.environ)
    env["SSH_ORIGINAL_COMMAND"] = original_command
    proc = subprocess.run(
        ["bash", _DISPATCHER_PATH],
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
    )
    return proc


class DispatcherExistsTests(unittest.TestCase):
    def test_script_is_present_and_has_valid_bash_syntax(self):
        self.assertTrue(os.path.isfile(_DISPATCHER_PATH))
        result = subprocess.run(["bash", "-n", _DISPATCHER_PATH], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(result.returncode, 0, result.stderr.decode())


class NewChannelArmsTests(unittest.TestCase):
    """The exec target (/usr/local/libexec/operator-request-channel/
    oprc-receive) does not exist on this test machine and must not be
    created here (that would be deploying to a real path outside the
    sandbox). A syntactically valid channel command therefore cannot
    complete successfully in this test -- but bash's own "cannot execute"
    failure (exit 126/127, *not* this script's own `denied:` text) is
    itself the positive signal: it proves the arm's own validation passed
    and control reached the `exec` line, which is exactly what these tests
    check. `denied:` on stderr, in contrast, means the *dispatcher itself*
    rejected the operand before ever reaching exec.
    """

    def _assert_reached_exec(self, result):
        stderr = result.stderr.decode()
        self.assertNotIn("denied:", stderr, "should have reached exec, not been denied: {}".format(stderr))
        self.assertNotEqual(result.returncode, 0)

    def _assert_denied(self, result, result_contains=None):
        stderr = result.stderr.decode()
        self.assertIn("denied:", stderr)
        self.assertNotEqual(result.returncode, 0)
        if result_contains:
            self.assertIn(result_contains, stderr)

    def test_submit_with_no_operand_reaches_exec(self):
        self._assert_reached_exec(run_dispatch("operator-request-submit"))

    def test_submit_with_extra_operand_is_denied(self):
        self._assert_denied(run_dispatch("operator-request-submit unexpected-arg"))

    def test_outbound_list_with_no_cursor_reaches_exec(self):
        self._assert_reached_exec(run_dispatch("operator-outbound-list"))

    def test_outbound_list_with_valid_cursor_reaches_exec(self):
        cursor = "req-20260808T120000+0900-" + "a" * 16
        self._assert_reached_exec(run_dispatch("operator-outbound-list " + cursor))

    def test_outbound_list_with_malformed_cursor_is_denied(self):
        self._assert_denied(run_dispatch("operator-outbound-list not-a-request-id"), "cursor")

    def test_message_get_requires_a_request_id(self):
        self._assert_denied(run_dispatch("operator-message-get"))

    def test_message_get_with_valid_id_reaches_exec(self):
        request_id = "req-20260808T120000+0900-" + "b" * 16
        self._assert_reached_exec(run_dispatch("operator-message-get " + request_id))

    def test_message_get_with_malformed_id_is_denied(self):
        self._assert_denied(run_dispatch("operator-message-get ../../etc/passwd"), "request-id")

    def test_message_get_with_extra_argument_is_denied(self):
        request_id = "req-20260808T120000+0900-" + "c" * 16
        self._assert_denied(run_dispatch("operator-message-get {} extra".format(request_id)))

    def test_request_status_requires_a_request_id(self):
        self._assert_denied(run_dispatch("operator-request-status"))

    def test_request_status_with_valid_id_reaches_exec(self):
        request_id = "req-20260808T120000+0900-" + "d" * 16
        self._assert_reached_exec(run_dispatch("operator-request-status " + request_id))

    def test_shell_metacharacters_in_request_id_are_denied(self):
        self._assert_denied(run_dispatch("operator-message-get $(rm -rf /)"))

    def test_semicolon_injection_attempt_is_denied(self):
        self._assert_denied(run_dispatch("operator-message-get req-x; rm -rf /"))

    def test_newline_in_original_command_is_denied(self):
        result = run_dispatch("operator-message-get req-x\nrm -rf /")
        self._assert_denied(result, "line break")


class UnknownAndAllowlistTests(unittest.TestCase):
    def test_completely_unknown_command_is_denied(self):
        result = run_dispatch("totally-unknown-operation-xyz")
        self.assertIn("denied:", result.stderr.decode())
        self.assertNotEqual(result.returncode, 0)

    def test_empty_command_is_denied(self):
        result = run_dispatch("")
        self.assertIn("denied:", result.stderr.decode())
        self.assertNotEqual(result.returncode, 0)


class ExistingOperationsNonRegressionTests(unittest.TestCase):
    """A sample of the pre-existing 25 arms whose underlying commands are
    generic system tools (no quory-specific file path), run locally.
    Confirms the new channel arms did not disturb the fixed-arity parser
    or existing case matches (requirement §10.3)."""

    def test_disk_still_works_with_no_operand(self):
        result = run_dispatch("disk")
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertNotIn("denied:", result.stderr.decode())

    def test_disk_with_extra_operand_is_still_denied(self):
        result = run_dispatch("disk extra")
        self.assertIn("denied:", result.stderr.decode())
        self.assertNotEqual(result.returncode, 0)

    def test_load_still_works(self):
        result = run_dispatch("load")
        self.assertEqual(result.returncode, 0, result.stderr.decode())

    def test_failed_still_works(self):
        result = run_dispatch("failed")
        self.assertEqual(result.returncode, 0, result.stderr.decode())

    def test_ports_still_works(self):
        result = run_dispatch("ports")
        self.assertEqual(result.returncode, 0, result.stderr.decode())

    def test_journal_system_still_works(self):
        result = run_dispatch("journal-system")
        self.assertEqual(result.returncode, 0, result.stderr.decode())

    def test_deployed_hash_unknown_name_still_denied(self):
        result = run_dispatch("deployed-hash not-a-real-name")
        self.assertIn("denied:", result.stderr.decode())


if __name__ == "__main__":
    unittest.main()
