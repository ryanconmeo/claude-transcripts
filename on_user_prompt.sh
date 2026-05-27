#!/usr/bin/env bash
input=$(cat)
session_id=$(echo "$input" | jq -r '.session_id // "unknown"')

# On first prompt, record which .raw file belongs to this session.
# The raw file was created seconds ago by the `claude` shell wrapper.
raw_map_file="/tmp/claude_session_raw_${session_id}"
if [ ! -f "$raw_map_file" ]; then
    latest_raw=$(ls -t "$HOME/claude-logs/"[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]_[0-9][0-9]-[0-9][0-9]-[0-9][0-9].raw 2>/dev/null | head -1)
    [ -n "$latest_raw" ] && basename "$latest_raw" .raw > "$raw_map_file"
fi
