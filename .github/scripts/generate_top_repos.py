#!/usr/bin/env python3
import json
import os
import sys
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from html import escape

API = "https://api.github.com/graphql"
TOKEN = os.environ.get("GITHUB_TOKEN", "")
USERNAME = os.environ.get("GITHUB_REPOSITORY_OWNER", "")
OUTPUT = os.environ.get("OUTPUT_PATH", "profile/top-repos.svg")

if not TOKEN or not USERNAME:
    sys.exit("GITHUB_TOKEN and GITHUB_REPOSITORY_OWNER are required")

def graphql(query, variables):
    payload = json.dumps({"query": query, "variables": variables}).encode("utf-8")
    req = urllib.request.Request(
        API,
        data=payload,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "github-profile-top-repos-action",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        data = json.load(response)
    if data.get("errors"):
        raise RuntimeError(json.dumps(data["errors"], indent=2))
    return data["data"]

meta_query = """
query($login: String!) {
  user(login: $login) { createdAt }
}
"""
created = graphql(meta_query, {"login": USERNAME})["user"]["createdAt"]
created_year = datetime.fromisoformat(created.replace("Z", "+00:00")).year
current_year = datetime.now(timezone.utc).year

contrib_query = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      commitContributionsByRepository(maxRepositories: 100) {
        repository {
          nameWithOwner
          url
          isPrivate
        }
        contributions { totalCount }
      }
    }
  }
}
"""

totals = defaultdict(lambda: {"count": 0, "url": ""})
for year in range(created_year, current_year + 1):
    start = f"{year}-01-01T00:00:00Z"
    if year == current_year:
        end = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    else:
        end = f"{year}-12-31T23:59:59Z"
    data = graphql(contrib_query, {"login": USERNAME, "from": start, "to": end})
    rows = data["user"]["contributionsCollection"]["commitContributionsByRepository"]
    for row in rows:
        repo = row["repository"]
        if repo["isPrivate"]:
            continue
        key = repo["nameWithOwner"]
        totals[key]["count"] += row["contributions"]["totalCount"]
        totals[key]["url"] = repo["url"]

items = sorted(totals.items(), key=lambda item: (-item[1]["count"], item[0].lower()))[:5]
width = 720
header_h = 62
row_h = 54
height = header_h + max(1, len(items)) * row_h + 20
rows = []
if items:
    for i, (name, info) in enumerate(items):
        y = header_h + i * row_h
        rows.append(f'''<a href="{escape(info['url'])}" target="_blank">
  <rect x="20" y="{y}" width="680" height="44" rx="8" fill="#161b22" stroke="#30363d"/>
  <text x="36" y="{y + 20}" class="repo">{escape(name)}</text>
  <text x="36" y="{y + 36}" class="meta">{info['count']} commit contribution{'s' if info['count'] != 1 else ''}</text>
</a>''')
else:
    rows.append(f'<text x="36" y="{header_h + 28}" class="meta">No public commit contributions found.</text>')

svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">
<title id="title">Top Contributed Repositories</title>
<desc id="desc">Top public repositories by commit contributions for {escape(USERNAME)}</desc>
<style>
  .title {{ font: 600 20px -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif; fill:#58a6ff; }}
  .repo {{ font: 600 14px -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif; fill:#c9d1d9; }}
  .meta {{ font: 400 12px -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif; fill:#8b949e; }}
</style>
<rect width="100%" height="100%" rx="10" fill="#0d1117" stroke="#30363d"/>
<text x="24" y="38" class="title">Top Contributed Repositories</text>
{''.join(rows)}
</svg>'''

os.makedirs(os.path.dirname(OUTPUT) or ".", exist_ok=True)
with open(OUTPUT, "w", encoding="utf-8", newline="\n") as f:
    f.write(svg)
print(f"Generated {OUTPUT} with {len(items)} repositories")
