# BinzoTv

A daily, cleaned IPTV playlist built from [iptv-org](https://github.com/iptv-org/iptv).

`update_playlist.py` pulls the Saudi, UAE, Kuwait, Qatar, Bahrain and Oman country lists plus the sports, news and documentary categories, gives each section an Arabic group name, drops dead and duplicate streams, puts the key channels (SSC, MBC, Al Arabiya, beIN and others) at the top of each section, and writes `sorted_iptv.m3u`.

A GitHub Actions workflow runs it every day at 04:00 UTC and commits the new file. It can also be run by hand from the Actions tab.

## Playlist link

Use this Raw link in TiviMate, IPTV Smarters or any M3U player:

```
https://raw.githubusercontent.com/albinzo/BinzoTv/main/sorted_iptv.m3u
```

## Nuvio add-on

`build_addon.py` turns the playlist into a static add-on in `docs/`, published with GitHub Pages and rebuilt by the same daily workflow. Each section shows up in Nuvio as its own row of live channels.

Install link (paste it in Nuvio under Add-ons):

```
https://albinzo.github.io/BinzoTv/manifest.json
```
