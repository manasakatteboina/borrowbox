
import os, sqlite3, hashlib, secrets
from pathlib import Path
from fastapi import FastAPI, Form, Request, HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

BASE = Path(__file__).resolve().parent
DB = BASE / "borrow_box.db"

app = FastAPI(title="Borrow Box")
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SESSION_SECRET", "borrow-box-demo-secret-change-me")
)
app.mount("/static", StaticFiles(directory=str(BASE / "static")), name="static")

def get_db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c

def init_db():
    with get_db() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS items(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            category TEXT NOT NULL,
            description TEXT,
            owner_id INTEGER NOT NULL,
            status TEXT DEFAULT 'available',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(owner_id) REFERENCES users(id)
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS borrow_requests(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER NOT NULL,
            borrower_id INTEGER NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(item_id, borrower_id),
            FOREIGN KEY(item_id) REFERENCES items(id),
            FOREIGN KEY(borrower_id) REFERENCES users(id)
        )""")

init_db()

def hash_password(password):
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 120000).hex()
    return f"{salt}${digest}"

def verify_password(password, stored):
    try:
        salt, digest = stored.split("$", 1)
        check = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 120000).hex()
        return secrets.compare_digest(check, digest)
    except Exception:
        return False

def current_user(request):
    return request.session.get("user")

@app.get("/")
def home():
    return FileResponse(BASE / "static" / "index.html")

@app.get("/api/me")
def me(request: Request):
    return {"user": current_user(request)}

@app.post("/api/register")
def register(request: Request, username: str = Form(...), password: str = Form(...)):
    username = username.strip()
    if len(username) < 3 or len(password) < 4:
        raise HTTPException(400, "Username must be 3+ characters and password 4+ characters.")
    try:
        with get_db() as c:
            cur = c.execute(
                "INSERT INTO users(username,password) VALUES(?,?)",
                (username, hash_password(password))
            )
            user_id = cur.lastrowid
    except sqlite3.IntegrityError:
        raise HTTPException(400, "Username already exists.")
    request.session["user"] = {"id": user_id, "username": username}
    return {"success": True, "user": request.session["user"]}

@app.post("/api/login")
def login(request: Request, username: str = Form(...), password: str = Form(...)):
    with get_db() as c:
        row = c.execute("SELECT * FROM users WHERE username=?", (username.strip(),)).fetchone()
    if not row or not verify_password(password, row["password"]):
        raise HTTPException(401, "Invalid username or password.")
    request.session["user"] = {"id": row["id"], "username": row["username"]}
    return {"success": True, "user": request.session["user"]}

@app.post("/api/logout")
def logout(request: Request):
    request.session.clear()
    return {"success": True}

@app.get("/api/items")
def items(request: Request, search: str = "", category: str = "all"):
    q = """SELECT items.id, items.title, items.category, items.description,
                   items.status, items.created_at, users.username AS owner
            FROM items JOIN users ON users.id=items.owner_id
            WHERE 1=1"""
    params = []
    if search.strip():
        q += " AND (LOWER(items.title) LIKE ? OR LOWER(items.description) LIKE ?)"
        s = f"%{search.strip().lower()}%"
        params += [s, s]
    if category != "all":
        q += " AND items.category=?"
        params.append(category)
    q += " ORDER BY items.id DESC"
    with get_db() as c:
        rows = c.execute(q, params).fetchall()
    return {"items": [dict(r) for r in rows]}

@app.post("/api/items")
def add_item(request: Request, title: str = Form(...), category: str = Form(...),
             description: str = Form("")):
    user = current_user(request)
    if not user:
        raise HTTPException(401, "Please login first.")
    if not title.strip():
        raise HTTPException(400, "Item title is required.")
    with get_db() as c:
        c.execute(
            "INSERT INTO items(title,category,description,owner_id) VALUES(?,?,?,?)",
            (title.strip(), category, description.strip(), user["id"])
        )
    return {"success": True}

@app.post("/api/items/{item_id}/request")
def request_borrow(request: Request, item_id: int):
    user = current_user(request)
    if not user:
        raise HTTPException(401, "Please login first.")
    with get_db() as c:
        item = c.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone()
        if not item:
            raise HTTPException(404, "Item not found.")
        if item["owner_id"] == user["id"]:
            raise HTTPException(400, "You cannot borrow your own item.")
        if item["status"] != "available":
            raise HTTPException(400, "This item is not available.")
        try:
            c.execute(
                "INSERT INTO borrow_requests(item_id,borrower_id) VALUES(?,?)",
                (item_id, user["id"])
            )
        except sqlite3.IntegrityError:
            raise HTTPException(400, "You already requested this item.")
    return {"success": True}

@app.get("/api/my-items")
def my_items(request: Request):
    user = current_user(request)
    if not user:
        raise HTTPException(401, "Please login first.")
    with get_db() as c:
        rows = c.execute("""
            SELECT items.*, 
                   (SELECT COUNT(*) FROM borrow_requests br WHERE br.item_id=items.id AND br.status='pending') AS requests
            FROM items WHERE owner_id=? ORDER BY id DESC
        """, (user["id"],)).fetchall()
    return {"items": [dict(r) for r in rows]}

@app.get("/api/requests")
def requests_for_owner(request: Request):
    user = current_user(request)
    if not user:
        raise HTTPException(401, "Please login first.")
    with get_db() as c:
        rows = c.execute("""
            SELECT br.id, br.status, br.created_at, items.id AS item_id,
                   items.title, users.username AS borrower
            FROM borrow_requests br
            JOIN items ON items.id=br.item_id
            JOIN users ON users.id=br.borrower_id
            WHERE items.owner_id=?
            ORDER BY br.id DESC
        """, (user["id"],)).fetchall()
    return {"requests": [dict(r) for r in rows]}

@app.post("/api/requests/{request_id}/approve")
def approve_request(request: Request, request_id: int):
    user = current_user(request)
    if not user:
        raise HTTPException(401, "Please login first.")
    with get_db() as c:
        row = c.execute("""
            SELECT br.*, items.owner_id FROM borrow_requests br
            JOIN items ON items.id=br.item_id WHERE br.id=?
        """, (request_id,)).fetchone()
        if not row or row["owner_id"] != user["id"]:
            raise HTTPException(404, "Request not found.")
        c.execute("UPDATE borrow_requests SET status='approved' WHERE id=?", (request_id,))
        c.execute("UPDATE items SET status='borrowed' WHERE id=?", (row["item_id"],))
        c.execute("""
            UPDATE borrow_requests SET status='rejected'
            WHERE item_id=? AND id<>? AND status='pending'
        """, (row["item_id"], request_id))
    return {"success": True}

@app.post("/api/requests/{request_id}/reject")
def reject_request(request: Request, request_id: int):
    user = current_user(request)
    if not user:
        raise HTTPException(401, "Please login first.")
    with get_db() as c:
        row = c.execute("""
            SELECT br.*, items.owner_id FROM borrow_requests br
            JOIN items ON items.id=br.item_id WHERE br.id=?
        """, (request_id,)).fetchone()
        if not row or row["owner_id"] != user["id"]:
            raise HTTPException(404, "Request not found.")
        c.execute("UPDATE borrow_requests SET status='rejected' WHERE id=?", (request_id,))
    return {"success": True}

@app.get("/api/my-borrows")
def my_borrows(request: Request):
    user = current_user(request)
    if not user:
        raise HTTPException(401, "Please login first.")
    with get_db() as c:
        rows = c.execute("""
            SELECT br.id, br.status, br.created_at, items.title, items.category,
                   users.username AS owner
            FROM borrow_requests br
            JOIN items ON items.id=br.item_id
            JOIN users ON users.id=items.owner_id
            WHERE br.borrower_id=? ORDER BY br.id DESC
        """, (user["id"],)).fetchall()
    return {"borrows": [dict(r) for r in rows]}
