"""Recover unpublished data after an automatic commit, including no-change runs.

Uses the workflow's short-lived GitHub token. No credentials or response bodies
are logged. Existing Pages branch/directory configuration is not changed.
"""
import json
import os
import re
import sys
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def decision(latest, target):
    if latest and latest.get("status") == "built" and latest.get("commit") == target:
        return "current"
    if latest and latest.get("status") in {"queued", "building"}:
        return "in_progress"
    return "request"


def main():
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    token = os.environ.get("GH_TOKEN", "")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo) or not token:
        print("Pages check requires workflow repository context and GH_TOKEN.")
        return 1

    def api(path, method="GET"):
        req = Request("https://api.github.com/repos/" + repo + path,
                      data=b"{}" if method == "POST" else None, method=method,
                      headers={"Authorization":"Bearer " + token, "Accept":"application/vnd.github+json",
                               "User-Agent":"Vantage-Pages-Publisher", "X-GitHub-Api-Version":"2022-11-28"})
        with urlopen(req, timeout=25) as response:
            return json.load(response)

    # A fresh API read catches another collector's commit after this checkout.
    # If a build is already queued, coalesce rather than queue duplicate builds.
    try:
        target = api("/commits/main")["sha"]
        try:
            latest = api("/pages/builds/latest")
        except HTTPError as error:
            if error.code != 404:
                raise
            latest = None
        action = decision(latest, target)
        if action != "request":
            print("Pages publication: " + action + ". Subsequent runs recheck pending changes.")
            return 0
        for attempt in range(3):
            try:
                api("/pages/builds", "POST")
                print("Pages build requested for current main. Deployment can take additional time.")
                return 0
            except HTTPError as error:
                if error.code not in {429, 500, 502, 503, 504} or attempt == 2:
                    raise
                time.sleep(2 * (attempt + 1))
    except Exception as error:
        print("Pages publication check failed (" + type(error).__name__ + "). Next run will recheck, even with unchanged observations.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
