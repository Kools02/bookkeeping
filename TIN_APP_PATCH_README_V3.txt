TIN App Patch v3

How to use:
1. Extract your tin_app RAR on your Windows PC.
2. Copy apply_tin_app_reference_search_space_fix_v3.py into the extracted tin_app folder, beside app.py.
3. Open PowerShell in the tin_app folder.
4. Run:
   python apply_tin_app_reference_search_space_fix_v3.py
5. Run:
   python app.py

This patch fixes:
- Broken Flask import caused by the earlier patch.
- Store/Address spaces while typing.
- Reference Summary full database search.
- Actions column disappearing during search.
- Pagination disappearing during search by adding search-result pagination.

Backups are created automatically before files are modified.
