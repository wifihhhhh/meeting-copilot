import hashlib
import hmac
import secrets

from sqlalchemy import select

from database.models import User, UserRecord
from database.sqlite import get_session, init_db


class AuthError(Exception):
    pass


class AuthService:
    def __init__(self) -> None:
        init_db()

    def register(self, username: str, password: str, display_name: str = "") -> UserRecord:
        username = self._clean_username(username)
        self._validate_password(password)
        with get_session() as session:
            existing = session.execute(select(User).where(User.username == username)).scalar_one_or_none()
            if existing is not None:
                raise AuthError("用户名已存在。")
            user = User(
                username=username,
                password_hash=hash_password(password),
                display_name=display_name.strip() or username,
            )
            session.add(user)
            session.flush()
            return to_user_record(user)

    def authenticate(self, username: str, password: str) -> UserRecord:
        username = self._clean_username(username)
        with get_session() as session:
            user = session.execute(select(User).where(User.username == username)).scalar_one_or_none()
            if user is None or not verify_password(password, user.password_hash):
                raise AuthError("用户名或密码错误。")
            return to_user_record(user)

    def get_user(self, user_id: int) -> UserRecord | None:
        with get_session() as session:
            user = session.get(User, user_id)
            return to_user_record(user) if user else None

    @staticmethod
    def _clean_username(username: str) -> str:
        clean = (username or "").strip().lower()
        if len(clean) < 3:
            raise AuthError("用户名至少需要 3 个字符。")
        return clean

    @staticmethod
    def _validate_password(password: str) -> None:
        if len(password or "") < 6:
            raise AuthError("密码至少需要 6 个字符。")


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120_000)
    return f"pbkdf2_sha256${salt}${digest.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, salt, expected = stored_hash.split("$", 2)
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120_000)
        return hmac.compare_digest(digest.hex(), expected)
    except Exception:
        return False


def to_user_record(user: User) -> UserRecord:
    return UserRecord(
        id=user.id,
        username=user.username,
        display_name=user.display_name or user.username,
        created_at=user.created_at,
    )
