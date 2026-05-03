from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class Admin(UserMixin, db.Model):
    """Platform admin / volunteer coordinator (XAMPP table `admins`)."""

    __tablename__ = "admins"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(254), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationship
    opportunities = db.relationship(
        "Opportunity", backref="admin", lazy=True, cascade="all, delete-orphan"
    )

    # ------------------------------------------------------------------
    # Password helpers
    # ------------------------------------------------------------------
    def set_password(self, plain_text: str) -> None:
        self.password_hash = generate_password_hash(plain_text)

    def check_password(self, plain_text: str) -> bool:
        return check_password_hash(self.password_hash, plain_text)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "full_name": self.full_name,
            "email": self.email,
        }


class PasswordReset(db.Model):
    """Rows for password reset tokens (XAMPP table `password_resets`)."""

    __tablename__ = "password_resets"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(254), nullable=False, index=True)
    token = db.Column(db.String(64), nullable=False, index=True)
    expires_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Opportunity(db.Model):
    """Volunteer opportunity created by an Admin."""

    __tablename__ = "opportunities"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    duration = db.Column(db.String(100), nullable=False)
    start_date = db.Column(db.String(50), nullable=False)   # stored as ISO string
    description = db.Column(db.Text, nullable=False)
    skills = db.Column(db.Text, nullable=False)             # comma-separated or free text
    category = db.Column(db.String(100), nullable=False)
    future_opportunities = db.Column(db.Boolean, default=False, nullable=False)
    max_applicants = db.Column(db.Integer, nullable=False, default=1)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Foreign key
    admin_id = db.Column(db.Integer, db.ForeignKey("admins.id"), nullable=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "duration": self.duration,
            "start_date": self.start_date,
            "description": self.description,
            "skills": self.skills,
            "category": self.category,
            "future_opportunities": self.future_opportunities,
            "max_applicants": self.max_applicants,
            "admin_id": self.admin_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
