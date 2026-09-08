from pathlib import Path
from datetime import datetime
import re

BASE = Path(__file__).resolve().parent
APP = BASE / 'app.py'
REF_HTML = BASE / 'templates' / 'reference.html'

missing = [str(p.relative_to(BASE)) for p in [APP, REF_HTML] if not p.exists()]
if missing:
    raise SystemExit(
        'Cannot find required files: ' + ', '.join(missing) + '\n'
        'Put this script inside your extracted tin_app folder, beside app.py, then run it again.'
    )

def read(path):
    return path.read_text(encoding='utf-8')

def backup(path: Path):
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    b = path.with_name(path.name + '.backup-' + stamp)
    b.write_text(read(path), encoding='utf-8')
    return b

def write_if_changed(path: Path, new_text: str, old_text: str):
    if new_text != old_text:
        b = backup(path)
        path.write_text(new_text, encoding='utf-8')
        print(f'Updated {path.relative_to(BASE)}  (backup: {b.name})')
    else:
        print(f'No change needed for {path.relative_to(BASE)}')

def clean_import_names(text):
    names = []
    for name in re.findall(r'\b[A-Za-z_]\w*\b', text):
        if name not in {'from', 'import'} and name not in names:
            names.append(name)
    return names

def ensure_flask_import(app_text):
    preferred = ['Flask', 'flash', 'jsonify', 'redirect', 'render_template', 'request', 'send_file', 'url_for']

    # Fix correct or broken multiline Flask imports.
    m = re.search(r'^from\s+flask\s+import\s*\((.*?)^\)\s*$', app_text, flags=re.M | re.S)
    if m:
        names = clean_import_names(m.group(1))
        for n in preferred:
            if n not in names:
                names.append(n)
        ordered = [n for n in preferred if n in names] + [n for n in names if n not in preferred]
        block = 'from flask import (\n' + ''.join(f'    {n},\n' for n in ordered) + ')'
        return app_text[:m.start()] + block + app_text[m.end():]

    # Fix single-line Flask import.
    m = re.search(r'^from\s+flask\s+import\s+([^\n]+)$', app_text, flags=re.M)
    if m:
        names = clean_import_names(m.group(1))
        for n in preferred:
            if n not in names:
                names.append(n)
        ordered = [n for n in preferred if n in names] + [n for n in names if n not in preferred]
        block = 'from flask import (\n' + ''.join(f'    {n},\n' for n in ordered) + ')'
        return app_text[:m.start()] + block + app_text[m.end():]

    block = 'from flask import (\n' + ''.join(f'    {n},\n' for n in preferred) + ')\n'
    return block + app_text

def ensure_from_import(app_text, module, name):
    # Handles: from module import name1, name2
    pattern = re.compile(rf'^from\s+{re.escape(module)}\s+import\s+([^\n]+)$', re.M)
    m = pattern.search(app_text)
    if m:
        names = [x.strip() for x in m.group(1).split(',') if x.strip()]
        if name not in names:
            names.append(name)
            app_text = app_text[:m.start(1)] + ', '.join(names) + app_text[m.end(1):]
        return app_text
    return f'from {module} import {name}\n' + app_text

# ---------------- app.py: add Excel export route ----------------
app_original = read(APP)
app_text = app_original
app_text = ensure_flask_import(app_text)
app_text = ensure_from_import(app_text, 'io', 'BytesIO')
app_text = ensure_from_import(app_text, 'openpyxl', 'Workbook')

