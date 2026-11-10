#!/usr/bin/env python3
"""Build local, auto-refreshing SVG cards from GitHub's public REST API."""
from __future__ import annotations

import html
import json
import os
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
USERNAME = os.environ.get("PROFILE_USERNAME", "ostovar04")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
API = "https://api.github.com"
COLORS = ["#7c3aed", "#e64d9b", "#14b8d4", "#f59e0b", "#8b5cf6"]


def api_json(url: str):
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "ostovar04-profile-stats-workflow",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    for attempt in range(4):
        try:
            request = Request(url, headers=headers)
            with urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError) as exc:
            if attempt == 3:
                raise RuntimeError(f"GitHub API request failed: {url}: {exc}") from exc
            time.sleep(2 ** attempt)
    raise RuntimeError(f"GitHub API request failed: {url}")


def get_profile_data():
    name = quote(USERNAME, safe="")
    profile = api_json(f"{API}/users/{name}")
    repositories = []
    page = 1
    while True:
        batch = api_json(
            f"{API}/users/{name}/repos?type=owner&sort=updated&per_page=100&page={page}"
        )
        if not isinstance(batch, list):
            raise RuntimeError("Unexpected repository response from GitHub API")
        owned = [repo for repo in batch if not repo.get("fork", False)]
        repositories.extend(owned)
        if len(batch) < 100:
            break
        page += 1

    stars = sum(int(repo.get("stargazers_count", 0)) for repo in repositories)
    language_bytes: dict[str, int] = {}
    for repo in repositories:
        language_url = repo.get("languages_url")
        if not language_url:
            continue
        languages = api_json(language_url)
        if isinstance(languages, dict):
            for language, size in languages.items():
                language_bytes[language] = language_bytes.get(language, 0) + int(size)

    return {
        "repositories": len(repositories),
        "stars": stars,
        "followers": int(profile.get("followers", 0)),
        "following": int(profile.get("following", 0)),
        "languages": sorted(language_bytes.items(), key=lambda item: item[1], reverse=True),
    }


