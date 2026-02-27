#!/usr/bin/env python3

import os, json, logging, re
from pathlib import Path
import requests
from PIL import Image, ImageDraw

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# ---------- CONFIG ----------
CFG_PATH = Path("config.json")
cfg = json.loads(CFG_PATH.read_text()) if CFG_PATH.exists() else {}

def get(k, default=""):
    return os.environ.get(k) or cfg.get(k) or default

HTB_TOKEN = get("HTB_TOKEN")
HTB_PROFILE_ID = get("HTB_PROFILE_ID")
THM_USER_ID = get("THM_USER_ID")
ABOUT_ME_FILE = Path("README.md")

ASSETS_DIR = Path("assets")
HTB_ASSETS = ASSETS_DIR / "htb"
THM_ASSETS = ASSETS_DIR / "thm"
HTB_ASSETS.mkdir(parents=True, exist_ok=True)
THM_ASSETS.mkdir(parents=True, exist_ok=True)

STATE_FILE = Path("state.json")

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
BASE_HEADERS = {"User-Agent": "curl"}

def safe_get(url, headers=None, params=None):
    hdr = BASE_HEADERS.copy()
    if headers:
        hdr.update(headers)
    r = requests.get(url, headers=hdr, params=params, timeout=20)
    r.raise_for_status()
    return r

def download(url, dest: Path):
    if not url or dest.exists():
        return
    r = safe_get(url)
    dest.write_bytes(r.content)

def slug(s):
    return re.sub(r"[^a-zA-Z0-9_-]", "_", s)

# ---------- COLORS ----------
DIFFICULTY_COLOR = {
    "easy":    (76, 175, 80),
    "medium":  (255, 193, 7),
    "hard":    (244, 67, 54),
    "insane":  (156, 39, 176),
    "unknown": (33, 150, 243)
}

DIFFICULTY = [ "easy",  "medium", "hard", "insane",  ]


def add_border(src: Path, dst: Path, diff: str, border=8, radius=12):

    color = DIFFICULTY_COLOR.get(diff.lower(), DIFFICULTY_COLOR["unknown"])
    try:
        img = Image.open(src).convert("RGBA")
    except Exception:
        img = Image.new("RGBA", (120, 120), (0,0,0,0))
    w,h = img.size
    nw, nh = w + 2*border, h + 2*border
    mask = Image.new("L", (nw, nh), 0)
    d = ImageDraw.Draw(mask)
    d.rounded_rectangle([(0,0),(nw-1,nh-1)], radius=radius, fill=255)
    colored = Image.new("RGBA", (nw, nh), color + (255,))
    layer = Image.new("RGBA", (nw, nh), (0,0,0,0))
    layer.paste(colored, (0,0), mask)
    layer.paste(img, (border, border), img)
    layer.save(dst)

# ---------- THM ----------
THM_API = "https://tryhackme.com/api/v2/public-profile/completed-rooms"

def fetch_thm_rooms():
    r = safe_get(THM_API, params={"user": THM_USER_ID, "limit": 100, "page": 1})
    return r.json()["data"]["docs"]

# ---------- HTB ----------
HTB_ACTIVITY = "https://labs.hackthebox.com/api/v4/profile/activity/{}"
HTB_MACHINE_PROFILE = "https://labs.hackthebox.com/api/v4/machine/profile/{}"
HTB_V5_MACHINES = "https://labs.hackthebox.com/api/v5/machines"

def auth_headers():
    return {"Authorization": f"Bearer {HTB_TOKEN}"} if HTB_TOKEN else {}

def fetch_htb_activity():
    return safe_get(HTB_ACTIVITY.format(HTB_PROFILE_ID), headers=auth_headers()).json()["profile"]["activity"]

def fetch_htb_machine(mid):
    return safe_get(HTB_MACHINE_PROFILE.format(mid), headers=auth_headers()).json()["info"]

def get_htb_avatar_domain():
    try:
        data = safe_get(HTB_V5_MACHINES, headers=auth_headers()).json()["data"]
        for m in data:
            url = m.get("avatar", "")
            if url.startswith("http"):
                return url.split("/avatars/")[0]
    except Exception as e:
        logging.warning("Avatar domain extraction failed: %s", e)
    return ""

# ---------- DERIVE OWNED ----------
def derive_htb(activity):
    machines = {}
    for a in activity:
        if a["object_type"] == "machine":
            machines.setdefault(a["id"], set()).add(a["type"])
    owned_machines = [mid for mid, flags in machines.items() if {"user", "root"} <= flags]
    return owned_machines

# ---------- MARKDOWN ----------
def img(src, name, difficulty):
    return f"<div align='center'><img src='{src}' width='110'/><br><sub>{name} · {difficulty}</sub></div>"

def grid(items):
    if not items:
        return "_No items_\n"
    rows = []
    for i in range(0, len(items), 4):
        chunk = items[i:i+4]
        rows.append("| " + " | ".join(chunk) + " |")
        if i == 0:
            rows.append("| " + " | ".join(["---"] * len(chunk)) + " |")
    return "\n".join(rows) + "\n"

START = "<!-- OWNED_SECTION_START -->"
END = "<!-- OWNED_SECTION_END -->"

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
        name = r["title"]
        diff = r["difficulty"]
        img_url = r["imageURL"]
        if diff.lower() not in DIFFICULTY:
            continue

        raw_path = THM_ASSETS / f"{slug(name)}.png"
        final_path = THM_ASSETS / f"{slug(name)}.png"
        download(img_url, raw_path)
        add_border(raw_path, final_path, diff)

        state["thm_rooms"][code] = {"name": name, "difficulty": diff.title(), "img": final_path.as_posix()}

    # --- HTB ---
    AVATAR_DOMAIN = get_htb_avatar_domain()
    activity = fetch_htb_activity()
    machine_ids = derive_htb(activity)

    for mid in machine_ids:
        if str(mid) in state["htb_machines"]:
            continue
        info = fetch_htb_machine(mid)
        name = info.get("name", f"machine_{mid}")
        diff = info.get("difficultyText", "unknown")

        avatar = info.get("avatar") or ""
        if avatar.startswith("/avatars/") and AVATAR_DOMAIN:
            avatar = f"{AVATAR_DOMAIN}{avatar}"

        raw_path = HTB_ASSETS / f"{slug(name)}.png"
        final_path = HTB_ASSETS / f"{slug(name)}.png"
        download(avatar, raw_path)
        add_border(raw_path, final_path, diff)

        state["htb_machines"][str(mid)] = {"name": name, "difficulty": diff.title(), "img": final_path.as_posix()}

    save_state(state)

    # ---------- BUILD MD ----------
    md = []
    md.append("## 🗡️ Owned Machines\n")
    md.append("### HackTheBox\n")
    md.append(grid([img(v["img"], v["name"], v["difficulty"]) for v in reversed(list(state["htb_machines"].values()))]))
    md.append("### TryHackMe\n")
    md.append(grid([img(v["img"], v["name"], v["difficulty"]) for v in reversed(list(state["thm_rooms"].values()))]))

    insert_block(ABOUT_ME_FILE, "\n".join(md))
    logging.info("DONE. THM: %d | HTB: %d", len(state["thm_rooms"]), len(state["htb_machines"]))

if __name__ == "__main__":
    main()
