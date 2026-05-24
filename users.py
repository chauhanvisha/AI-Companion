import hashlib
import os

import psycopg2
import psycopg2.errors
from psycopg2.extras import RealDictCursor


def _hash(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()


def _conn():
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT", "5432"),
        dbname=os.getenv("DB_NAME", "postgres"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        sslmode="require",
    )
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                password_hash TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS user_profiles (
                username    TEXT PRIMARY KEY,
                field       TEXT,
                target_role TEXT,
                school      TEXT,
                updated_at  TIMESTAMP DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS session_notes (
                id          SERIAL PRIMARY KEY,
                username    TEXT NOT NULL,
                scenario    TEXT NOT NULL,
                notes       TEXT NOT NULL,
                created_at  TIMESTAMP DEFAULT NOW()
            );
            """
        )
    conn.commit()
    return conn


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------

def get_profile(username: str) -> dict | None:
    """Return {"field": ..., "target_role": ..., "school": ...} or None if no profile saved yet."""
    conn = _conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT field, target_role, school FROM user_profiles WHERE username = %s",
                (username,),
            )
            row = cur.fetchone()
    finally:
        conn.close()
    return dict(row) if row else None


def save_profile(username: str, field: str, target_role: str, school: str = "") -> None:
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO user_profiles (username, field, target_role, school, updated_at)
                VALUES (%s, %s, %s, %s, NOW())
                ON CONFLICT (username) DO UPDATE
                    SET field = EXCLUDED.field,
                        target_role = EXCLUDED.target_role,
                        school = EXCLUDED.school,
                        updated_at = NOW()
                """,
                (username, field, target_role, school),
            )
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Session notes
# ---------------------------------------------------------------------------

def get_session_notes(username: str, limit: int = 3) -> list[dict]:
    """Return last `limit` session summaries, newest first."""
    conn = _conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT scenario, notes, created_at
                FROM session_notes
                WHERE username = %s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (username, limit),
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


def save_session_note(username: str, scenario: str, notes: str) -> None:
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO session_notes (username, scenario, notes) VALUES (%s, %s, %s)",
                (username, scenario, notes),
            )
        conn.commit()
    finally:
        conn.close()
