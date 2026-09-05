---
name: obsidian-memos
description: Capture memo, lesson, and todo text in Obsidian.
version: 1.0.0
author: LicHaoWei, Hermes Agent
license: MIT
platforms: [macos, linux, windows]
metadata:
  hermes:
    tags: [Obsidian, memo, notes, capture]
    related_skills: [obsidian]
    config:
      - key: obsidian_memos.vault_path
        description: Absolute path to the Obsidian vault used for memo capture.
        default: "~/Documents/NOTE240925_clean1"
        prompt: Obsidian vault path
---

# Obsidian Memos

Use this skill when the user explicitly asks to save a `memo`, `lesson`, or `todo` from the current message into the local Obsidian vault. The original text is written locally first; a short evaluation is generated only after the write succeeds. Do not replace or rewrite the original memo.

## When to Use

- `memo:` / `memo：` / `备忘：` / `记录：` → `OpenClaw远程笔记/memos/`
- `lesson:` / `lesson：` / `教训：` → `OpenClaw远程笔记/lessons/`
- `todo:` / `todo：` / `待办：` → `OpenClaw远程笔记/todos/`
- A request such as “写入 memo” with an explicitly supplied memo body.

Do not use this skill for ordinary conversation, workspace memory, or OneDrive mirror maintenance.

## Prerequisites

- The configured vault path must exist or be creatable.
- The skill uses only the local filesystem and Python standard library.
- The destination is `<vault>/OpenClaw远程笔记/<folder>/YYYYMMDD.md`. The folder name is a preserved Obsidian data-layout label, not a runtime dependency.

## Behavior

The enabled `obsidian-memo-capture` Hermes plugin intercepts explicit memo prefixes on Telegram before normal agent dispatch. It writes the original body, then sends a short evaluation back to the same Telegram chat. Non-Telegram messages and ordinary text pass through normally.

## Manual Run

Run the bundled writer through `terminal`:

```bash
python3 ${HERMES_SKILL_DIR}/scripts/capture_memo.py \
  --vault "<resolved vault path>" --folder memos --content "原始 memo 内容"
```

For a no-write preview:

```bash
python3 ${HERMES_SKILL_DIR}/scripts/capture_memo.py \
  --vault "<resolved vault path>" --folder memos --content "测试内容" --dry-run
```

## Procedure

1. Identify the explicit type prefix and remove only that routing prefix. Keep the remaining body unchanged.
2. Resolve the configured vault path. Do not use `/root/obsidian-vault` or any `.openclaw` path on this Mac.
3. The writer creates the destination and appends under an exclusive lock. Its JSON must contain `ok=true`, `written=true`, and a concrete `path`.
4. Only after a successful write, generate a short Chinese evaluation: core idea, one strength, and at most one practical refinement.
5. If evaluation fails, report that the original was saved; evaluation failure must not roll back or duplicate the memo.

## Pitfalls

- Do not invoke the old OpenClaw Node scripts or `append_and_sync.sh`.
- Do not put memo text in persistent Hermes memory unless explicitly requested.
- Do not silently append the evaluation to the original memo.
- Multiline content is valid and remains multiline.
- The plugin intentionally handles only Telegram text messages with an explicit prefix.

## Verification

A local run is accepted only when the JSON is successful and the returned path exists under the configured vault. Plugin status is checked with `hermes plugins list`; gateway status with `hermes gateway status`. Use a labeled test memo for live Telegram verification and inspect the resulting Obsidian file afterward.
