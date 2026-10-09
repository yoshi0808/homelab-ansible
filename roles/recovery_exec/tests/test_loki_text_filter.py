#!/usr/bin/env python3
"""Offline coverage for the fixed-literal Loki text query vocabulary."""

import base64
import contextlib
import importlib.machinery
import importlib.util
import io
import os
import pathlib
import stat
import subprocess
import tempfile
import unittest

import jinja2


ROLE_DIR = pathlib.Path(__file__).resolve().parents[1]
TEMPLATES_DIR = ROLE_DIR / "templates"
HELPER_PATH = ROLE_DIR / "files" / "recovery-loki-helper"
VALID_TEXTS = ("00:16:f5:22:da:86", "kicked", "EVENT_STA_LEAVE", "u7-2f")
INVALID_TEXTS = ("", "a" * 65, "has space", 'has"quote', "has'quote", "has\\slash", "$(id)", ";", "|", "line\nbreak", "*", "/")


def _environment():
    environment = jinja2.Environment(loader=jinja2.FileSystemLoader(str(TEMPLATES_DIR)))
    environment.filters["b64decode"] = lambda value: base64.b64decode(value).decode("utf-8")
    environment.globals["lookup"] = lambda kind, name: "ssh-ed25519 FIXTURE"
    return environment


def _context():
    target = {
        "name": "monnie",
        "host": "fixture.internal",
        "investigate_services": ["loki"],
        "investigate_extra": [],
    }
    return {
        "target": target,
        "target_item": target,
        "recovery_exec_investigate_key": "/fixture/recovery-key",
        "recovery_exec_ssh_dir": "/fixture/recovery-ssh",
        "recovery_exec_operator_user": "yoshi",
        "recovery_exec_operator_investigate_key": "/fixture/operator-key",
        "recovery_exec_operator_ssh_dir": "/fixture/operator-ssh",
    }


