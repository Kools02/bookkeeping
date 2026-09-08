from pathlib import Path
from datetime import datetime

APP = Path("app.py")

if not APP.exists():
    raise SystemExit("ERROR: app.py not found. Put this script beside app.py and run again.")

text = APP.read_text(encoding="utf-8")

backup = APP.with_name(f"app.py.backup-safe-fix-{datetime.now().strftime('%Y%m%d-%H%M%S')}")
backup.write_text(text, encoding="utf-8")

# Normalize line endings while editing
lines = text.splitlines()

# 1) Remove all duplicate/misplaced "from __future__ import annotations"
cleaned = []
for line in lines:
    if line.strip() == "from __future__ import annotations":
        continue
    cleaned.append(line)

# 2) Keep shebang / encoding comment before future import if present
top_comments = []
while cleaned and (cleaned[0].startswith("#!") or "coding" in cleaned[0].lower()):
    top_comments.append(cleaned.pop(0))

# Remove blank lines before first code
while cleaned and cleaned[0].strip() == "":
    cleaned.pop(0)

lines = top_comments + ["from __future__ import annotations"] + cleaned
text = "\n".join(lines) + "\n"

# 3) Fix broken Flask import block if older patch damaged it.
# This avoids regex, so it will not crash.
bad_start = "from flask import (, jsonify"
if bad_start in text:
    start = text.find(bad_start)
    end = text.find("\n)", start)
    if end != -1:
        end += 2
        good_import = (
            "from flask import (\n"
            "    Flask,\n"
            "    flash,\n"
            "    jsonify,\n"
            "    redirect,\n"
            "    render_template,\n"
            "    request,\n"
            "    send_file,\n"
            "    url_for,\n"
            ")"
        )
        text = text[:start] + good_import + text[end:]

# 4) If there are duplicate jsonify lines in a normal Flask import block, leave it alone.
# Duplicate imports do not break the app.

# 5) Add BytesIO import only if needed and missing
if "BytesIO" in text and "from io import BytesIO" not in text:
    text = text.replace(
        "from __future__ import annotations\n",
        "from __future__ import annotations\nfrom io import BytesIO\n",
        1,
    )

APP.write_text(text, encoding="utf-8")

print("DONE: app.py was fixed safely.")
print(f"Backup created: {backup.name}")
print("Now run: python app.py")
