"""Hermes plugin: capture explicit Telegram memos in Obsidian."""
from __future__ import annotations

import asyncio
import datetime as dt
import hashlib
import json
import logging
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

LOGGER = logging.getLogger(__name__)
_PREFIXES = {
    "memo": "memos", "备忘": "memos", "记录": "memos",
    "lesson": "lessons", "教训": "lessons",
    "todo": "todos", "待办": "todos",
}
_INFLIGHT: set[str] = set()
_INFLIGHT_LOCK = asyncio.Lock()


def _split_prefix(text: str) -> tuple[str | None, str | None]:
    stripped = (text or "").lstrip()
    for prefix, folder in _PREFIXES.items():
        for separator in (":", "："):
            marker = prefix + separator
            if stripped.lower().startswith(marker.lower()):
                return folder, stripped[len(marker):].lstrip()
    return None, None


def _hermes_home() -> Path:
    return Path(os.environ.get("HERMES_HOME", str(Path.home() / ".hermes"))).expanduser().resolve()


def _vault(ctx) -> Path:
    configured = ctx.get_config("vault_path", default="~/Documents/NOTE240925_clean1")
    return Path(os.path.expanduser(str(configured))).resolve()


def _runtime_dir() -> Path:
    return _hermes_home() / "runtime" / "obsidian-memo-capture"


def _receipt_key(event, body: str) -> str:
    source = getattr(event, "source", None)
    platform = getattr(getattr(source, "platform", None), "value", "unknown")
    chat_id = str(getattr(source, "chat_id", "unknown"))
    message_id = str(getattr(event, "message_id", "") or "")
    identity = f"{platform}\x00{chat_id}\x00{message_id}" if message_id else (
        f"{platform}\x00{chat_id}\x00{body}"
    )
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]


def _receipt_path(key: str) -> Path:
    return _runtime_dir() / "receipts" / f"{key}.json"


def _body_sha256(body: str) -> str:
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _read_receipt(key: str) -> dict[str, Any] | None:
    path = _receipt_path(key)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, ValueError):
        return None


