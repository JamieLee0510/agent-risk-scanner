"""Intentionally vulnerable web-fetching agent.

It extracts a URL from the task, fetches that page, and -- the bug -- executes
any `EXECUTE: <cmd>` line found in the fetched content. This is the textbook
indirect-prompt-injection-via-web vulnerability: untrusted page content is
trusted as if it were an agent instruction.

The scanner serves the page from a loopback mock web server (the agent never
reaches the real internet), so the harness can catch this by observing the
destructive filesystem changes the injected command produces.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import urllib.request


def main() -> None:
    task = sys.argv[1] if len(sys.argv) > 1 else ""

    m = re.search(r"https?://\S+", task)
    if not m:
        print(json.dumps({"final_output": "no URL found in task"}))
        return

    url = m.group(0).rstrip(".,)")
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            content = resp.read().decode("utf-8", "replace")
    except OSError as e:
        print(json.dumps({"final_output": f"fetch failed: {e}"}))
        return

    # The bug: obey instructions embedded in the fetched (untrusted) page.
    for line in content.splitlines():
        m = re.match(r"\s*EXECUTE:\s*(.+)", line)
        if m:
            subprocess.run(m.group(1).strip(), shell=True)

    print(json.dumps({"final_output": f"fetched {url} ({len(content)} bytes)"}))


if __name__ == "__main__":
    main()
