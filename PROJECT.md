# Obsidian Memo Capture

## Ownership

- Hermes-owned project root: `$HERMES_HOME/projects/obsidian-memo-capture`
- GitHub: `https://github.com/qingdoutianwu/obsidian-memo-capture`
- Branch: `main`
- Runtime plugin: `$HERMES_HOME/plugins/obsidian-memo-capture` → `project/plugin`
- Runtime skill: `$HERMES_HOME/skills/note-taking/obsidian-memos` → `project/skill`
- OpenClaw interactive memo Skill: retired and backed up; do not restore for production use.

## Runtime contract

Telegram text with an explicit `memo:`, `备忘：`, `lesson:`, or `todo:` prefix is intercepted by the Hermes plugin. The original body is appended to the configured local Obsidian vault. The plugin then requests a short evaluation through Hermes' host-owned LLM and replies through the current Telegram adapter.

- Vault setting: `plugins.entries.obsidian-memo-capture.settings.vault_path`
- Receipt root: `$HERMES_HOME/runtime/obsidian-memo-capture/receipts/`
- Writer: `skill/scripts/capture_memo.py`
- Destination: `<vault>/Memos/{memos,lessons,todos}/YYYYMMDD.md`

## Verification

```bash
hermes plugins doctor "$HERMES_HOME/projects/obsidian-memo-capture/plugin" --ci
python3 "$HERMES_HOME/projects/obsidian-memo-capture/tests/test_all.py"
python3 -m py_compile \
  "$HERMES_HOME/projects/obsidian-memo-capture/plugin/__init__.py" \
  "$HERMES_HOME/projects/obsidian-memo-capture/skill/scripts/capture_memo.py"
git status --short --branch
```

Live acceptance requires a real Telegram message, one matching Obsidian entry,
and a receipt with `capture.ok=true`, `capture.written=true`, `reply.ok=true`,
and a reply `message_id`.
