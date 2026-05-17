import hashlib
import os

import psycopg2
import psycopg2.errors
from dotenv import load_dotenv

load_dotenv()


def _get_database_url() -> str:
    # Streamlit Cloud stores secrets in st.secrets, not os.environ
    try:
        import streamlit as st
        url = st.secrets.get("DATABASE_URL") or os.getenv("DATABASE_URL")
    except Exception:
        url = os.getenv("DATABASE_URL")
    return url


def _hash(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()


def _conn():
    conn = psycopg2.connect(_get_database_url(), sslmode="require")
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
