"""SQLite storage for roster data."""

import json
import sqlite3
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)
DB_PATH = Path(__file__).parent / "spotter.db"


def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables if they don't exist."""
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS rosters (
            team_abbr TEXT NOT NULL,
            players_json TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (team_abbr)
        );
        CREATE TABLE IF NOT EXISTS scrape_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_abbr TEXT NOT NULL,
            status TEXT NOT NULL,
            player_count INTEGER DEFAULT 0,
            error TEXT,
            scraped_at TEXT NOT NULL
        );
    """)
    conn.commit()
    conn.close()
    logger.info("Database initialized")


def save_roster(team_abbr: str, players: list[dict]):
    """Save or update a team's roster."""
    conn = get_db()
    now = datetime.utcnow().isoformat()
    conn.execute(
        "INSERT OR REPLACE INTO rosters (team_abbr, players_json, updated_at) VALUES (?, ?, ?)",
        (team_abbr, json.dumps(players), now)
    )
    conn.execute(
        "INSERT INTO scrape_log (team_abbr, status, player_count, scraped_at) VALUES (?, ?, ?, ?)",
        (team_abbr, "success", len(players), now)
    )
    conn.commit()
    conn.close()


def log_scrape_error(team_abbr: str, error: str):
    conn = get_db()
    now = datetime.utcnow().isoformat()
    conn.execute(
        "INSERT INTO scrape_log (team_abbr, status, error, scraped_at) VALUES (?, ?, ?, ?)",
        (team_abbr, "error", error, now)
    )
    conn.commit()
    conn.close()


def get_roster(team_abbr: str) -> dict | None:
    """Get a team's roster. Returns {players, updated_at} or None."""
    conn = get_db()
    row = conn.execute(
        "SELECT players_json, updated_at FROM rosters WHERE team_abbr = ?",
        (team_abbr,)
    ).fetchone()
    conn.close()

    if row:
        return {
            "players": json.loads(row["players_json"]),
            "updated_at": row["updated_at"]
        }
    return None


def get_all_teams_status() -> list[dict]:
    """Get scrape status for all teams."""
    conn = get_db()
    rows = conn.execute(
        "SELECT team_abbr, updated_at, json_array_length(players_json) as count FROM rosters"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
