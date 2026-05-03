import logging
import os
import re
import uuid
from datetime import datetime, timedelta

import bcrypt
import MySQLdb
from flask import Flask, jsonify, request, send_from_directory, session
from flask_cors import CORS
from flask_mysqldb import MySQL

_BASE = os.path.dirname(os.path.abspath(__file__))
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-me-in-production")
app.config["MYSQL_HOST"] = os.environ.get("MYSQL_HOST", "localhost")
app.config["MYSQL_USER"] = os.environ.get("MYSQL_USER", "root")
app.config["MYSQL_PASSWORD"] = os.environ.get("MYSQL_PASSWORD", "")
app.config["MYSQL_DB"] = os.environ.get("ADMIN_PORTAL_DB", "admin_portal")
app.config["MYSQL_CURSORCLASS"] = "DictCursor"
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

CORS(app, supports_credentials=True)
mysql = MySQL(app)
logging.basicConfig(level=logging.INFO)


def ok(data=None, message=None, status=200):
    payload = {"success": True}
    if message:
        payload["message"] = message
    if data is not None:
        payload["data"] = data
    return jsonify(payload), status


def err(message, status=400):
    return jsonify({"success": False, "message": message}), status


def get_json_body():
    body = request.get_json(silent=True)
    return body if isinstance(body, dict) else {}


def validate_email(email):
    return bool(EMAIL_RE.fullmatch(email or ""))


