TIN App Patch v4 - Entries Search

How to use:
1. Extract your tin_app RAR on your computer.
2. Copy apply_tin_app_entries_search_fix_v4.py into the extracted tin_app folder, beside app.py.
3. Open PowerShell/CMD inside that tin_app folder.
4. Run:
   python apply_tin_app_entries_search_fix_v4.py
5. Start the app again:
   python app.py

This patch adds a search/filter box to the Entries page.
The filter searches the full Entry database for the selected month, not only the current pagination page.
It also keeps the Edit/Delete Actions column and gives search results their own 10/20/50/100 pagination.

The script creates timestamped backup files before editing anything.
