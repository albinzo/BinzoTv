#!/usr/bin/env python3
"""Build sorted_iptv.m3u from iptv-org: fetch, rename groups, health-check, dedupe, sort."""
import re
import sys
from concurrent.futures import ThreadPoolExecutor

import requests

SOURCES = [
    ("السعودية", "https://iptv-org.github.io/iptv/countries/sa.m3u"),
    ("الإمارات", "https://iptv-org.github.io/iptv/countries/ae.m3u"),
    ("الكويت", "https://iptv-org.github.io/iptv/countries/kw.m3u"),
    ("قطر", "https://iptv-org.github.io/iptv/countries/qa.m3u"),
    ("البحرين", "https://iptv-org.github.io/iptv/countries/bh.m3u"),
    ("عُمان", "https://iptv-org.github.io/iptv/countries/om.m3u"),
    ("الرياضة", "https://iptv-org.github.io/iptv/categories/sports.m3u"),
    ("الأخبار", "https://iptv-org.github.io/iptv/categories/news.m3u"),
    ("الوثائقية", "https://iptv-org.github.io/iptv/categories/documentary.m3u"),
]
PRIORITY = ["SSC", "MBC", "Al Arabiya", "Al Ekhbariya", "Rotana", "beIN",
            "AD Sports", "Dubai Sports", "Alkass"]
EPG_HEADER = '#EXTM3U url-tvg="https://iptv-org.github.io/epg/guides/sa/stc.com.sa.epg.xml"'
OUTPUT = "sorted_iptv.m3u"
TIMEOUT = 5
WORKERS = 25
DEFAULT_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"


def parse_m3u(text, group):
    """Return list of channels: {name, extinf, opts, url, ua, referer}."""
    channels, extinf, opts = [], None, []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#EXTM3U"):
            continue
        if line.startswith("#EXTINF"):
            extinf, opts = line, []
        elif line.startswith("#EXTVLCOPT") or line.startswith("#KODIPROP"):
            opts.append(line)
        elif not line.startswith("#") and extinf:
            name = extinf.rsplit(",", 1)[-1].strip()
            # unify group-title
            if 'group-title="' in extinf:
                inf = re.sub(r'group-title="[^"]*"', f'group-title="{group}"', extinf)
            else:
                inf = extinf.replace(",", f' group-title="{group}",', 1) if "," in extinf else extinf
            ua = next((o.split("=", 1)[1] for o in opts if "http-user-agent=" in o), DEFAULT_UA)
            ref = next((o.split("=", 1)[1] for o in opts if "http-referrer=" in o), None)
            channels.append({"name": name, "group": group, "extinf": inf, "opts": opts,
                             "url": line, "ua": ua, "referer": ref})
            extinf, opts = None, []
    return channels


def is_alive(ch):
    headers = {"User-Agent": ch["ua"]}
    if ch["referer"]:
        headers["Referer"] = ch["referer"]
    try:
        # light GET: stream the body and read only the first bytes
        with requests.get(ch["url"], headers=headers, timeout=TIMEOUT,
                          stream=True, allow_redirects=True) as r:
            if r.status_code not in (200, 206, 301, 302):
                return False
            next(r.iter_content(512), None)
            return True
    except Exception:
        return False


def priority_rank(name):
    low = name.lower()
    for i, kw in enumerate(PRIORITY):
        if kw.lower() in low:
            return i
    return len(PRIORITY)


def main():
    all_channels = []
    for group, url in SOURCES:
        try:
            r = requests.get(url, timeout=30)
            r.raise_for_status()
            r.encoding = "utf-8"
            chs = parse_m3u(r.text, group)
            print(f"[fetch] {group}: {len(chs)}")
            all_channels.extend(chs)
        except Exception as e:
            print(f"[fetch] {group}: FAILED ({e})")

    total = len(all_channels)

    # dedupe within each group (same URL or same name)
    seen, unique = set(), []
    for ch in all_channels:
        k_url = (ch["group"], ch["url"].strip().lower())
        k_name = (ch["group"], re.sub(r"\W+", "", ch["name"].lower()))
        if k_url in seen or k_name in seen:
            continue
        seen.update((k_url, k_name))
        unique.append(ch)
    dupes = total - len(unique)

    # health check each distinct URL once
    urls = {}
    for ch in unique:
        urls.setdefault(ch["url"], ch)
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        results = dict(zip(urls, pool.map(is_alive, urls.values())))
    alive = [ch for ch in unique if results[ch["url"]]]
    dead = len(unique) - len(alive)

    # sort: section order, then priority keywords, then name
    order = {g: i for i, (g, _) in enumerate(SOURCES)}
    alive.sort(key=lambda c: (order[c["group"]], priority_rank(c["name"]), c["name"].lower()))

    with open(OUTPUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(EPG_HEADER + "\n")
        for ch in alive:
            f.write(ch["extinf"] + "\n")
            for o in ch["opts"]:
                f.write(o + "\n")
            f.write(ch["url"] + "\n")

    print("-" * 40)
    print(f"Fetched:     {total}")
    print(f"Duplicates:  {dupes}")
    print(f"Dead links:  {dead}")
    print(f"Working:     {len(alive)}  -> {OUTPUT}")
    return 0 if alive else 1


if __name__ == "__main__":
    sys.exit(main())
