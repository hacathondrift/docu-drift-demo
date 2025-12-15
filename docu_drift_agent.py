import os
import sys
import requests
from openai import OpenAI

# ---------------- CONFIG ----------------
GITHUB_API = "https://api.github.com"

OWNER = os.getenv("REPO_OWNER")
REPO = os.getenv("REPO_NAME")
PR = os.getenv("PR_NUMBER")
TOKEN = os.getenv("GITHUB_TOKEN")
SHA = os.getenv("GITHUB_SHA")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_KEY)

HEADERS = {
    "Authorization": f"token {TOKEN}",
    "Accept": "application/vnd.github+json"
}

# ---------------- GITHUB HELPERS ----------------
def get_pr_files():
    url = f"{GITHUB_API}/repos/{OWNER}/{REPO}/pulls/{PR}/files"
    r = requests.get(url, headers=HEADERS)
    r.raise_for_status()
    return r.json()

def post_review(msg):
    url = f"{GITHUB_API}/repos/{OWNER}/{REPO}/pulls/{PR}/reviews"
    requests.post(url, headers=HEADERS, json={
        "body": msg,
        "event": "REQUEST_CHANGES"
    })

def set_status(state, desc):
    url = f"{GITHUB_API}/repos/{OWNER}/{REPO}/statuses/{SHA}"
    requests.post(url, headers=HEADERS, json={
        "state": state,
        "context": "Docu-Drift Agent",
        "description": desc
    })

# ---------------- README LOGIC ----------------
def load_readme():
    with open("README.md", "r", encoding="utf-8") as f:
        return f.read()

def index_readme_sections(readme):
    sections = {}
    current = None

    for line in readme.splitlines():
        if line.startswith("## "):
            current = line.replace("## ", "").strip()
            sections[current] = []
        elif current:
            sections[current].append(line)

    return {k: "\n".join(v) for k, v in sections.items()}

# ---------------- AI INTELLIGENCE ----------------
def infer_code_intent(code_diff):
    prompt = f"""
Analyze the following code diff and answer with ONLY ONE section name
that best matches the change.

Possible sections:
- Users API
- Pagination
- Authentication
- Error Handling
- Other

Diff:
{code_diff}
"""
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )
    return resp.choices[0].message.content.strip()

# ---------------- MAIN ----------------
print("🚀 Starting Advanced Docu-Drift Agent")

files = get_pr_files()
changed_files = [f["filename"] for f in files]

print("📂 Changed files:", changed_files)

code_files = [f for f in files if f["filename"].startswith("routes/")]
readme_files = [f for f in files if f["filename"] == "README.md"]

if not code_files:
    print("✅ No code changes detected")
    sys.exit(0)

if not readme_files:
    post_review("❌ Code changed but README was not updated.")
    set_status("failure", "README not updated")
    sys.exit(1)

code_diff = "\n".join(f.get("patch", "") for f in code_files)
readme_patch = readme_files[0].get("patch", "")

intent = infer_code_intent(code_diff)
print("🧠 Detected intent:", intent)

readme_text = load_readme()
sections = index_readme_sections(readme_text)

print("📖 README sections:", list(sections.keys()))

if intent not in sections:
    post_review(
        f"❌ Code change relates to **{intent}**, "
        f"but README has no such section."
    )
    set_status("failure", "Missing README section")
    sys.exit(1)

if intent.lower() not in readme_patch.lower():
    post_review(
        f"❌ Code change affects **{intent}**, "
        f"but that section was NOT updated in README.\n\n"
        f"Please update the **{intent}** section."
    )
    set_status("failure", "Relevant README section not updated")
    sys.exit(1)

print("✅ README correctly updated for code change")
set_status("success", "Documentation matches code changes")