def ensure_mysql_ready():
    db_name = app.config["MYSQL_DB"]
    conn = MySQLdb.connect(
        host=app.config["MYSQL_HOST"],
        user=app.config["MYSQL_USER"],
        passwd=app.config["MYSQL_PASSWORD"],
    )
    try:
        cur = conn.cursor()
        cur.execute(
            f"CREATE DATABASE IF NOT EXISTS `{db_name}` "
            "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        )
        cur.execute(f"USE `{db_name}`")
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS admins (
                id INT AUTO_INCREMENT PRIMARY KEY,
                full_name VARCHAR(150) NOT NULL,
                email VARCHAR(254) NOT NULL UNIQUE,
                password_hash VARCHAR(255) NOT NULL,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS password_resets (
                id INT AUTO_INCREMENT PRIMARY KEY,
                email VARCHAR(254) NOT NULL,
                token VARCHAR(100) NOT NULL UNIQUE,
                expires_at DATETIME NOT NULL,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS opportunities (
                id INT AUTO_INCREMENT PRIMARY KEY,
                title VARCHAR(255) NOT NULL,
                duration VARCHAR(100) NOT NULL,
                start_date DATE NOT NULL,
                description TEXT NOT NULL,
                skills TEXT NOT NULL,
                category VARCHAR(120) NOT NULL,
                future_opportunities TINYINT(1) NOT NULL DEFAULT 0,
                max_applicants INT NOT NULL,
                created_by INT NOT NULL,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_opportunities_created_by (created_by),
                CONSTRAINT fk_opportunities_admin
                    FOREIGN KEY (created_by) REFERENCES admins(id)
                    ON DELETE CASCADE ON UPDATE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """
        )
        conn.commit()
    finally:
        conn.close()


try:
    ensure_mysql_ready()
    app.logger.info("MySQL ready on database '%s'", app.config["MYSQL_DB"])
except Exception as exc:
    app.logger.exception("MySQL setup failed: %s", exc)


@app.route("/")
def health():
    return "Flask API running"


@app.route("/admin")
def admin_page():
    return send_from_directory(_BASE, "admin.html")


@app.route("/admin.css")
def admin_css():
    return send_from_directory(_BASE, "admin.css")


@app.route("/admin.js")
def admin_js():
    return send_from_directory(_BASE, "admin.js")


@app.route("/api/signup", methods=["POST"])
def signup():
    body = get_json_body()
    full_name = str(body.get("full_name", "")).strip()
    email = str(body.get("email", "")).strip().lower()
    password = str(body.get("password", ""))
    confirm = str(body.get("confirm_password", body.get("confirmPassword", "")))

    if not all([full_name, email, password, confirm]):
        return err("All fields are required.", 400)
    if not validate_email(email):
        return err("Invalid email address.", 400)
    if len(password) < 8:
        return err("Password must be at least 8 characters.", 400)
    if password != confirm:
        return err("Passwords do not match.", 400)

    try:
        cur = mysql.connection.cursor()
        cur.execute("SELECT id FROM admins WHERE email=%s LIMIT 1", (email,))
        if cur.fetchone():
            return err("An account with this email already exists.", 400)

        password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("ascii")
        cur.execute(
            "INSERT INTO admins (full_name, email, password_hash) VALUES (%s, %s, %s)",
            (full_name, email, password_hash),
        )
        mysql.connection.commit()
        return ok(message="Signup successful.")
    except MySQLdb.IntegrityError:
        return err("An account with this email already exists.", 400)
    except Exception:
        app.logger.exception("Signup failed")
        return err("Database error. Please try again.", 500)


@app.route("/api/login", methods=["POST"])
def login():
    body = get_json_body()
    email = str(body.get("email", "")).strip().lower()
    password = str(body.get("password", ""))

    if not email or not password:
        return err("Invalid email or password.", 401)
    if not validate_email(email):
        return err("Invalid email or password.", 401)

    try:
        cur = mysql.connection.cursor()
        cur.execute(
            "SELECT id, full_name, email, password_hash FROM admins WHERE email=%s LIMIT 1",
            (email,),
        )
        row = cur.fetchone()
        if not row:
            return err("Invalid email or password.", 401)

        stored_hash = row["password_hash"]
        if isinstance(stored_hash, str):
            stored_hash = stored_hash.encode("utf-8")

        if not bcrypt.checkpw(password.encode("utf-8"), stored_hash):
            return err("Invalid email or password.", 401)

        session["admin_id"] = int(row["id"])
        return ok(
            data={
                "id": int(row["id"]),
                "full_name": row["full_name"],
                "email": row["email"],
            },
            message="Login successful.",
        )
    except Exception:
        app.logger.exception("Login failed")
        return err("Database error. Please try again.", 500)


@app.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return ok(message="Logged out.")


@app.route("/api/forgot", methods=["POST"])
@app.route("/api/forgot-password", methods=["POST"])
def forgot():
    body = get_json_body()
    email = str(body.get("email", "")).strip().lower()

    try:
        if validate_email(email):
            cur = mysql.connection.cursor()
            cur.execute("SELECT id FROM admins WHERE email=%s LIMIT 1", (email,))
            admin = cur.fetchone()
            if admin:
                token = str(uuid.uuid4())
                expires_at = datetime.utcnow() + timedelta(hours=1)
                cur.execute("DELETE FROM password_resets WHERE email=%s", (email,))
                cur.execute(
                    "INSERT INTO password_resets (email, token, expires_at) VALUES (%s, %s, %s)",
                    (email, token, expires_at),
                )
                mysql.connection.commit()
    except Exception:
        app.logger.exception("Forgot password failed")

    return ok(message="If that email exists, reset link sent.")


@app.route("/api/reset/<token>", methods=["POST"])
def reset(token):
    body = get_json_body()
    password = str(body.get("password", ""))
    confirm = str(body.get("confirm_password", body.get("confirmPassword", password)))

    if len(password) < 8:
        return err("Password must be at least 8 characters.", 400)
    if password != confirm:
        return err("Passwords do not match.", 400)

    try:
        cur = mysql.connection.cursor()
        cur.execute(
            "SELECT email FROM password_resets WHERE token=%s AND expires_at > NOW() LIMIT 1",
            (token,),
        )
        row = cur.fetchone()
        if not row:
            return err("Invalid or expired token.", 400)

        new_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("ascii")
        cur.execute("UPDATE admins SET password_hash=%s WHERE email=%s", (new_hash, row["email"]))
        cur.execute("DELETE FROM password_resets WHERE token=%s", (token,))
        mysql.connection.commit()
        return ok(message="Password updated successfully.")
    except Exception:
        app.logger.exception("Reset password failed")
        return err("Database error. Please try again.", 500)


@app.route("/api/opportunity", methods=["POST"])
def add_opportunity():
    admin_id = session.get("admin_id")
    if not admin_id:
        return err("Unauthorized.", 401)

    body = get_json_body()
    title = str(body.get("title", "")).strip()
    duration = str(body.get("duration", "")).strip()
    start_date = str(body.get("start_date", "")).strip()
    description = str(body.get("description", "")).strip()
    skills_value = body.get("skills", [])
    category = str(body.get("category", "")).strip()
    future_opportunities = 1 if bool(body.get("future_opportunities", False)) else 0

    try:
        max_applicants = int(body.get("max_applicants", 0))
    except (TypeError, ValueError):
        max_applicants = 0

    if not all([title, duration, start_date, description, category]) or max_applicants <= 0:
        return err("Missing or invalid opportunity fields.", 400)

    if isinstance(skills_value, list):
        skills = ",".join(str(s).strip() for s in skills_value if str(s).strip())
    else:
        skills = str(skills_value).strip()
    if not skills:
        return err("Skills are required.", 400)

    try:
        cur = mysql.connection.cursor()
        cur.execute(
            """
            INSERT INTO opportunities
            (title, duration, start_date, description, skills, category, future_opportunities, max_applicants, created_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                title,
                duration,
                start_date,
                description,
                skills,
                category,
                future_opportunities,
                max_applicants,
                int(admin_id),
            ),
        )
        mysql.connection.commit()
        return ok(message="Opportunity created.")
    except Exception:
        app.logger.exception("Add opportunity failed")
        return err("Database error. Please try again.", 500)


@app.route("/api/opportunities", methods=["GET"])
def list_opportunities():
    try:
        cur = mysql.connection.cursor()
        cur.execute(
            """
            SELECT id, title, duration, start_date, description, skills, category,
                   future_opportunities, max_applicants, created_by, created_at
            FROM opportunities
            ORDER BY created_at DESC
            """
        )
        rows = cur.fetchall()
        data = []
        for row in rows:
            skills = row.get("skills") or ""
            data.append(
                {
                    "id": int(row["id"]),
                    "title": row["title"],
                    "duration": row["duration"],
                    "start_date": row["start_date"].isoformat() if row.get("start_date") else None,
                    "description": row["description"],
                    "skills": [s.strip() for s in skills.split(",") if s.strip()],
                    "category": row["category"],
                    "future_opportunities": bool(row["future_opportunities"]),
                    "max_applicants": int(row["max_applicants"]),
                    "created_by": int(row["created_by"]),
                    "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
                }
            )
        return ok(data=data)
    except Exception:
        app.logger.exception("List opportunities failed")
        return err("Database error. Please try again.", 500)


if __name__ == "__main__":
    app.run(debug=True)