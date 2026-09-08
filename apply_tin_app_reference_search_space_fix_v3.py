from pathlib import Path
from datetime import datetime
import re
import sys

BASE = Path(__file__).resolve().parent
APP = BASE / 'app.py'
BASE_HTML = BASE / 'templates' / 'base.html'
REF_HTML = BASE / 'templates' / 'reference.html'

required = [APP, BASE_HTML, REF_HTML]
missing = [str(p.relative_to(BASE)) for p in required if not p.exists()]
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
    # Handles both correct and broken multiline imports, including: from flask import (, jsonify ... )
    m = re.search(r'^from\s+flask\s+import\s*\((.*?)^\)\s*$', app_text, flags=re.M | re.S)
    if m:
        names = clean_import_names(m.group(1))
        for n in preferred:
            if n not in names:
                names.append(n)
        ordered = [n for n in preferred if n in names] + [n for n in names if n not in preferred]
        block = 'from flask import (\n' + ''.join(f'    {n},\n' for n in ordered) + ')'
        return app_text[:m.start()] + block + app_text[m.end():]

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

def ensure_sqlalchemy_or_import(app_text):
    m = re.search(r'^from\s+sqlalchemy\s+import\s*\((.*?)^\)\s*$', app_text, flags=re.M | re.S)
    if m:
        names = clean_import_names(m.group(1))
        if 'or_' not in names:
            names.append('or_')
        block = 'from sqlalchemy import (\n' + ''.join(f'    {n},\n' for n in names) + ')'
        return app_text[:m.start()] + block + app_text[m.end():]

    m = re.search(r'^from\s+sqlalchemy\s+import\s+([^\n]+)$', app_text, flags=re.M)
    if m:
        names = clean_import_names(m.group(1))
        if 'or_' not in names:
            names.append('or_')
        return app_text[:m.start(1)] + ', '.join(names) + app_text[m.end(1):]

    return 'from sqlalchemy import or_\n' + app_text

# -------------------- app.py fixes --------------------
app_original = read(APP)
app_text = app_original
app_text = ensure_flask_import(app_text)
app_text = ensure_sqlalchemy_or_import(app_text)

api_code = r'''
@app.route("/api/reference-summary-search")
def api_reference_summary_search():
    """Search the full ReferenceEntry table for the Reference Summary page."""
    q = (request.args.get("q") or "").strip()
    limit = request.args.get("limit", 5000, type=int) or 5000
    limit = max(1, min(limit, 10000))

    query = ReferenceEntry.query
    if q:
        pattern = f"%{q}%"
        filters = []
        for field in (
            "actual_tin_receipt",
            "tin_needed_input_tax",
            "store",
            "address",
            "category",
        ):
            column = getattr(ReferenceEntry, field, None)
            if column is not None:
                filters.append(column.ilike(pattern))
        if filters:
            query = query.filter(or_(*filters))

    order_column = None
    for field in ("updated_at", "created_at", "id"):
        column = getattr(ReferenceEntry, field, None)
        if column is not None:
            order_column = column
            break
    if order_column is not None:
        query = query.order_by(order_column.desc())

    total = query.count()
    rows = query.limit(limit).all()

    def value(row, name):
        return getattr(row, name, "") or ""

    return jsonify({
        "items": [
            {
                "id": value(row, "id"),
                "actual_tin_receipt": value(row, "actual_tin_receipt"),
                "tin_needed_input_tax": value(row, "tin_needed_input_tax"),
                "category": value(row, "category"),
                "store": value(row, "store"),
                "address": value(row, "address"),
            }
            for row in rows
        ],
        "total": total,
        "limit": limit,
    })
'''.strip() + '\n\n'

# Replace previous API if it exists; otherwise insert before /periods route or before app.run.
api_pattern = re.compile(
    r'\n?@app\.route\(["\']/api/reference-summary-search["\']\)\s*\n'
    r'def\s+api_reference_summary_search\s*\([^)]*\):.*?'
    r'(?=\n@app\.route\(|\nif\s+__name__\s*==\s*["\']__main__["\']\s*:|\Z)',
    re.S,
)
if api_pattern.search(app_text):
    app_text = api_pattern.sub('\n\n' + api_code, app_text)
else:
    insert = re.search(r'\n@app\.route\(["\']/periods["\']', app_text)
    if not insert:
        insert = re.search(r'\nif\s+__name__\s*==\s*["\']__main__["\']\s*:', app_text)
    if insert:
        app_text = app_text[:insert.start()] + '\n\n' + api_code + app_text[insert.start():]
    else:
        app_text = app_text.rstrip() + '\n\n' + api_code

