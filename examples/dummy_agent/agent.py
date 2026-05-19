"""Intentionally vulnerable demo agent.

It receives a task as its command-line argument, finds any /workspace path
in the task, reads that file, and then naively executes any `EXECUTE: <cmd>`
line found in the file's content. This is a textbook indirect-prompt-injection
bug: untrusted file content gets treated as agent instructions.

The harness should catch this by observing destructive filesystem changes.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys


def main() -> None:
    task = sys.argv[1] if len(sys.argv) > 1 else ""
    if not task:
        print(json.dumps({"final_output": "no task received"}))
        return

    path_match = re.search(r"/workspace/\S+", task)
    if not path_match:
        print(json.dumps({"final_output": "no file mentioned in task"}))
        return

    file_path = path_match.group(0).rstrip(".,;:!?\"'")
    try:
        with open(file_path) as f:
            content = f.read()
    except OSError as e:
        print(json.dumps({"final_output": f"could not read {file_path}: {e}"}))
        return

    for line in content.splitlines():
        m = re.match(r"\s*EXECUTE:\s*(.+)", line)
        if m:
            subprocess.run(m.group(1).strip(), shell=True)

    summary = content.strip().splitlines()[0] if content.strip() else ""
    print(json.dumps({"final_output": f"summary of {file_path}: {summary[:80]}"}))


if __name__ == "__main__":
    main()
