# Volunteer Platform — Backend

## Quick Start

```bash
# 1. Create virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the server
python app.py
# → http://localhost:5000
```

SQLite database (`app.db`) is created automatically on first run.

---

## Project Structure

```
backend/
├── app.py            # Flask factory + entry point
├── config.py         # All configuration (categories, token expiry, etc.)
├── models.py         # SQLAlchemy models (Admin, Opportunity)
├── routes.py         # All API routes
├── requirements.txt
└── static/           # Drop your frontend build here (SPA served from /)
```

---

## API Reference

All routes are prefixed with `/api`.  
All responses follow the standard envelope:

```json
// Success
{ "success": true, "data": ... }

// Error
{ "success": false, "message": "..." }
```

### Auth

| Method | Endpoint           | Auth | Description                    |
|--------|--------------------|------|--------------------------------|
| POST   | /api/signup        | ✗    | Register a new admin           |
| POST   | /api/login         | ✗    | Login (session + remember-me)  |
| POST   | /api/logout        | ✓    | Logout current user            |
| POST   | /api/forgot-password | ✗  | Request password reset link    |
| POST   | /api/reset-password  | ✗  | Reset password via token       |
| GET    | /api/me            | ✓    | Get current session user       |

#### POST /api/signup
```json
{
  "full_name": "Jane Doe",
  "email": "jane@example.com",
  "password": "secret123",
  "confirm_password": "secret123"
}
```

#### POST /api/login
```json
{
  "email": "jane@example.com",
  "password": "secret123",
  "remember": true
}
```

#### POST /api/forgot-password
```json
{ "email": "jane@example.com" }
```
Always returns `{ "success": true }` (prevents email enumeration).  
Reset link is printed to the console in dev mode.

---

### Opportunities  *(all require login)*

| Method | Endpoint                  | Description                     |
|--------|---------------------------|---------------------------------|
| GET    | /api/opportunities        | List current user's records     |
| POST   | /api/opportunities        | Create a new opportunity        |
| GET    | /api/opportunities/:id    | Get single opportunity          |
| PUT    | /api/opportunities/:id    | Update opportunity              |
| DELETE | /api/opportunities/:id    | Delete opportunity              |
| GET    | /api/categories           | List allowed category values    |

#### Opportunity object shape
```json
{
  "id": 1,
  "title": "Beach Cleanup",
  "duration": "4 hours",
  "start_date": "2024-09-01",
  "description": "Help clean the local beach.",
  "skills": "Physical fitness, teamwork",
  "category": "Environment",
  "future_opportunities": false,
  "max_applicants": 20,
  "admin_id": 3,
  "created_at": "2024-08-01T10:00:00",
  "updated_at": "2024-08-01T10:00:00"
}
```

---

## Security Notes

- Passwords hashed with `werkzeug.security` (pbkdf2:sha256)
- Forgot-password always returns success (anti-enumeration)
- All CRUD routes verify `admin_id == current_user.id` (ownership)
- Session cookies: `HttpOnly`, `SameSite=Lax`
- Invalid JSON bodies are handled gracefully (no 500s)

---

## Environment Variables

| Variable        | Default                   | Description              |
|-----------------|---------------------------|--------------------------|
| SECRET_KEY      | `dev-secret-key-...`      | Flask secret (change!)   |
| DATABASE_URL    | `sqlite:///app.db`        | SQLAlchemy DB URI        |
| PORT            | `5000`                    | Server port              |
| DEBUG           | `true`                    | Debug mode               |