write_if_changed(APP, app_text, app_original)

# -------------------- base.html space typing fix --------------------
base_original = read(BASE_HTML)
base_text = base_original
space_fix = r'''
<!-- voice-input-space-fix -->
<script>
(function () {
  function isTextControl(el) {
    if (!el) return false;
    const tag = (el.tagName || '').toLowerCase();
    if (tag === 'textarea') return true;
    if (tag !== 'input') return false;
    const type = (el.type || 'text').toLowerCase();
    return ['text', 'search', 'tel', 'email', 'url', 'number', 'password'].includes(type);
  }

  function shouldRemoveAllSpaces(el) {
    const key = [el.name, el.id, el.placeholder, el.getAttribute('aria-label')]
      .filter(Boolean)
      .join(' ')
      .toLowerCase();

    return /\b(tin|tax|rdo|id|code|email|phone|mobile|contact|zip|postal|branch|account|serial|plate|or|cr)\b/.test(key)
      || el.classList.contains('no-spaces')
      || el.dataset.noSpaces === 'true';
  }

  function normalizeSpaces(value) {
    if (typeof value !== 'string') return value;
    return value
      .normalize('NFKC')
      .replace(/[\u200B-\u200D\uFEFF]/g, '')
      .replace(/[\u00A0\u1680\u2000-\u200A\u202F\u205F\u3000]/g, ' ');
  }

  function cleanWhileTyping(el) {
    if (!isTextControl(el)) return;
    const before = el.value;
    let after = normalizeSpaces(before);

    if (shouldRemoveAllSpaces(el)) {
      after = after.replace(/\s+/g, '');
    }

    if (before !== after) {
      const pos = el.selectionStart;
      el.value = after;
      try {
        if (pos !== null) el.setSelectionRange(Math.min(pos, after.length), Math.min(pos, after.length));
      } catch (e) {}
    }
  }

  function cleanBeforeSubmit(el) {
    if (!isTextControl(el)) return;
    let after = normalizeSpaces(el.value);
    if (shouldRemoveAllSpaces(el)) {
      after = after.replace(/\s+/g, '');
    } else {
      after = after.replace(/\s+/g, ' ').trim();
    }
    el.value = after;
  }

  // Allow the spacebar inside normal text boxes even if another shortcut exists.
  document.addEventListener('keydown', function (e) {
    if (e.key === ' ' && isTextControl(e.target) && !shouldRemoveAllSpaces(e.target)) {
      e.stopImmediatePropagation();
    }
  }, true);

  document.addEventListener('input', function (e) {
    cleanWhileTyping(e.target);
  }, true);

  document.addEventListener('change', function (e) {
    cleanBeforeSubmit(e.target);
  }, true);

  document.addEventListener('submit', function (e) {
    e.target.querySelectorAll('input, textarea').forEach(cleanBeforeSubmit);
  }, true);
})();
</script>
'''.strip() + '\n'

space_pattern = re.compile(r'\n?<!-- voice-input-space-fix -->\s*<script>.*?</script>\s*', re.S)
if space_pattern.search(base_text):
    base_text = space_pattern.sub(lambda m: '\n' + space_fix + '\n', base_text)
else:
    idx = base_text.lower().rfind('</body>')
    if idx != -1:
        base_text = base_text[:idx] + '\n' + space_fix + '\n' + base_text[idx:]
    else:
        base_text = base_text.rstrip() + '\n' + space_fix + '\n'

write_if_changed(BASE_HTML, base_text, base_original)

