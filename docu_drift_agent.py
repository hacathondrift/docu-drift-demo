import os
import requests
from openai import OpenAI

GITHUB_API = "https://api.github.com"

OWNER = os.getenv("REPO_OWNER")
REPO = os.getenv("REPO_NAME")
PR = os.getenv("PR_NUMBER")
TOKEN = os.getenv("GITHUB_TOKEN")
SHA = os.getenv("GITHUB_SHA")

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
HEADERS = {"Authorization": f"token {TOKEN}"}

def get_pr_files():
    url = f"{GITHUB_API}/repos/{OWNER}/{REPO}/pulls/{PR}/files"
    return requests.get(url, headers=HEADERS).json()

def post_review(msg):
    url = f"{GITHUB_API}/repos/{OWNER}/{REPO}/pulls/{PR}/reviews"
    requests.post(url, headers=HEADERS,
        json={"body": msg, "event": "REQUEST_CHANGES"}
    )

def set_status(state, msg):
    url = f"{GITHUB_API}/repos/{OWNER}/{REPO}/statuses/{SHA}"
    requests.post(url, headers=HEADERS,
        json={"state": state, "context": "Docu-Drift Agent", "description": msg}
    )

files = get_pr_files()
changed = [f["filename"] for f in files]

code_changed = any(f.startswith("routes/") for f in changed)
docs_changed = any(f.startswith("docs/") for f in changed)

if code_changed and not docs_changed:
    feedback = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a documentation compliance reviewer."},
            {"role": "user", "content": f"Code changed but docs missing:\n{changed}"}
        ],
        temperature=0
    ).choices[0].message.content

    post_review("❌ Documentation Drift Detected\n\n" + feedback)
    set_status("failure", "Documentation update required")
else:
    set_status("success", "Documentation is consistent")
