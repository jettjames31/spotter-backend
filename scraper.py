"""
Scraper for NFL team websites using Selenium.
NFL team sites render roster tables with JavaScript, so we need a headless browser.
All 32 sites use the same CMS, so the HTML structure is consistent once rendered.

Data enrichment from ourlads.com for draft info + original team.
"""

import logging
import re
import time
from typing import Optional

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

logger = logging.getLogger(__name__)


def get_driver():
    """Create a headless Chrome browser instance."""
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    try:
        driver = webdriver.Chrome(options=options)
        return driver
    except Exception as e:
        logger.error(f"Failed to create Chrome driver: {e}")
        raise


def scrape_roster(url: str, driver=None) -> list[dict]:
    """
    Scrape the roster table from an NFL team site using Selenium.
    Returns a list of player dicts.
    """
    own_driver = driver is None
    if own_driver:
        driver = get_driver()

    players = []
    try:
        logger.info(f"Loading {url}...")
        driver.get(url)

        # Wait for roster table to load (up to 15 seconds)
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "table tbody tr td"))
        )
        # Extra wait for full render
        time.sleep(2)

        # Find all table rows
        rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")

        for row in rows:
            cells = row.find_elements(By.TAG_NAME, "td")
            if len(cells) < 7:
                continue

            # Extract text from each cell
            name = cells[0].text.strip()
            number = cells[1].text.strip()
            position = cells[2].text.strip()
            height = cells[3].text.strip()
            weight = cells[4].text.strip()
            age = cells[5].text.strip()
            experience = cells[6].text.strip()
            college = cells[7].text.strip() if len(cells) > 7 else ""

            # Skip header rows or empty
            if not name or name.lower() == "player":
                continue

            # Clean number
            try:
                number = int(number) if number else 0
            except ValueError:
                number = 0

            # Clean age
            try:
                age = int(age) if age else 0
            except ValueError:
                age = 0

            players.append({
                "name": name,
                "number": number,
                "position": position,
                "height": height,
                "weight": weight,
                "age": age,
                "experience": experience,
                "college": college,
                "starter": False,
                "prevTeam": "",
                "draft": "",
            })

        logger.info(f"Scraped {len(players)} players from {url}")

    except Exception as e:
        logger.error(f"Error scraping {url}: {e}")
    finally:
        if own_driver:
            driver.quit()

    return players


def scrape_depth_chart(url: str, driver=None) -> dict:
    """
    Scrape the depth chart from an NFL team site.
    Returns dict mapping position -> list of player names (first = starter).
    """
    own_driver = driver is None
    if own_driver:
        driver = get_driver()

    depth = {}
    try:
        logger.info(f"Loading depth chart {url}...")
        driver.get(url)

        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "table tbody tr td"))
        )
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
                # Try to find links first (player names are usually links)
                links = cell.find_elements(By.TAG_NAME, "a")
                if links:
                    for link in links:
                        name = link.text.strip()
                        if name:
                            players_at_pos.append(name)
                else:
                    text = cell.text.strip()
                    if text:
                        players_at_pos.append(text)

            if players_at_pos:
                depth[pos] = players_at_pos

        logger.info(f"Scraped depth chart: {len(depth)} positions from {url}")

    except Exception as e:
        logger.error(f"Error scraping depth chart {url}: {e}")
    finally:
        if own_driver:
            driver.quit()

    return depth


def merge_starter_info(players: list[dict], depth_chart: dict) -> list[dict]:
    """Mark players as starters based on depth chart (first at each position)."""
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


# ═══════════════ OURLADS ENRICHMENT ═══════════════

# Map our team abbreviations -> ourlads URL abbreviations
OURLADS_TEAM_MAP = {
    "ARI": "ARZ", "ATL": "ATL", "BAL": "BAL", "BUF": "BUF",
    "CAR": "CAR", "CHI": "CHI", "CIN": "CIN", "CLE": "CLE",
    "DAL": "DAL", "DEN": "DEN", "DET": "DET", "GB": "GB",
    "HOU": "HOU", "IND": "IND", "JAX": "JAX", "KC": "KC",
    "LAC": "SD", "LAR": "RAM", "LV": "LV", "MIA": "MIA",
    "MIN": "MIN", "NE": "NE", "NO": "NO", "NYG": "NYG",
    "NYJ": "NYJ", "PHI": "PHI", "PIT": "PIT", "SEA": "SEA",
    "SF": "SF", "TB": "TB", "TEN": "TEN", "WAS": "WAS",
}

