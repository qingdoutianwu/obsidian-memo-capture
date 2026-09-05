from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skill" / "scripts" / "capture_memo.py"
PLUGIN_PATH = ROOT / "plugin" / "__init__.py"


def run(vault: Path, *args: str) -> dict:
    process = subprocess.run(
        [sys.executable, str(SCRIPT), "--vault", str(vault), *args],
        capture_output=True,
        text=True,
        check=True,
    )
    import json
    return json.loads(process.stdout)


def load_plugin():
    spec = importlib.util.spec_from_file_location("obsidian_memo_capture", PLUGIN_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_prefixes() -> None:
    plugin = load_plugin()
    assert plugin._split_prefix(" memo： hello") == ("memos", "hello")
    assert plugin._split_prefix("备忘：多行\n内容") == ("memos", "多行\n内容")
    assert plugin._split_prefix("lesson: x") == ("lessons", "x")
    assert plugin._split_prefix("ordinary text") == (None, None)


def test_receipt_key_and_reuse() -> None:
    plugin = load_plugin()
    source = SimpleNamespace(platform=SimpleNamespace(value="telegram"), chat_id="42")
    event = SimpleNamespace(source=source, message_id="100")
    assert plugin._receipt_key(event, "one") == plugin._receipt_key(event, "two")
    other_event = SimpleNamespace(source=source, message_id="101")
    assert plugin._receipt_key(event, "one") != plugin._receipt_key(other_event, "one")
    no_id_event = SimpleNamespace(source=source, message_id=None)
    assert plugin._receipt_key(no_id_event, "one") != plugin._receipt_key(no_id_event, "two")
    body = "same body"
    existing = {
        "folder": "memos",
        "body_sha256": plugin._body_sha256(body),
        "capture": {"ok": True, "written": True, "path": "/tmp/note.md"},
    }
    assert plugin._capture_is_reusable(existing, "memos", body)
    assert not plugin._capture_is_reusable(existing, "lessons", body)
    assert not plugin._capture_is_reusable(existing, "memos", "changed")


def test_atomic_receipt_round_trip() -> None:
    plugin = load_plugin()
    with tempfile.TemporaryDirectory() as directory:
        old_home = os.environ.get("HERMES_HOME")
        os.environ["HERMES_HOME"] = directory
        try:
            plugin._write_receipt("abc123", {"status": "reply_pending"})
            assert plugin._read_receipt("abc123") == {"status": "reply_pending"}
            assert not list((Path(directory) / "runtime/obsidian-memo-capture/receipts").glob("*.tmp"))
        finally:
            if old_home is None:
                os.environ.pop("HERMES_HOME", None)
            else:
                os.environ["HERMES_HOME"] = old_home


def test_writer_behavior() -> None:
    with tempfile.TemporaryDirectory() as directory:
        vault = Path(directory)
        preview = run(vault, "--folder", "memos", "--content", "测试 😀\n第二行", "--dry-run")
        assert preview["ok"] is True and preview["written"] is False
        assert not (vault / "Memos").exists()
        body = "第一行\n第二行 *markdown* 😀"
        result = run(vault, "--folder", "memos", "--content", body, "--timestamp", "2026-08-29T12:34:56")
        assert result["written"] is True
        assert Path(result["path"]).read_text(encoding="utf-8") == "- [12:34] " + body + "\n"
        run(vault, "--folder", "lessons", "--content", "a", "--timestamp", "2026-08-29T12:00:00")
        run(vault, "--folder", "lessons", "--content", "b", "--timestamp", "2026-08-29T12:01:00")
        lessons = vault / "Memos/lessons/20260829.md"
        assert lessons.read_text(encoding="utf-8") == "- [12:00] a\n- [12:01] b\n"


if __name__ == "__main__":
    test_prefixes()
    test_receipt_key_and_reuse()
    test_atomic_receipt_round_trip()
    test_writer_behavior()
    print("all tests: PASS")
