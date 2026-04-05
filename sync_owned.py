#!/usr/bin/env python3

import os, json, logging, re
from pathlib import Path
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# ---------- CONFIG ----------
CFG_PATH = Path("config.json")
cfg = json.loads(CFG_PATH.read_text()) if CFG_PATH.exists() else {}

def get(k, default=""):
    return os.environ.get(k) or cfg.get(k) or default

HTB_TOKEN      = get("HTB_TOKEN")
HTB_PROFILE_ID = get("HTB_PROFILE_ID")
THM_USER_ID    = get("THM_USER_ID")
ABOUT_ME_FILE  = Path("README.md")

ASSETS_DIR = Path("assets")
ASSETS_DIR.mkdir(parents=True, exist_ok=True)

STATE_FILE = Path("state.json")

DIFFICULTY = ["easy", "medium", "hard", "insane"]

# ---------- STATE ----------
def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    s = {"htb_machines": {}, "thm_rooms": {}}
    STATE_FILE.write_text(json.dumps(s, indent=2))
    return s

def save_state(s):
    STATE_FILE.write_text(json.dumps(s, indent=2))

# ---------- HTTP ----------
def safe_get(url, headers=None, params=None):
    hdr = {"User-Agent": "curl"}
    if headers:
        hdr.update(headers)
    r = requests.get(url, headers=hdr, params=params, timeout=20)
    r.raise_for_status()
    return r

def slug(s):
    return re.sub(r"[^a-zA-Z0-9_-]", "_", s)

# ---------- SVG ----------
def _pill(x_label, label, color, x_pill, count):
    return f"""  <text x="{x_label}" y="67" text-anchor="start" font-family="sans-serif" font-size="22" font-weight="500" letter-spacing="0.05em" fill="{color}">{label}</text>
  <rect x="{x_pill}" y="46" width="42" height="26" rx="13" fill="{color}" fill-opacity="0.15"/>
  <text x="{x_pill + 21}" y="64" text-anchor="middle" font-family="sans-serif" font-size="20" font-weight="600" fill="{color}" fill-opacity="0.75">{count}</text>"""

def generate_svg(counts: dict, output: Path):
    svg = f"""<svg width="100%" viewBox="0 0 680 120" xmlns="http://www.w3.org/2000/svg">
  <line x1="0" y1="60" x2="680" y2="60" stroke="#808080" stroke-opacity="0.5" stroke-width="1"/>
  <line x1="170" y1="30" x2="170" y2="90" stroke="#808080" stroke-opacity="0.5" stroke-width="1"/>
  <line x1="340" y1="30" x2="340" y2="90" stroke="#808080" stroke-opacity="0.5" stroke-width="1"/>
  <line x1="510" y1="30" x2="510" y2="90" stroke="#808080" stroke-opacity="0.5" stroke-width="1"/>
{_pill(28,  "Insane", "#a855f7", 114, counts.get("insane", 0))}
{_pill(198, "Hard",   "#ef4444", 252, counts.get("hard",   0))}
{_pill(356, "Medium", "#eab308", 432, counts.get("medium", 0))}
{_pill(530, "Easy",   "#22c55e", 584, counts.get("easy",   0))}
</svg>"""
    output.write_text(svg, encoding="utf-8")
    logging.info("SVG written → %s", output)

# ---------- THM ----------
THM_API = "https://tryhackme.com/api/v2/public-profile/completed-rooms"

def fetch_thm_rooms():
    r = safe_get(THM_API, params={"user": THM_USER_ID, "limit": 100, "page": 1})
    return r.json()["data"]["docs"]

# ---------- HTB ----------
HTB_ACTIVITY       = "https://labs.hackthebox.com/api/v4/profile/activity/{}"
HTB_MACHINE_PROFILE = "https://labs.hackthebox.com/api/v4/machine/profile/{}"

def auth_headers():
    return {"Authorization": f"Bearer {HTB_TOKEN}"} if HTB_TOKEN else {}

def fetch_htb_activity():
    return safe_get(HTB_ACTIVITY.format(HTB_PROFILE_ID), headers=auth_headers()).json()["profile"]["activity"]

def fetch_htb_machine(mid):
    return safe_get(HTB_MACHINE_PROFILE.format(mid), headers=auth_headers()).json()["info"]

def derive_htb(activity):
    machines = {}
    for a in activity:
        if a["object_type"] == "machine":
            machines.setdefault(a["id"], set()).add(a["type"])
    return [mid for mid, flags in machines.items() if {"user", "root"} <= flags]

# ---------- COUNT ----------
def count_by_difficulty(items):
    counts = {d: 0 for d in DIFFICULTY}
    for v in items:
        d = v["difficulty"].lower()
        if d in counts:
            counts[d] += 1
    return counts

# ---------- MARKDOWN ----------
START = "<!-- OWNED_SECTION_START -->"
END   = "<!-- OWNED_SECTION_END -->"

def insert_block(path, content):
    block = f"{START}\n{content}\n{END}"
    txt = path.read_text(encoding="utf-8") if path.exists() else ""
    if START in txt:
        txt = re.sub(f"{START}.*?{END}", block, txt, flags=re.S)
    else:
        txt += "\n\n" + block
    path.write_text(txt, encoding="utf-8")

# ---------- MAIN ----------
def main():
    state = load_state()

    # --- THM ---
    for r in fetch_thm_rooms():
        code = r["code"]
        if code in state["thm_rooms"]:
            continue
        diff = r["difficulty"]
        if diff.lower() not in DIFFICULTY:
            continue
        state["thm_rooms"][code] = {"name": r["title"], "difficulty": diff.title()}

    # --- HTB ---
    activity   = fetch_htb_activity()
    machine_ids = derive_htb(activity)

    for mid in machine_ids:
        if str(mid) in state["htb_machines"]:
            continue
        info = fetch_htb_machine(mid)
        name = info.get("name", f"machine_{mid}")
        diff = info.get("difficultyText", "unknown")
        if diff.lower() not in DIFFICULTY:
            continue
        state["htb_machines"] = {
            str(mid): {"name": name, "difficulty": diff.title()},
            **state["htb_machines"]
        }

    save_state(state)

    # --- COUNTS & SVGs ---
    htb_counts   = count_by_difficulty(state["htb_machines"].values())
    thm_counts   = count_by_difficulty(state["thm_rooms"].values())

    generate_svg(htb_counts,   ASSETS_DIR / "htb_bar.svg")
    generate_svg(thm_counts,   ASSETS_DIR / "thm_bar.svg")

    # --- README ---
    md = [
        "## 🗡️ Owned Machines",
        "\n**HackTheBox**\n",
        "<img src='assets/htb_bar.svg' width='100%'>\n",
        "**TryHackMe**\n",
        "<img src='assets/thm_bar.svg' width='100%'>\n",
    ]

    insert_block(ABOUT_ME_FILE, "\n".join(md))
    logging.info("DONE — THM: %d | HTB: %d", len(state["thm_rooms"]), len(state["htb_machines"]))

if __name__ == "__main__":
    main()
