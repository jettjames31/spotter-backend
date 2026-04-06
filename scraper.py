"""
Scraper for NFL team websites using Selenium + ESPN API enrichment.

Pipeline:
1. Official team sites (Selenium) -> roster data, height/weight/age/college
2. Official team sites (Selenium) -> depth chart for starter info
3. ESPN JSON API (requests) -> draft info, injuries, previous team
   No Selenium needed for ESPN! Plain HTTP requests to public API.
"""

import logging
import re
import time

import requests as http_requests

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

logger = logging.getLogger(__name__)


def get_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    try:
        return webdriver.Chrome(options=options)
    except Exception as e:
        logger.error(f"Failed to create Chrome driver: {e}")
        raise


def scrape_roster(url, driver=None):
    own_driver = driver is None
    if own_driver:
        driver = get_driver()
    players = []
    try:
        logger.info(f"Loading {url}...")
        driver.get(url)
        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.CSS_SELECTOR, "table tbody tr td")))
        time.sleep(2)
        rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
        for row in rows:
            cells = row.find_elements(By.TAG_NAME, "td")
            if len(cells) < 7:
                continue
            name = cells[0].text.strip()
            number = cells[1].text.strip()
            position = cells[2].text.strip()
            height = cells[3].text.strip()
            weight = cells[4].text.strip()
            age = cells[5].text.strip()
            experience = cells[6].text.strip()
            college = cells[7].text.strip() if len(cells) > 7 else ""
            if not name or name.lower() == "player":
                continue
            try:
                number = int(number) if number else 0
            except ValueError:
                number = 0
            try:
                age = int(age) if age else 0
            except ValueError:
                age = 0
            players.append({
                "name": name, "number": number, "position": position,
                "height": height, "weight": weight, "age": age,
                "experience": experience, "college": college,
                "starter": False, "prevTeam": "", "draft": "",
                "injury_status": "", "injury_detail": "",
            })
        logger.info(f"Scraped {len(players)} players from {url}")
    except Exception as e:
        logger.error(f"Error scraping {url}: {e}")
    finally:
        if own_driver:
            driver.quit()
    return players


def scrape_depth_chart(url, driver=None):
    own_driver = driver is None
    if own_driver:
        driver = get_driver()
    depth = {}
    try:
        logger.info(f"Loading depth chart {url}...")
        driver.get(url)
        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.CSS_SELECTOR, "table tbody tr td")))
        time.sleep(2)
        rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
        for row in rows:
            cells = row.find_elements(By.TAG_NAME, "td")
            if len(cells) < 2:
                continue
            pos = cells[0].text.strip()
            if not pos or pos.lower() == "position":
                continue
            players_at_pos = []
            for cell in cells[1:]:
                links = cell.find_elements(By.TAG_NAME, "a")
                if links:
                    for link in links:
                        n = link.text.strip()
                        if n:
                            players_at_pos.append(n)
                else:
                    t = cell.text.strip()
                    if t:
                        players_at_pos.append(t)
            if players_at_pos:
                depth[pos] = players_at_pos
        logger.info(f"Scraped depth chart: {len(depth)} positions from {url}")
    except Exception as e:
        logger.error(f"Error scraping depth chart {url}: {e}")
    finally:
        if own_driver:
            driver.quit()
    return depth


def merge_starter_info(players, depth_chart):
    starter_names = set()
    for pos, names in depth_chart.items():
        if names:
            starter_names.add(names[0].lower().strip())
    for player in players:
        if player["name"].lower().strip() in starter_names:
            player["starter"] = True
    starters = sum(1 for p in players if p["starter"])
    logger.info(f"Marked {starters} starters out of {len(players)} players")
    return players


# =========== ESPN API ENRICHMENT (plain HTTP, no Selenium) ===========

