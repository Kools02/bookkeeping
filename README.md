# TIN Input App

A mobile-friendly Python web app for encoding monthly receipt data using a reference Excel file.

## What it does

- Upload a reference Excel file with a `REFERENCE` sheet.
- Look up by **Actual TIN Number**.
- Auto-fill:
  - CAT
  - STORE
  - ADDRESS
  - TIN NUMBER ON INPUT TAX
- Auto-compute:
  - 12% VAT = `invoice / 1.12 * 12%`
  - COST W/O VAT = `invoice - VAT`
- Manage dynamic monthly periods like `Mar'26`, `Apr'26`, etc.
- Allow multiple users to encode at the same time in a browser.
- Works on desktop and mobile browsers.
- Export each month back to Excel.

## Reference file format

The uploaded file must contain a sheet named `REFERENCE` with these columns:

- `ACTUAL TIN NUMBER ON RECEIPT`
- `TIN NUMBER NEEDED ON INPUT TAX`
- `STORE`
- `ADDRESS`
- `CAT`

## Quick start

### 1) Create a virtual environment

Windows:

```powershell
python -m venv .venv
.\.venv\Scripts\activate
```

Linux/macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2) Install dependencies

```bash
pip install -r requirements.txt
```

### 3) Run the app

```bash
python app.py
```

Open:

```text
http://127.0.0.1:5000
```

## Use on phones or other PCs on the same network

Run the app, then open this from another device on your network:

```text
http://YOUR-PC-IP:5000
```

The app already listens on `0.0.0.0`, so other devices can connect if your firewall allows port `5000`.

## Production suggestion

For real office use with several users, use:

- `gunicorn` on Linux
- `DATABASE_URL` pointing to PostgreSQL or MySQL
- a reverse proxy like Nginx
- HTTPS
- user login if needed

Example:

```bash
set DATABASE_URL=postgresql://user:password@localhost/tin_app
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

## Notes

- Small teams can start with SQLite.
- For heavier simultaneous use, switch to PostgreSQL.
- TIN matching uses a normalized form, so minor formatting differences like hyphens are handled better.
