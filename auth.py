import hashlib
import os

import psycopg2
import psycopg2.errors
from dotenv import load_dotenv

load_dotenv()


def _get_db_params() -> dict:
    try:
        import streamlit as st
        return {
            "host":     st.secrets.get("DB_HOST")     or os.getenv("DB_HOST"),
            "port":     st.secrets.get("DB_PORT")     or os.getenv("DB_PORT", "5432"),
            "dbname":   st.secrets.get("DB_NAME")     or os.getenv("DB_NAME", "postgres"),
            "user":     st.secrets.get("DB_USER")     or os.getenv("DB_USER"),
            "password": st.secrets.get("DB_PASSWORD") or os.getenv("DB_PASSWORD"),
            "sslmode":  "require",
        }
    except Exception:
        return {
            "host":     os.getenv("DB_HOST"),
            "port":     os.getenv("DB_PORT", "5432"),
            "dbname":   os.getenv("DB_NAME", "postgres"),
            "user":     os.getenv("DB_USER"),
            "password": os.getenv("DB_PASSWORD"),
            "sslmode":  "require",
        }


def _hash(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()


def _conn():
    params = _get_db_params()
    if not params["host"]:
        raise RuntimeError("DB_HOST secret is missing. Add DB_HOST, DB_USER, DB_PASSWORD etc. in Streamlit secrets.")
    conn = psycopg2.connect(**params)
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
