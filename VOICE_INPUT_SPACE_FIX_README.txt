How to apply this fix to tin_app

1. Extract your tin_app.rar on your computer.
2. Copy apply_voice_input_space_fix.py into the extracted tin_app folder, beside app.py.
3. Open CMD/Terminal inside that tin_app folder.
4. Run:
   python apply_voice_input_space_fix.py
5. Restart your Flask/web app.

What it fixes:
- Phone voice input sometimes inserts normal spaces, non-breaking spaces, or invisible characters.
- On typing/change/form submit, this script cleans those spaces.
- For fields named like TIN, tax, RDO, ID, code, email, phone, mobile, contact, zip, branch, account, etc., it removes all spaces.
- For normal text fields like names/addresses, it only trims and collapses repeated spaces, so names like "Juan Dela Cruz" stay readable.

If one specific field still has spaces, add class="no-spaces" or data-no-spaces="true" to that input in the template.
