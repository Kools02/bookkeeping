# Bookkeeping V2 upgrade

This package contains a first-pass professional UI refresh plus targeted safety/validation fixes for `Kools02/bookkeeping`.

## Included

- Reworked `templates/base.html` with professional navigation, active-month indicator, consistent typography, icons, alerts, and footer.
- New `static/app.css` design system.
- Reworked dashboard (`templates/index.html`).
- Reworked receipt form (`templates/entry_form.html`) with live match status.
- `.gitignore` to stop committing the SQLite database, uploads, exports, Python caches, and backup files.
- `app.py.patch` for:
  - mandatory `SECRET_KEY`
  - safer session cookie defaults
  - production-safe debug behavior
  - rejection of NaN/infinite/negative invoice values
  - fixing the legacy Excel header typo (`aaaa`)
- Basic tests for TIN/category normalization and VAT calculation.

## Apply

From the repository root:

1. Copy the `templates/` and `static/` files over the existing files.
2. Copy `.gitignore` to the repository root.
3. Apply `app.py.patch` with Git:
   `git apply app.py.patch`
4. Install test dependency if needed:
   `pip install pytest`
5. Set a real secret before starting:
   - Windows PowerShell: `$env:SECRET_KEY="a-long-random-secret"`
   - Linux/macOS: `export SECRET_KEY="a-long-random-secret"`
6. Run tests:
   `pytest -q`
7. Start the app:
   `python app.py`

## Important cleanup

The current public repository contains `tin_app.db`, `__pycache__`, multiple `*.backup-*` files, and patch/fix scripts. Those are development artifacts and should not remain in the production repository. The `.gitignore` prevents new copies, but already-tracked files need to be removed with Git.

Do **not** delete your existing database blindly if it contains data. Back it up first.

## Next pass

The next worthwhile step is to split `app.py` into blueprints/services, add CSRF protection and proper production configuration, improve reference import reporting, and add automated integration tests for every receipt workflow.
