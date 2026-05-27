#!/usr/bin/env python3
"""
Stop hook: saves a clean, readable markdown transcript of the Claude Code session.
Receives JSON payload via stdin, writes to ~/claude-logs/<date>_<time>_<short-id>.md
"""
import json
import re
import sys
import os
from datetime import datetime, timezone
from pathlib import Path


def extract_text(content):
    """Return (text_parts, tool_lines) from a content block list or string."""
    if isinstance(content, str):
        return content.strip(), []
    if not isinstance(content, list):
        return "", []

    text_parts = []
    tool_lines = []
    for block in content:
        if not isinstance(block, dict):
            continue
        btype = block.get("type", "")
        if btype == "text":
            t = block.get("text", "").strip()
            if t:
                text_parts.append(t)
        elif btype == "tool_use":
            name = block.get("name", "tool")
            inp = block.get("input", {})
            # One-line summary: command for Bash, file_path for Read/Edit/Write, etc.
            summary = _tool_summary(name, inp)
            tool_lines.append(f"`{name}`{': ' + summary if summary else ''}")
        elif btype == "tool_result":
            # Skip — verbose and low signal in a readable log
            pass
    return "\n\n".join(text_parts), tool_lines


def _tool_summary(name, inp):
    """Return a short one-line summary of a tool call input."""
    if not isinstance(inp, dict):
        return ""
    if name == "Bash":
        cmd = inp.get("command", "")
        return cmd[:120] + ("…" if len(cmd) > 120 else "")
    if name in ("Read", "Edit", "Write"):
        return inp.get("file_path", "")
    if name == "Agent":
        return inp.get("description", "")
    if name in ("WebSearch", "WebFetch"):
        return inp.get("query", inp.get("url", ""))
    # Generic: show first string value
    for v in inp.values():
        if isinstance(v, str) and v:
            return v[:80] + ("…" if len(v) > 80 else "")
    return ""


def format_timestamp(ts_str):
    if not ts_str:
        return ""
    try:
        dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        return dt.astimezone().strftime("%H:%M:%S")
    except Exception:
        return ts_str[:19]


def slugify(text, max_len=50):
    """Convert a title to a lowercase-hyphenated filename-safe slug."""
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"\s+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text[:max_len].rstrip("-")


_ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

def _raw_search_text(entries, session_id):
    """Return strings to search for in a stripped .raw file to confirm session match."""
    needles = [session_id]
    for entry in entries:
        if entry.get("type") != "user":
            continue
        msg = entry.get("message", {})
        text, _ = extract_text(msg.get("content", ""))
        if text and len(text) > 10:
            needles.append(text[:200])
            break
    return needles


def rename_matching_raws(logs_dir, entries, session_id, slug):
    """Rename the .raw file for this session. Uses the temp mapping written by
    on_user_prompt.sh as the primary source; falls back to content matching."""
    bare_ts_pat = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}$")

    # Primary: read the session→raw mapping recorded at first prompt
    raw_map_file = Path(f"/tmp/claude_session_raw_{session_id}")
    candidates = []
    if raw_map_file.exists():
        stem = raw_map_file.read_text().strip()
        mapped = logs_dir / f"{stem}.raw"
        if mapped.exists() and bare_ts_pat.match(stem):
            candidates = [mapped]

    # Fallback: content search
    if not candidates:
        needles = _raw_search_text(entries, session_id)
        for raw_file in sorted(logs_dir.glob("*.raw")):
            if not bare_ts_pat.match(raw_file.stem):
                continue
            try:
                raw_text = _ansi_escape.sub("", raw_file.read_bytes()[:200_000].decode("utf-8", errors="ignore"))
            except Exception:
                continue
            if any(needle in raw_text for needle in needles):
                candidates.append(raw_file)

    for raw_file in candidates:
        new_path = logs_dir / f"{raw_file.stem}_{slug}.raw"
        raw_file.rename(new_path)
        print(f"[save_transcript] Renamed raw {raw_file.name} → {new_path.name}", file=sys.stderr)


