"""All 32 NFL teams with their site URLs and metadata."""

TEAMS = {
    "ARI": {"name": "Arizona Cardinals", "site": "azcardinals.com", "color": "#97233F"},
    "ATL": {"name": "Atlanta Falcons", "site": "atlantafalcons.com", "color": "#A71930"},
    "BAL": {"name": "Baltimore Ravens", "site": "baltimoreravens.com", "color": "#241773"},
    "BUF": {"name": "Buffalo Bills", "site": "buffalobills.com", "color": "#00338D"},
    "CAR": {"name": "Carolina Panthers", "site": "panthers.com", "color": "#0085CA"},
    "CHI": {"name": "Chicago Bears", "site": "chicagobears.com", "color": "#0B162A"},
    "CIN": {"name": "Cincinnati Bengals", "site": "bengals.com", "color": "#FB4F14"},
    "CLE": {"name": "Cleveland Browns", "site": "clevelandbrowns.com", "color": "#311D00"},
    "DAL": {"name": "Dallas Cowboys", "site": "dallascowboys.com", "color": "#003594"},
    "DEN": {"name": "Denver Broncos", "site": "denverbroncos.com", "color": "#FB4F14"},
    "DET": {"name": "Detroit Lions", "site": "detroitlions.com", "color": "#0076B6"},
    "GB":  {"name": "Green Bay Packers", "site": "packers.com", "color": "#203731"},
    "HOU": {"name": "Houston Texans", "site": "houstontexans.com", "color": "#03202F"},
    "IND": {"name": "Indianapolis Colts", "site": "colts.com", "color": "#002C5F"},
    "JAX": {"name": "Jacksonville Jaguars", "site": "jaguars.com", "color": "#006778"},
    "KC":  {"name": "Kansas City Chiefs", "site": "chiefs.com", "color": "#E31837"},
    "LV":  {"name": "Las Vegas Raiders", "site": "raiders.com", "color": "#000000"},
    "LAC": {"name": "Los Angeles Chargers", "site": "chargers.com", "color": "#0080C6"},
    "LAR": {"name": "Los Angeles Rams", "site": "therams.com", "color": "#003594"},
    "MIA": {"name": "Miami Dolphins", "site": "miamidolphins.com", "color": "#008E97"},
    "MIN": {"name": "Minnesota Vikings", "site": "vikings.com", "color": "#4F2683"},
    "NE":  {"name": "New England Patriots", "site": "patriots.com", "color": "#002244"},
    "NO":  {"name": "New Orleans Saints", "site": "neworleanssaints.com", "color": "#D3BC8D"},
    "NYG": {"name": "New York Giants", "site": "giants.com", "color": "#0B2265"},
    "NYJ": {"name": "New York Jets", "site": "newyorkjets.com", "color": "#125740"},
    "PHI": {"name": "Philadelphia Eagles", "site": "philadelphiaeagles.com", "color": "#004C54"},
    "PIT": {"name": "Pittsburgh Steelers", "site": "steelers.com", "color": "#FFB612"},
    "SF":  {"name": "San Francisco 49ers", "site": "49ers.com", "color": "#AA0000"},
    "SEA": {"name": "Seattle Seahawks", "site": "seahawks.com", "color": "#002244"},
    "TB":  {"name": "Tampa Bay Buccaneers", "site": "buccaneers.com", "color": "#D50A0A"},
    "TEN": {"name": "Tennessee Titans", "site": "tennesseetitans.com", "color": "#0C2340"},
    "WAS": {"name": "Washington Commanders", "site": "commanders.com", "color": "#5A1414"},
}

def get_roster_url(abbr: str) -> str:
    site = TEAMS[abbr]["site"]
    return f"https://www.{site}/team/players-roster/"

def get_depth_chart_url(abbr: str) -> str:
    site = TEAMS[abbr]["site"]
    return f"https://www.{site}/team/depth-chart"
