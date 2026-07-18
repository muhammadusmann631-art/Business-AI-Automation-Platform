"""Auth — bcrypt password hashing + JWT sessions (Credentials-style login).

Self-contained: users live in the SQLite `users` table (see database.py). No
external auth service. Passwords are ALWAYS bcrypt-hashed; the JWT secret comes
from the environment (JWT_SECRET), never hard-coded.
"""

import os
import time
import warnings

import bcrypt
import jwt

import database as db

# The dev-default secret is short; real deployments set a 32+ byte JWT_SECRET.
# Silence PyJWT's length warning so it doesn't clutter the logs.
try:
    from jwt.warnings import InsecureKeyLengthWarning

    warnings.filterwarnings("ignore", category=InsecureKeyLengthWarning)
except Exception:
    pass

JWT_SECRET = os.getenv("JWT_SECRET", "dev-insecure-secret-change-me-please-32bytes-minimum-0123456789")
JWT_ALG = "HS256"
JWT_TTL = 7 * 24 * 3600  # 7 days

# Default admin, seeded once for testing. CHANGE THE PASSWORD in production.
DEFAULT_ADMIN = {"name": "Admin", "email": "admin@agicore.com", "password": "admin123", "role": "admin"}


class AuthError(Exception):
    """Signup/login failure with a user-safe message."""


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except Exception:
        return False


def _public(user: dict) -> dict:
    """User fields safe to expose (never the password hash)."""
    return {"id": user["id"],  "name": user["name"], "email": user["email"], "role": user["role"]}


def make_token(user: dict) -> str:
    now = int(time.time())
    payload = {
        "sub": str(user["id"]),  # PyJWT requires sub to be a string
        "email": user["email"],
        "name": user["name"],
        "role": user["role"],
        "iat": now,
        "exp": now + JWT_TTL,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
    except Exception:
        return None


def signup(name: str, email: str, password: str) -> dict:
    name = (name or "").strip()
    email = (email or "").strip().lower()
    if not name or "@" not in email:
        raise AuthError("A valid name and email are required.")
    if len(password or "") < 8:
        raise AuthError("Password must be at least 8 characters.")
    if db.get_user_by_email(email):
        raise AuthError("An account with this email already exists.")
    uid = db.create_user(name, email, hash_password(password), role="user")
    return _public(db.get_user_by_id(uid))


def login(email: str, password: str) -> tuple[str, dict]:
    user = db.get_user_by_email((email or "").strip().lower())
    if not user or not verify_password(password or "", user["password_hash"]):
        raise AuthError("Invalid email or password.")
    return make_token(user), _public(user)


def current_user(auth_header: str | None) -> dict | None:
    """Decode a `Bearer <token>` header into the user payload, or None."""
    if not auth_header or not auth_header.lower().startswith("bearer "):
        return None
    return decode_token(auth_header.split(" ", 1)[1].strip())


def ensure_admin() -> None:
    """Seed the default admin user once. Idempotent."""
    if db.get_user_by_email(DEFAULT_ADMIN["email"]):
        return
    db.create_user(
        DEFAULT_ADMIN["name"], DEFAULT_ADMIN["email"],
        hash_password(DEFAULT_ADMIN["password"]), role="admin",
    )
    print(f"[AUTH] seeded default admin: {DEFAULT_ADMIN['email']} / {DEFAULT_ADMIN['password']} "
          "(CHANGE THIS PASSWORD)")


if __name__ == "__main__":
    db.seed()
    ensure_admin()
    tok, u = login(DEFAULT_ADMIN["email"], DEFAULT_ADMIN["password"])
    print("login ok:", u)
    print("token decodes:", decode_token(tok)["email"])
    assert decode_token("garbage") is None
    try:
        login(DEFAULT_ADMIN["email"], "wrong")
    except AuthError as e:
        print("wrong password rejected:", e)
