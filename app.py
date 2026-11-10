import csv
import io
import os
import sqlite3
from datetime import date, datetime
from functools import wraps

from flask import Flask, Response, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-key-before-deployment")
DB_PATH = os.environ.get("DATABASE_PATH", "expenses.db")
CATEGORIES = ["Food", "Transport", "Shopping", "Bills", "Health", "Education", "Entertainment", "Travel", "Other"]

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with db() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            kind TEXT NOT NULL CHECK(kind IN ('income','expense')),
            title TEXT NOT NULL,
            category TEXT NOT NULL,
            amount REAL NOT NULL CHECK(amount > 0),
            txn_date TEXT NOT NULL,
            notes TEXT DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS budgets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            category TEXT NOT NULL,
            month TEXT NOT NULL,
            amount REAL NOT NULL CHECK(amount > 0),
            UNIQUE(user_id, category, month),
            FOREIGN KEY(user_id) REFERENCES users(id)
        );
        """)

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper

@app.context_processor
def inject_globals():
    return {"categories": CATEGORIES, "today": date.today().isoformat()}

@app.route("/")
def index():
    return redirect(url_for("dashboard") if session.get("user_id") else url_for("login"))

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not name or not email or len(password) < 8:
            flash("Enter your name, a valid email and a password of at least 8 characters.", "error")
            return render_template("register.html")
        try:
            with db() as conn:
                conn.execute("INSERT INTO users(name,email,password_hash) VALUES(?,?,?)",
                             (name, email, generate_password_hash(password)))
            flash("Account created. Please sign in.", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("An account with that email already exists.", "error")
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        with db() as conn:
            user = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            return redirect(url_for("dashboard"))
        flash("Incorrect email or password.", "error")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/dashboard")
@login_required
def dashboard():
    month = request.args.get("month", date.today().strftime("%Y-%m"))
    uid = session["user_id"]
    with db() as conn:
        totals = conn.execute("""
            SELECT
              COALESCE(SUM(CASE WHEN kind='income' THEN amount END),0) income,
              COALESCE(SUM(CASE WHEN kind='expense' THEN amount END),0) expense
            FROM transactions WHERE user_id=? AND substr(txn_date,1,7)=?
        """, (uid, month)).fetchone()
        recent = conn.execute("SELECT * FROM transactions WHERE user_id=? ORDER BY txn_date DESC,id DESC LIMIT 8", (uid,)).fetchall()
        by_category = conn.execute("""
            SELECT category, SUM(amount) total FROM transactions
            WHERE user_id=? AND kind='expense' AND substr(txn_date,1,7)=?
            GROUP BY category ORDER BY total DESC
        """, (uid, month)).fetchall()
        budget_rows = conn.execute("SELECT category,amount FROM budgets WHERE user_id=? AND month=?", (uid, month)).fetchall()
    budgets = {r["category"]: r["amount"] for r in budget_rows}
    spent = {r["category"]: r["total"] for r in by_category}
    return render_template("dashboard.html", month=month, totals=totals, recent=recent,
                           labels=[r["category"] for r in by_category],
                           values=[r["total"] for r in by_category],
                           budgets=budgets, spent=spent)

@app.route("/transactions")
@login_required
def transactions():
    kind = request.args.get("kind", "")
    category = request.args.get("category", "")
    month = request.args.get("month", "")
    query = "SELECT * FROM transactions WHERE user_id=?"
    params = [session["user_id"]]
    if kind in ("income", "expense"):
        query += " AND kind=?"; params.append(kind)
    if category in CATEGORIES:
        query += " AND category=?"; params.append(category)
    if month:
        query += " AND substr(txn_date,1,7)=?"; params.append(month)
    query += " ORDER BY txn_date DESC,id DESC"
    with db() as conn:
        rows = conn.execute(query, params).fetchall()
    return render_template("transactions.html", rows=rows, selected_kind=kind,
                           selected_category=category, selected_month=month)

@app.route("/transaction/add", methods=["GET", "POST"])
@app.route("/transaction/<int:txn_id>/edit", methods=["GET", "POST"])
@login_required
def transaction_form(txn_id=None):
    with db() as conn:
        item = conn.execute("SELECT * FROM transactions WHERE id=? AND user_id=?",
                            (txn_id, session["user_id"])).fetchone() if txn_id else None
        if txn_id and not item:
            flash("Transaction not found.", "error")
            return redirect(url_for("transactions"))
        if request.method == "POST":
            kind = request.form.get("kind")
            title = request.form.get("title", "").strip()
            category = request.form.get("category")
            raw_amount = request.form.get("amount", "")
            txn_date = request.form.get("txn_date")
            notes = request.form.get("notes", "").strip()
            try:
                amount = float(raw_amount)
                datetime.strptime(txn_date, "%Y-%m-%d")
                if kind not in ("income", "expense") or category not in CATEGORIES or not title or amount <= 0:
                    raise ValueError()
            except (ValueError, TypeError):
                flash("Please enter valid transaction details and an amount greater than zero.", "error")
                return render_template("transaction_form.html", item=item)
            values = (kind, title, category, amount, txn_date, notes)
            if txn_id:
                conn.execute("""UPDATE transactions SET kind=?,title=?,category=?,amount=?,txn_date=?,notes=?
                                WHERE id=? AND user_id=?""", (*values, txn_id, session["user_id"]))
                flash("Transaction updated.", "success")
            else:
                conn.execute("""INSERT INTO transactions(user_id,kind,title,category,amount,txn_date,notes)
                                VALUES(?,?,?,?,?,?,?)""", (session["user_id"], *values))
                flash("Transaction added.", "success")
            return redirect(url_for("transactions"))
    return render_template("transaction_form.html", item=item)

@app.post("/transaction/<int:txn_id>/delete")
@login_required
def delete_transaction(txn_id):
    with db() as conn:
        conn.execute("DELETE FROM transactions WHERE id=? AND user_id=?", (txn_id, session["user_id"]))
    flash("Transaction deleted.", "success")
    return redirect(url_for("transactions"))

@app.route("/budgets", methods=["GET", "POST"])
@login_required
def budgets():
    month = request.values.get("month", date.today().strftime("%Y-%m"))
    if request.method == "POST":
        category = request.form.get("category")
        try:
            amount = float(request.form.get("amount", ""))
            datetime.strptime(month + "-01", "%Y-%m-%d")
            if category not in CATEGORIES or amount <= 0:
                raise ValueError()
        except ValueError:
            flash("Enter a valid category and budget amount.", "error")
            return redirect(url_for("budgets", month=month))
        with db() as conn:
            conn.execute("""INSERT INTO budgets(user_id,category,month,amount) VALUES(?,?,?,?)
                            ON CONFLICT(user_id,category,month) DO UPDATE SET amount=excluded.amount""",
                         (session["user_id"], category, month, amount))
        flash("Budget saved.", "success")
        return redirect(url_for("budgets", month=month))
    with db() as conn:
        rows = conn.execute("""
            SELECT b.category,b.amount,COALESCE(SUM(t.amount),0) spent
            FROM budgets b LEFT JOIN transactions t
              ON t.user_id=b.user_id AND t.category=b.category AND t.kind='expense'
              AND substr(t.txn_date,1,7)=b.month
            WHERE b.user_id=? AND b.month=?
            GROUP BY b.id ORDER BY b.category
        """, (session["user_id"], month)).fetchall()
    return render_template("budgets.html", month=month, rows=rows)

@app.route("/export")
@login_required
def export_csv():
    with db() as conn:
        rows = conn.execute("""SELECT kind,title,category,amount,txn_date,notes FROM transactions
                               WHERE user_id=? ORDER BY txn_date DESC""", (session["user_id"],)).fetchall()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Type", "Title", "Category", "Amount", "Date", "Notes"])
    for row in rows:
        writer.writerow(list(row))
    return Response("\ufeff" + output.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=expense-transactions.csv"})

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