# Map ourlads orig team abbreviations back to full team names
OURLADS_ORIG_TEAM_NAMES = {
    "ARZ": "Arizona Cardinals", "ATL": "Atlanta Falcons",
    "BAL": "Baltimore Ravens", "BUF": "Buffalo Bills",
    "CAR": "Carolina Panthers", "CHI": "Chicago Bears",
    "CIN": "Cincinnati Bengals", "CLE": "Cleveland Browns",
    "DAL": "Dallas Cowboys", "DEN": "Denver Broncos",
    "DET": "Detroit Lions", "GB": "Green Bay Packers",
    "HOU": "Houston Texans", "IND": "Indianapolis Colts",
    "JAX": "Jacksonville Jaguars", "KC": "Kansas City Chiefs",
    "SD": "Los Angeles Chargers", "LAC": "Los Angeles Chargers",
    "RAM": "Los Angeles Rams", "LAR": "Los Angeles Rams",
    "LV": "Las Vegas Raiders", "OAK": "Las Vegas Raiders",
    "MIA": "Miami Dolphins", "MIN": "Minnesota Vikings",
    "NE": "New England Patriots", "NO": "New Orleans Saints",
    "NYG": "New York Giants", "NYJ": "New York Jets",
    "PHI": "Philadelphia Eagles", "PIT": "Pittsburgh Steelers",
    "SEA": "Seattle Seahawks", "SF": "San Francisco 49ers",
    "TB": "Tampa Bay Buccaneers", "TEN": "Tennessee Titans",
    "WAS": "Washington Commanders", "STL": "Los Angeles Rams",
}


def parse_ourlads_draft(draft_str: str) -> str:
    """
    Parse ourlads draft status column into a readable format.
    Input examples:
      "23 01 031"  ->  "2023 R1 P31"
      "22 CFA"     ->  "UDFA"
      "17 07 233"  ->  "2017 R7 P233"
      "25 05 156"  ->  "2025 R5 P156"
      "20 CFA"     ->  "UDFA"
    """
    draft_str = draft_str.strip()
    if not draft_str:
        return ""

    # Check for undrafted / college free agent
    if "CFA" in draft_str.upper() or "FA" in draft_str.upper():
        return "UDFA"

    # Try to parse "YY RR PPP" format
    parts = draft_str.split()
    if len(parts) >= 3:
        try:
            year = parts[0]
            rnd = parts[1]
            pick = parts[2]

            # Convert 2-digit year to 4-digit
            if len(year) == 2:
                yr_int = int(year)
                year = f"20{year}" if yr_int < 50 else f"19{year}"

            rnd_int = int(rnd)
            pick_int = int(pick)
            return f"{year} R{rnd_int} P{pick_int}"
        except (ValueError, IndexError):
            pass

    # Try regex as fallback
    m = re.match(r"(\d{2,4})\s+(\d{1,2})\s+(\d{1,3})", draft_str)
    if m:
        year = m.group(1)
        if len(year) == 2:
            year = f"20{year}"
        return f"{year} R{int(m.group(2))} P{int(m.group(3))}"

    return draft_str  # Return as-is if we can't parse


def normalize_name(name: str) -> str:
    """Normalize a player name for fuzzy matching."""
    # Handle "Last, First" format from ourlads
    if "," in name:
        parts = name.split(",", 1)
        name = f"{parts[1].strip()} {parts[0].strip()}"
    # Lowercase, strip suffixes like Jr., Sr., III, II
    name = name.lower().strip()
    name = re.sub(r'\s+(jr\.?|sr\.?|iii|ii|iv|v)$', '', name, flags=re.IGNORECASE)
    # Remove periods and extra spaces
    name = name.replace(".", "").replace("  ", " ")
    return name


