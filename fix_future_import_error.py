from pathlib import Path
import re
from datetime import datetime

APP = Path("app.py")

if not APP.exists():
    raise SystemExit("ERROR: app.py not found. Put this script beside app.py and run again.")

text = APP.read_text(encoding="utf-8")

backup = APP.with_name(f"app.py.backup-future-import-fix-{datetime.now().strftime('%Y%m%d-%H%M%S')}")
backup.write_text(text, encoding="utf-8")

# Remove every future annotations import wherever it appears
lines = text.splitlines()
new_lines = []
for line in lines:
    if line.strip() == "from __future__ import annotations":
        continue
    new_lines.append(line)

# Preserve shebang / coding comment at very top if present
prefix = []
while new_lines and (new_lines[0].startswith("#!") or "coding" in new_lines[0].lower()):
    prefix.append(new_lines.pop(0))

# Remove leading blank lines after prefix
while new_lines and not new_lines[0].strip():
    new_lines.pop(0)

fixed_lines = prefix + ["from __future__ import annotations"] + new_lines
fixed = "\n".join(fixed_lines) + "\n"

# Repair common broken Flask import caused by older patches
broken_pattern = re.compile(
    r"from flask import \(\s*,?\s*jsonify\s*\n(?P<body>.*?\n\)",
    re.DOTALL
)
if broken_pattern.search(fixed):
    fixed = broken_pattern.sub(
        "from flask import (\n"
        "    Flask,\n"
        "    flash,\n"
        "    jsonify,\n"
        "    redirect,\n"
        "    render_template,\n"
        "    request,\n"
        "    send_file,\n"
        "    url_for,\n"
        ")",
        fixed,
        count=1
    )

# Ensure BytesIO exists if the export route was added
if "BytesIO" in fixed and "from io import BytesIO" not in fixed:
    # Insert after future import
    fixed = fixed.replace(
        "from __future__ import annotations\n",
        "from __future__ import annotations\nfrom io import BytesIO\n",
        1
    )

APP.write_text(fixed, encoding="utf-8")
print("Fixed app.py.")
print(f"Backup created: {backup.name}")
print("Now run: python app.py")
