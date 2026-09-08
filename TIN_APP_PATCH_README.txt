TIN app patch: space typing fix + full Reference Summary search

How to use:
1. Extract your tin_app RAR on your Windows PC.
2. Copy apply_tin_app_reference_search_space_fix.py into the extracted tin_app folder, beside app.py.
3. Open CMD or PowerShell inside that tin_app folder.
4. Run:

   python apply_tin_app_reference_search_space_fix.py

5. Restart the Flask/web app.

What it changes:
- templates/base.html
  Fixes the previous phone voice-input cleanup so Store, Address, names, and other normal text fields accept spaces while typing.
  TIN/phone/email/code-like fields still remove spaces automatically.

- app.py
  Adds /api/reference-summary-search, which searches the full ReferenceEntry database.

- templates/reference.html
  Adds a search box to the Reference Summary table. The search calls the backend API, so it filters all reference rows, not only the currently visible pagination page.

Backups:
The script creates timestamped .backup files before editing each file.
