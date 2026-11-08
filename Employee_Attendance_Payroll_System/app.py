import os
import sqlite3
from datetime import date
from functools import wraps

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, session, redirect, url_for
from werkzeug.security import check_password_hash, generate_password_hash

load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-only-change-me")

DB_PATH = os.path.join(os.path.dirname(__file__), "employee_payroll.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def query(sql, params=(), one=False, commit=False):
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute(sql, params)
        if commit:
            conn.commit()
            return None
        result = cur.fetchone() if one else cur.fetchall()
        if one:
            return dict(result) if result else None
        return [dict(r) for r in result]
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def init_db():
    """Create all tables and seed the default admin user if not present."""
    conn = get_db()
    cur = conn.cursor()
    cur.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'employee' CHECK(role IN ('admin','employee')),
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_code TEXT NOT NULL UNIQUE,
            full_name TEXT NOT NULL,
            email TEXT UNIQUE,
            department TEXT NOT NULL,
            designation TEXT NOT NULL,
            joining_date TEXT NOT NULL,
            basic_salary REAL NOT NULL DEFAULT 0,
            allowances REAL NOT NULL DEFAULT 0,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL,
            attendance_date TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('Present','Absent','Half-day','Leave')),
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            UNIQUE(employee_id, attendance_date),
            FOREIGN KEY(employee_id) REFERENCES employees(id)
        );

        CREATE TABLE IF NOT EXISTS leave_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL,
            from_date TEXT NOT NULL,
            to_date TEXT NOT NULL,
            reason TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Pending' CHECK(status IN ('Pending','Approved','Rejected')),
            reviewed_by INTEGER,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY(employee_id) REFERENCES employees(id),
            FOREIGN KEY(reviewed_by) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS payroll (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL,
            payroll_month TEXT NOT NULL,
            basic_salary REAL NOT NULL,
            allowances REAL NOT NULL DEFAULT 0,
            deductions REAL NOT NULL DEFAULT 0,
            overtime_pay REAL NOT NULL DEFAULT 0,
            present_days REAL NOT NULL DEFAULT 0,
            absent_days REAL NOT NULL DEFAULT 0,
            half_days REAL NOT NULL DEFAULT 0,
            leave_days REAL NOT NULL DEFAULT 0,
            net_salary REAL NOT NULL DEFAULT 0,
            generated_at TEXT DEFAULT (datetime('now')),
            UNIQUE(employee_id, payroll_month),
            FOREIGN KEY(employee_id) REFERENCES employees(id)
        );

        CREATE INDEX IF NOT EXISTS idx_attendance_date ON attendance(attendance_date);
        CREATE INDEX IF NOT EXISTS idx_payroll_month ON payroll(payroll_month);
    """)
    conn.commit()

    existing = cur.execute("SELECT id FROM users WHERE username='admin'").fetchone()
    if not existing:
        pw_hash = generate_password_hash("admin123")
        cur.execute(
            "INSERT INTO users(username, password_hash, role) VALUES(?,?,?)",
            ("admin", pw_hash, "admin")
        )
        conn.commit()
        print("✓ Default admin created: admin / admin123")

    conn.close()


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def api_login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            return jsonify({"error": "Please log in"}), 401
        return fn(*args, **kwargs)
    return wrapper


def roles_required(*roles):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not session.get("user_id"):
                return jsonify({"error": "Please log in"}), 401
            if session.get("role") not in roles:
                return jsonify({"error": "You do not have permission"}), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator


# ---------------------------------------------------------------------------
# Page routes
# ---------------------------------------------------------------------------

@app.route("/")
def home():
    return render_template("login.html") if not session.get("user_id") else redirect(url_for("dashboard_page"))


@app.route("/dashboard")
def dashboard_page():
    if not session.get("user_id"):
        return redirect(url_for("home"))
    return render_template("dashboard.html", username=session.get("username"), role=session.get("role"))


@app.route("/employees")
def employees_page():
    if not session.get("user_id"): return redirect(url_for("home"))
    return render_template("employees.html")


@app.route("/attendance")
def attendance_page():
    if not session.get("user_id"): return redirect(url_for("home"))
    return render_template("attendance.html")


@app.route("/leaves")
def leaves_page():
    if not session.get("user_id"): return redirect(url_for("home"))
    return render_template("leaves.html")


@app.route("/payroll")
def payroll_page():
    if not session.get("user_id"): return redirect(url_for("home"))
    return render_template("payroll.html")


@app.route("/reports")
def reports_page():
    if not session.get("user_id"): return redirect(url_for("home"))
    return render_template("reports.html")


# ---------------------------------------------------------------------------
# Auth API
# ---------------------------------------------------------------------------

@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or request.form
    username = data.get("username", "").strip()
    password = data.get("password", "")
    user = query(
        "SELECT id, username, password_hash, role FROM users WHERE username=? AND is_active=1",
        (username,), one=True
    )
    if not user or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "Invalid username or password"}), 401
    session.clear()
    session.update(user_id=user["id"], username=user["username"], role=user["role"])
    return jsonify({"message": "Login successful", "role": user["role"]})


@app.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"message": "Logged out"})


@app.route("/api/me", methods=["GET"])
@api_login_required
def me():
    return jsonify({"username": session["username"], "role": session["role"]})


# ---------------------------------------------------------------------------
# Dashboard API
# ---------------------------------------------------------------------------

@app.route("/api/dashboard", methods=["GET"])
@api_login_required
def dashboard():
    total = query("SELECT COUNT(*) AS n FROM employees WHERE is_active=1", one=True)["n"]
    today = date.today().isoformat()
    present = query(
        "SELECT COUNT(*) AS n FROM attendance WHERE attendance_date=? AND status IN ('Present','Half-day')",
        (today,), one=True
    )["n"]
    absent = query(
        "SELECT COUNT(*) AS n FROM attendance WHERE attendance_date=? AND status='Absent'",
        (today,), one=True
    )["n"]
    month = date.today().strftime("%Y-%m")
    payroll = query(
        "SELECT COALESCE(SUM(net_salary),0) AS total FROM payroll WHERE payroll_month=?",
        (month,), one=True
    )["total"]
    return jsonify({
        "total_employees": total,
        "present_today": present,
        "absent_today": absent,
        "monthly_payroll": float(payroll or 0)
    })


# ---------------------------------------------------------------------------
# Employees API
# ---------------------------------------------------------------------------

@app.route("/api/employees", methods=["GET"])
@api_login_required
def list_employees():
    rows = query(
        "SELECT id, employee_code, full_name, email, department, designation, "
        "joining_date, basic_salary, allowances, is_active FROM employees ORDER BY id DESC"
    )
    for r in rows:
        r["basic_salary"] = float(r["basic_salary"] or 0)
        r["allowances"] = float(r["allowances"] or 0)
    return jsonify(rows)


@app.route("/api/employees", methods=["POST"])
@roles_required("admin")
def add_employee():
    d = request.get_json() or {}
    required = ["employee_code", "full_name", "department", "designation", "joining_date", "basic_salary"]
    if any(not str(d.get(k, "")).strip() for k in required):
        return jsonify({"error": "Please fill all required fields"}), 400
    try:
        query(
            "INSERT INTO employees(employee_code,full_name,email,department,designation,"
            "joining_date,basic_salary,allowances) VALUES(?,?,?,?,?,?,?,?)",
            (d["employee_code"], d["full_name"], d.get("email"), d["department"],
             d["designation"], d["joining_date"], d["basic_salary"], d.get("allowances", 0)),
            commit=True
        )
        return jsonify({"message": "Employee added"}), 201
    except sqlite3.IntegrityError:
        return jsonify({"error": "Employee code or email already exists"}), 409


@app.route("/api/employees/<int:emp_id>", methods=["PUT"])
@roles_required("admin")
def update_employee(emp_id):
    d = request.get_json() or {}
    try:
        query(
            "UPDATE employees SET full_name=?,email=?,department=?,designation=?,"
            "joining_date=?,basic_salary=?,allowances=? WHERE id=?",
            (d["full_name"], d.get("email"), d["department"], d["designation"],
             d["joining_date"], d["basic_salary"], d.get("allowances", 0), emp_id),
            commit=True
        )
        return jsonify({"message": "Employee updated"})
    except (KeyError, sqlite3.Error):
        return jsonify({"error": "Could not update employee. Check the submitted details."}), 400


@app.route("/api/employees/<int:emp_id>/deactivate", methods=["PATCH"])
@roles_required("admin")
def deactivate_employee(emp_id):
    query("UPDATE employees SET is_active=0 WHERE id=?", (emp_id,), commit=True)
    return jsonify({"message": "Employee deactivated"})


# ---------------------------------------------------------------------------
# Attendance API
# ---------------------------------------------------------------------------

@app.route("/api/attendance", methods=["POST"])
@roles_required("admin")
def mark_attendance():
    d = request.get_json() or {}
    if d.get("status") not in ("Present", "Absent", "Half-day", "Leave"):
        return jsonify({"error": "Invalid attendance status"}), 400
    query(
        "INSERT INTO attendance(employee_id,attendance_date,status,notes) VALUES(?,?,?,?) "
        "ON CONFLICT(employee_id,attendance_date) DO UPDATE SET status=excluded.status, notes=excluded.notes",
        (d.get("employee_id"), d.get("attendance_date"), d["status"], d.get("notes")),
        commit=True
    )
    return jsonify({"message": "Attendance saved"}), 201


@app.route("/api/attendance", methods=["GET"])
@api_login_required
def attendance_report():
    month = request.args.get("month", date.today().strftime("%Y-%m"))
    rows = query(
        "SELECT a.id, e.employee_code, e.full_name, a.attendance_date, a.status, a.notes "
        "FROM attendance a JOIN employees e ON e.id=a.employee_id "
        "WHERE strftime('%Y-%m', a.attendance_date)=? ORDER BY a.attendance_date DESC, e.full_name",
        (month,)
    )
    return jsonify(rows)


# ---------------------------------------------------------------------------
# Leave API
# ---------------------------------------------------------------------------

@app.route("/api/leaves", methods=["POST"])
@api_login_required
def apply_leave():
    d = request.get_json() or {}
    if not all(d.get(k) for k in ("employee_id", "from_date", "to_date", "reason")):
        return jsonify({"error": "Please complete all leave fields"}), 400
    query(
        "INSERT INTO leave_requests(employee_id,from_date,to_date,reason) VALUES(?,?,?,?)",
        (d["employee_id"], d["from_date"], d["to_date"], d["reason"]),
        commit=True
    )
    return jsonify({"message": "Leave request submitted"}), 201


@app.route("/api/leaves", methods=["GET"])
@api_login_required
def list_leaves():
    rows = query(
        "SELECT l.id, e.full_name, l.from_date, l.to_date, l.reason, l.status, l.created_at "
        "FROM leave_requests l JOIN employees e ON e.id=l.employee_id ORDER BY l.id DESC"
    )
    return jsonify(rows)


@app.route("/api/leaves/<int:leave_id>", methods=["PATCH"])
@roles_required("admin")
def decide_leave(leave_id):
    status = (request.get_json() or {}).get("status")
    if status not in ("Approved", "Rejected"):
        return jsonify({"error": "Choose Approved or Rejected"}), 400
    query(
        "UPDATE leave_requests SET status=?, reviewed_by=? WHERE id=?",
        (status, session["user_id"], leave_id),
        commit=True
    )
    return jsonify({"message": "Leave {}".format(status.lower())})


# ---------------------------------------------------------------------------
# Payroll API
# ---------------------------------------------------------------------------

@app.route("/api/payroll/run", methods=["POST"])
@roles_required("admin")
def run_payroll():
    d = request.get_json() or {}
    month = d.get("month")
    if not month:
        return jsonify({"error": "Select a payroll month"}), 400
    employees = query("SELECT id, basic_salary, allowances FROM employees WHERE is_active=1")
    created = 0
    for e in employees:
        attendance = query(
            """SELECT
                SUM(CASE WHEN status='Present' THEN 1 ELSE 0 END) AS present_days,
                SUM(CASE WHEN status='Half-day' THEN 1 ELSE 0 END) AS half_days,
                SUM(CASE WHEN status='Absent' THEN 1 ELSE 0 END) AS absent_days,
                SUM(CASE WHEN status='Leave' THEN 1 ELSE 0 END) AS leave_days
            FROM attendance WHERE employee_id=? AND strftime('%Y-%m', attendance_date)=?""",
            (e["id"], month), one=True
        )
        present = int(attendance["present_days"] or 0)
        half = int(attendance["half_days"] or 0)
        absent = int(attendance["absent_days"] or 0)
        leave = int(attendance["leave_days"] or 0)
        days_in_month = 30
        paid_days = min(days_in_month, present + half * 0.5 + leave)
        basic = float(e["basic_salary"])
        allowance = float(e["allowances"] or 0)
        gross = (basic + allowance) * (paid_days / days_in_month)
        deduction = (basic + allowance) - gross
        net = gross
        query(
            """INSERT INTO payroll(employee_id,payroll_month,basic_salary,allowances,deductions,overtime_pay,
            present_days,absent_days,half_days,leave_days,net_salary)
            VALUES(?,?,?,?,?,0,?,?,?,?,?)
            ON CONFLICT(employee_id,payroll_month) DO UPDATE SET
                basic_salary=excluded.basic_salary, allowances=excluded.allowances,
                deductions=excluded.deductions, present_days=excluded.present_days,
                absent_days=excluded.absent_days, half_days=excluded.half_days,
                leave_days=excluded.leave_days, net_salary=excluded.net_salary""",
            (e["id"], month, basic, allowance, deduction, present, absent, half, leave, net),
            commit=True
        )
        created += 1
    return jsonify({"message": "Payroll calculated for {} employees".format(created)})


@app.route("/api/payroll", methods=["GET"])
@api_login_required
def payroll_report():
    month = request.args.get("month", date.today().strftime("%Y-%m"))
    rows = query(
        """SELECT p.id, e.employee_code, e.full_name, p.payroll_month, p.basic_salary, p.allowances,
        p.deductions, p.overtime_pay, p.present_days, p.absent_days, p.half_days, p.leave_days, p.net_salary
        FROM payroll p JOIN employees e ON e.id=p.employee_id WHERE p.payroll_month=? ORDER BY e.full_name""",
        (month,)
    )
    for r in rows:
        for k in ("basic_salary", "allowances", "deductions", "overtime_pay", "net_salary"):
            r[k] = float(r[k] or 0)
    return jsonify(rows)


# ---------------------------------------------------------------------------
# Reports API
# ---------------------------------------------------------------------------

@app.route("/api/reports", methods=["GET"])
@api_login_required
def reports():
    month = request.args.get("month", date.today().strftime("%Y-%m"))
    attendance = query(
        "SELECT status, COUNT(*) AS count FROM attendance "
        "WHERE strftime('%Y-%m', attendance_date)=? GROUP BY status",
        (month,)
    )
    payroll = query(
        "SELECT COUNT(*) AS employees, COALESCE(SUM(net_salary),0) AS total FROM payroll WHERE payroll_month=?",
        (month,), one=True
    )
    return jsonify({
        "attendance": attendance,
        "payroll": {"employees": payroll["employees"], "total": float(payroll["total"] or 0)}
    })


@app.errorhandler(500)
def server_error(_):
    return jsonify({"error": "Server error. Check the terminal output."}), 500


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    init_db()
    print("\n🚀  PeoplePay running at http://127.0.0.1:5000")
    print("   Login credentials: admin / admin123\n")
    app.run(debug=True, use_reloader=False)