def find_transcript(payload):
    """Return path to the JSONL transcript, or None."""
    path = payload.get("transcript_path", "")
    if path and os.path.exists(path):
        return path

    # Fall back: search ~/.claude/projects/ for a file containing the session id
    session_id = payload.get("session_id", "")
    if not session_id:
        return None

    projects_dir = Path.home() / ".claude" / "projects"
    if not projects_dir.exists():
        return None

    candidates = sorted(projects_dir.rglob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    for c in candidates[:20]:  # check only the most recent files to stay fast
        try:
            first_line = c.read_text(encoding="utf-8", errors="ignore").splitlines()[0]
            if session_id in first_line:
                return str(c)
        except Exception:
            continue
    return None


def render_transcript(entries, session_id, cwd):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        f"# Claude Code Session",
        f"",
        f"| Field | Value |",
        f"|-------|-------|",
        f"| Date | {now} |",
        f"| Session | `{session_id}` |",
        f"| Directory | `{cwd or '—'}` |",
        f"",
        f"---",
        f"",
    ]

    rendered_any = False
    for entry in entries:
        etype = entry.get("type", "")
        if etype not in ("user", "assistant"):
            continue

        message = entry.get("message", {})
        if not isinstance(message, dict):
            continue

        role = message.get("role", etype)
        content = message.get("content", "")
        ts = format_timestamp(entry.get("timestamp", ""))

        text, tool_lines = extract_text(content)

        # Skip entries that are only tool_result (no text, no tool_use)
        if not text and not tool_lines:
            continue

        header = "### User" if role == "user" else "### Assistant"
        time_tag = f" *{ts}*" if ts else ""
        lines.append(f"{header}{time_tag}")
        lines.append("")

        if text:
            lines.append(text)
            lines.append("")

        if tool_lines:
            lines.append("**Tool calls:**")
            for tl in tool_lines:
                lines.append(f"- {tl}")
            lines.append("")

        lines.append("---")
        lines.append("")
        rendered_any = True

    if not rendered_any:
        lines.append("*(no messages)*")

    return "\n".join(lines)


def main():
    import time
    time.sleep(1)  # wait for JSONL transcript to be flushed before reading

    raw = sys.stdin.read().strip()
    if not raw:
        sys.exit(0)

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        sys.exit(0)

    session_id = payload.get("session_id", "unknown")
    cwd = payload.get("cwd", "")

    transcript_path = find_transcript(payload)
    if not transcript_path:
        print(f"[save_transcript] Could not find transcript for session {session_id}", file=sys.stderr)
        sys.exit(0)

    entries = []
    try:
        with open(transcript_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        print(f"[save_transcript] Error reading {transcript_path}: {e}", file=sys.stderr)
        sys.exit(0)

    if not entries:
        sys.exit(0)

    transcript_md = render_transcript(entries, session_id, cwd)

    logs_dir = Path.home() / "claude-logs"
    logs_dir.mkdir(exist_ok=True)

    # Use session start time to match the .raw filename (YYYY-MM-DD_HH-MM-SS)
    first_ts = next((e.get("timestamp", "") for e in entries if e.get("timestamp")), "")
    try:
        start_dt = datetime.fromisoformat(first_ts.replace("Z", "+00:00")).astimezone()
        file_ts = start_dt.strftime("%Y-%m-%d_%H-%M-%S")
    except Exception:
        file_ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    ai_title = next((e.get("aiTitle", "") for e in entries if e.get("type") == "ai-title"), "")
    slug = slugify(ai_title) if ai_title else ""
    out_path = logs_dir / (f"{file_ts}_{slug}.md" if slug else f"{file_ts}.md")

    # Remove any stale file with the same timestamp prefix (e.g. pre-title version)
    for old in logs_dir.glob(f"{file_ts}*.md"):
        if old != out_path:
            old.unlink()

    out_path.write_text(transcript_md, encoding="utf-8")
    print(f"[save_transcript] Saved to {out_path}", file=sys.stderr)

    if slug:
        rename_matching_raws(logs_dir, entries, session_id, slug)

    sys.exit(0)


if __name__ == "__main__":
    main()
