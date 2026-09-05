from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "skill" / "scripts" / "capture_memo.py"


def run(tmp_path: Path, *args: str) -> dict:
    process = subprocess.run(
        [sys.executable, str(SCRIPT), "--vault", str(tmp_path), *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(process.stdout)


def test_dry_run_is_side_effect_free(tmp_path: Path) -> None:
    result = run(tmp_path, "--folder", "memos", "--content", "测试 😀\n第二行", "--dry-run")
    assert result["ok"] is True
    assert result["written"] is False
    assert not (tmp_path / "Memos").exists()


def test_capture_preserves_multiline_body(tmp_path: Path) -> None:
    body = "第一行\n第二行 *markdown* 😀"
    result = run(
        tmp_path,
        "--folder", "memos",
        "--content", body,
        "--timestamp", "2026-08-29T12:34:56",
    )
    path = Path(result["path"])
    assert result["written"] is True
    assert path.exists()
    assert path.read_text(encoding="utf-8") == "- [12:34] " + body + "\n"


def test_capture_appends_without_overwrite(tmp_path: Path) -> None:
    run(tmp_path, "--folder", "lessons", "--content", "a", "--timestamp", "2026-08-29T12:00:00")
    run(tmp_path, "--folder", "lessons", "--content", "b", "--timestamp", "2026-08-29T12:01:00")
    path = tmp_path / "Memos" / "lessons" / "20260829.md"
    assert path.read_text(encoding="utf-8") == "- [12:00] a\n- [12:01] b\n"
