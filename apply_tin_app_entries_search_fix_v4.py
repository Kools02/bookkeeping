from pathlib import Path
from datetime import datetime
import re

BASE = Path(__file__).resolve().parent
APP = BASE / 'app.py'
TEMPLATES = BASE / 'templates'

if not APP.exists() or not TEMPLATES.exists():
    raise SystemExit(
        'Cannot find app.py or templates folder.\n'
        'Put this script inside your extracted tin_app folder, beside app.py, then run it again.'
    )

def read(path: Path) -> str:
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

# -------------------- app.py: add full-database entries search API --------------------
app_original = read(APP)
app_text = app_original
app_text = ensure_flask_import(app_text)
app_text = ensure_sqlalchemy_or_import(app_text)

entry_api_code = r'''
@app.route("/api/entries-search")
def api_entries_search():
    """Search the full Entry table for the Entries page, optionally limited by period_id."""
    q = (request.args.get("q") or "").strip()
    period_id = request.args.get("period_id", type=int)
    limit = request.args.get("limit", 5000, type=int) or 5000
    limit = max(1, min(limit, 10000))

    query = Entry.query
    if period_id:
        query = query.filter(Entry.period_id == period_id)

    if q:
        pattern = f"%{q}%"
        filters = []
        for field in (
            "category",
            "store",
            "address",
            "actual_tin_number",
            "tin_number_on_input_tax",
        ):
            column = getattr(Entry, field, None)
            if column is not None:
                filters.append(column.ilike(pattern))

        # Allow searching numbers like invoice, VAT, and cost as text when supported by DB.
        for field in ("invoice_value", "vat_12", "cost_wo_vat"):
            column = getattr(Entry, field, None)
            if column is not None:
                try:
                    filters.append(column.cast(db.String).ilike(pattern))
                except Exception:
                    pass

        if filters:
            query = query.filter(or_(*filters))

    order_column = None
    for field in ("created_at", "id"):
        column = getattr(Entry, field, None)
        if column is not None:
            order_column = column
            break
    if order_column is not None:
        query = query.order_by(order_column.desc())

    total = query.count()
    rows = query.limit(limit).all()

    def value(row, name):
        return getattr(row, name, "") or ""

    def money(row, name):
        val = getattr(row, name, None)
        if val is None:
            return ""
        try:
            return f"{float(val):,.2f}"
        except Exception:
            return str(val)

    return jsonify({
        "items": [
            {
                "id": value(row, "id"),
                "category": value(row, "category"),
                "store": value(row, "store"),
                "address": value(row, "address"),
                "actual_tin_number": value(row, "actual_tin_number"),
                "tin_number_on_input_tax": value(row, "tin_number_on_input_tax"),
                "invoice_value": money(row, "invoice_value"),
                "vat_12": money(row, "vat_12"),
                "cost_wo_vat": money(row, "cost_wo_vat"),
                "period_id": value(row, "period_id"),
            }
            for row in rows
        ],
        "total": total,
        "limit": limit,
    })
'''.strip() + '\n\n'

api_pattern = re.compile(
    r'\n?@app\.route\(["\']/api/entries-search["\']\)\s*\n'
    r'def\s+api_entries_search\s*\([^)]*\):.*?'
    r'(?=\n@app\.route\(|\nif\s+__name__\s*==\s*["\']__main__["\']\s*:|\Z)',
    re.S,
)
if api_pattern.search(app_text):
    app_text = api_pattern.sub('\n\n' + entry_api_code, app_text)
else:
    # Insert near other API/search routes if possible, otherwise before periods or app.run.
    insert = re.search(r'\n@app\.route\(["\']/api/reference-summary-search["\']', app_text)
    if insert:
        # Put entries API before reference API.
        app_text = app_text[:insert.start()] + '\n\n' + entry_api_code + app_text[insert.start():]
    else:
        insert = re.search(r'\n@app\.route\(["\']/periods["\']', app_text)
        if not insert:
            insert = re.search(r'\nif\s+__name__\s*==\s*["\']__main__["\']\s*:', app_text)
        if insert:
            app_text = app_text[:insert.start()] + '\n\n' + entry_api_code + app_text[insert.start():]
        else:
            app_text = app_text.rstrip() + '\n\n' + entry_api_code

