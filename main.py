"""
Spotter Board API
=================
Endpoints:
  GET  /api/teams              → List all 32 teams with colors and scrape status
  GET  /api/roster/{abbr}      → Get roster for a team (from DB, scraped from official site)
  POST /api/scrape/{abbr}      → Force re-scrape a single team
  POST /api/scrape-all         → Scrape all 32 teams (runs in background)
  GET  /api/scrape-status      → Check if a scrape is currently running + progress
  GET  /api/health             → Health check

The scraper runs automatically every 6 hours to keep rosters fresh.
"""

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from threading import Thread

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler

from teams import TEAMS, get_roster_url, get_depth_chart_url
from scraper import scrape_team
from database import init_db, save_roster, get_roster, log_scrape_error, get_all_teams_status

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ── Scrape State ─────────────────────────────────────────

scrape_state = {
    "running": False,
    "started_at": None,
    "completed": 0,
    "total": 32,
    "current_team": "",
    "errors": [],
    "finished_at": None,
}


# ── Scrape Jobs ──────────────────────────────────────────

def scrape_single_team(abbr: str) -> dict:
    """Scrape one team and save to DB. Returns result summary."""
    logger.info(f"Scraping {abbr}...")
    try:
        roster_url = get_roster_url(abbr)
        depth_url = get_depth_chart_url(abbr)
        players = scrape_team(roster_url, depth_url, abbr)

        if players:
            save_roster(abbr, players)
            logger.info(f"✓ {abbr}: {len(players)} players saved")
            return {"team": abbr, "status": "ok", "players": len(players)}
        else:
            log_scrape_error(abbr, "No players found")
            return {"team": abbr, "status": "empty", "players": 0}

    except Exception as e:
        logger.error(f"✗ {abbr}: {e}")
        log_scrape_error(abbr, str(e))
        return {"team": abbr, "status": "error", "error": str(e)}


def scrape_all_teams():
    """Scrape all 32 teams. Called on schedule and on-demand."""
    global scrape_state
    scrape_state["running"] = True
    scrape_state["started_at"] = datetime.now(timezone.utc).isoformat()
    scrape_state["completed"] = 0
    scrape_state["total"] = len(TEAMS)
    scrape_state["errors"] = []
    scrape_state["finished_at"] = None

    logger.info("Starting full scrape of all 32 teams...")
    results = []
    for i, abbr in enumerate(TEAMS):
        scrape_state["current_team"] = abbr
        result = scrape_single_team(abbr)
        results.append(result)
        scrape_state["completed"] = i + 1
        if result["status"] == "error":
            scrape_state["errors"].append(abbr)

    ok = sum(1 for r in results if r["status"] == "ok")
    logger.info(f"Full scrape complete: {ok}/32 teams successful")

    scrape_state["running"] = False
    scrape_state["finished_at"] = datetime.now(timezone.utc).isoformat()
    scrape_state["current_team"] = ""
    return results


# ── App Lifecycle ────────────────────────────────────────

scheduler = BackgroundScheduler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    init_db()

    # Schedule automatic scraping every 6 hours
    scheduler.add_job(scrape_all_teams, "interval", hours=6, id="auto_scrape")
    scheduler.start()
    logger.info("Scheduler started — scraping every 6 hours")

    # Initial scrape in background (don't block startup)
    if not get_all_teams_status():
        Thread(target=scrape_all_teams, daemon=True).start()

    yield

    # Shutdown
    scheduler.shutdown()


# ── FastAPI App ──────────────────────────────────────────

app = FastAPI(
    title="Spotter Board API",
    description="Live NFL roster data for broadcast spotter boards",
    version="1.1.0",
    lifespan=lifespan,
)

# Allow frontend from any origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "spotter-board-api"}


@app.get("/api/teams")
def list_teams():
    """List all 32 teams with metadata and data freshness."""
    status_map = {s["team_abbr"]: s for s in get_all_teams_status()}
    result = []
    for abbr, info in TEAMS.items():
        entry = {
            "abbr": abbr,
            "name": info["name"],
            "color": info["color"],
            "site": info["site"],
            "hasData": abbr in status_map,
        }
        if abbr in status_map:
            entry["playerCount"] = status_map[abbr].get("count", 0)
            entry["updatedAt"] = status_map[abbr].get("updated_at", "")
        result.append(entry)
    return result


@app.get("/api/roster/{abbr}")
def get_team_roster(abbr: str):
    """Get the roster for a team. Returns players + metadata."""
    abbr = abbr.upper()
    if abbr not in TEAMS:
        raise HTTPException(404, f"Unknown team: {abbr}")

    data = get_roster(abbr)
    if not data:
        # No cached data — scrape now
        result = scrape_single_team(abbr)
        if result["status"] != "ok":
            raise HTTPException(503, f"Could not fetch roster for {abbr}. Try again.")
        data = get_roster(abbr)

    return {
        "team": {
            "abbr": abbr,
            "name": TEAMS[abbr]["name"],
            "color": TEAMS[abbr]["color"],
        },
        "players": data["players"],
        "updatedAt": data["updated_at"],
    }


@app.post("/api/scrape/{abbr}")
def force_scrape_team(abbr: str):
    """Force re-scrape a single team."""
    abbr = abbr.upper()
    if abbr not in TEAMS:
        raise HTTPException(404, f"Unknown team: {abbr}")
    result = scrape_single_team(abbr)
    return result


@app.post("/api/scrape-all")
def force_scrape_all():
    """Trigger a full scrape of all 32 teams (runs in background)."""
    if scrape_state["running"]:
        return {
            "status": "already_running",
            "message": "A scrape is already in progress",
            "completed": scrape_state["completed"],
            "total": scrape_state["total"],
            "current_team": scrape_state["current_team"],
        }
    Thread(target=scrape_all_teams, daemon=True).start()
    return {"status": "started", "message": "Scraping all 32 teams in background"}


@app.get("/api/scrape-status")
def get_scrape_status():
    """Check current scrape progress. Frontend polls this."""
    return {
        "running": scrape_state["running"],
        "completed": scrape_state["completed"],
        "total": scrape_state["total"],
        "current_team": scrape_state["current_team"],
        "started_at": scrape_state["started_at"],
        "finished_at": scrape_state["finished_at"],
        "errors": scrape_state["errors"],
    }


# ── Run ──────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
