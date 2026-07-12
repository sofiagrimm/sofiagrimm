#!/usr/bin/env python3
"""
Generate a neofetch-style GitHub profile README with a fixed ASCII portrait
and auto-fetched GitHub stats.

Run locally with no token to produce a placeholder README.
In GitHub Actions, set STATS_TOKEN (a PAT) so stats across all repos are read.
"""
import os
import time
import requests

USER = os.environ.get("GH_USER", "sofiagrimm")
TOKEN = os.environ.get("STATS_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""
API = "https://api.github.com"
GQL = "https://api.github.com/graphql"
HEADERS = {"Authorization": f"bearer {TOKEN}"} if TOKEN else {}
DASH = "-"

# ---------- stats ----------

def graphql(query, variables):
    r = requests.post(GQL, json={"query": query, "variables": variables},
                      headers=HEADERS, timeout=30)
    r.raise_for_status()
    data = r.json()
    if "errors" in data:
        raise RuntimeError(data["errors"])
    return data["data"]

def fetch_user_and_repos():
    q = """
    query($login:String!, $after:String){
      user(login:$login){
        followers{ totalCount }
        repositoriesContributedTo(first:1,
          contributionTypes:[COMMIT, PULL_REQUEST, REPOSITORY]){ totalCount }
        repositories(first:100, after:$after, ownerAffiliations:[OWNER],
          isFork:false, orderBy:{field:STARGAZERS, direction:DESC}){
          totalCount
          pageInfo{ hasNextPage endCursor }
          nodes{ nameWithOwner stargazerCount }
        }
      }
    }"""
    followers = contributed = repo_count = stars = 0
    names = []
    after = None
    while True:
        u = graphql(q, {"login": USER, "after": after})["user"]
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
    return followers, contributed, repo_count, stars, names

def repo_contrib_stats(name_with_owner):
    """Return (commits, additions, deletions) by USER on the default branch."""
    owner, repo = name_with_owner.split("/", 1)
    url = f"{API}/repos/{owner}/{repo}/stats/contributors"
    for _ in range(6):
        r = requests.get(url, headers=HEADERS, timeout=30)
        if r.status_code == 202:      # GitHub is still computing; wait
            time.sleep(3)
            continue
        if r.status_code == 204 or not r.text.strip():
            return 0, 0, 0
        r.raise_for_status()
        for c in r.json():
            if c.get("author", {}).get("login", "").lower() == USER.lower():
                a = sum(w["a"] for w in c["weeks"])
                d = sum(w["d"] for w in c["weeks"])
                return c["total"], a, d
        return 0, 0, 0
    return 0, 0, 0

def fetch_stats():
    followers, contributed, repos, stars, names = fetch_user_and_repos()
    commits = adds = dels = 0
    for nm in names:
        try:
            c, a, d = repo_contrib_stats(nm)
            commits += c
            adds += a
            dels += d
        except Exception:
            pass
    net = adds - dels
    return dict(repos=repos, contributed=contributed, stars=stars,
                followers=followers, commits=commits,
                net=net, adds=adds, dels=dels)

# ---------- rendering ----------

ESC = "\x1b"
R = ESC + "[0m"
def c(x): return ESC + "[" + x + "m"
US = c("32;1"); LB = c("36;1"); HD = c("33;1")
NUM = c("32"); DIM = c("90"); ADD = c("32"); DEL = c("31")

def field(label, value):
    return f"{LB}{label:<15}{R}{value}"

def num(v):
    return f"{v:,}" if isinstance(v, int) else str(v)

def build(stats):
    n = lambda v: NUM + num(v) + R
    info = [
        US + "sofia@grimm" + R,
        DIM + "-" * 24 + R,
        field("OS", "macOS (New Haven)"),
        field("Host", "Yale University, Class of 2029"),
        field("Kernel", "Molecular Biophysics & Biochemistry"),
        field("Uptime", "19 years"),
        field("IDE", "VS Code, Jupyter, RStudio"),
        "",
        field("Languages.Prog", "Python, R, JavaScript"),
        field("Languages.Doc", "LaTeX, Markdown, HTML"),
        field("Languages.Real", "English, Chinese, Spanish, Latin"),
        "",
        field("Labs", "Higley (neuro), Wiznia (biomed)"),
        field("Focus", "translational science, health policy"),
        "",
        field("Hobbies.Sci", "neuro imaging, biomarker policy"),
        field("Hobbies.IRL", "vintage fashion, dance"),
        "",
        HD + "Contact" + R,
        field("Website", "sofiagrimm.com"),
        field("GitHub", "github.com/sofiagrimm"),
        "",
        HD + "GitHub Stats" + R,
        f"{LB}{'Repos':<15}{R}{n(stats['repos'])}   "
        f"{DIM}Contributed {R}{n(stats['contributed'])}   "
        f"{LB}Stars {R}{n(stats['stars'])}",
        f"{LB}{'Followers':<15}{R}{n(stats['followers'])}",
        f"{LB}{'Commits':<15}{R}{n(stats['commits'])}",
        f"{LB}{'Lines of Code':<15}{R}{n(stats['net'])}  "
        f"{DIM}({R}{ADD}{num(stats['adds'])}++{R}{DIM}, {R}"
        f"{DEL}{num(stats['dels'])}--{R}{DIM}){R}",
    ]

    portrait = open("portrait.txt", encoding="utf-8").read().split("\n")
    PW = max(len(l) for l in portrait)
    off = 1 if len(portrait) > len(info) else 0
    total = max(len(portrait), len(info) + off)

    def get(lst, i, o=0):
        j = i - o
        return lst[j] if 0 <= j < len(lst) else ""

    out = []
    for i in range(total):
        left = get(portrait, i).ljust(PW)
        right = get(info, i, off)
        out.append((left + "    " + right).rstrip())
    return "```ansi\n" + "\n".join(out) + "\n```\n"

def main():
    if TOKEN:
        try:
            stats = fetch_stats()
        except Exception as e:
            print("stats fetch failed, using placeholders:", e)
            stats = dict(repos=DASH, contributed=DASH, stars=DASH,
                         followers=DASH, commits=DASH, net=DASH,
                         adds=DASH, dels=DASH)
    else:
        print("no token; writing placeholder README")
        stats = dict(repos=DASH, contributed=DASH, stars=DASH,
                     followers=DASH, commits=DASH, net=DASH,
                     adds=DASH, dels=DASH)
    with open("README.md", "w", encoding="utf-8") as f:
        f.write(build(stats))
    print("README.md written")

if __name__ == "__main__":
    main()
