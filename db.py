"""
SQLite database layer — async (aiosqlite) for FastAPI routes,
sync helpers for the worker thread.
"""
import sqlite3
import uuid
from datetime import datetime, timedelta

import aiosqlite

DB_PATH_DEFAULT = "/data/app.db"

import os

def _db_path() -> str:
    return os.getenv("DB_PATH", DB_PATH_DEFAULT)


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

async def init_db() -> None:
    async with aiosqlite.connect(_db_path()) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                job_id          TEXT PRIMARY KEY,
                session_id      TEXT NOT NULL,
                url             TEXT NOT NULL,
                title           TEXT,
                status          TEXT NOT NULL DEFAULT 'pending',
                progress_message TEXT,
                total_parts     INTEGER,
                current_part    INTEGER DEFAULT 0,
                error           TEXT,
                created_at      TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(session_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS files (
                file_id      TEXT PRIMARY KEY,
                job_id       TEXT NOT NULL,
                session_id   TEXT NOT NULL,
                filename     TEXT NOT NULL,
                filepath     TEXT NOT NULL,
                part_number  INTEGER,
                total_parts  INTEGER,
                title        TEXT,
                status       TEXT NOT NULL DEFAULT 'available',
                created_at   TEXT NOT NULL,
                expires_at   TEXT NOT NULL,
                FOREIGN KEY (job_id) REFERENCES jobs(job_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS push_subscriptions (
                id                TEXT PRIMARY KEY,
                session_id        TEXT NOT NULL,
                subscription_json TEXT NOT NULL,
                created_at        TEXT NOT NULL
            )
        """)
        await db.commit()


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------

async def ensure_session(session_id: str) -> None:
    async with aiosqlite.connect(_db_path()) as db:
        await db.execute(
            "INSERT OR IGNORE INTO sessions (session_id, created_at) VALUES (?, ?)",
            (session_id, datetime.utcnow().isoformat()),
        )
        await db.commit()


# ---------------------------------------------------------------------------
# Jobs — async
# ---------------------------------------------------------------------------

async def create_job(job_id: str, session_id: str, url: str) -> dict:
    async with aiosqlite.connect(_db_path()) as db:
        await db.execute(
            "INSERT INTO jobs (job_id, session_id, url, status, created_at) VALUES (?, ?, ?, 'pending', ?)",
            (job_id, session_id, url, datetime.utcnow().isoformat()),
        )
        await db.commit()
    return await get_job(job_id)


async def get_job(job_id: str) -> dict | None:
    async with aiosqlite.connect(_db_path()) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def update_job(job_id: str, **kwargs) -> None:
    if not kwargs:
        return
    clause = ", ".join(f"{k} = ?" for k in kwargs)
    values = list(kwargs.values()) + [job_id]
    async with aiosqlite.connect(_db_path()) as db:
        await db.execute(f"UPDATE jobs SET {clause} WHERE job_id = ?", values)
        await db.commit()


# Jobs — sync (called from worker thread)

def _sync_conn():
    conn = sqlite3.connect(_db_path(), timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn


def update_job_sync(job_id: str, **kwargs) -> None:
    if not kwargs:
        return
    clause = ", ".join(f"{k} = ?" for k in kwargs)
    values = list(kwargs.values()) + [job_id]
    conn = _sync_conn()
    try:
        conn.execute(f"UPDATE jobs SET {clause} WHERE job_id = ?", values)
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Files — async
# ---------------------------------------------------------------------------

async def get_file(file_id: str) -> dict | None:
    async with aiosqlite.connect(_db_path()) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM files WHERE file_id = ?", (file_id,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def get_files_for_session(session_id: str) -> list[dict]:
    async with aiosqlite.connect(_db_path()) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM files WHERE session_id = ? AND status = 'available' ORDER BY created_at DESC",
            (session_id,),
        ) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


async def delete_file(file_id: str, session_id: str) -> dict | None:
    file = await get_file(file_id)
    if not file or file["session_id"] != session_id:
        return None
    async with aiosqlite.connect(_db_path()) as db:
        await db.execute(
            "UPDATE files SET status = 'deleted' WHERE file_id = ?", (file_id,)
        )
        await db.commit()
    return file


async def get_expired_files() -> list[dict]:
    now = datetime.utcnow().isoformat()
    async with aiosqlite.connect(_db_path()) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM files WHERE status = 'available' AND expires_at <= ?",
            (now,),
        ) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


async def mark_file_deleted(file_id: str) -> None:
    async with aiosqlite.connect(_db_path()) as db:
        await db.execute(
            "UPDATE files SET status = 'deleted' WHERE file_id = ?", (file_id,)
        )
        await db.commit()


# Files — sync (called from worker thread)

def create_file_sync(
    file_id: str,
    job_id: str,
    session_id: str,
    filename: str,
    filepath: str,
    part_number: int,
    total_parts: int,
    title: str,
) -> None:
    now = datetime.utcnow()
    expires = now + timedelta(hours=24)
    conn = _sync_conn()
    try:
        conn.execute(
            """INSERT INTO files
               (file_id, job_id, session_id, filename, filepath,
                part_number, total_parts, title, status, created_at, expires_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'available', ?, ?)""",
            (
                file_id, job_id, session_id, filename, filepath,
                part_number, total_parts, title,
                now.isoformat(), expires.isoformat(),
            ),
        )
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Push subscriptions
# ---------------------------------------------------------------------------

async def save_push_subscription(session_id: str, subscription_json: str) -> None:
    sub_id = str(uuid.uuid4())
    async with aiosqlite.connect(_db_path()) as db:
        await db.execute(
            "DELETE FROM push_subscriptions WHERE session_id = ?", (session_id,)
        )
        await db.execute(
            "INSERT INTO push_subscriptions (id, session_id, subscription_json, created_at) VALUES (?, ?, ?, ?)",
            (sub_id, session_id, subscription_json, datetime.utcnow().isoformat()),
        )
        await db.commit()


async def get_push_subscription(session_id: str) -> dict | None:
    async with aiosqlite.connect(_db_path()) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM push_subscriptions WHERE session_id = ? ORDER BY created_at DESC LIMIT 1",
            (session_id,),
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


def get_push_subscription_sync(session_id: str) -> dict | None:
    conn = _sync_conn()
    try:
        cur = conn.execute(
            "SELECT * FROM push_subscriptions WHERE session_id = ? ORDER BY created_at DESC LIMIT 1",
            (session_id,),
        )
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_job_sync(job_id: str) -> dict | None:
    conn = _sync_conn()
    try:
        cur = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,))
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()
