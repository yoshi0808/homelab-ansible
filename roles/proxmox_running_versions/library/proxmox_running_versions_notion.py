#!/usr/bin/python
"""Publish the fixed Proxmox Watch page with a recoverable updating state."""
import json
import os
import stat
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from contextlib import contextmanager
from pathlib import Path
from zoneinfo import ZoneInfo
import fcntl

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.proxmox_running_versions import (
    NODES, header_block, node_block, normalize, render_complete,
)

VERSION = "2025-09-03"


class PublishError(Exception):
    """Only static error codes cross the module boundary."""


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise PublishError("redirect_refused")


class Client:
    def __init__(self, token_file):
        descriptor = os.open(token_file, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(descriptor, encoding="utf-8") as stream:
            metadata = os.fstat(stream.fileno())
            if not stat.S_ISREG(metadata.st_mode) or stat.S_IMODE(metadata.st_mode) != 0o600:
                raise PublishError("token_permissions")
            self.token = stream.read().strip()
        if not self.token:
            raise PublishError("token_empty")
        self.opener = urllib.request.build_opener(NoRedirect())

    def call(self, method, path, body=None, retry=True):
        if not path.startswith("/") or ".." in path:
            raise PublishError("invalid_api_path")
        payload = None if body is None else json.dumps(body).encode("utf-8")
        for attempt in range(3):
            request = urllib.request.Request(
                "https://api.notion.com/v1" + path, data=payload, method=method,
                headers={"Authorization": "Bearer " + self.token,
                         "Notion-Version": VERSION, "Content-Type": "application/json"},
            )
            try:
                with self.opener.open(request, timeout=30) as response:
                    return json.load(response)
            except urllib.error.HTTPError as exc:
                if retry and attempt < 2 and (exc.code == 429 or (method != "POST" and exc.code >= 500)):
                    try:
                        time.sleep(min(30, max(1, int(exc.headers.get("Retry-After", "2")))))
                    except ValueError:
                        time.sleep(2)
                    continue
                raise PublishError("http_" + str(exc.code)) from None
            except (OSError, ValueError, urllib.error.URLError):
                if retry and method != "POST" and attempt < 2:
                    time.sleep(2)
                    continue
                raise PublishError("response_unknown") from None
        raise PublishError("retry_exhausted")

    def children(self, page):
        rows, cursor = [], None
        while True:
            path = "/blocks/" + page + "/children?page_size=100"
            if cursor:
                path += "&start_cursor=" + urllib.parse.quote(cursor)
            response = self.call("GET", path)
            rows.extend(response["results"])
            if not response.get("has_more"):
                return rows
            cursor = response.get("next_cursor")
            if not cursor:
                raise PublishError("missing_cursor")


def code_block(text):
    return {"object": "block", "type": "code", "code": {
        "language": "plain text",
        "rich_text": [{"type": "text", "text": {"content": text}}],
    }}


def patch_code(client, block_id, text):
    client.call("PATCH", "/blocks/" + block_id, {"code": code_block(text)["code"]})


def append_code(client, page, text):
    # Appending children is non-idempotent. A transport failure can mean the
    # server accepted the append but its response was lost, so never replay it.
    response = client.call(
        "PATCH", "/blocks/" + page + "/children", {"children": [code_block(text)]}, retry=False
    )
    rows = response.get("results", [])
    if len(rows) != 1 or not isinstance(rows[0].get("id"), str):
        raise PublishError("append_response_invalid")
    return rows[0]["id"]


def is_empty_paragraph(block):
    """Accept only Notion's unambiguously empty paragraph placeholder."""
    if block.get("type") != "paragraph" or not isinstance(block.get("paragraph"), dict):
        return False
    if block.get("has_children") is not False:
        return False
    rich_text = block["paragraph"].get("rich_text")
    if not isinstance(rich_text, list):
        return False
    return all(isinstance(item, dict) and item.get("plain_text") == "" for item in rich_text)


@contextmanager
def page_lock(directory):
    """Reject a concurrent publisher before token or Notion I/O."""
    root = Path(directory).absolute()
    if root == Path("/") or any(path.is_symlink() for path in (root, *root.parents)):
        raise PublishError("unsafe_lock_directory")
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    lock_path = root / ".notion-page.lock"
    if lock_path.is_symlink():
        raise PublishError("unsafe_lock_file")
    descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise PublishError("publication_busy") from exc
        yield
    finally:
        os.close(descriptor)


def publish(client, page, nodes, updated_at, overall):
    blocks = client.children(page)
    # The page Yoshinobu created reads as <empty-block/>. Treat exactly one
    # empty paragraph as a Notion editor placeholder, not managed content.
    if len(blocks) == 1 and is_empty_paragraph(blocks[0]):
        client.call("DELETE", "/blocks/" + blocks[0]["id"])
        blocks = []
    if len(blocks) > 3 or any(block.get("type") != "code" or not isinstance(block.get("id"), str) for block in blocks):
        raise PublishError("managed_blocks_invalid")
    # This is intentionally first: any later failure leaves readers state=updating.
    if blocks:
        header_id = blocks[0]["id"]
        patch_code(client, header_id, header_block("updating", "unknown", "unknown"))
    else:
        header_id = append_code(client, page, header_block("updating", "unknown", "unknown"))
        blocks = [{"id": header_id}]
    values = (node_block(nodes["pve1"]), node_block(nodes["pve2"]))
    for index, value in enumerate(values, start=1):
        if len(blocks) > index:
            patch_code(client, blocks[index]["id"], value)
        else:
            append_code(client, page, value)
    patch_code(client, header_id, header_block("complete", updated_at, overall))


def main():
    module = AnsibleModule(argument_spec={
        "page": {"type": "str", "required": True},
        "token_file": {"type": "path", "required": True},
        "lock_directory": {"type": "path", "required": True},
        "observations": {"type": "dict", "required": True},
        "apply_report_dir": {"type": "path", "required": True},
        "suppress": {"type": "bool", "default": True},
    }, supports_check_mode=True)
    updated_at = datetime.now(ZoneInfo("Asia/Tokyo")).strftime("%Y-%m-%dT%H:%M:%S%z")
    nodes, overall, execution_error = normalize(module.params["observations"], module.params["apply_report_dir"])
    body = render_complete(nodes, updated_at, overall)
    if module.check_mode or module.params["suppress"]:
        module.exit_json(changed=False, publication="suppressed", body=body,
                         overall_status=overall, execution_error=execution_error)
    try:
        with page_lock(module.params["lock_directory"]):
            publish(Client(module.params["token_file"]), module.params["page"], nodes, updated_at, overall)
        module.exit_json(changed=True, publication="published", body=body,
                         overall_status=overall, execution_error=execution_error)
    except PublishError as exc:
        module.fail_json(msg=str(exc), publication="incomplete", body=body,
                         overall_status=overall, execution_error=execution_error)
    except (OSError, ValueError, KeyError, TypeError):
        module.fail_json(msg="publication_failed", publication="incomplete", body=body,
                         overall_status=overall, execution_error=execution_error)


if __name__ == "__main__":
    main()
