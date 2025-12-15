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
    """
    Uses LLM to understand WHAT the code change impacts
    """
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

# ================== MAIN EXECUTION ==================
print("🚀 Starting Docu-Drift Agent (Advanced Mode)")

pr_files = get_pr_files()
changed_files = [f["filename"] for f in pr_files]

print("📂 Changed files:", changed_files)

code_files = [f for f in pr_files if f["filename"].startswith("routes/")]
readme_files = [f for f in pr_files if f["filename"] == "README.md"]

# No code change → nothing to validate
if not code_files:
    print("✅ No code changes detected")
    set_commit_status("success", "No documentation check required")
    sys.exit(0)

# README missing entirely
if not readme_files:
    message = (
        "❌ **Documentation Drift Detected**\n\n"
        "Code was modified, but **README.md was not updated**.\n\n"
        "Please update the relevant README section to describe the "
        "new or modified behavior."
    )
    post_review_comment(message)
    set_commit_status("failure", "README not updated")
    sys.exit(1)

# Build diff text
code_diff = "\n".join(f.get("patch", "") for f in code_files)
readme_patch = readme_files[0].get("patch", "")

# Infer intent
intent = infer_change_intent(code_diff)
print("🧠 Detected change intent:", intent)

readme_text = load_readme()
readme_sections = index_readme_sections(readme_text)

print("📖 README sections found:", list(readme_sections.keys()))

# Missing relevant section
if intent not in readme_sections:
    message = (
        "❌ **Documentation Drift Detected**\n\n"
        f"The code changes relate to **{intent}**, "
        "but the README does not contain a corresponding section.\n\n"
        f"Please add a **{intent}** section to README.md "
        "and document the recent changes."
    )
    post_review_comment(message)
    set_commit_status("failure", "Missing README section")
    sys.exit(1)

# Relevant section NOT updated
if intent.lower() not in readme_patch.lower():
    message = (
        "❌ **Documentation Drift Detected**\n\n"
        f"The code change impacts **{intent}**, "
        "but the relevant section in README.md was not updated.\n\n"
        "**What changed in code:**\n"
        f"- Behavior related to **{intent}**\n\n"
        "**What is missing in documentation:**\n"
        f"- Update the **{intent}** section to explain the new or modified behavior.\n\n"
        "Please update the README accordingly."
    )
    post_review_comment(message)
    set_commit_status("failure", "Relevant README section not updated")
    sys.exit(1)

# SUCCESS
print("✅ Documentation correctly updated")
set_commit_status("success", "Documentation matches code changes")