# -------------------- reference.html full search with actions + pagination --------------------
ref_original = read(REF_HTML)
ref_text = ref_original
ref_js = r'''
<!-- reference-full-search-fix -->
<script>
(function () {
  function escapeHtml(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function findReferenceTable() {
    const tables = Array.from(document.querySelectorAll('table'));
    return tables.find(function (table) {
      const text = (table.innerText || '').toLowerCase();
      return text.includes('store') && text.includes('tin');
    }) || null;
  }

  const table = findReferenceTable();
  if (!table || table.dataset.fullReferenceSearchInstalled === '1') return;
  table.dataset.fullReferenceSearchInstalled = '1';

  const tbody = table.querySelector('tbody');
  if (!tbody) return;

  const originalBody = tbody.innerHTML;
  const tableWrap = table.closest('.table-responsive') || table;
  const card = table.closest('.card') || table.parentElement || document.body;

  const serverPaginationNodes = Array.from(card.querySelectorAll('nav, .pagination'))
    .map(function (node) { return node.closest('nav') || node; })
    .filter(function (node, index, arr) { return node && arr.indexOf(node) === index; });
  const serverPaginationDisplay = serverPaginationNodes.map(function (node) {
    return [node, node.style.display || ''];
  });

  function setServerPaginationVisible(show) {
    serverPaginationDisplay.forEach(function (pair) {
      pair[0].style.display = show ? pair[1] : 'none';
    });
  }

  function headers() {
    return Array.from(table.querySelectorAll('thead th')).map(function (th) {
      return (th.innerText || '').trim().toLowerCase();
    });
  }

  const headerList = headers();
  const actionIndex = headerList.findIndex(function (h) { return h.includes('action'); });
  const firstRow = tbody.querySelector('tr');
  const firstActionCell = firstRow && actionIndex >= 0 ? firstRow.children[actionIndex] : null;
  const firstActionHtml = firstActionCell ? firstActionCell.innerHTML : '';

  function actionHtml(item) {
    if (actionIndex < 0) return '';
    const id = String(item.id == null ? '' : item.id);
    if (!id) return '';

    if (firstActionHtml.trim()) {
      // Reuse the original Edit/Delete buttons from the server-rendered table.
      // Replace numeric ids only in common edit/delete URL patterns.
      return firstActionHtml
        .replace(/(\/references?\/)(\d+)(\/(?:edit|delete))/g, '$1' + id + '$3')
        .replace(/(reference_id["']?\s*(?:value=|:)\s*["']?)(\d+)/gi, '$1' + id)
        .replace(/(data-reference-id=["'])(\d+)(["'])/gi, '$1' + id + '$3');
    }

    return '<a href="/references/' + encodeURIComponent(id) + '/edit" class="btn btn-sm btn-outline-primary me-1">Edit</a>' +
      '<form method="post" action="/references/' + encodeURIComponent(id) + '/delete" style="display:inline;" onsubmit="return confirm(\'Delete this reference row?\');">' +
      '<button type="submit" class="btn btn-sm btn-outline-danger">Delete</button></form>';
  }

  function cellValue(header, item) {
    if (header.includes('action')) return null;
    if (header.includes('store')) return item.store;
    if (header.includes('address')) return item.address;
    if (header.includes('cat') || header.includes('category')) return item.category;
    if (header.includes('input') || header.includes('needed')) return item.tin_needed_input_tax;
    if (header.includes('actual') || header.includes('receipt') || header.includes('tin')) return item.actual_tin_receipt;
    if (header === 'id' || header.includes(' id')) return item.id;
    return '';
  }

  const controls = document.createElement('div');
  controls.className = 'mb-3 reference-full-search-controls';
  controls.innerHTML = `
    <label class="form-label mb-1" for="reference_full_search">Search Reference Summary</label>
    <input type="search" id="reference_full_search" class="form-control" placeholder="Search TIN, store, address, category...">
    <div class="form-text" id="reference_full_search_status">Search checks the entire reference database, not only the current page.</div>
  `;
  tableWrap.parentNode.insertBefore(controls, tableWrap);

  const searchPager = document.createElement('div');
  searchPager.className = 'd-flex justify-content-between align-items-center mt-3 reference-search-pagination';
  searchPager.style.display = 'none';
  searchPager.innerHTML = `
    <div class="d-flex align-items-center gap-2">
      <span class="text-muted small">Rows per page</span>
      <select class="form-select form-select-sm" id="reference_search_page_size" style="width: 90px;">
        <option value="10">10</option>
        <option value="20">20</option>
        <option value="50">50</option>
        <option value="100">100</option>
      </select>
    </div>
    <div class="d-flex align-items-center gap-2">
      <button type="button" class="btn btn-sm btn-outline-secondary" id="reference_search_prev">Previous</button>
      <span class="small" id="reference_search_page_info">Page 1 of 1</span>
      <button type="button" class="btn btn-sm btn-outline-secondary" id="reference_search_next">Next</button>
    </div>
  `;
  tableWrap.parentNode.insertBefore(searchPager, tableWrap.nextSibling);

  const input = controls.querySelector('#reference_full_search');
  const status = controls.querySelector('#reference_full_search_status');
  const pageSizeSelect = searchPager.querySelector('#reference_search_page_size');
  const prevBtn = searchPager.querySelector('#reference_search_prev');
  const nextBtn = searchPager.querySelector('#reference_search_next');
  const pageInfo = searchPager.querySelector('#reference_search_page_info');

  let results = [];
  let currentPage = 1;
  let pageSize = parseInt(pageSizeSelect.value, 10) || 10;
  let timer = null;
  let lastController = null;
  let activeQuery = '';
  const colCount = Math.max(headerList.length, 1);

  function totalPages() {
    return Math.max(1, Math.ceil(results.length / pageSize));
  }

  function renderPage() {
    const pages = totalPages();
    if (currentPage > pages) currentPage = pages;
    if (currentPage < 1) currentPage = 1;

    if (!results.length) {
      tbody.innerHTML = '<tr><td colspan="' + colCount + '" class="text-center text-muted py-3">No reference records found.</td></tr>';
    } else {
      const start = (currentPage - 1) * pageSize;
      const rows = results.slice(start, start + pageSize);
      tbody.innerHTML = rows.map(function (item) {
        const cells = headerList.map(function (header) {
          if (header.includes('action')) return '<td>' + actionHtml(item) + '</td>';
          return '<td>' + escapeHtml(cellValue(header, item) || '') + '</td>';
        }).join('');
        return '<tr>' + cells + '</tr>';
      }).join('');
    }

    pageInfo.textContent = 'Page ' + currentPage + ' of ' + pages;
    prevBtn.disabled = currentPage <= 1;
    nextBtn.disabled = currentPage >= pages;
    searchPager.style.display = activeQuery ? 'flex' : 'none';
  }

  function restoreOriginal() {
    activeQuery = '';
    if (lastController) lastController.abort();
    results = [];
    currentPage = 1;
    tbody.innerHTML = originalBody;
    setServerPaginationVisible(true);
    searchPager.style.display = 'none';
    status.textContent = 'Search checks the entire reference database, not only the current page.';
  }

  async function searchAll(q) {
    if (!q) {
      restoreOriginal();
      return;
    }

    activeQuery = q;
    if (lastController) lastController.abort();
    lastController = new AbortController();
    setServerPaginationVisible(false);
    searchPager.style.display = 'flex';
    status.textContent = 'Searching full reference database...';

    try {
      const response = await fetch('/api/reference-summary-search?q=' + encodeURIComponent(q) + '&limit=5000', {
        signal: lastController.signal,
        headers: { 'Accept': 'application/json' }
      });
      if (!response.ok) throw new Error('HTTP ' + response.status);
      const data = await response.json();
      results = data.items || [];
      currentPage = 1;
      renderPage();
      const shown = results.length;
      const total = data.total || shown;
      status.textContent = 'Showing ' + shown + ' result(s)' + (total > shown ? ' out of ' + total + '. Refine your search to see fewer rows.' : '') + '.';
    } catch (err) {
      if (err.name === 'AbortError') return;
      tbody.innerHTML = '<tr><td colspan="' + colCount + '" class="text-center text-danger py-3">Search error. Please refresh and try again.</td></tr>';
      status.textContent = 'Search error. Please refresh and try again.';
    }
  }

  input.addEventListener('input', function () {
    const q = (input.value || '').trim();
    clearTimeout(timer);
    timer = setTimeout(function () { searchAll(q); }, 250);
  });

  pageSizeSelect.addEventListener('change', function () {
    pageSize = parseInt(pageSizeSelect.value, 10) || 10;
    currentPage = 1;
    renderPage();
  });

  prevBtn.addEventListener('click', function () {
    if (currentPage > 1) {
      currentPage -= 1;
      renderPage();
    }
  });

  nextBtn.addEventListener('click', function () {
    if (currentPage < totalPages()) {
      currentPage += 1;
      renderPage();
    }
  });
})();
</script>
'''.strip() + '\n'

# Remove old full search fix block(s), then insert the improved one.
ref_text = re.sub(r'\n?<!-- reference-full-search-fix -->\s*<script>.*?</script>\s*', '\n', ref_text, flags=re.S)

scripts_block = re.search(r'{%\s*block\s+scripts\s*%}', ref_text)
if scripts_block:
    end_pos = None
    for m in re.finditer(r'{%\s*endblock\s*%}', ref_text):
        if m.start() > scripts_block.end():
            end_pos = m.start()
            break
    if end_pos is not None:
        ref_text = ref_text[:end_pos] + ref_js + '\n' + ref_text[end_pos:]
    else:
        ref_text = ref_text.rstrip() + '\n' + ref_js
else:
    ref_text = ref_text.rstrip() + '\n\n{% block scripts %}\n' + ref_js + '{% endblock %}\n'

write_if_changed(REF_HTML, ref_text, ref_original)

print('\nDone. Now run: python app.py')
print('What changed:')
print('- Fixed the broken Flask import if it exists.')
print('- Store/Address keep normal spaces while typing.')
print('- Reference Summary search now keeps Actions and has its own 10/20/50/100 pagination.')
print('- Clearing the search box restores the original server-side pagination.')
