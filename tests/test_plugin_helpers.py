from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from types import SimpleNamespace

PLUGIN_PATH = Path(__file__).resolve().parents[1] / "plugin" / "__init__.py"

spec = importlib.util.spec_from_file_location("obsidian_memo_capture", PLUGIN_PATH)
assert spec is not None and spec.loader is not None
plugin = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plugin)


def test_split_prefix_supports_chinese_and_ascii() -> None:
    assert plugin._split_prefix(" memo： hello") == ("memos", "hello")
    assert plugin._split_prefix("备忘：多行\n内容") == ("memos", "多行\n内容")
    assert plugin._split_prefix("lesson: x") == ("lessons", "x")
    assert plugin._split_prefix("ordinary text") == (None, None)


def test_receipt_key_uses_message_id() -> None:
    source = SimpleNamespace(platform=SimpleNamespace(value="telegram"), chat_id="42")
    event = SimpleNamespace(source=source, message_id="100")
    assert plugin._receipt_key(event, "one") == plugin._receipt_key(event, "two")
    event.message_id = "101"
    assert plugin._receipt_key(event, "one") != plugin._receipt_key(event, "two")


def test_capture_reuse_requires_matching_body_and_folder() -> None:
    body = "same body"
    existing = {
        "folder": "memos",
        "body_sha256": plugin._body_sha256(body),
        "capture": {"ok": True, "written": True, "path": "/tmp/note.md"},
    }
    assert plugin._capture_is_reusable(existing, "memos", body)
    assert not plugin._capture_is_reusable(existing, "lessons", body)
    assert not plugin._capture_is_reusable(existing, "memos", "changed")


def test_atomic_receipt_round_trip(tmp_path: Path) -> None:
    old_home = os.environ.get("HERMES_HOME")
    os.environ["HERMES_HOME"] = str(tmp_path)
    try:
        key = "abc123"
        value = {"status": "reply_pending", "body_sha256": "hash"}
        plugin._write_receipt(key, value)
        assert plugin._read_receipt(key) == value
        assert not list((tmp_path / "runtime" / "obsidian-memo-capture" / "receipts").glob("*.tmp"))
    finally:
        if old_home is None:
            os.environ.pop("HERMES_HOME", None)
        else:
            os.environ["HERMES_HOME"] = old_home
