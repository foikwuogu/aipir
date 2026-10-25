#!/usr/bin/env python3
"""01 - Fetch HAI 21.03 (primary) and HAI 20.07 (replication) at a pinned commit.

Tries raw.githubusercontent.com first; if that host is unreachable, falls back to a
partial git clone of the same commit. Every file is logged to data/raw/PROVENANCE.txt
(name, bytes, SHA-256, URL, access date). Idempotent: existing files with a matching
SHA-256 in the log are not re-downloaded.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RAW = os.path.join(ROOT, "data", "raw")
LOG = os.path.join(RAW, "PROVENANCE.txt")
REPO = "https://github.com/icsdataset/hai.git"
COMMIT = "2a814cebc9a66b06c9e5cd545e2d72e65d383737"
FILES = {
    "hai-21.03": ["train1", "train2", "train3", "test1", "test2", "test3", "test4", "test5"],
    "hai-20.07": ["train1", "train2", "test1", "test2"],
}


def url(ver, name):
    return f"https://raw.githubusercontent.com/icsdataset/hai/{COMMIT}/{ver}/{name}.csv.gz"


def log(path, src, note):
    subprocess.run([sys.executable, os.path.join(HERE, "provenance.py"), path, src,
                    "--log", LOG, "--note", note], check=True)


def try_http(ver, name, dest):
    try:
        urllib.request.urlretrieve(url(ver, name), dest)
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"  http failed ({exc.__class__.__name__}); will use git fallback")
        return False


def git_fallback(missing):
    tmp = tempfile.mkdtemp()
    subprocess.run(["git", "clone", "-q", "--filter=blob:none", "--no-checkout", REPO, tmp], check=True)
    subprocess.run(["git", "-C", tmp, "checkout", "-q", COMMIT, "--"] +
                   [f"{v}/{n}.csv.gz" for v, n, _ in missing], check=True)
    for v, n, dest in missing:
        shutil.copy(os.path.join(tmp, v, f"{n}.csv.gz"), dest)
        log(dest, url(v, n), f"git checkout {REPO}@{COMMIT[:12]} {v}/{n}.csv.gz")
    shutil.rmtree(tmp, ignore_errors=True)


def main():
    os.makedirs(RAW, exist_ok=True)
    missing = []
    for ver, names in FILES.items():
        os.makedirs(os.path.join(RAW, ver), exist_ok=True)
        for n in names:
            dest = os.path.join(RAW, ver, f"{n}.csv.gz")
            if os.path.exists(dest):
                print("have", ver, n)
                continue
            print("fetch", ver, n)
            if try_http(ver, n, dest):
                log(dest, url(ver, n), f"pinned commit {COMMIT[:12]}")
            else:
                missing.append((ver, n, dest))
    if missing:
        git_fallback(missing)
    print("done; provenance in", LOG)


if __name__ == "__main__":
    main()