def enrich_with_ourlads(players: list[dict], team_abbr: str, driver=None) -> list[dict]:
    """
    Enrich players with draft info and original team from ourlads.com roster page.
    
    Ourlads roster table columns:
    #, Player, Pos., DOB, Age, HT, WT, School, Orig. Team, Draft Status, NFL Exp.
    """
    ourlads_abbr = OURLADS_TEAM_MAP.get(team_abbr, team_abbr)
    url = f"https://www.ourlads.com/nfldepthcharts/roster/{ourlads_abbr}"

    own_driver = driver is None
    if own_driver:
        driver = get_driver()

    try:
        logger.info(f"Enriching from Ourlads: {url}")
        driver.get(url)

        # Wait for the roster table
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "table"))
        )
        time.sleep(2)

        # Find all tables, the roster table has columns like #, Player, Pos., etc.
        tables = driver.find_elements(By.CSS_SELECTOR, "table")
        roster_table = None
        for table in tables:
            headers = table.find_elements(By.CSS_SELECTOR, "th")
            header_text = " ".join([h.text.strip().lower() for h in headers])
            if "player" in header_text and ("draft" in header_text or "orig" in header_text):
                roster_table = table
                break

        if not roster_table:
            # Fallback: try the largest table on the page
            tables_with_rows = [(t, len(t.find_elements(By.CSS_SELECTOR, "tr"))) for t in tables]
            if tables_with_rows:
                roster_table = max(tables_with_rows, key=lambda x: x[1])[0]

        if not roster_table:
            logger.warning(f"Could not find roster table on {url}")
            return players

        rows = roster_table.find_elements(By.CSS_SELECTOR, "tr")

        # Build lookup: normalized name -> {draft, origTeam}
        ourlads_data = {}

        for row in rows:
            cells = row.find_elements(By.TAG_NAME, "td")
            if len(cells) < 10:
                continue

            # Columns: #(0), Player(1), Pos(2), DOB(3), Age(4), HT(5), WT(6), School(7), Orig.Team(8), Draft(9), Exp(10)
            try:
                player_cell = cells[1]
                # Player name might be in a link
                links = player_cell.find_elements(By.TAG_NAME, "a")
                raw_name = links[0].text.strip() if links else player_cell.text.strip()

                if not raw_name or raw_name.lower() in ("player", "active players", "practice squad", "reserve"):
                    continue

                orig_team_text = cells[8].text.strip() if len(cells) > 8 else ""
                draft_text = cells[9].text.strip() if len(cells) > 9 else ""

                norm = normalize_name(raw_name)
                ourlads_data[norm] = {
                    "draft": parse_ourlads_draft(draft_text),
                    "origTeam": orig_team_text,
                }
            except Exception:
                continue

        # Match and merge into our players
        enriched_draft = 0
        enriched_prev = 0

        for p in players:
            norm = normalize_name(p["name"])

            match = ourlads_data.get(norm)

            # Try last-name-only matching if exact match fails
            if not match:
                last_name = norm.split()[-1] if norm.split() else ""
                first_initial = norm[0] if norm else ""
                for oname, odata in ourlads_data.items():
                    oparts = oname.split()
                    if oparts and oparts[-1] == last_name:
                        # Check first initial matches too
                        if oparts[0] and oparts[0][0] == first_initial:
                            match = odata
                            break

            if match:
                # Draft info
                if match["draft"] and not p.get("draft"):
                    p["draft"] = match["draft"]
                    enriched_draft += 1

                # Previous team: if orig team differs from current team
                orig = match.get("origTeam", "")
                if orig and not p.get("prevTeam"):
                    # Convert ourlads abbr to full team name
                    orig_full = OURLADS_ORIG_TEAM_NAMES.get(orig, "")
                    # Only set prevTeam if it's a different team
                    our_abbr_for_orig = None
                    for our_key, ol_val in OURLADS_TEAM_MAP.items():
                        if ol_val == orig:
                            our_abbr_for_orig = our_key
                            break
                    if our_abbr_for_orig and our_abbr_for_orig != team_abbr and orig_full:
                        p["prevTeam"] = orig_full
                        enriched_prev += 1

        logger.info(f"Ourlads enrichment for {team_abbr}: {enriched_draft} draft, {enriched_prev} prevTeam out of {len(players)} players")

    except Exception as e:
        logger.error(f"Ourlads enrichment failed for {team_abbr}: {e}")
    finally:
        if own_driver:
            driver.quit()

    return players


