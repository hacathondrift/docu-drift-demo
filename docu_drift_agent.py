import os
import sys
import requests
from openai import OpenAI

# ================== CONFIG ==================
GITHUB_API = "https://api.github.com"

OWNER = os.getenv("REPO_OWNER")
REPO = os.getenv("REPO_NAME")
PR_NUMBER = os.getenv("PR_NUMBER")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_SHA = os.getenv("GITHUB_SHA")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json"
}

# ================== GITHUB HELPERS ==================
def get_pr_files():
    url = f"{GITHUB_API}/repos/{OWNER}/{REPO}/pulls/{PR_NUMBER}/files"
    r = requests.get(url, headers=HEADERS)
    r.raise_for_status()
    return r.json()

def post_review_comment(body):
    url = f"{GITHUB_API}/repos/{OWNER}/{REPO}/pulls/{PR_NUMBER}/reviews"
    requests.post(
        url,
        headers=HEADERS,
        json={"body": body, "event": "REQUEST_CHANGES"}
    )

def set_commit_status(state, description):
    url = f"{GITHUB_API}/repos/{OWNER}/{REPO}/statuses/{GITHUB_SHA}"
    requests.post(
        url,
        headers=HEADERS,
        json={
            "state": state,
            "context": "Docu-Drift Agent",
            "description": description
        }
    )

# ================== README ==================
def load_readme():
    if not os.path.exists("README.md"):
        return ""
    with open("README.md", "r", encoding="utf-8") as f:
        return f.read()

def index_readme_sections(text):
    sections = {}
    current = None
    for line in text.splitlines():
        if line.startswith("## "):
            current = line.replace("## ", "").strip()
            sections[current] = []
        elif current:
            sections[current].append(line)
    return {k: "\n".join(v) for k, v in sections.items()}

# ================== AI ==================
def infer_change_intent(code_diff):
    prompt = (
        "Analyze this code diff and return ONLY ONE of:\n"
        "Users API, Pagination, Authentication, Error Handling, Other\n\n"
        f"{code_diff}"
    )
    r = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )
    return r.choices[0].message.content.strip()

def generate_readme_fix(intent, code_diff):
    prompt = (
        f"Write a concise README section for '{intent}' based on this code:\n\n"
        f"{code_diff}"
    )
    r = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )
    return r.choices[0].message.content.strip()

# ================== MAIN ==================
print("🚀 Starting Docu-Drift Agent")

files = get_pr_files()
changed_files = [f["filename"] for f in files]
print("📂 Changed files:", changed_files)

code_files = [f for f in files if f["filename"].startswith("routes/")]
readme_files = [f for f in files if f["filename"] == "README.md"]

if not code_files:
    set_commit_status("success", "No documentation check required")
    sys.exit(0)

code_diff = "\n".join(f.get("patch", "") for f in code_files)
intent = infer_change_intent(code_diff)
print("🧠 Detected intent:", intent)

if not readme_files:
    suggestion = generate_readme_fix(intent, code_diff)

    comment = (
        "❌ **Documentation Drift Detected**\n\n"
        f"Code changes affect **{intent}**, but README.md was not updated.\n\n"
        "### ✅ Suggested Fix\n\n"
        "```suggestion\n"
        f"## {intent}\n{suggestion}\n"
        "```"
    )

    post_review_comment(comment)
    set_commit_status("failure", "README not updated")
    sys.exit(1)

readme_patch = readme_files[0].get("patch", "")
readme_text = load_readme()
sections = index_readme_sections(readme_text)

if intent not in sections or intent.lower() not in readme_patch.lower():
    suggestion = generate_readme_fix(intent, code_diff)

    comment = (
        "❌ **Documentation Drift Detected**\n\n"
        f"Code impacts **{intent}**, but README was not updated correctly.\n\n"
        "### ✅ Suggested Fix\n\n"
        "```suggestion\n"
        f"## {intent}\n{suggestion}\n"
        "```"
    )

    post_review_comment(comment)
    set_commit_status("failure", "Documentation update required")
    sys.exit(1)

set_commit_status("success", "Documentation matches code changes")
print("✅ Documentation validated successfully")
