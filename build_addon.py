#!/usr/bin/env python3
"""Turn sorted_iptv.m3u into a static Stremio-style add-on for Nuvio (served by GitHub Pages).

Output goes to docs/:
  manifest.json
  catalog/channel/<catalog-id>.json and catalog/channel/<catalog-id>/skip=<n>.json
  meta/channel/<id>.json
  stream/channel/<id>.json

Live TV uses the add-on type "channel" (Nuvio treats "tv" as a synonym for series).
"""
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

PLAYLIST = Path("sorted_iptv.m3u")
OUT = Path("docs")
TYPE = "channel"
ID_PREFIX = "binzotv-"
PAGE = 100
VERSION = "1.0.0"

# playlist group -> (catalog id, display name); order follows the playlist
GROUPS = {
    "السعودية": "sa",
    "الإمارات": "ae",
    "الكويت": "kw",
    "قطر": "qa",
    "البحرين": "bh",
    "عُمان": "om",
    "الرياضة": "sports",
    "الأخبار": "news",
    "الوثائقية": "docs",
}

ATTR = re.compile(r'([a-zA-Z-]+)="([^"]*)"')


def parse(text):
    channels, info, opts = [], None, []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#EXTM3U"):
            continue
        if line.startswith("#EXTINF"):
            head, _, name = line.rpartition(",")
            info = {"name": name.strip(), **dict(ATTR.findall(head))}
            opts = []
        elif line.startswith("#EXTVLCOPT"):
            opts.append(line.split(":", 1)[1])
        elif not line.startswith("#") and info:
            headers = {}
            for o in opts:
                key, _, val = o.partition("=")
                if key == "http-user-agent" and val:
                    headers["User-Agent"] = val
                elif key == "http-referrer" and val:
                    headers["Referer"] = val
            channels.append({**info, "url": line, "headers": headers})
            info, opts = None, []
    return channels


def channel_id(ch):
    return ID_PREFIX + hashlib.sha1(ch["url"].encode("utf-8")).hexdigest()[:12]


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def main():
    channels = parse(PLAYLIST.read_text(encoding="utf-8"))
    if not channels:
        print("No channels in playlist")
        return 1

    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()
    (OUT / ".nojekyll").write_text("")

    by_group = {}
    for ch in channels:
        by_group.setdefault(ch.get("group-title", ""), []).append(ch)

    catalogs = []
    order = list(GROUPS) + [g for g in by_group if g not in GROUPS]
    for n, group in enumerate(order):
        items = by_group.get(group)
        if not items:
            continue
        cat_id = GROUPS.get(group, f"group{n}")
        catalogs.append({"type": TYPE, "id": cat_id, "name": group,
                         "extra": [{"name": "skip", "isRequired": False}]})

        metas = []
        for ch in items:
            cid = channel_id(ch)
            logo = ch.get("tvg-logo") or None
            preview = {"id": cid, "type": TYPE, "name": ch["name"], "posterShape": "landscape"}
            if logo:
                preview.update(poster=logo, logo=logo)
            metas.append(preview)

            meta = {**preview, "description": f"{group} · BinzoTv (iptv-org)",
                    "genres": [group]}
            write(OUT / "meta" / TYPE / f"{cid}.json", {"meta": meta})

            stream = {"url": ch["url"], "name": "BinzoTv", "title": ch["name"]}
            if ch["headers"]:
                stream["behaviorHints"] = {"notWebReady": True,
                                           "proxyHeaders": {"request": ch["headers"]}}
            write(OUT / "stream" / TYPE / f"{cid}.json", {"streams": [stream]})

        for start in range(0, len(metas), PAGE):
            page = {"metas": metas[start:start + PAGE]}
            if start == 0:
                write(OUT / "catalog" / TYPE / f"{cat_id}.json", page)
            write(OUT / "catalog" / TYPE / cat_id / f"skip={start}.json", page)
        # an empty page past the end, so clients stop paging cleanly
        write(OUT / "catalog" / TYPE / cat_id / f"skip={len(metas)}.json", {"metas": []})

    manifest = {
        "id": "com.binzo.tv",
        "version": VERSION,
        "name": "BinzoTv",
        "description": "Free Gulf, sports, news and documentary TV channels from iptv-org, refreshed daily.",
        "types": [TYPE],
        "catalogs": catalogs,
        "resources": [
            "catalog",
            {"name": "meta", "types": [TYPE], "idPrefixes": [ID_PREFIX]},
            {"name": "stream", "types": [TYPE], "idPrefixes": [ID_PREFIX]},
        ],
        "idPrefixes": [ID_PREFIX],
        "behaviorHints": {"configurable": False, "configurationRequired": False},
    }
    write(OUT / "manifest.json", manifest)

    print(f"Add-on built: {len(channels)} channels in {len(catalogs)} catalogs -> {OUT}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
