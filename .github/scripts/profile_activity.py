"""Rewrite the profile activity block from public GitHub data."""
import json
import os
import urllib.parse
import urllib.request
from pathlib import Path

README = Path(__file__).resolve().parents[2] / "README.md"
START = "<!-- activity:start -->"
END = "<!-- activity:end -->"
USER = "Nani2139"
SKIP = {"Hack", "Dockerfile", "Procfile", "Makefile"}


def get(path: str):
    req = urllib.request.Request(
        "https://api.github.com/" + path,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "profile-activity",
            "Authorization": f"Bearer {os.environ['GH_TOKEN']}" if os.environ.get("GH_TOKEN") else "",
        },
    )
    if not os.environ.get("GH_TOKEN"):
        req.remove_header("Authorization")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def search_count(query: str) -> int:
    return int(get("search/issues?" + urllib.parse.urlencode({"q": query, "per_page": 1}))["total_count"])


def languages() -> list[tuple[str, float]]:
    totals: dict[str, int] = {}
    page = 1
    while True:
        batch = get(f"users/{USER}/repos?per_page=100&page={page}&type=owner")
        if not batch:
            break
        for repo in batch:
            if repo.get("fork"):
                continue
            for name, count in get(f"repos/{USER}/{repo['name']}/languages").items():
                if name not in SKIP:
                    totals[name] = totals.get(name, 0) + count
        if len(batch) < 100:
            break
        page += 1
    ranked = sorted(totals.items(), key=lambda item: item[1], reverse=True)[:6]
    total = sum(count for _name, count in ranked) or 1
    return [(name, count * 100 / total) for name, count in ranked]


def main() -> None:
    langs = " · ".join(f"{name} {share:.1f}%" for name, share in languages())
    prs = search_count(f"author:{USER} type:pr is:public")
    comments = search_count(f"commenter:{USER} is:public")
    block = "\n".join(
        [
            START,
            "Public activity on this account. A weekly workflow rewrites this block from pull requests, comments, and repository languages.",
            "",
            "| | |",
            "|---|---|",
            f"| Public pull requests | {prs} |",
            f"| Public comments | {comments} |",
            f"| Languages by code | {langs} |",
            END,
        ]
    )
    text = README.read_text(encoding="utf-8")
    start = text.find(START)
    end = text.find(END)
    if start < 0 or end < 0:
        raise SystemExit("activity markers missing")
    updated = text[:start] + block + text[end + len(END) :]
    README.write_text(updated, encoding="utf-8")
    print(block)


if __name__ == "__main__":
    main()
