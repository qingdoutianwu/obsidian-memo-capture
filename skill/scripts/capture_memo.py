#!/usr/bin/env python3
"""Capture an explicit memo/lesson/todo into a local Obsidian vault."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib
from contextlib import contextmanager

ALLOWED_FOLDERS = {"memos", "lessons", "todos"}
DEFAULT_VAULT = pathlib.Path.home() / "Documents" / "NOTE240925_clean1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--vault", default=str(DEFAULT_VAULT))
    parser.add_argument("--folder", choices=sorted(ALLOWED_FOLDERS), default="memos")
    parser.add_argument("--content", required=True)
    parser.add_argument("--timestamp", default="", help="ISO timestamp; defaults to now")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


@contextmanager
def file_lock(lock_path: pathlib.Path):
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = lock_path.open("a", encoding="utf-8")
    try:
        try:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        except ImportError:
            pass
        yield
    finally:
        try:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        except ImportError:
            pass
        handle.close()


def main() -> int:
    args = parse_args()
    content = args.content
    if not content.strip():
        print(json.dumps({"ok": False, "error": "empty_content"}, ensure_ascii=False))
        return 2

    vault = pathlib.Path(os.path.expanduser(args.vault)).resolve()
    destination = vault / "Memos" / args.folder
    timestamp = dt.datetime.fromisoformat(args.timestamp) if args.timestamp else dt.datetime.now()
    path = destination / f"{timestamp:%Y%m%d}.md"
    line = f"- [{timestamp:%H:%M}] {content}\n"
    result = {
        "ok": True,
        "written": False,
        "dry_run": args.dry_run,
        "folder": args.folder,
        "path": str(path),
        "relative_path": str(path.relative_to(vault)),
        "chars": len(content),
        "line": line,
    }
    if args.dry_run:
        print(json.dumps(result, ensure_ascii=False))
        return 0

    try:
        destination.mkdir(parents=True, exist_ok=True)
        with file_lock(destination / ".capture.lock"):
            with path.open("a", encoding="utf-8", newline="") as handle:
                handle.write(line)
                handle.flush()
                os.fsync(handle.fileno())
        result["written"] = True
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except Exception as exc:
        result.update({"ok": False, "error": type(exc).__name__, "detail": str(exc)})
        print(json.dumps(result, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