def make_profile_svg(theme: str, data: dict) -> str:
    dark = theme == "dark"
    bg1, bg2 = ("#111528", "#211934") if dark else ("#fff9fc", "#eeeaff")
    border = "#513567" if dark else "#dcc9f1"
    ink = "#fff0fa" if dark else "#382744"
    muted = "#cbbbdc" if dark else "#746584"
    accent = "#64e8ff" if dark else "#7c3aed"
    pink = "#ff79c8" if dark else "#e64d9b"
    cyan = "#64e8ff" if dark else "#14b8d4"
    cells = [
        ("PUBLIC REPOS", data["repositories"], 28, 76),
        ("TOTAL STARS", data["stars"], 251, 76),
        ("FOLLOWERS", data["followers"], 28, 145),
        ("FOLLOWING", data["following"], 251, 145),
    ]
    card_markup = []
    for index, (label, value, x, y) in enumerate(cells):
        color = COLORS[index]
        card_markup.append(
            f'<rect x="{x}" y="{y}" width="201" height="56" rx="13" '
            f'fill="{bg2}" stroke="{border}" stroke-width="1.2"/>'
            f'<circle cx="{x + 17}" cy="{y + 18}" r="4" fill="{color}"/>'
            f'<text x="{x + 29}" y="{y + 22}" font-family="Arial, sans-serif" '
            f'font-size="10" font-weight="700" letter-spacing=".8" fill="{muted}">{label}</text>'
            f'<text x="{x + 17}" y="{y + 46}" font-family="Arial, sans-serif" '
            f'font-size="21" font-weight="800" fill="{accent}">{value:,}</text>'
            f'<path d="M{x + 155} {y + 43}l7-8 7 4 8-14 8 7" fill="none" '
            f'stroke="{pink}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" opacity=".75"/>'
        )
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="480" height="230" viewBox="0 0 480 230" role="img" aria-labelledby="title desc">
<title id="title">GitHub stats for {html.escape(USERNAME)}</title>
<desc id="desc">Public repositories, stars, followers, and following, generated from GitHub's public API.</desc>
<defs><linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop stop-color="{bg1}"/><stop offset="1" stop-color="{bg2}"/></linearGradient><linearGradient id="line" x1="0" y1="0" x2="1" y2="0"><stop stop-color="{cyan}"/><stop offset="1" stop-color="{pink}"/></linearGradient></defs>
<rect x="2" y="2" width="476" height="226" rx="20" fill="url(#bg)" stroke="{border}" stroke-width="2"/>
<path d="M16 40V16h52M464 190v24h-52" fill="none" stroke="url(#line)" stroke-width="3" stroke-linecap="round"/>
<path d="m443 19 4 8 9 1-7 6 2 9-8-4-8 4 2-9-7-6 9-1z" fill="{pink}"/>
<text x="26" y="31" font-family="Arial, sans-serif" font-size="10" font-weight="800" letter-spacing="1.7" fill="{pink}">✦ PROFILE QUEST  ·  GITHUB STATS</text>
<text x="26" y="59" font-family="Arial, sans-serif" font-size="19" font-weight="800" fill="{ink}">{html.escape(USERNAME)}</text>
{''.join(card_markup)}
<text x="27" y="217" font-family="Arial, sans-serif" font-size="8" letter-spacing=".8" fill="{muted}">PUBLIC GITHUB DATA · REFRESH WORKFLOW INCLUDED</text>
</svg>'''


def make_languages_svg(theme: str, languages: list[tuple[str, int]]) -> str:
    dark = theme == "dark"
    bg1, bg2 = ("#111528", "#211934") if dark else ("#fff9fc", "#eeeaff")
    border = "#513567" if dark else "#dcc9f1"
    ink = "#fff0fa" if dark else "#382744"
    muted = "#cbbbdc" if dark else "#746584"
    accent = "#64e8ff" if dark else "#7c3aed"
    pink = "#ff79c8" if dark else "#e64d9b"
    total = sum(size for _, size in languages)
    top = languages[:5]
    rows = []
    for index, (label, size) in enumerate(top):
        y = 81 + index * 26
        percent = size * 100 / total if total else 0
        display = f"{percent:.1f}%"
        bar_width = max(3, 390 * percent / 100)
        color = COLORS[index]
        rows.append(
            f'<text x="27" y="{y}" font-family="Arial, sans-serif" font-size="11" '
            f'font-weight="700" fill="{ink}">{html.escape(label)}</text>'
            f'<text x="451" y="{y}" text-anchor="end" font-family="Arial, sans-serif" '
            f'font-size="10" font-weight="700" fill="{muted}">{display}</text>'
            f'<rect x="27" y="{y + 6}" width="426" height="6" rx="3" fill="{bg2}"/>'
            f'<rect x="27" y="{y + 6}" width="{bar_width:.1f}" height="6" rx="3" fill="{color}"/>'
        )
    if not rows:
        rows.append(
            f'<text x="240" y="122" text-anchor="middle" font-family="Arial, sans-serif" '
            f'font-size="12" font-weight="700" fill="{muted}">No public language data yet</text>'
        )
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="480" height="230" viewBox="0 0 480 230" role="img" aria-labelledby="title desc">
<title id="title">Top programming languages for {html.escape(USERNAME)}</title>
<desc id="desc">Language byte totals across public, non-fork repositories, refreshed by GitHub Actions.</desc>
<defs><linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop stop-color="{bg1}"/><stop offset="1" stop-color="{bg2}"/></linearGradient><linearGradient id="line" x1="0" y1="0" x2="1" y2="0"><stop stop-color="{pink}"/><stop offset="1" stop-color="{accent}"/></linearGradient></defs>
<rect x="2" y="2" width="476" height="226" rx="20" fill="url(#bg)" stroke="{border}" stroke-width="2"/>
<path d="M16 40V16h52M464 190v24h-52" fill="none" stroke="url(#line)" stroke-width="3" stroke-linecap="round"/>
<path d="m442 20 4 8 9 1-7 6 2 9-8-4-8 4 2-9-7-6 9-1z" fill="{pink}"/>
<text x="26" y="31" font-family="Arial, sans-serif" font-size="10" font-weight="800" letter-spacing="1.7" fill="{pink}">✧ LANGUAGE QUEST  ·  TOP LANGUAGES</text>
<text x="26" y="59" font-family="Arial, sans-serif" font-size="19" font-weight="800" fill="{ink}">{html.escape(USERNAME)}</text>
{''.join(rows)}
<text x="27" y="217" font-family="Arial, sans-serif" font-size="8" letter-spacing=".8" fill="{muted}">PUBLIC REPOSITORIES · REFRESH WORKFLOW INCLUDED</text>
</svg>'''


def main() -> None:
    data = get_profile_data()
    for theme in ("light", "dark"):
        target = ROOT / "assets" / theme
        target.mkdir(parents=True, exist_ok=True)
        (target / "github-stats.svg").write_text(make_profile_svg(theme, data), encoding="utf-8")
        (target / "top-languages.svg").write_text(make_languages_svg(theme, data["languages"]), encoding="utf-8")
    print(
        f"Updated {USERNAME}: {data['repositories']} public repos, {data['stars']} stars, "
        f"{len(data['languages'])} language entries."
    )


if __name__ == "__main__":
    main()
