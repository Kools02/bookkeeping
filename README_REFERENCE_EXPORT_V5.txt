TIN app Reference Export Excel patch v5

What this adds:
- Adds /reference/export route to app.py
- Adds an Export Excel button on the Reference page
- Exports the full Reference Summary database, not only the visible page

How to use:
1. Extract this ZIP.
2. Copy apply_tin_app_reference_export_excel_v5.py and RUN_REFERENCE_EXPORT_PATCH.bat into your extracted tin_app folder beside app.py.
3. Double-click RUN_REFERENCE_EXPORT_PATCH.bat, or run:
   python apply_tin_app_reference_export_excel_v5.py
4. Restart the app:
   python app.py
5. Open http://127.0.0.1:5000/reference and click Export Excel.

If openpyxl is missing, run:
python -m pip install openpyxl
