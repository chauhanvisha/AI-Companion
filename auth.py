import hashlib
import os

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()

_DATABASE_URL = os.getenv("DATABASE_URL")


def _hash(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()


def _conn():
    conn = psycopg2.connect(_DATABASE_URL)
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                password_hash TEXT NOT NULL
            )
            """
        )
    conn.commit()
    return conn


def register(username: str, password: str) -> tuple[bool, str]:
    username = username.strip()
    if not username or not password:
        return False, "Username and password cannot be empty."
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users (username, password_hash) VALUES (%s, %s)",
                (username, _hash(password)),
            )
        conn.commit()
        return True, ""
    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        return False, "Username already taken."
    finally:
        conn.close()


def login(username: str, password: str) -> tuple[bool, str]:
    username = username.strip()
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT password_hash FROM users WHERE username = %s", (username,)
            )
            row = cur.fetchone()
    finally:
        conn.close()
    if not row:
        return False, "Username not found."
    if row[0] != _hash(password):
        return False, "Incorrect password."
    return True, ""
