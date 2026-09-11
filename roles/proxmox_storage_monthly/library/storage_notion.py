#!/usr/bin/python
"""Publish an archived report; suppress before credentials, network or state IO."""
import json
import os
import stat
import time
import urllib.error
import urllib.parse
import urllib.request

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.storage_files import locked, read_json, save_json, report_path, plain
from ansible.module_utils.storage_monthly import markdown

VERSION = "2025-09-03"
SLOTS = 32


class PublishError(Exception):
    """Only static non-secret error codes may cross the module boundary."""


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise PublishError("redirect_refused")


class Client:
    def __init__(self, token_file):
        fd = os.open(token_file, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, encoding="utf-8") as stream:
            metadata = os.fstat(stream.fileno())
            if not stat.S_ISREG(metadata.st_mode) or stat.S_IMODE(metadata.st_mode) != 0o600:
                raise PublishError("token_permissions")
            self.token = stream.read().strip()
        if not self.token:
            raise PublishError("token_empty")
        self.opener = urllib.request.build_opener(NoRedirect())

    def call(self, method, path, body=None):
        if not path.startswith("/") or ".." in path:
            raise PublishError("invalid_api_path")
        payload = None if body is None else json.dumps(body).encode()
        if payload and len(payload) > 500000:
            raise PublishError("payload_too_large")
        for attempt in range(3):
            request = urllib.request.Request("https://api.notion.com/v1" + path, data=payload, method=method,
                                             headers={"Authorization": "Bearer " + self.token,
                                                      "Notion-Version": VERSION, "Content-Type": "application/json"})
            try:
                with self.opener.open(request, timeout=30) as response:
                    return json.load(response)
            except urllib.error.HTTPError as exc:
                if attempt < 2 and (exc.code == 429 or (method != "POST" and exc.code >= 500)):
                    try:
                        delay = min(30, max(1, int(exc.headers.get("Retry-After", "2"))))
                    except ValueError:
                        delay = 2
                    time.sleep(delay)
                    continue
                raise PublishError("http_" + str(exc.code)) from None
            except (OSError, ValueError, urllib.error.URLError):
                if method != "POST" and attempt < 2:
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
            cursor = response["next_cursor"]
            if not cursor:
                raise PublishError("missing_cursor")


def paragraph(text):
    return {"object": "block", "type": "paragraph", "paragraph": {
        "rich_text": [{"type": "text", "text": {"content": text}}] if text else []}}


def content(block):
    return "".join(t.get("plain_text", t.get("text", {}).get("content", ""))
                   for t in block.get("paragraph", {}).get("rich_text", []))


def publish(root, report, parent, client):
    month = report["month"]
    title = "ストレージ月次点検 " + month
    marker = "storage-monthly:v1:" + month
    text = markdown(report)
    chunks = [text[i:i + 1800] for i in range(0, len(text), 1800)]
    if len(chunks) > SLOTS:
        raise PublishError("report_too_large")
    chunks += [""] * (SLOTS - len(chunks))
    path = root / (month + ".publication.json")
    state = read_json(path) if path.exists() else {"phase": "new"}
    create_now = False
    if state.get('parent', parent) != parent:
        raise PublishError('parent_changed')
    if state.get("collected_at", "") > report["collected_at"]:
        raise PublishError("older_report_refused")
    if state["phase"] == "new":
        matches = []
        for child in client.children(parent):
            if child.get('child_page', {}).get('title') == title:
                blocks = client.children(child['id'])
                if not blocks or content(blocks[0]) != marker:
                    raise PublishError('monthly_title_conflict')
                matches.append(child['id'])
        if len(matches) > 1:
            raise PublishError('duplicate_monthly_pages')
        # Reserve before POST. Any uncertain failure keeps this reservation.
        state = {"phase": "creating", "collected_at": report["collected_at"], "parent": parent}
        if matches:
            state['page_id'] = matches[0]
        else:
            create_now = True
        save_json(path, state)
    # Only this invocation's new reservation may POST; persisted creating is uncertain.
    if create_now:
        created = client.call("POST", "/pages", {
            "parent": {"page_id": parent},
            "properties": {"title": {"type": "title", "title": [{"type": "text", "text": {"content": title}}]}},
            "children": [paragraph(marker), paragraph("更新中")] + [paragraph("") for _ in range(SLOTS)],
        })
        state["page_id"] = created["id"]
        save_json(path, state)
    if not state.get("page_id"):
        matches = []
        for child in client.children(parent):
            if child.get("child_page", {}).get("title") == title:
                blocks = client.children(child["id"])
                if blocks and content(blocks[0]) == marker:
                    matches.append(child["id"])
        if len(matches) != 1:
            raise PublishError("creation_uncertain_manual_reconciliation_required")
        state["page_id"] = matches[0]
        save_json(path, state)
    page = state["page_id"]
    blocks = client.children(page)
    if len(blocks) < SLOTS + 2 or content(blocks[0]) != marker:
        raise PublishError("managed_blocks_changed")
    ids = [b["id"] for b in blocks[:SLOTS + 2]]
    if state.get("blocks") and state["blocks"] != ids:
        raise PublishError("managed_block_identity_changed")
    if any(b["type"] != "paragraph" for b in blocks[:SLOTS + 2]):
        raise PublishError("managed_block_type_changed")
    state.update(phase="updating", blocks=ids, collected_at=report["collected_at"])
    save_json(path, state)

    def patch(block, value):
        client.call("PATCH", "/blocks/" + block, {"paragraph": paragraph(value)["paragraph"]})

    patch(ids[1], "更新中: " + report["report_id"])
    for block, chunk in zip(ids[2:], chunks):
        patch(block, chunk)
    patch(ids[1], "公開完了: " + report["report_id"] + " / " + report["collected_at"])
    state.update(phase="published", report_id=report["report_id"])
    save_json(path, state)
    save_json(root / (report['report_id'] + '.published.json'), {'report_id': report['report_id'], 'page_id': page})
    return "https://www.notion.so/" + page.replace("-", "")


def main():
    module = AnsibleModule(argument_spec={
        "directory": {"type": "path", "required": True},
        "report_id": {"type": "str", "required": True},
        "parent": {"type": "str", "required": True},
        "token_file": {"type": "path", "required": True},
        "suppress": {"type": "bool", "default": True},
    }, supports_check_mode=True)
    if module.check_mode or module.params["suppress"]:
        module.exit_json(changed=False, publication="suppressed", url="")
    try:
        with locked(module.params["directory"]) as root:
            report = read_json(report_path(root, module.params["report_id"]))
            client = Client(module.params["token_file"])
            url = publish(root, report, module.params["parent"], client)
        module.exit_json(changed=True, publication="published", url=url)
    except PublishError as exc:
        module.fail_json(msg=str(exc), publication="incomplete", url="")
    except (OSError, ValueError, KeyError, TypeError):
        module.fail_json(msg="publication_failed", publication="incomplete", url="")


if __name__ == "__main__":
    main()
