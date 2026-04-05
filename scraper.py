"""
Scraper for NFL team websites using Selenium.
NFL team sites render roster tables with JavaScript, so we need a headless browser.
All 32 sites use the same CMS, so the HTML structure is consistent once rendered.
"""

import logging
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
        logger.info("Make sure Chrome and chromedriver are installed.")
        logger.info("Install with: pip install chromedriver-autoinstaller")
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


def scrape_team(roster_url: str, depth_chart_url: str) -> list[dict]:
    """Full pipeline: scrape roster + depth chart with a shared browser session."""
    driver = get_driver()
    try:
        players = scrape_roster(roster_url, driver)
        if not players:
            return []

        depth = scrape_depth_chart(depth_chart_url, driver)
        if depth:
            players = merge_starter_info(players, depth)

        return players
    finally:
        driver.quit()
