"""Rewrite the profile stats block from public GitHub data."""
import json
import os
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

README = Path(__file__).resolve().parents[2] / "README.md"
START = "<!-- stats:start -->"
END = "<!-- stats:end -->"
USER = "Nani2139"
SKIP = {"Hack", "Dockerfile", "Procfile", "Makefile"}
WINDOWS = [
    ("2023-04-02T00:00:00Z", "2024-04-02T00:00:00Z"),
    ("2024-04-02T00:00:00Z", "2025-04-02T00:00:00Z"),
    ("2025-04-02T00:00:00Z", "2026-04-02T00:00:00Z"),
    ("2026-04-02T00:00:00Z", "2026-10-08T00:00:00Z"),
]


def request(url: str, body: bytes | None = None):
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "profile-activity",
    }
    token = os.environ.get("GH_TOKEN", "")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=body, headers=headers)
    with urllib.request.urlopen(req, timeout=40) as resp:
        return json.loads(resp.read().decode())


def graphql(query: str):
    payload = json.dumps({"query": query}).encode()
    data = request("https://api.github.com/graphql", payload)
    if data.get("errors"):
        raise SystemExit(data["errors"][0]["message"])
    return data["data"]


def get(path: str):
    return request("https://api.github.com/" + path)


def search_count(query: str) -> int:
    return int(get("search/issues?" + urllib.parse.urlencode({"q": query, "per_page": 1}))["total_count"])


def languages() -> str:
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
    return " · ".join(f"{name} {count * 100 / total:.1f}%" for name, count in ranked)


def commits_and_stars() -> tuple[int, int]:
    data = graphql(
        f"""
        query {{
          user(login: "{USER}") {{
            repositories(first: 100, privacy: PUBLIC, ownerAffiliations: OWNER, isFork: false) {{
              nodes {{
                stargazerCount
                defaultBranchRef {{
                  target {{ ... on Commit {{ history {{ totalCount }} }} }}
                }}
              }}
            }}
          }}
        }}
        """
    )
    commits = 0
    stars = 0
    for node in data["user"]["repositories"]["nodes"]:
        stars += node["stargazerCount"] or 0
        ref = node.get("defaultBranchRef") or {}
        target = ref.get("target") or {}
        history = target.get("history") or {}
        commits += history.get("totalCount") or 0
    return commits, stars


def contributions() -> tuple[int, int, str, str, int, str, str]:
    days: dict[str, int] = {}
    for start, end in WINDOWS:
        data = graphql(
            f"""
            query {{
              user(login: "{USER}") {{
                contributionsCollection(from: "{start}", to: "{end}") {{
                  contributionCalendar {{
                    weeks {{ contributionDays {{ date contributionCount }} }}
                  }}
                }}
              }}
            }}
            """
        )
        weeks = data["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
        for week in weeks:
            for day in week["contributionDays"]:
                if start[:10] <= day["date"] < end[:10]:
                    days[day["date"]] = day["contributionCount"]
    ordered = sorted(days)
    total = sum(days.values())
    best = cur = 0
    best_range = ("", "")
    cur_start = ""
    for day in ordered:
        if days[day]:
            if cur == 0:
                cur_start = day
            cur += 1
            if cur > best:
                best = cur
                best_range = (cur_start, day)
        else:
            cur = 0
    current = 0
    start = end = ""
    for day in reversed(ordered):
        if days[day]:
            if not end:
                end = day
            start = day
            current += 1
        elif end:
            break
    return total, current, start, end, best, best_range[0], best_range[1]


def shown(day: str) -> str:
    return datetime.strptime(day, "%Y-%m-%d").strftime("%-d %b %Y") if os.name != "nt" else datetime.strptime(day, "%Y-%m-%d").strftime("%#d %b %Y")


def main() -> None:
    commits, stars = commits_and_stars()
    total, current, cur_start, cur_end, best, best_start, best_end = contributions()
    prs = search_count(f"author:{USER} type:pr is:public")
    comments = search_count(f"commenter:{USER} is:public")
    langs = languages()
    block = "\n".join(
        [
            START,
            "Counted from public repositories. Forks are left out. A weekly workflow rewrites this block.",
            "",
            "| | |",
            "|---|---|",
            f"| Commits on the default branch | {commits} |",
            f"| Contributions since Apr 2023 | {total} |",
            f"| Current streak | {current} days ({shown(cur_start)} – {shown(cur_end)}) |",
            f"| Longest streak | {best} days ({shown(best_start)} – {shown(best_end)}) |",
            f"| Public pull requests | {prs} |",
            f"| Public comments | {comments} |",
            f"| Stars | {stars} |",
            f"| Languages by code | {langs} |",
            END,
        ]
    )
    text = README.read_text(encoding="utf-8")
    start = text.find(START)
    end = text.find(END)
    if start < 0 or end < 0:
        raise SystemExit("stats markers missing")
    README.write_text(text[:start] + block + text[end + len(END) :], encoding="utf-8")
    print(block)


if __name__ == "__main__":
    main()
