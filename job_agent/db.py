import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "jobs.db"


def _connect():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    with _connect() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                title TEXT,
                company TEXT,
                location TEXT,
                description TEXT,
                url TEXT,
                source TEXT,
                posted_at TEXT,
                match_score INTEGER DEFAULT 0,
                ai_assessment TEXT DEFAULT '',
                application_status TEXT DEFAULT 'Not applied'
            )
        """)


def upsert_jobs(jobs):
    with _connect() as con:
        for job in jobs:
            con.execute("""
                INSERT INTO jobs (
                    id, title, company, location, description,
                    url, source, posted_at, match_score, ai_assessment
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    title=excluded.title,
                    company=excluded.company,
                    location=excluded.location,
                    description=excluded.description,
                    url=excluded.url,
                    source=excluded.source,
                    posted_at=excluded.posted_at,
                    match_score=excluded.match_score,
                    ai_assessment=excluded.ai_assessment
            """, tuple(job.get(key, "") for key in [
                "id", "title", "company", "location", "description",
                "url", "source", "posted_at", "match_score", "ai_assessment"
            ]))


def get_jobs():
    with _connect() as con:
        rows = con.execute(
            "SELECT * FROM jobs ORDER BY match_score DESC, posted_at DESC"
        ).fetchall()

    return [dict(row) for row in rows]


def update_application(job_id, status):
    with _connect() as con:
        con.execute(
            "UPDATE jobs SET application_status=? WHERE id=?",
            (status, job_id)
        )