write_if_changed(APP, app_text, app_original)

# -------------------- Find entries template --------------------
def looks_like_entries_template(path: Path, text: str) -> int:
    low = text.lower()
    score = 0
    for term in ['entries', 'new entry', 'export excel', 'invoice', 'vat', 'tin input tax', 'actual tin']:
        if term in low:
            score += 1
    if '<table' in low and 'actions' in low and 'store' in low:
        score += 3
    if 'reference summary' in low or 'upload reference' in low or 'single reference entry' in low:
        score -= 4
    return score

candidates = []
for path in TEMPLATES.glob('*.html'):
    try:
        text = read(path)
    except Exception:
        continue
    score = looks_like_entries_template(path, text)
    if score >= 4:
        candidates.append((score, path, text))

if not candidates:
    raise SystemExit(
        '\nCould not find the Entries template automatically.\n'
        'Please check your templates folder and tell me the filename for the Entries page, for example entries.html.\n'
        'app.py was still updated with the entries search API.'
    )

candidates.sort(reverse=True, key=lambda x: x[0])
ENTRIES_HTML = candidates[0][1]
entries_original = candidates[0][2]
entries_text = entries_original

entry_js = r'''
<!-- entries-full-search-fix -->
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

  function findEntriesTable() {
    const tables = Array.from(document.querySelectorAll('table'));
    return tables.find(function (table) {
      const text = (table.innerText || '').toLowerCase();
      return text.includes('invoice') && text.includes('vat') && text.includes('actual tin') && text.includes('actions');
    }) || null;
  }

  const table = findEntriesTable();
  if (!table || table.dataset.fullEntriesSearchInstalled === '1') return;
  table.dataset.fullEntriesSearchInstalled = '1';

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
      // Reuse the real Edit/Delete buttons from your existing table and replace only the row id.
      return firstActionHtml
        .replace(/(\/entries?\/)(\d+)(\/(?:edit|delete))/g, '$1' + id + '$3')
        .replace(/(\/entry\/)(\d+)(\/(?:edit|delete))/g, '$1' + id + '$3')
        .replace(/(entry_id["']?\s*(?:value=|:)\s*["']?)(\d+)/gi, '$1' + id)
        .replace(/(data-entry-id=["'])(\d+)(["'])/gi, '$1' + id + '$3');
    }

    return '<a href="/entries/' + encodeURIComponent(id) + '/edit" class="btn btn-sm btn-outline-primary me-1">Edit</a>' +
      '<form method="post" action="/entries/' + encodeURIComponent(id) + '/delete" style="display:inline;" onsubmit="return confirm(\'Delete this entry?\');">' +
      '<button type="submit" class="btn btn-sm btn-outline-danger">Delete</button></form>';
  }

  function cellValue(header, item) {
    if (header.includes('action')) return null;
    if (header === 'cat' || header.includes('category')) return item.category;
    if (header.includes('store')) return item.store;
    if (header.includes('address')) return item.address;
    if (header.includes('actual')) return item.actual_tin_number;
    if (header.includes('input') || header.includes('needed')) return item.tin_number_on_input_tax;
    if (header.includes('invoice')) return item.invoice_value;
    if (header === 'vat' || header.includes('vat')) return item.vat_12;
    if (header.includes('cost')) return item.cost_wo_vat;
    return '';
  }

  function currentPeriodId() {
    // Prefer the visible period dropdown on the Entries page.
    const byName = document.querySelector('select[name="period_id"]');
    if (byName && byName.value) return byName.value;

    // Fallback: read period_id from the URL, if present.
    try {
      const params = new URLSearchParams(window.location.search);
      return params.get('period_id') || '';
    } catch (e) {
      return '';
    }
  }

  const controls = document.createElement('div');
  controls.className = 'mb-3 entries-full-search-controls';
  controls.innerHTML = `
    <label class="form-label mb-1" for="entries_full_search">Search Entries</label>
    <input type="search" id="entries_full_search" class="form-control" placeholder="Search CAT, store, address, TIN, invoice, VAT...">
    <div class="form-text" id="entries_full_search_status">Search checks all entries for the selected month, not only the current page.</div>
  `;
  tableWrap.parentNode.insertBefore(controls, tableWrap);

  const searchPager = document.createElement('div');
  searchPager.className = 'd-flex justify-content-between align-items-center mt-3 entries-search-pagination';
  searchPager.style.display = 'none';
  searchPager.innerHTML = `
    <div class="d-flex align-items-center gap-2">
      <span class="text-muted small">Rows per page</span>
      <select class="form-select form-select-sm" id="entries_search_page_size" style="width: 90px;">
        <option value="10">10</option>
        <option value="20">20</option>
        <option value="50">50</option>
        <option value="100">100</option>
      </select>
    </div>
    <div class="d-flex align-items-center gap-2">
      <button type="button" class="btn btn-sm btn-outline-secondary" id="entries_search_prev">Previous</button>
      <span class="small" id="entries_search_page_info">Page 1 of 1</span>
      <button type="button" class="btn btn-sm btn-outline-secondary" id="entries_search_next">Next</button>
    </div>
  `;
  tableWrap.parentNode.insertBefore(searchPager, tableWrap.nextSibling);

  const input = controls.querySelector('#entries_full_search');
  const status = controls.querySelector('#entries_full_search_status');
  const pageSizeSelect = searchPager.querySelector('#entries_search_page_size');
  const prevBtn = searchPager.querySelector('#entries_search_prev');
  const nextBtn = searchPager.querySelector('#entries_search_next');
  const pageInfo = searchPager.querySelector('#entries_search_page_info');

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
      tbody.innerHTML = '<tr><td colspan="' + colCount + '" class="text-center text-muted py-3">No entries found.</td></tr>';
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
    status.textContent = 'Search checks all entries for the selected month, not only the current page.';
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
    status.textContent = 'Searching all entries for the selected month...';

    const periodId = currentPeriodId();
    let url = '/api/entries-search?q=' + encodeURIComponent(q) + '&limit=5000';
    if (periodId) url += '&period_id=' + encodeURIComponent(periodId);

    try {
      const response = await fetch(url, {
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

# Remove old entries search block, then inject the improved one.
entries_text = re.sub(r'\n?<!-- entries-full-search-fix -->\s*<script>.*?</script>\s*', '\n', entries_text, flags=re.S)

scripts_block = re.search(r'{%\s*block\s+scripts\s*%}', entries_text)
if scripts_block:
    end_pos = None
    for m in re.finditer(r'{%\s*endblock\s*%}', entries_text):
        if m.start() > scripts_block.end():
            end_pos = m.start()
            break
    if end_pos is not None:
        entries_text = entries_text[:end_pos] + entry_js + '\n' + entries_text[end_pos:]
    else:
        entries_text = entries_text.rstrip() + '\n' + entry_js
else:
    entries_text = entries_text.rstrip() + '\n\n{% block scripts %}\n' + entry_js + '{% endblock %}\n'

write_if_changed(ENTRIES_HTML, entries_text, entries_original)

print('\nDone. Now run: python app.py')
print('What changed:')
print('- Added full-database search API for Entries: /api/entries-search')
print('- Added Entries search box above the Entries table.')
print('- Search filters all rows for the selected month, not only the current page.')
print('- Search results keep the Actions column and include 10/20/50/100 pagination.')
print('- Clearing the search box restores the original table and server pagination.')
