# Borrow Box

A full-stack student item sharing platform.

## Features
- Register and login
- Add items for lending
- Search and filter items
- Send borrow requests
- Approve/reject requests
- Track items you lend
- Track items you request
- SQLite database
- Responsive frontend

## Run locally
pip install -r requirements.txt
uvicorn main:app --reload

Open http://127.0.0.1:8000

## Render
Build command:
pip install -r requirements.txt

Start command:
uvicorn main:app --host 0.0.0.0 --port $PORT
