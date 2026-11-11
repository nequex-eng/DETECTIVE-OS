"""Static checks for the public investigation workspace.

Extract inline JavaScript and ask Node to parse it. Also assert that
every result workspace has both a tab and a corresponding pane.
"""
from html.parser import HTMLParser
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent.parent
HTML = ROOT / "public" / "investigate.html"


class Scripts(HTMLParser):
    def __init__(self):
        super().__init__()
        self.inline = False
        self.parts = []
        self.current = []

    def handle_starttag(self, tag, attrs):
        if tag == "script":
            self.inline = not any(k == "src" for k, _ in attrs)
            self.current = []

    def handle_data(self, data):
        if self.inline:
            self.current.append(data)

    def handle_endtag(self, tag):
        if tag == "script" and self.inline:
            self.parts.append("".join(self.current))
            self.inline = False
            self.current = []


def main():
    source = HTML.read_text(encoding="utf-8")
    parser = Scripts()
    parser.feed(source)
    if not parser.parts:
        raise SystemExit("No inline JavaScript found in investigate.html")
    required = ("summary", "hypotheses", "sources", "coverage", "timeline",
                "graph", "contradictions", "plan", "review", "report", "events")
    for name in required:
        if f'data-tab="{name}"' not in source:
            raise SystemExit(f"Missing result tab: {name}")
        if f'id="pane-{name}"' not in source:
            raise SystemExit(f"Missing result pane: {name}")
    with tempfile.TemporaryDirectory() as td:
        for index, code in enumerate(parser.parts):
            target = Path(td) / f"inline-{index}.js"
            target.write_text(code, encoding="utf-8")
            result = subprocess.run(
                ["node", "--check", str(target)],
                capture_output=True, text=True)
            if result.returncode:
                raise SystemExit(result.stderr or result.stdout)
    print(f"frontend checks passed: {len(parser.parts)} inline script(s), "
          f"{len(required)} result workspaces")


if __name__ == "__main__":
    main()
