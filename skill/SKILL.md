---
name: obsidian-memos
description: Capture memo, lesson, and todo text in Obsidian.
version: 1.0.0
author: qingdoutianwu, Hermes Agent
license: MIT
platforms: [macos, linux, windows]
metadata:
  hermes:
    tags: [Obsidian, memo, notes, capture]
    related_skills: []
---

# Obsidian Memos

Capture explicit `memo`, `lesson`, and `todo` messages in a local Obsidian vault. The original text is written first; evaluation is optional and must never block or rewrite the saved text.

## When to Use

- `memo:` / `memo：` / `备忘：` / `记录：` → `OpenClaw远程笔记/memos/`
- `lesson:` / `lesson：` / `教训：` → `OpenClaw远程笔记/lessons/`
- `todo:` / `todo：` / `待办：` → `OpenClaw远程笔记/todos/`

Do not use for ordinary conversation, Hermes persistent memory, or OneDrive mirror maintenance.

## Prerequisites

- A local Obsidian vault path.
- Python standard library only for the bundled writer.
- For automatic Telegram interception, enable the companion `obsidian-memo-capture` Hermes plugin.

## Quick Reference

```bash
python3 scripts/capture_memo.py \
  --vault "<vault>" --folder memos --content "原始内容"

python3 scripts/capture_memo.py \
  --vault "<vault>" --folder memos --content "测试内容" --dry-run
```

## Procedure

1. Remove only the explicit routing prefix; preserve the remaining body exactly.
2. Append to `<vault>/OpenClaw远程笔记/<folder>/YYYYMMDD.md` under a file lock.
3. Require the writer JSON to report `ok=true`, `written=true`, and a concrete path.
4. If Telegram interception is enabled, the plugin sends a short evaluation to the same chat only after the write succeeds.
5. Treat a prior `delivered` receipt for the same Telegram message key as already handled; do not write or reply again.

## Pitfalls

- Never use `/root/obsidian-vault` or an OpenClaw runtime path on macOS.
- Never commit vault contents, Telegram credentials, `.env` files, receipts, or logs.
- Evaluation failure does not invalidate a successful write.
- Multiline Markdown and emoji are valid and remain unchanged.

## Verification

Use the writer dry-run and a temporary vault for local tests. For live Telegram acceptance, confirm the target file contains one original entry and the receipt contains `capture.ok=true`, `capture.written=true`, `reply.ok=true`, and a reply `message_id`.
