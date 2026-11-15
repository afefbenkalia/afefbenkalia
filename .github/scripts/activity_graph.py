"""Render a contribution-activity line chart as an SVG for the profile README.

Replaces the hosted github-readme-activity-graph service (its deployment is
gone) with a self-generated card in the README's own palette.

Usage:
    GITHUB_TOKEN=... python activity_graph.py --user USER --out dist/activity-graph.svg
    python activity_graph.py --input days.json --out preview.svg   # offline preview

`days.json` is a list of {"date": "YYYY-MM-DD", "count": N} objects.
Standard library only, so the workflow needs no `pip install`.
"""

import argparse
import datetime as dt
import json
import os
import sys
import urllib.request
from xml.sax.saxutils import escape

DAYS = 31

# README palette
BG_FROM, BG_TO = "#060A14", "#0D1430"
BORDER = "#1C2747"
GRID = "#1C2747"
TITLE = "#2DD4BF"
TEXT = "#E8EEF9"
MUTED = "#8C98B8"
DIM = "#56628A"
LINE = "#2DD4BF"
POINT = "#A78BFA"

MONO = "'JetBrains Mono', 'Fira Code', 'SF Mono', Consolas, 'Liberation Mono', 'Courier New', monospace"
SANS = "'Segoe UI', Ubuntu, 'Helvetica Neue', Helvetica, Arial, sans-serif"

QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar {
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}
"""


def fetch_days(user: str, token: str) -> list[dict]:
    today = dt.datetime.now(dt.timezone.utc).date()
    start = today - dt.timedelta(days=DAYS - 1)
    body = json.dumps({
        "query": QUERY,
        "variables": {
            "login": user,
            "from": f"{start.isoformat()}T00:00:00Z",
            "to": f"{today.isoformat()}T23:59:59Z",
        },
    }).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={
            "Authorization": f"bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "profile-readme-activity-graph",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.load(resp)
    if payload.get("errors") or not (payload.get("data") or {}).get("user"):
        raise RuntimeError(f"GitHub GraphQL error: {payload.get('errors') or 'user not found'}")
    weeks = payload["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    days = [
        {"date": d["date"], "count": d["contributionCount"]}
        for w in weeks
        for d in w["contributionDays"]
    ]
    days.sort(key=lambda d: d["date"])
    return days[-DAYS:]


def nice_max(value: int) -> int:
    """Round the y-axis ceiling up to a value that splits into 4 clean steps."""
    for step in (1, 2, 3, 5, 10, 15, 20, 25, 50, 75, 100, 150, 250, 500):
        if step * 4 >= value:
            return step * 4
    return -(-value // 1000) * 1000


def render(days: list[dict], user: str) -> str:
    w, h = 1200, 380
    left, right, top, bottom = 76, 40, 104, 64
    pw, ph = w - left - right, h - top - bottom
    n = len(days)
    counts = [d["count"] for d in days]
    ymax = nice_max(max(counts) if counts else 0)
    total = sum(counts)

    def x(i: int) -> float:
        return left + (pw * i / (n - 1) if n > 1 else pw / 2)

    def y(v: float) -> float:
        return top + ph - ph * v / ymax

    pts = [(x(i), y(c)) for i, c in enumerate(counts)]
    line_d = "M " + " L ".join(f"{px:.1f} {py:.1f}" for px, py in pts)
    area_d = f"{line_d} L {pts[-1][0]:.1f} {top + ph} L {pts[0][0]:.1f} {top + ph} Z"

    out = []
    a = out.append
    a(f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" '
      f'aria-label="Contribution activity for {escape(user)} over the last {n} days: {total} contributions">')
    a(f"<title>Contribution activity for {escape(user)} over the last {n} days: {total} contributions</title>")
    a("<defs>")
    a(f'<linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{BG_FROM}"/>'
      f'<stop offset="1" stop-color="{BG_TO}"/></linearGradient>')
    a(f'<linearGradient id="area" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{LINE}" stop-opacity="0.35"/>'
      f'<stop offset="1" stop-color="{LINE}" stop-opacity="0"/></linearGradient>')
    a('<linearGradient id="brand" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#2DD4BF"/>'
      '<stop offset="0.5" stop-color="#38BDF8"/><stop offset="1" stop-color="#A78BFA"/></linearGradient>')
    a(f'<pattern id="dots" width="24" height="24" patternUnits="userSpaceOnUse"><circle cx="2" cy="2" r="1" fill="{BORDER}"/></pattern>')
    a(f'<clipPath id="frame"><rect width="{w}" height="{h}" rx="14"/></clipPath>')
    a("</defs>")
    a("<style>"
      ".draw { stroke-dasharray: 1; stroke-dashoffset: 1; animation: draw 1.8s ease-out forwards; }"
      "@keyframes draw { to { stroke-dashoffset: 0; } }"
      ".fade { opacity: 0; animation: fade .8s ease-out forwards; }"
      "@keyframes fade { to { opacity: 1; } }"
      "</style>")
    a('<g clip-path="url(#frame)">')
    a(f'<rect width="{w}" height="{h}" fill="url(#bg)"/>')
    a(f'<rect width="{w}" height="{h}" fill="url(#dots)" opacity="0.55"/>')

    # header
    a(f'<text x="40" y="50" font-family="{MONO}" font-size="13" letter-spacing="2.5" fill="{TITLE}">LAST {n} DAYS</text>')
    a(f'<text x="40" y="80" font-family="{SANS}" font-weight="800" font-size="24" fill="{TEXT}">Contribution activity</text>')
    a(f'<text x="{w - 40}" y="80" text-anchor="end" font-family="{SANS}" font-weight="800" font-size="26" fill="url(#brand)">{total}</text>')
    a(f'<text x="{w - 40}" y="50" text-anchor="end" font-family="{MONO}" font-size="13" letter-spacing="2" fill="{DIM}">CONTRIBUTIONS</text>')

    # grid + y labels
    for k in range(5):
        v = ymax * k / 4
        gy = y(v)
        a(f'<line x1="{left}" y1="{gy:.1f}" x2="{w - right}" y2="{gy:.1f}" stroke="{GRID}" stroke-dasharray="{"0" if k == 0 else "3 5"}"/>')
        a(f'<text x="{left - 14}" y="{gy + 4:.1f}" text-anchor="end" font-family="{MONO}" font-size="12" fill="{DIM}">{int(v)}</text>')

    # x labels: every few days so they never collide
    step = max(1, round(n / 10))
    for i, d in enumerate(days):
        if i % step == 0 or i == n - 1:
            date = dt.date.fromisoformat(d["date"])
            a(f'<text x="{x(i):.1f}" y="{top + ph + 26}" text-anchor="middle" font-family="{MONO}" font-size="12" fill="{MUTED}">'
              f'{date.strftime("%b")} {date.day}</text>')

    a(f'<path d="{area_d}" fill="url(#area)" class="fade"/>')
    a(f'<path d="{line_d}" fill="none" stroke="{LINE}" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round" pathLength="1" class="draw"/>')
    for i, (px, py) in enumerate(pts):
        a(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="3.5" fill="{POINT}" stroke="{BG_TO}" stroke-width="1.5" class="fade" '
          f'style="animation-delay:{0.6 + 1.2 * i / max(n - 1, 1):.2f}s"><title>{days[i]["date"]}: {counts[i]}</title></circle>')
    a("</g>")
    a(f'<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="14" fill="none" stroke="{BORDER}"/>')
    a("</svg>")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", default=os.environ.get("GITHUB_REPOSITORY_OWNER", ""))
    ap.add_argument("--out", required=True)
    ap.add_argument("--input", help="JSON list of {date, count} instead of calling the API")
    args = ap.parse_args()

    if args.input:
        with open(args.input, encoding="utf-8") as f:
            days = json.load(f)[-DAYS:]
    else:
        token = os.environ.get("GITHUB_TOKEN")
        if not token or not args.user:
            print("GITHUB_TOKEN and --user are required", file=sys.stderr)
            return 1
        days = fetch_days(args.user, token)

    if not days:
        print("No contribution data returned", file=sys.stderr)
        return 1

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(render(days, args.user))
    print(f"Wrote {args.out} ({len(days)} days, {sum(d['count'] for d in days)} contributions)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
