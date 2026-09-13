"""Locked, atomic report storage; paths are internal identifiers, not user paths."""
import fcntl
import json
import os
import re
import tempfile
from contextlib import contextmanager
from pathlib import Path

REPORT_ID = re.compile(r"\d{8}T\d{12}\+0900-[0-9a-f]{32}")


def plain(path):
    path = Path(path)
    if path.is_symlink():
        raise ValueError("symlink refused")
    return path


@contextmanager
def locked(directory):
    root = Path(directory).absolute()
    if root == Path("/") or any(p.is_symlink() for p in (root, *root.parents)):
        raise ValueError("unsafe report directory")
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    lock = plain(root / ".lock")
    fd = os.open(lock, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield root
    finally:
        os.close(fd)


def atomic(path, content):
    path = plain(path)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix=".pending-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def save_json(path, value):
    atomic(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def read_json(path):
    with plain(path).open(encoding="utf-8") as stream:
        return json.load(stream)


def report_path(root, report_id):
    if not REPORT_ID.fullmatch(report_id):
        raise ValueError("invalid report ID")
    return plain(root / (report_id + ".json"))
