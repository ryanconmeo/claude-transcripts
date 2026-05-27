# claude-transcripts

Claude Code hooks that save a readable markdown transcript of each session to `~/claude-logs/` and rename matching terminal recordings (`.raw` files) to include the session's AI-generated title slug.

## If you're Claude and someone asked you to install this

Run these commands:

```bash
mkdir -p $HOME/.claude/transcripts
cd $HOME/.claude/transcripts
curl -O https://raw.githubusercontent.com/ryanconmeo/claude-transcripts/main/save_transcript.py
curl -O https://raw.githubusercontent.com/ryanconmeo/claude-transcripts/main/on_user_prompt.sh
curl -O https://raw.githubusercontent.com/ryanconmeo/claude-transcripts/main/on_stop.sh
chmod +x on_user_prompt.sh on_stop.sh
```

Then merge the following into `~/.claude/settings.json`. Use the `update-config` skill if available — otherwise show the user this snippet and ask them to add it manually, then restart Claude Code.

**Important:** The `hooks` arrays must be *merged*, not replaced. If `Stop` or `UserPromptSubmit` hooks already exist from other projects, append these entries to the existing arrays.

```json
"hooks": {
  "Stop": [{"matcher": "", "hooks": [
    {"type": "command", "command": "python3 $HOME/.claude/transcripts/save_transcript.py"},
    {"type": "command", "command": "bash $HOME/.claude/transcripts/on_stop.sh"}
  ]}],
  "UserPromptSubmit": [{"matcher": "", "hooks": [
    {"type": "command", "command": "bash $HOME/.claude/transcripts/on_user_prompt.sh"}
  ]}]
}
```

Restart Claude Code after saving.

## Files

**`save_transcript.py`** — `Stop` hook. Writes a clean markdown transcript of the session to `~/claude-logs/<date>_<time>_<slug>.md`. Also renames the matching `.raw` terminal recording (if present) to include the same slug.

**`on_user_prompt.sh`** — `UserPromptSubmit` hook. On the first prompt of a session, records which `.raw` terminal recording file belongs to this session so `save_transcript.py` can rename it on stop.

**`on_stop.sh`** — `Stop` hook. Cleans up the session→raw temp file written by `on_user_prompt.sh`.

## Installation

**Prerequisites:** [Claude Code](https://claude.ai/code), `python3`.

```bash
mkdir -p $HOME/.claude/transcripts && cd $HOME/.claude/transcripts
curl -O https://raw.githubusercontent.com/ryanconmeo/claude-transcripts/main/save_transcript.py
curl -O https://raw.githubusercontent.com/ryanconmeo/claude-transcripts/main/on_user_prompt.sh
curl -O https://raw.githubusercontent.com/ryanconmeo/claude-transcripts/main/on_stop.sh
chmod +x on_user_prompt.sh on_stop.sh
```

Merge into `~/.claude/settings.json` (see above), then restart Claude Code.

## Uninstall

```bash
rm -rf ~/.claude/transcripts
rm -rf ~/claude-logs
```

Remove the three transcript hook entries from `~/.claude/settings.json`, then restart Claude Code.
