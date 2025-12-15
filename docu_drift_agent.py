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
    response = requests.get(url, headers=HEADERS)
    response.raise_for_status()
    return response.json()

def post_review_comment(message):
    url = f"{GITHUB_API}/repos/{OWNER}/{REPO}/pulls/{PR_NUMBER}/reviews"
    requests.post(
        url,
        headers=HEADERS,
        json={"body": message, "event": "REQUEST_CHANGES"}
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

# ================== README HANDLING ==================
def load_readme():
    if not os.path.exists("README.md"):
        return ""
    with open("README.md", "r", encoding="utf-8") as f:
        return f.read()

def index_readme_sections(readme_text):
    sections = {}
    current_section = None
    for line in readme_text.splitlines():
        if line.startswith("## "):
            current_section = line.replace("## ", "").strip()
            sections[current_section] = []
        elif current_section:
            sections[current_section].append(line)
    return {k: "\n".join(v) for k, v in sections.items()}

# ================== AI INTELLIGENCE ==================
def infer_change_intent(code_diff):
    prompt = f"""
You are a senior software architect.

Analyze the following code diff and respond with ONLY ONE
most relevant documentation section name from this list:

- Users API
- Pagination
- Authentication
- Error Handling
- Other

Code Diff:
{code_diff}
"""
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )
    return response.choices[0].message.content.strip()

def generate_readme_fix(intent, code_diff):
    prompt = f"""
You are an expert technical writer.

Generate a concise README section update for:
Section: {intent}

Based on this code change:
{code_diff}

Return ONLY markdown content for that section.
"""
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )
    return response.choices[0].message.content.strip()

# ================== MAIN ==================
print("🚀 Starting Docu-Drift Agent (Advanced + Auto-Suggest)")

pr_files = get_pr_files()
changed_files = [f["filename"] for f in pr_files]

print("📂 Changed files:", changed_files)

code_files = [f for f in pr_files if f["filename"].startswith("routes/")]
readme_files = [f for f in pr_files if f["filename"] == "README.md"]

# No code change
if not code_files:
    print("✅ No code changes detected")
    set_commit_status("success", "No documentation check required")
    sys.exit(0)

code_diff = "\n".join(f.get("patch", "") for f in code_files)

intent = infer_change_intent(code_diff)
print("🧠 Detected change intent:", intent)

# README missing
if not readme_files:
    suggestion = generate_readme_fix(intent, code_diff)

    comment = f"""
❌ **Documentation Drift Detected**

The code change affects **{intent}**, but `README.md` was not updated.

### ✅ Suggested Fix (click **Apply suggestion**)
```suggestion
## {intent}
{suggestion}