ESPN_TEAM_IDS = {
    "ARI": 22, "ATL": 1, "BAL": 33, "BUF": 2,
    "CAR": 29, "CHI": 3, "CIN": 4, "CLE": 5,
    "DAL": 6, "DEN": 7, "DET": 8, "GB": 9,
    "HOU": 34, "IND": 11, "JAX": 30, "KC": 12,
    "LV": 13, "LAC": 24, "LAR": 14, "MIA": 15,
    "MIN": 16, "NE": 17, "NO": 18, "NYG": 19,
    "NYJ": 20, "PHI": 21, "PIT": 23, "SEA": 26,
    "SF": 25, "TB": 27, "TEN": 10, "WAS": 28,
}

ESPN_TEAM_NAMES = {
    22: "Arizona Cardinals", 1: "Atlanta Falcons", 33: "Baltimore Ravens",
    2: "Buffalo Bills", 29: "Carolina Panthers", 3: "Chicago Bears",
    4: "Cincinnati Bengals", 5: "Cleveland Browns", 6: "Dallas Cowboys",
    7: "Denver Broncos", 8: "Detroit Lions", 9: "Green Bay Packers",
    34: "Houston Texans", 11: "Indianapolis Colts", 30: "Jacksonville Jaguars",
    12: "Kansas City Chiefs", 13: "Las Vegas Raiders", 24: "Los Angeles Chargers",
    14: "Los Angeles Rams", 15: "Miami Dolphins", 16: "Minnesota Vikings",
    17: "New England Patriots", 18: "New Orleans Saints", 19: "New York Giants",
    20: "New York Jets", 21: "Philadelphia Eagles", 23: "Pittsburgh Steelers",
    26: "Seattle Seahawks", 25: "San Francisco 49ers", 27: "Tampa Bay Buccaneers",
    10: "Tennessee Titans", 28: "Washington Commanders",
}


def normalize_name(name):
    name = name.lower().strip()
    name = re.sub(r'\s+(jr\.?|sr\.?|iii|ii|iv|v)$', '', name, flags=re.IGNORECASE)
    name = name.replace(".", "").replace("'", "").replace("\u2019", "")
    return name


