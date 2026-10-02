"""PreToolUse hook: block accidental deletion of the Spendly SQLite database.

Claude Code pipes the pending tool call to stdin as JSON. If the call would
delete, truncate, or overwrite expense_tracker.db, this script prints a
"deny" decision so the tool never runs. Anything else is allowed through.
"""

import json
import re
import sys

DB_NAME = "expense_tracker.db"

# Commands / APIs that remove or clobber files, in bash, PowerShell, cmd, Python.
DELETE_PATTERN = re.compile(
    r"""
    \brm\b | \brmdir\b | \bunlink\b | \bshred\b | \btruncate\b
    | \bdel\b | \berase\b | \brd\b
    | \bRemove-Item\b | \bri\b | \bClear-Content\b | \bSet-Content\b
    | \bmv\b | \bmove\b | \bMove-Item\b | \bRename-Item\b
    | os\.remove | os\.unlink | shutil\.rmtree | \.unlink\(
    | >\s*["']?[^\s|;&]*expense_tracker\.db    # shell redirect truncation
    """,
    re.IGNORECASE | re.VERBOSE,
)

# Targets that would include the DB: its name, a *.db glob, or a wipe of the project.
TARGET_PATTERN = re.compile(
    r"""
    expense_tracker\.db
    | \*\.db\b | \*\.\*
    | (?:^|\s)["']?(?:\.|\*|\./\*|\.\\\*)["']?(?:\s|$)
    """,
    re.IGNORECASE | re.VERBOSE,
)

# git clean -x / -X removes ignored files, and the DB is in .gitignore.
GIT_CLEAN_IGNORED = re.compile(r"\bgit\s+clean\b[^|;&]*\s-\w*[xX]", re.IGNORECASE)


def deny(reason):
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }))
    sys.exit(0)


def check_command(command):
    if GIT_CLEAN_IGNORED.search(command):
        deny(
            f"Blocked: 'git clean -x/-X' would delete the gitignored {DB_NAME}. "
            "Run it manually if you really mean it."
        )
    if DELETE_PATTERN.search(command) and TARGET_PATTERN.search(command):
        deny(
            f"Blocked: this command looks like it would delete or overwrite {DB_NAME}. "
            "The expense tracker database is protected by .claude/hooks/protect_db.py. "
            "If deletion is really intended, ask the user to do it manually."
        )


def check_file_write(file_path):
    if file_path.replace("\\", "/").lower().endswith(DB_NAME):
        deny(f"Blocked: writing directly to {DB_NAME} would overwrite the database.")


def main():
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)  # never break the session on malformed input

    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {}) or {}

    if tool_name in ("Bash", "PowerShell"):
        check_command(tool_input.get("command", ""))
    elif tool_name in ("Write", "Edit", "NotebookEdit"):
        check_file_write(tool_input.get("file_path", "") or tool_input.get("notebook_path", ""))

    sys.exit(0)


if __name__ == "__main__":
    main()
