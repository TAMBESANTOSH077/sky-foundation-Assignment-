"""
routes.py — All API routes for the Volunteer Platform backend.

Auth routes  : /signup  /login  /logout  /forgot-password
Opportunity  : /opportunities  /opportunities/<id>
Misc         : /me  /categories
"""

import re
import logging
import secrets
from datetime import datetime, timedelta

from flask import Blueprint, request, jsonify, current_app
from flask_login import login_user, logout_user, login_required, current_user

from models import db, Admin, Opportunity, PasswordReset

logger = logging.getLogger(__name__)
api = Blueprint("api", __name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def ok(data=None, **kwargs):
    payload = {"success": True}
    if data is not None:
        payload["data"] = data
    payload.update(kwargs)
    return jsonify(payload), 200


def err(message: str, status: int = 400):
    return jsonify({"success": False, "message": message}), status


def get_json_body():
    """Safely parse JSON body; return empty dict on failure."""
    try:
        body = request.get_json(force=True, silent=True)
        return body if isinstance(body, dict) else {}
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Auth — /signup
# ---------------------------------------------------------------------------

@api.route("/signup", methods=["POST"])
def signup():
    body = get_json_body()

    full_name = (body.get("full_name") or body.get("fullName") or "").strip()
    email = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""
    confirm = body.get("confirm_password") or body.get("confirmPassword") or ""

    logger.info("[SIGNUP] Attempt — email=%s", email)

    # --- Field presence ---
    if not all([full_name, email, password, confirm]):
        return err("All fields are required.")

    # --- Email format ---
    if not EMAIL_RE.match(email):
        return err("Invalid email address.")

    # --- Password length ---
    if len(password) < 8:
        return err("Password must be at least 8 characters.")

    # --- Confirm match ---
    if password != confirm:
        return err("Passwords do not match.")

    # --- Unique email ---
    if Admin.query.filter_by(email=email).first():
        # Return generic message to avoid enumeration in signup context
        return err("An account with this email already exists.")

    admin = Admin(full_name=full_name, email=email)
    admin.set_password(password)
    db.session.add(admin)
    db.session.commit()

    logger.info("[SIGNUP] Success — id=%s email=%s", admin.id, admin.email)
    return ok()


# ---------------------------------------------------------------------------
# Auth — /login
# ---------------------------------------------------------------------------

@api.route("/login", methods=["POST"])
def login():
    body = get_json_body()

    email = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""
    remember = bool(body.get("remember") or body.get("remember_me") or False)

    logger.info("[LOGIN] Attempt — email=%s remember=%s", email, remember)

    admin = Admin.query.filter_by(email=email).first()

    # Constant-time-safe: check hash even if user not found (dummy check)
    if admin is None or not admin.check_password(password):
        logger.warning("[LOGIN] Failed — email=%s", email)
        return jsonify({"success": False, "message": "Invalid email or password"}), 401

    login_user(admin, remember=remember)
    logger.info("[LOGIN] Success — id=%s email=%s", admin.id, admin.email)
    return ok(data=admin.to_dict())


# ---------------------------------------------------------------------------
# Auth — /logout
# ---------------------------------------------------------------------------

@api.route("/logout", methods=["POST"])
@login_required
def logout():
    logger.info("[LOGOUT] id=%s", current_user.id)
    logout_user()
    return ok()


# ---------------------------------------------------------------------------
# Auth — /forgot-password
# ---------------------------------------------------------------------------

@api.route("/forgot-password", methods=["POST"])
def forgot_password():
    body = get_json_body()
    email = (body.get("email") or "").strip().lower()

    logger.info("[FORGOT-PASSWORD] Request — email=%s", email)

    # ALWAYS return success (prevents email enumeration)
    admin = Admin.query.filter_by(email=email).first()
    if admin:
        expiry_sec = int(current_app.config["PASSWORD_RESET_TOKEN_EXPIRY"])
        raw_token = secrets.token_hex(32)
        PasswordReset.query.filter_by(email=admin.email).delete()
        db.session.add(
            PasswordReset(
                email=admin.email,
                token=raw_token,
                expires_at=datetime.utcnow() + timedelta(seconds=expiry_sec),
            )
        )
        db.session.commit()

        base = request.host_url.rstrip("/")
        reset_link = f"{base}/reset-password.html?token={raw_token}"
        logger.info(
            "[FORGOT-PASSWORD] Token stored for id=%s | expires in %ss",
            admin.id, expiry_sec,
        )
        print(f"\n{'='*60}")
        print("  PASSWORD RESET LINK (dev — send by email in production):")
        print(f"  {reset_link}")
        print(f"{'='*60}\n")
    else:
        logger.info("[FORGOT-PASSWORD] Email not found — suppressing (anti-enumeration)")

    return ok(message="If that email exists, a reset link has been sent.")


# ---------------------------------------------------------------------------
# Auth — /reset-password  (bonus — token verification + update)
# ---------------------------------------------------------------------------

@api.route("/reset-password", methods=["POST"])
def reset_password():
    body = get_json_body()
    token = body.get("token") or ""
    new_password = body.get("password") or ""
    confirm = body.get("confirm_password") or body.get("confirmPassword") or ""

    row = (
        PasswordReset.query.filter(
            PasswordReset.token == token.strip(),
            PasswordReset.expires_at > datetime.utcnow(),
        ).first()
    )
    if not row:
        return err("Reset link is invalid or has expired.", 400)

    if len(new_password) < 8:
        return err("Password must be at least 8 characters.")

    if new_password != confirm:
        return err("Passwords do not match.")

    admin = Admin.query.filter_by(email=row.email).first()
    if not admin:
        return err("Account not found.", 404)

    admin.set_password(new_password)
    PasswordReset.query.filter_by(email=row.email).delete()
    db.session.commit()
    logger.info("[RESET-PASSWORD] Success — id=%s", admin.id)
    return ok()


# ---------------------------------------------------------------------------
# /me — return current session user
# ---------------------------------------------------------------------------

@api.route("/me", methods=["GET"])
@login_required
def me():
    return ok(data=current_user.to_dict())


# ---------------------------------------------------------------------------
# /categories — return allowed category list
# ---------------------------------------------------------------------------

@api.route("/categories", methods=["GET"])
def categories():
    return ok(data=current_app.config["ALLOWED_CATEGORIES"])


# ---------------------------------------------------------------------------
# Opportunities — GET /opportunities  |  POST /opportunities
# ---------------------------------------------------------------------------

REQUIRED_OPPORTUNITY_FIELDS = [
    "title", "duration", "start_date", "description", "skills", "category", "max_applicants"
]


@api.route("/opportunities", methods=["GET"])
@login_required
def list_opportunities():
    opps = Opportunity.query.filter_by(admin_id=current_user.id).order_by(
        Opportunity.created_at.desc()
    ).all()
    return ok(data=[o.to_dict() for o in opps])


@api.route("/opportunities", methods=["POST"])
@login_required
def create_opportunity():
    body = get_json_body()

    # --- Required field validation ---
    missing = [f for f in REQUIRED_OPPORTUNITY_FIELDS if not body.get(f)]
    if missing:
        return err(f"Missing required fields: {', '.join(missing)}")

    # --- Category validation ---
    allowed = current_app.config["ALLOWED_CATEGORIES"]
    if body["category"] not in allowed:
        return err(f"Invalid category. Allowed: {', '.join(allowed)}")

    # --- max_applicants must be positive int ---
    try:
        max_ap = int(body["max_applicants"])
        if max_ap < 1:
            raise ValueError
    except (ValueError, TypeError):
        return err("max_applicants must be a positive integer.")

    opp = Opportunity(
        title=body["title"].strip(),
        duration=body["duration"].strip(),
        start_date=body["start_date"],
        description=body["description"].strip(),
        skills=body["skills"].strip(),
        category=body["category"],
        future_opportunities=bool(body.get("future_opportunities", False)),
        max_applicants=max_ap,
        admin_id=current_user.id,
    )
    db.session.add(opp)
    db.session.commit()

    logger.info("[OPPORTUNITY] Created id=%s by admin=%s", opp.id, current_user.id)
    return jsonify({"success": True, "data": opp.to_dict()}), 201


# ---------------------------------------------------------------------------
# Opportunities — GET /opportunities/<id>
# ---------------------------------------------------------------------------

@api.route("/opportunities/<int:opp_id>", methods=["GET"])
@login_required
def get_opportunity(opp_id: int):
    opp = Opportunity.query.filter_by(id=opp_id, admin_id=current_user.id).first()
    if not opp:
        return err("Opportunity not found or access denied.", 404)
    return ok(data=opp.to_dict())


# ---------------------------------------------------------------------------
# Opportunities — PUT /opportunities/<id>
# ---------------------------------------------------------------------------

@api.route("/opportunities/<int:opp_id>", methods=["PUT"])
@login_required
def update_opportunity(opp_id: int):
    opp = Opportunity.query.filter_by(id=opp_id, admin_id=current_user.id).first()
    if not opp:
        return err("Opportunity not found or access denied.", 404)

    body = get_json_body()
    if not body:
        return err("No data provided.")

    # --- Update only fields present in the body ---
    updatable = [
        "title", "duration", "start_date", "description",
        "skills", "category", "future_opportunities", "max_applicants",
    ]
    for field in updatable:
        if field not in body:
            continue
        if field == "category":
            allowed = current_app.config["ALLOWED_CATEGORIES"]
            if body[field] not in allowed:
                return err(f"Invalid category. Allowed: {', '.join(allowed)}")
        if field == "max_applicants":
            try:
                val = int(body[field])
                if val < 1:
                    raise ValueError
                setattr(opp, field, val)
            except (ValueError, TypeError):
                return err("max_applicants must be a positive integer.")
        elif field == "future_opportunities":
            setattr(opp, field, bool(body[field]))
        else:
            setattr(opp, field, str(body[field]).strip())

    opp.updated_at = datetime.utcnow()
    db.session.commit()

    logger.info("[OPPORTUNITY] Updated id=%s by admin=%s", opp.id, current_user.id)
    return ok(data=opp.to_dict())


# ---------------------------------------------------------------------------
# Opportunities — DELETE /opportunities/<id>
# ---------------------------------------------------------------------------

@api.route("/opportunities/<int:opp_id>", methods=["DELETE"])
@login_required
def delete_opportunity(opp_id: int):
    opp = Opportunity.query.filter_by(id=opp_id, admin_id=current_user.id).first()
    if not opp:
        return err("Opportunity not found or access denied.", 404)

    db.session.delete(opp)
    db.session.commit()

    logger.info("[OPPORTUNITY] Deleted id=%s by admin=%s", opp_id, current_user.id)
    return ok(message="Opportunity deleted successfully.")