def enrich_with_espn_api(players, team_abbr):
    """Enrich players with draft, injury, prevTeam from ESPN's public JSON API."""
    espn_id = ESPN_TEAM_IDS.get(team_abbr)
    if not espn_id:
        logger.warning(f"No ESPN team ID for {team_abbr}")
        return players

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    espn_data = {}

    # Step 1: Fetch ESPN roster JSON
    try:
        logger.info(f"Fetching ESPN API roster for {team_abbr} (ID {espn_id})...")
        r = http_requests.get(
            f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/{espn_id}/roster",
            timeout=15, headers=headers
        )
        r.raise_for_status()
        data = r.json()

        for group in data.get("athletes", []):
            for athlete in group.get("items", []):
                name = athlete.get("fullName") or athlete.get("displayName", "")
                if not name:
                    continue
                norm = normalize_name(name)

                # Draft
                draft = ""
                di = athlete.get("draft", {})
                if di and isinstance(di, dict):
                    yr = di.get("year", "")
                    rnd = di.get("round", "")
                    pick = di.get("selection", "")
                    if yr and rnd:
                        draft = f"{yr} R{rnd} P{pick}" if pick else f"{yr} R{rnd}"

                # Injury
                injury_status = ""
                injury_detail = ""
                injuries = athlete.get("injuries", [])
                if injuries:
                    inj = injuries[0]
                    injury_status = inj.get("status", "")
                    itype = inj.get("type", {})
                    injury_detail = itype.get("description", "") if isinstance(itype, dict) else ""

                # Status
                si = athlete.get("status", {})
                espn_status = si.get("name", "Active") if isinstance(si, dict) else "Active"

                espn_data[norm] = {
                    "draft": draft,
                    "injury_status": injury_status,
                    "injury_detail": injury_detail,
                    "espn_status": espn_status,
                    "espn_id": athlete.get("id", ""),
                }

        logger.info(f"ESPN roster: {len(espn_data)} athletes for {team_abbr}")
    except Exception as e:
        logger.error(f"ESPN roster fetch failed for {team_abbr}: {e}")
        return players

    # Step 2: Match and merge
    enriched_draft = 0
    enriched_injury = 0

    for p in players:
        norm = normalize_name(p["name"])
        match = espn_data.get(norm)

        # Fallback: last name + first initial
        if not match:
            parts = norm.split()
            if len(parts) >= 2:
                last = parts[-1]
                fi = parts[0][0] if parts[0] else ""
                for en, ed in espn_data.items():
                    ep = en.split()
                    if ep and ep[-1] == last and ep[0] and ep[0][0] == fi:
                        match = ed
                        break

        if match:
            if match["draft"] and not p.get("draft"):
                p["draft"] = match["draft"]
                enriched_draft += 1
            if match["injury_status"]:
                p["injury_status"] = match["injury_status"]
                p["injury_detail"] = match.get("injury_detail", "")
                enriched_injury += 1
            es = match.get("espn_status", "")
            if es and es.lower() != "active":
                if "injured" in es.lower():
                    p["status"] = "IR"
                elif "practice" in es.lower():
                    p["status"] = "Practice Squad"

    logger.info(f"ESPN enrichment for {team_abbr}: {enriched_draft} draft, {enriched_injury} injuries")

    # Step 3: Individual athlete lookups for remaining draft info + prevTeam
    missing = [p for p in players if not p.get("draft")]
    if missing:
        logger.info(f"Fetching individual athlete details for {min(len(missing), 30)} players...")
        fetched = 0
        for p in missing[:30]:
            norm = normalize_name(p["name"])
            match = espn_data.get(norm)
            if not match:
                parts = norm.split()
                if len(parts) >= 2:
                    last = parts[-1]
                    fi = parts[0][0] if parts[0] else ""
                    for en, ed in espn_data.items():
                        ep = en.split()
                        if ep and ep[-1] == last and ep[0] and ep[0][0] == fi:
                            match = ed
                            break
            if not match or not match.get("espn_id"):
                continue
            aid = match["espn_id"]
            try:
                ar = http_requests.get(
                    f"https://site.web.api.espn.com/apis/common/v3/sports/football/nfl/athletes/{aid}/overview",
                    timeout=10, headers=headers
                )
                if ar.status_code == 200:
                    ad = ar.json()
                    bio = ad.get("athlete", {})
                    di = bio.get("draft", {})
                    if di and isinstance(di, dict):
                        yr = di.get("year", "")
                        rnd = di.get("round", "")
                        pick = di.get("selection", "")
                        if yr and rnd:
                            p["draft"] = f"{yr} R{rnd} P{pick}" if pick else f"{yr} R{rnd}"
                            fetched += 1
                        # prevTeam from draft team
                        dt = di.get("team", {})
                        dtid = dt.get("id") if isinstance(dt, dict) else None
                        if dtid:
                            try:
                                dtid = int(dtid)
                            except (ValueError, TypeError):
                                dtid = None
                            if dtid and dtid != espn_id:
                                orig = ESPN_TEAM_NAMES.get(dtid, "")
                                if orig and not p.get("prevTeam"):
                                    p["prevTeam"] = orig
                time.sleep(0.3)
            except Exception:
                continue
        logger.info(f"Individual lookups: {fetched} additional draft records")

    return players


# =========== MAIN PIPELINE ===========

def scrape_team(roster_url, depth_chart_url, team_abbr=""):
    """Full pipeline: official site (Selenium) + ESPN API (HTTP requests)."""
    driver = get_driver()
    try:
        players = scrape_roster(roster_url, driver)
        if not players:
            return []
        depth = scrape_depth_chart(depth_chart_url, driver)
        if depth:
            players = merge_starter_info(players, depth)
    finally:
        driver.quit()

    # ESPN enrichment - no Selenium needed
    if team_abbr:
        players = enrich_with_espn_api(players, team_abbr)

    return players