export_code = r'''
@app.route("/reference/export")
def export_references_excel():
    """Export the full Reference Summary database to Excel."""
    references = ReferenceEntry.query.order_by(ReferenceEntry.id.asc()).all()

    wb = Workbook()
    ws = wb.active
    ws.title = "Reference Summary"

    headers = [
        "Actual TIN Number on Receipt",
        "TIN Number Needed on Input Tax",
        "CAT",
        "Store",
        "Address",
    ]
    ws.append(headers)

    for ref in references:
        ws.append([
            getattr(ref, "actual_tin_receipt", "") or "",
            getattr(ref, "tin_needed_input_tax", "") or "",
            getattr(ref, "category", "") or "",
            getattr(ref, "store", "") or "",
            getattr(ref, "address", "") or "",
        ])

    for column_cells in ws.columns:
        column_letter = column_cells[0].column_letter
        max_length = 0
        for cell in column_cells:
            value = str(cell.value) if cell.value is not None else ""
            max_length = max(max_length, len(value))
        ws.column_dimensions[column_letter].width = min(max_length + 3, 70)

    output = BytesIO()
    wb.save(output)
    output.seek(0)

    return send_file(
        output,
        as_attachment=True,
        download_name="reference_summary.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
'''.strip() + '\n\n'

route_pattern = re.compile(
    r'\n?@app\.route\(["\']/reference/export["\']\)\s*\n'
    r'def\s+export_references_excel\s*\([^)]*\):.*?'
    r'(?=\n@app\.route\(|\nif\s+__name__\s*==\s*["\']__main__["\']\s*:|\Z)',
    re.S,
)
if route_pattern.search(app_text):
    app_text = route_pattern.sub('\n\n' + export_code, app_text)
else:
    insert = re.search(r'\nif\s+__name__\s*==\s*["\']__main__["\']\s*:', app_text)
    if insert:
        app_text = app_text[:insert.start()] + '\n\n' + export_code + app_text[insert.start():]
    else:
        app_text = app_text.rstrip() + '\n\n' + export_code

write_if_changed(APP, app_text, app_original)

# ---------------- reference.html: add Export Excel button ----------------
ref_original = read(REF_HTML)
ref_text = ref_original

export_js = r'''
<!-- reference-export-excel-fix -->
<script>
(function () {
  function findReferenceTable() {
    const tables = Array.from(document.querySelectorAll('table'));
    return tables.find(function (table) {
      const text = (table.innerText || '').toLowerCase();
      return text.includes('tin') && text.includes('store');
    }) || null;
  }

  const table = findReferenceTable();
  if (!table) return;

  const card = table.closest('.card') || table.parentElement || document.body;
  if (card.querySelector('[data-reference-export-excel="true"]')) return;

  const tableWrap = table.closest('.table-responsive') || table;
  const wrap = document.createElement('div');
  wrap.className = 'd-flex justify-content-end align-items-center mb-3 gap-2';
  wrap.setAttribute('data-reference-export-excel', 'true');
  wrap.innerHTML = '<a href="/reference/export" class="btn btn-success">Export Excel</a>';

  // Put the button before the table, after any search controls if they already exist.
  const searchControls = card.querySelector('.reference-full-search-controls');
  if (searchControls && searchControls.parentNode) {
    searchControls.parentNode.insertBefore(wrap, searchControls.nextSibling);
  } else if (tableWrap && tableWrap.parentNode) {
    tableWrap.parentNode.insertBefore(wrap, tableWrap);
  } else {
    card.insertBefore(wrap, card.firstChild);
  }
})();
</script>
'''.strip() + '\n'

ref_text = re.sub(r'\n?<!-- reference-export-excel-fix -->\s*<script>.*?</script>\s*', '\n', ref_text, flags=re.S)

scripts_block = re.search(r'{%\s*block\s+scripts\s*%}', ref_text)
if scripts_block:
    end_pos = None
    for m in re.finditer(r'{%\s*endblock\s*%}', ref_text):
        if m.start() > scripts_block.end():
            end_pos = m.start()
            break
    if end_pos is not None:
        ref_text = ref_text[:end_pos] + export_js + '\n' + ref_text[end_pos:]
    else:
        ref_text = ref_text.rstrip() + '\n' + export_js
else:
    ref_text = ref_text.rstrip() + '\n\n{% block scripts %}\n' + export_js + '{% endblock %}\n'

write_if_changed(REF_HTML, ref_text, ref_original)

print('\nDone.')
print('Restart the app: python app.py')
print('Then open http://127.0.0.1:5000/reference and click Export Excel.')
