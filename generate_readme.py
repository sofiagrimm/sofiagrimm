#!/usr/bin/env python3
"""
Generate a neofetch-style GitHub profile as an SVG image (profile.svg) with a
black background, real colors, and an ASCII portrait, plus auto-fetched stats.
README.md simply embeds the SVG so it scales to fit any screen.
"""
import os, time, html, calendar, requests
from datetime import date

USER = os.environ.get("GH_USER", "sofiagrimm")
TOKEN = os.environ.get("STATS_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""
API = "https://api.github.com"
GQL = "https://api.github.com/graphql"
HEADERS = {"Authorization": f"bearer {TOKEN}"} if TOKEN else {}
DASH = "-"

# ---------------- stats ----------------
def graphql(query, variables):
    r = requests.post(GQL, json={"query": query, "variables": variables},
                      headers=HEADERS, timeout=30)
    r.raise_for_status()
    d = r.json()
    if "errors" in d:
        raise RuntimeError(d["errors"])
    return d["data"]

def fetch_user_and_repos():
    # viewer = the authenticated token owner, so private repos are included
    # (requires a PAT with 'repo' scope)
    q = """
    query($after:String){
      viewer{
        login
        followers{ totalCount }
        repositoriesContributedTo(first:1,
          contributionTypes:[COMMIT, PULL_REQUEST, REPOSITORY]){ totalCount }
        repositories(first:100, after:$after, ownerAffiliations:[OWNER],
          isFork:false, orderBy:{field:STARGAZERS, direction:DESC}){
          totalCount
          pageInfo{ hasNextPage endCursor }
          nodes{ nameWithOwner stargazerCount isPrivate }
        }
      }
    }"""
    login = ""
    followers = contributed = repo_count = stars = 0
    names, after = [], None
    while True:
        u = graphql(q, {"after": after})["viewer"]
        login = u["login"]
        followers = u["followers"]["totalCount"]
        contributed = u["repositoriesContributedTo"]["totalCount"]
        repos = u["repositories"]
        repo_count = repos["totalCount"]
        for n in repos["nodes"]:
            stars += n["stargazerCount"]
            names.append(n["nameWithOwner"])
        if repos["pageInfo"]["hasNextPage"]:
            after = repos["pageInfo"]["endCursor"]
        else:
            break
    return login, followers, contributed, repo_count, stars, names

def repo_contrib_stats(nameWithOwner, login):
    owner, repo = nameWithOwner.split("/", 1)
    url = f"{API}/repos/{owner}/{repo}/stats/contributors"
    for _ in range(6):
        r = requests.get(url, headers=HEADERS, timeout=30)
        if r.status_code == 202:
            time.sleep(3); continue
        if r.status_code == 204 or not r.text.strip():
            return 0, 0, 0
        r.raise_for_status()
        for c in r.json():
            if c.get("author", {}).get("login", "").lower() == login.lower():
                a = sum(w["a"] for w in c["weeks"])
                d = sum(w["d"] for w in c["weeks"])
                return c["total"], a, d
        return 0, 0, 0
    return 0, 0, 0

def fetch_stats():
    login, followers, contributed, repos, stars, names = fetch_user_and_repos()
    commits = adds = dels = 0
    for nm in names:
        try:
            c, a, d = repo_contrib_stats(nm, login)
            commits += c; adds += a; dels += d
        except Exception:
            pass
    return dict(repos=repos, contributed=contributed, stars=stars,
                followers=followers, commits=commits,
                net=adds - dels, adds=adds, dels=dels)

# ---------------- colors ----------------
FG = "#c9d1d9"; GREEN = "#3fb950"; CYAN = "#58d5dd"; YELLOW = "#d29922"
DIM = "#6e7681"; RED = "#f85149"; NUM = "#3fb950"

def uptime(born=date(2007, 10, 19)):
    t = date.today()
    y, m, d = t.year - born.year, t.month - born.month, t.day - born.day
    if d < 0:
        m -= 1
        pm = t.month - 1 or 12
        py = t.year if t.month > 1 else t.year - 1
        d += calendar.monthrange(py, pm)[1]
    if m < 0:
        y -= 1
        m += 12
    return f"{y} years, {m} months, {d} days"

def num(v):
    return f"{v:,}" if isinstance(v, int) else str(v)

def info_lines(s):
    def field(label, value):
        return [(f"{label:<15}", CYAN), (value, FG)]
    n = lambda v: (num(v), NUM)
    return [
        [("sofia@grimm", GREEN)],
        [("-" * 24, DIM)],
        field("OS", "macOS (New Haven)"),
        field("Host", "Yale University, Class of 2029"),
        field("Kernel", "Molecular Biophysics & Biochemistry"),
        field("Uptime", uptime()),
        field("IDE", "VS Code, Jupyter, RStudio"),
        [],
        field("Languages.Prog", "Python, R, JavaScript"),
        field("Languages.Doc", "LaTeX, Markdown, HTML"),
        field("Languages.Real", "English, Chinese, Spanish, Latin"),
        [],
        field("Currently", "Neural circuit imaging, Higley Lab"),
        field("Focus", "Neuroscience, proteomics"),
        field("Experience", "Fermilab, Stanford, Cambridge, MSU"),
        [],
        field("Hobbies.Sci", "Digitizing Cushing's brain-tumor archive"),
        field("Hobbies.IRL", "Fashion, dance, concerts"),
        [],
        [("Contact", YELLOW)],
        field("Website", "sofiagrimm.com"),
        field("GitHub", "github.com/sofiagrimm"),
        [],
        [("GitHub Stats", YELLOW)],
        [(f"{'Repos':<15}", CYAN), n(s["repos"]), ("   ", FG),
         ("Contributed ", DIM), n(s["contributed"]), ("   ", FG),
         ("Stars ", CYAN), n(s["stars"])],
        [(f"{'Followers':<15}", CYAN), n(s["followers"])],
        [(f"{'Commits':<15}", CYAN), n(s["commits"])],
        [(f"{'Lines of Code':<15}", CYAN), n(s["net"]), ("  (", DIM),
         (f"{num(s['adds'])}++", GREEN), (", ", DIM),
         (f"{num(s['dels'])}--", RED), (")", DIM)],
    ]

# ---------------- svg ----------------
CHW, LH, FS, PAD, GAP = 8.6, 17.0, 14.5, 22, 26
LEFT = 22                          # small left margin for the portrait
PSCALE = 1.0                        # portrait rendered at the even, full size
PCHW, PLH, PFS = CHW * PSCALE, LH * PSCALE, FS * PSCALE

def esc(t):
    return html.escape(t, quote=False)

def build_svg(stats):
    portrait = open("portrait.txt", encoding="utf-8").read().split("\n")
    info = info_lines(stats)

    port_w = max(len(l) for l in portrait)
    port_lines = len(portrait)
    port_h = port_lines * PLH

    info_chars = [sum(len(t) for t, _ in seg) for seg in info]
    max_info = max(info_chars) if info_chars else 0

    # scale the info column so its top and bottom line up with the portrait
    info_units = len(info)
    info_lh = port_h / info_units
    info_scale = info_lh / LH
    info_fs = FS * info_scale
    info_chw = CHW * 1.08 * info_scale         # over-estimate so text never clips

    info_x = LEFT + port_w * PCHW * 1.06 + 74   # gap between portrait and text
    total_w = info_x + max_info * info_chw + PAD
    total_h = port_h + 2 * PAD

    out = []
    out.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{total_w:.0f}" '
        f'height="{total_h:.0f}" viewBox="0 0 {total_w:.0f} {total_h:.0f}" '
        f'font-family="ui-monospace,SFMono-Regular,Consolas,Menlo,monospace" '
        f'font-size="{FS}">')
    out.append(f'<rect width="100%" height="100%" fill="#000000"/>')

    # portrait (smaller)
    for i, line in enumerate(portrait):
        if not line.strip():
            continue
        y = PAD + (i + 1) * PLH
        out.append(
            f'<text x="{LEFT}" y="{y:.1f}" font-size="{PFS:.2f}" '
            f'xml:space="preserve" fill="{FG}">{esc(line)}</text>')

    # info (scaled to portrait height)
    for j, seg in enumerate(info):
        if not seg:
            continue
        y = PAD + (j + 1) * info_lh
        spans = "".join(
            f'<tspan fill="{color}" xml:space="preserve">{esc(text)}</tspan>'
            for text, color in seg)
        out.append(
            f'<text x="{info_x:.0f}" y="{y:.1f}" font-size="{info_fs:.2f}">'
            f'{spans}</text>')

    out.append('</svg>')
    return "\n".join(out)

def main():
    if TOKEN:
        try:
            stats = fetch_stats()
        except Exception as e:
            print("stats fetch failed, using placeholders:", e)
            stats = {k: DASH for k in
                     ["repos","contributed","stars","followers","commits","net","adds","dels"]}
    else:
        print("no token; placeholder stats")
        stats = {k: DASH for k in
                 ["repos","contributed","stars","followers","commits","net","adds","dels"]}

    with open("profile.svg", "w", encoding="utf-8") as f:
        f.write(build_svg(stats))
    with open("README.md", "w", encoding="utf-8") as f:
        f.write('<img src="./profile.svg" width="100%" alt="Sofia Grimm">\n')
    print("wrote profile.svg and README.md")

if __name__ == "__main__":
    main()