def _helper_module():
    loader = importlib.machinery.SourceFileLoader("recovery_loki_helper", str(HELPER_PATH))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class LokiTextFilterTests(unittest.TestCase):
    def _run_wrapper(self, arguments):
        rendered = _environment().get_template("homelab-investigate.sh.j2").render(**_context())
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            script = root / "wrapper"
            script.write_text(rendered.replace("/usr/bin/id -un", "id -un"), encoding="utf-8")
            script.chmod(script.stat().st_mode | stat.S_IXUSR)
            fake_bin = root / "bin"
            fake_bin.mkdir()
            (fake_bin / "id").write_text("#!/bin/sh\nprintf 'yoshi\\n'\n", encoding="utf-8")
            (fake_bin / "ssh").write_text("#!/bin/sh\nprintf '%s\\n' \"$@\"\n", encoding="utf-8")
            for path in fake_bin.iterdir():
                path.chmod(path.stat().st_mode | stat.S_IXUSR)
            environment = os.environ | {"PATH": f"{fake_bin}:{os.environ['PATH']}"}
            return subprocess.run([str(script), *arguments], capture_output=True, text=True, env=environment, check=False)

    def _run_dispatch(self, command):
        rendered = _environment().get_template("recovery-investigate-dispatch.sh.j2").render(**_context())
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            helper = root / "helper"
            helper.write_text("#!/bin/sh\nprintf '%s\\n' \"$@\"\n", encoding="utf-8")
            helper.chmod(helper.stat().st_mode | stat.S_IXUSR)
            script = root / "dispatch"
            script.write_text(
                rendered.replace("/usr/local/sbin/recovery-loki-helper", str(helper)), encoding="utf-8"
            )
            script.chmod(script.stat().st_mode | stat.S_IXUSR)
            return subprocess.run(
                [str(script)], capture_output=True, text=True,
                env=os.environ | {"SSH_ORIGINAL_COMMAND": command}, check=False,
            )

    def test_wrapper_accepts_fixed_literals_and_rejects_bad_text_or_windows(self):
        for text in VALID_TEXTS:
            with self.subTest(text=text):
                result = self._run_wrapper(["loki-text", "all", "2026-10-01T00:00", "7d", text])
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(f"loki-text all 2026-10-01T00:00 7d {text}", result.stdout)
        for text in INVALID_TEXTS:
            with self.subTest(text=repr(text)):
                result = self._run_wrapper(["loki-text", "all", "2026-10-01T00:00", "7d", text])
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("denied:", result.stderr)
                self.assertEqual(result.stdout, "")
        for window in ("8d", "30d"):
            result = self._run_wrapper(["loki-text", "all", "2026-10-01T00:00", window, "kicked"])
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("denied:", result.stderr)

    def test_dispatch_independently_validates_text_and_window(self):
        for text in VALID_TEXTS:
            with self.subTest(text=text):
                result = self._run_dispatch(f"loki-text all 2026-10-01T00:00 7d {text}")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.splitlines(), ["text", "all", "2026-10-01T00:00", "7d", text])
        for text in INVALID_TEXTS:
            with self.subTest(text=repr(text)):
                result = self._run_dispatch(f"loki-text all 2026-10-01T00:00 7d {text}")
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("denied:", result.stderr)
                self.assertEqual(result.stdout, "")
        for window in ("8d", "30d"):
            result = self._run_dispatch(f"loki-text all 2026-10-01T00:00 {window} kicked")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("denied:", result.stderr)
            self.assertEqual(result.stdout, "")

    def test_helper_uses_literal_filter_without_level_selector(self):
        helper = _helper_module()
        captured = []
        helper.loki_get = lambda path, params: captured.append((path, params)) or {"data": {"result": []}}
        for text in VALID_TEXTS:
            with self.subTest(text=text):
                helper.cmd_text(["all", "2026-10-01T00:00", "7d", text])
                query = captured[-1][1]["query"]
                self.assertEqual(query, '{job=~".+"} |= "%s"' % text)
                self.assertNotIn("{}", query)
                self.assertIn('|= "%s"' % text, query)
                self.assertNotIn("|~", query)
                self.assertNotIn("level=", query)

    def test_helper_limits_a_job_specific_query_without_level_selector(self):
        helper = _helper_module()
        captured = []
        helper.loki_get = lambda path, params: captured.append((path, params)) or {"data": {"result": []}}
        helper.cmd_text(["unifi", "2026-10-01T00:00", "7d", "kicked"])
        query = captured[-1][1]["query"]
        self.assertEqual(query, '{job="unifi"} |= "kicked"')
        self.assertNotIn("level=", query)

    def test_helper_rejects_invalid_text_and_windows_before_query(self):
        helper = _helper_module()
        calls = []
        helper.loki_get = lambda path, params: calls.append((path, params))
        for text in INVALID_TEXTS:
            with self.subTest(text=repr(text)), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    helper.cmd_text(["all", "2026-10-01T00:00", "7d", text])
        for window in ("8d", "30d"):
            with self.subTest(window=window), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    helper.cmd_text(["all", "2026-10-01T00:00", window, "kicked"])
        self.assertEqual(calls, [])

    def test_text_uses_shared_truncation_and_line_length_limits(self):
        helper = _helper_module()
        values = [[str(1_700_000_000_000_000_000 + index), "x" * 1200] for index in range(helper.MAX_LINES + 1)]
        helper.loki_get = lambda path, params: {"data": {"result": [{"stream": {"job": "unifi", "host": "fixture"}, "values": values}]}}
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            helper.cmd_text(["all", "2026-10-01T00:00", "7d", "kicked"])
        lines = output.getvalue().splitlines()
        self.assertEqual(len(lines), helper.MAX_LINES)
        self.assertTrue(lines[-1].startswith("[TRUNCATED — read "))
        self.assertTrue(all(len(line) <= helper.MAX_LINE_LENGTH for line in lines[:-1]))
        self.assertEqual(helper.MAX_LINE_LENGTH, 1000)

    def test_existing_window_allowlists_do_not_gain_long_text_windows(self):
        helper = _helper_module()
        self.assertNotIn("3d", helper.ALLOWED_WINDOW_WINDOWS)
        self.assertNotIn("7d", helper.ALLOWED_WINDOW_WINDOWS)
        self.assertNotIn("3d", helper.ALLOWED_ERRORS_WINDOWS)
        self.assertNotIn("7d", helper.ALLOWED_ERRORS_WINDOWS)


if __name__ == "__main__":
    unittest.main()
