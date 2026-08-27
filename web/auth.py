"""JWT authentication for MarketLens web app — database-backed."""
import logging
import os
import secrets
import threading
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

logger = logging.getLogger(__name__)

JWT_SECRET = os.environ.get("MLENS_JWT_SECRET")
if not JWT_SECRET:
    logger.critical(
        "MLENS_JWT_SECRET environment variable is not set. "
        "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
    )
    raise SystemExit("MLENS_JWT_SECRET environment variable is required. See logs for instructions.")

JWT_ALGORITHM = "HS256"
TOKEN_EXPIRY_HOURS = 24

security = HTTPBearer(auto_error=False)

_db = None


def _get_db():
    global _db
    if _db is None:
        from database.manager import DatabaseManager
        _db = DatabaseManager()
    return _db


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


def create_token(username: str) -> str:
    payload = {
        "sub": username,
        "exp": datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRY_HOURS),
        "iat": datetime.now(timezone.utc),
        "jti": secrets.token_hex(16),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> Optional[str]:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload.get("sub")
    except jwt.InvalidTokenError:
        return None


def register_user(username: str, password: str, email: str = "") -> bool:
    db = _get_db()
    pw_hash = hash_password(password)
    user_id = db.create_user(username, pw_hash, email)
    if user_id is None:
        return False
    db.create_subscription(user_id, tier="free", days=0)
    logger.info("Registered user: %s (id=%d)", username, user_id)
    return True


def authenticate_user(username: str, password: str) -> bool:
    db = _get_db()
    user = db.get_user_by_username(username)
    if not user:
        return False
    return verify_password(password, user["password_hash"])


def get_user_subscription(username: str) -> Optional[dict]:
    db = _get_db()
    user = db.get_user_by_username(username)
    if not user:
        return None
    return db.get_active_subscription(user["id"])


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> str:
    token = None
    if credentials and credentials.credentials:
        token = credentials.credentials
    if not token:
        token = request.cookies.get("mjl_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    username = decode_token(token)
    if not username:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    db = _get_db()
    user = db.get_user_by_username(username)
    if not user or not user.get("is_active", 1):
        raise HTTPException(status_code=401, detail="Account disabled")
    return username