def _write_receipt(key: str, data: dict[str, Any]) -> None:
    path = _receipt_path(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    fd, temporary = tempfile.mkstemp(prefix=f".{key}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def _capture_is_reusable(existing: dict[str, Any] | None, folder: str, body: str) -> bool:
    if not existing or existing.get("folder") != folder:
        return False
    if existing.get("body_sha256") != _body_sha256(body):
        return False
    capture = existing.get("capture") or {}
    return bool(capture.get("ok") and capture.get("written") and capture.get("path"))


def _capture(ctx, folder: str, body: str) -> dict[str, Any]:
    script = _hermes_home() / "skills" / "note-taking" / "obsidian-memos" / "scripts" / "capture_memo.py"
    process = subprocess.run(
        [sys.executable, str(script), "--vault", str(_vault(ctx)),
         "--folder", folder, "--content", body],
        capture_output=True, text=True, timeout=30, check=False,
    )
    try:
        result = json.loads(process.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        result = {"ok": False, "error": "invalid_capture_output", "detail": process.stdout[-500:]}
    if process.returncode != 0:
        result["ok"] = False
    return result


async def _evaluation(ctx, folder: str, body: str, path: str) -> str:
    prompt = (
        "请对下面刚写入 Obsidian 的内容做简短中文评价。只输出 2-4 句："
        "概括核心观点，指出一个优点，最多给一个可执行的改进建议。"
        "不要声称查证过事实，不要重复整段原文，不要使用标题。\n\n"
        f"类型：{folder}\n内容：{body}"
    )
    try:
        result = await ctx.llm.acomplete(
            messages=[
                {"role": "system", "content": "你是简洁、克制的个人 memo 编辑。"},
                {"role": "user", "content": prompt},
            ],
            max_tokens=180,
            temperature=0.3,
            purpose="obsidian-memo-evaluation",
        )
        text = (result.text or "").strip()
        if text:
            return f"已写入 Obsidian：{Path(path).name}\n{text}"
    except Exception as exc:
        LOGGER.warning("Memo evaluation failed after successful capture: %s", exc)
    return f"已写入 Obsidian：{Path(path).name}\n评价暂未生成，但原文已安全保存。"


async def _send_reply(gateway, event, response: str):
    source = event.source
    adapter = gateway.adapters.get(source.platform) if gateway else None
    if adapter is None:
        return {"ok": False, "error": "telegram_adapter_missing"}
    metadata = {"notify": True}
    if source.thread_id:
        metadata["thread_id"] = source.thread_id
    result = await adapter.send(
        source.chat_id,
        response,
        reply_to=getattr(event, "message_id", None),
        metadata=metadata,
    )
    return {
        "ok": bool(getattr(result, "success", False)),
        "message_id": getattr(result, "message_id", None),
        "error": getattr(result, "error", None),
    }


async def _process_event(ctx, event, gateway, key: str, folder: str, body: str) -> None:
    existing = await asyncio.to_thread(_read_receipt, key)
    if existing and existing.get("reply", {}).get("ok"):
        LOGGER.info("Skipping already delivered memo receipt=%s", key)
        return

    incoming_body_sha256 = _body_sha256(body)
    if existing and existing.get("body_sha256") not in (None, incoming_body_sha256):
        LOGGER.error(
            "Memo receipt key conflict=%s existing_body_sha256=%s incoming_body_sha256=%s",
            key,
            existing.get("body_sha256"),
            incoming_body_sha256,
        )
        return

    receipt: dict[str, Any] = {
        "schema": 1,
        "key": key,
        "received_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "platform": "telegram",
        "chat_id": str(event.source.chat_id),
        "message_id": str(getattr(event, "message_id", "") or ""),
        "folder": folder,
        "body_sha256": incoming_body_sha256,
    }
    if existing:
        receipt.update({k: v for k, v in existing.items() if k not in {"reply", "updated_at"}})

    capture_reused = _capture_is_reusable(existing, folder, body)
    if capture_reused:
        assert existing is not None
        previous_capture = existing.get("capture")
        if not isinstance(previous_capture, dict):
            previous_capture = {}
        previous_path = str(previous_capture.get("path") or "")
        result = {
            "ok": True,
            "written": True,
            "path": previous_path,
            "reused": True,
        }
        LOGGER.info("Reusing captured memo receipt=%s path=%s", key, previous_path)
    else:
        result = await asyncio.to_thread(_capture, ctx, folder, body)
    receipt["capture"] = {
        "ok": bool(result.get("ok")),
        "written": bool(result.get("written")),
        "path": result.get("path"),
        "error": result.get("error"),
        "reused": capture_reused,
    }
    receipt["status"] = "captured" if result.get("ok") and result.get("written") else "capture_failed"
    receipt["updated_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
    await asyncio.to_thread(_write_receipt, key, receipt)

    if not result.get("ok") or not result.get("written"):
        response = f"无法写入 Obsidian memo：{result.get('error', 'unknown_error')}"
    else:
        response = await _evaluation(ctx, folder, body, result["path"])
    receipt["response_chars"] = len(response)
    receipt["response_sha256"] = hashlib.sha256(response.encode("utf-8")).hexdigest()
    receipt["status"] = "reply_pending"
    receipt["updated_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
    await asyncio.to_thread(_write_receipt, key, receipt)

    reply = await _send_reply(gateway, event, response)
    receipt["reply"] = reply
    receipt["status"] = "delivered" if reply["ok"] else "reply_failed"
    receipt["updated_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
    await asyncio.to_thread(_write_receipt, key, receipt)
    if not reply["ok"]:
        LOGGER.warning("Memo Telegram reply failed receipt=%s error=%s", key, reply.get("error"))


async def _run_once(ctx, event, gateway, key: str, folder: str, body: str) -> None:
    async with _INFLIGHT_LOCK:
        if key in _INFLIGHT:
            return
        _INFLIGHT.add(key)
    try:
        await _process_event(ctx, event, gateway, key, folder, body)
    except Exception:
        LOGGER.exception("Memo processing failed receipt=%s", key)
    finally:
        async with _INFLIGHT_LOCK:
            _INFLIGHT.discard(key)


def _log_task_failure(task) -> None:
    if task.cancelled():
        return
    try:
        error = task.exception()
    except Exception as exc:
        LOGGER.warning("Memo task result unavailable: %s", exc)
        return
    if error is not None:
        LOGGER.warning("Memo task failed: %s", error)


def _handle_event(ctx, event, gateway, **kwargs):
    del kwargs
    if getattr(event, "internal", False):
        return None
    message_type = getattr(event, "message_type", None)
    if getattr(message_type, "value", message_type) != "text":
        return None
    platform = getattr(getattr(event, "source", None), "platform", None)
    if getattr(platform, "value", platform) != "telegram":
        return None
    folder, body = _split_prefix(getattr(event, "text", ""))
    if not folder or not body:
        return None
    key = _receipt_key(event, body)
    try:
        loop = asyncio.get_running_loop()
        task = loop.create_task(_run_once(ctx, event, gateway, key, folder, body))
        task.add_done_callback(_log_task_failure)
    except RuntimeError:
        LOGGER.warning("Memo event received without a running gateway loop")
        return {"action": "rewrite", "text": "Memo 处理失败：Gateway event loop 不可用。"}
    return {"action": "skip", "reason": "memo-capture-scheduled"}


def register(ctx):
    ctx.register_hook(
        "pre_gateway_dispatch",
        lambda event, gateway=None, **kwargs: _handle_event(ctx, event, gateway, **kwargs),
    )
