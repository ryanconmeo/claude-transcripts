#!/usr/bin/env bash
input=$(cat)
session_id=$(echo "$input" | jq -r '.session_id // "unknown"')
rm -f "/tmp/claude_session_raw_${session_id}"
