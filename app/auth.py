from passlib.context import CryptContext
from .database import get_connection

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def create_user(username: str, password: str, role: str):
    conn = get_connection()
    cur = conn.cursor()
    password_hash = pwd_context.hash(password)
    cur.execute(
        "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
        (username, password_hash, role)
    )
    conn.commit()
    cur.close()
    conn.close()

def verify_user(username: str, password: str):
    """Geeft rol terug als login goed is, anders None."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT password_hash, role FROM users WHERE username = ?",
        (username,)
    )
    row = cur.fetchone()
    cur.close()
    conn.close()

    if not row:
        return None

    password_hash, role = row
    if not pwd_context.verify(password, password_hash):
        return None

    return role
