import os
import sys
import requests
from openai import OpenAI

# ================= CONFIG =================
GITHUB_API = "https://api.github.com"

OWNER = os.getenv("REPO_OWNER")
REPO = os.getenv("REPO_NAME")
PR = os.getenv("PR_NUMBER")
TOKEN = os.getenv("GITHUB_TOKEN")
SHA = os.getenv("GITHUB_SHA")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")

# ================= CLIENTS =================
client = OpenAI(api_key=OPENAI_KEY)

HEADERS = {
    "Authorization": f"token {TOKEN}",
    "Accept": "application/vnd.github+json"
}

# ================= HELPERS =================
def get_pr_files():
    url = f"{GITHUB_API}/repos/{OWNER}/{REPO}/pulls/{PR}/files"
    resp = requests.get(url, headers=HEADERS)
    resp.raise_for_status()
    return resp.json()

def post_review(message):
    print("📝 Posting PR review comment...")
    url = f"{GITHUB_API}/repos/{OWNER}/{REPO}/pulls/{PR}/reviews"
    requests.post(
        url,
        headers=HEADERS,
        json={
            "body": message,
            "event": "REQUEST_CHANGES"
        }
    )

def set_status(state, description):
    print(f"📌 Setting commit status: {state.upper()} — {description}")
    url = f"{GITHUB_API}/repos/{OWNER}/{REPO}/statuses/{SHA}"
    requests.post(
        url,
        headers=HEADERS,
        json={
            "state": state,  # success | failure
            "context": "Docu-Drift Agent",
            "description": description
        }
    )

# ================= MAIN =================
print("🚀 Starting Docu-Drift Agent")
print(f"🔍 Repository: {OWNER}/{REPO}")
print(f"🔍 PR Number: {PR}")

files = get_pr_files()
changed_files = [f["filename"] for f in files]

print("📂 Changed files:", changed_files)

code_changed = any(f.startswith("routes/") for f in changed_files)
docs_changed = any(f.startswith("docs/") for f in changed_files)

print(f"🧠 Code changed: {code_changed}")
print(f"🧠 Docs changed: {docs_changed}")

# ================= DRIFT DETECTED =================
if code_changed and not docs_changed:
    print("❌ Documentation Drift Detected")

    ai_response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": "You are an expert software documentation compliance reviewer."
            },
            {
                "role": "user",
                "content": (
                    "The following code files were changed without updating documentation:\n"
                    f"{changed_files}\n\n"
                    "Explain which documentation should be updated and why."
                )
            }
        ],
        temperature=0,
        max_tokens=300
    )

    feedback = ai_response.choices[0].message.content

    post_review(
        "❌ **Documentation Drift Detected**\n\n"
        f"{feedback}\n\n"
        "**Action Required:** Update the corresponding documentation files."
    )

    set_status("failure", "Documentation update required")

    print("🚫 Blocking PR — exiting with failure")
    sys.exit(1)

# ================= NO DRIFT =================
else:
    print("✅ No documentation drift detected")
    set_status("success", "Documentation is consistent")
