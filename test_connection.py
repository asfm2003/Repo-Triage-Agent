"""
Sanity check: confirms the GitHub token can see the repo and list issues,
before we build anything more complex on top of it.
"""
from dotenv import load_dotenv
import os
from github import Github, Auth

load_dotenv()  # must run BEFORE we read the env vars below

token = os.getenv("GITHUB_TOKEN")
owner = os.getenv("GITHUB_REPO_OWNER")
name = os.getenv("GITHUB_REPO_NAME")

auth = Auth.Token(token)
gh = Github(auth=auth)

repo = gh.get_repo(f"{owner}/{name}")
print(f"Connected to: {repo.full_name}")
print(f"Repo visibility: {'private' if repo.private else 'public'}")

issues = list(repo.get_issues(state="all"))
print(f"Total issues found: {len(issues)}")

for issue in issues[:5]:
    print(f"  #{issue.number}: {issue.title} [{issue.state}]")

if len(issues) == 0:
    print("\nNo issues yet — that's fine, we'll create 2-3 test issues next step.")