# ═══════════════ LEGACY ESPN ENRICHMENT (KEPT AS FALLBACK) ═══════════════

ESPN_TEAM_MAP = {
    "ARI":"ari","ATL":"atl","BAL":"bal","BUF":"buf","CAR":"car","CHI":"chi",
    "CIN":"cin","CLE":"cle","DAL":"dal","DEN":"den","DET":"det","GB":"gb",
    "HOU":"hou","IND":"ind","JAX":"jax","KC":"kc","LV":"lv","LAC":"lac",
    "LAR":"lar","MIA":"mia","MIN":"min","NE":"ne","NO":"no","NYG":"nyg",
    "NYJ":"nyj","PHI":"phi","PIT":"pit","SF":"sf","SEA":"sea","TB":"tb",
    "TEN":"ten","WAS":"wsh"
}

def enrich_with_espn(players: list[dict], team_abbr: str, driver=None) -> list[dict]:
    """Enrich players with draft info from ESPN roster page (fallback)."""
    espn_abbr = ESPN_TEAM_MAP.get(team_abbr, team_abbr.lower())
    url = f"https://www.espn.com/nfl/team/roster/_/name/{espn_abbr}"

    own_driver = driver is None
    if own_driver:
        driver = get_driver()

    try:
        logger.info(f"Enriching from ESPN: {url}")
        driver.get(url)
        time.sleep(3)

        rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
        espn_data = {}

        for row in rows:
            cells = row.find_elements(By.TAG_NAME, "td")
            if len(cells) < 3:
                continue

            name_el = row.find_elements(By.CSS_SELECTOR, "a.AnchorLink")
            if not name_el:
                continue
            name = name_el[0].text.strip()
            if not name:
                continue

            cell_texts = [c.text.strip() for c in cells]

            draft = ""
            for ct in cell_texts:
                if "Undrafted" in ct or "UDFA" in ct:
                    draft = "UDFA"
                    break
                m = re.search(r"'?(\d{2,4})\s*[:,]?\s*R(?:d|ound)?\s*(\d+)\s*[:,]?\s*P(?:ick)?\s*(\d+)", ct, re.IGNORECASE)
                if m:
                    yr = m.group(1)
                    if len(yr) == 2:
                        yr = "20" + yr
                    draft = f"{yr} R{m.group(2)} P{m.group(3)}"
                    break

            if name.lower() not in espn_data:
                espn_data[name.lower()] = {"draft": draft}

        enriched = 0
        for p in players:
            pname = p["name"].lower()
            if pname in espn_data and espn_data[pname].get("draft") and not p.get("draft"):
                p["draft"] = espn_data[pname]["draft"]
                enriched += 1

        logger.info(f"ESPN enriched {enriched}/{len(players)} players with draft info")

    except Exception as e:
        logger.error(f"ESPN enrichment failed: {e}")
    finally:
        if own_driver:
            driver.quit()

    return players


# ═══════════════ MAIN PIPELINE ═══════════════

def scrape_team(roster_url: str, depth_chart_url: str, team_abbr: str = "") -> list[dict]:
    """Full pipeline: scrape roster + depth chart + ourlads enrichment with shared browser."""
    driver = get_driver()
    try:
        # 1. Scrape roster from official team site
        players = scrape_roster(roster_url, driver)
        if not players:
            return []

        # 2. Scrape depth chart for starter info
        depth = scrape_depth_chart(depth_chart_url, driver)
        if depth:
            players = merge_starter_info(players, depth)

        # 3. Enrich with ourlads (draft info + previous team)
        if team_abbr:
            players = enrich_with_ourlads(players, team_abbr, driver)

            # 4. Fallback to ESPN for any players still missing draft info
            players_missing_draft = sum(1 for p in players if not p.get("draft"))
            if players_missing_draft > len(players) * 0.5:
                logger.info(f"Many players missing draft info ({players_missing_draft}), trying ESPN fallback...")
                players = enrich_with_espn(players, team_abbr, driver)

        return players
    finally:
        driver.quit()
