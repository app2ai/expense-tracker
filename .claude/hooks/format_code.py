"""PostToolUse hook: format Python files with black after Claude edits them.

Claude Code pipes the finished tool call to stdin as JSON. If the edited file
is a project .py file, black reformats it in place. If black can't parse the
file (a syntax error), the error is sent back to Claude via exit code 2 so it
can fix the code.
"""

import json
import subprocess
import sys
from pathlib import Path

SKIP_DIRS = {"wenv", "venv", ".venv", "__pycache__", ".git"}


def main():
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)  # never break the session on malformed input

    tool_input = payload.get("tool_input", {}) or {}
    file_path = tool_input.get("file_path", "")
    if not file_path:
        sys.exit(0)

    path = Path(file_path)
    if path.suffix != ".py" or not path.is_file():
        sys.exit(0)
    if SKIP_DIRS.intersection(path.parts):
        sys.exit(0)

    result = subprocess.run(
        [sys.executable, "-m", "black", "--quiet", str(path)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        print(f"black could not format {path.name}:\n{result.stderr.strip()}", file=sys.stderr)
        sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
