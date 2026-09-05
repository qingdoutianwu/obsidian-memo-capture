# Obsidian Memo Capture for Hermes

A standalone Hermes Agent plugin and skill that turns explicit Telegram memo messages into local Obsidian notes, then replies with a short LLM evaluation.

## Flow

```text
Telegram → Hermes Gateway → pre_gateway_dispatch → Obsidian Markdown → Telegram reply
```

The original memo is written deterministically before evaluation. Evaluation failure never rolls back the saved memo.

## Included

- `plugin/` — Hermes general plugin (`plugin.yaml` + `__init__.py`)
- `skill/` — portable Hermes Skill (`SKILL.md` + `scripts/capture_memo.py`)
- `tests/` — stdlib-only writer and plugin-helper smoke tests
- `.github/workflows/ci.yml` — GitHub Actions validation workflow

## Install locally

Copy or symlink the two runtime directories:

```bash
mkdir -p ~/.hermes/plugins ~/.hermes/skills/note-taking
cp -R plugin ~/.hermes/plugins/obsidian-memo-capture
cp -R skill ~/.hermes/skills/note-taking/obsidian-memos
hermes plugins enable obsidian-memo-capture
hermes config set plugins.entries.obsidian-memo-capture.settings.vault_path "$HOME/Documents/NOTE240925_clean1"
hermes gateway restart
```

The plugin uses `<vault>/OpenClaw远程笔记/{memos,lessons,todos}/YYYYMMDD.md` to preserve the existing vault layout. Change the configured vault path for another vault.

## Message prefixes

- `memo:` / `memo：` / `备忘：` / `记录：`
- `lesson:` / `lesson：` / `教训：`
- `todo:` / `todo：` / `待办：`

Only explicit Telegram text messages are intercepted. Ordinary text, other platforms, media, and internal events pass through normally.

## Verification

```bash
hermes plugins doctor ~/.hermes/plugins/obsidian-memo-capture --ci
python3 tests/test_capture_memo.py
hermes plugins list --plain --no-bundled
hermes gateway status
```

For a live test, send a labeled `memo：...` message to the configured Telegram bot. Verify the target Markdown file contains exactly one original entry and the Hermes receipt reports `capture.ok=true`, `capture.written=true`, and `reply.ok=true` with a reply `message_id`.

## Security

Do not commit Telegram tokens, provider credentials, `.env` files, personal vault contents, receipts, or machine-specific runtime logs. The plugin does not send outbound network requests except through Hermes' host-owned LLM and Telegram adapter APIs.
