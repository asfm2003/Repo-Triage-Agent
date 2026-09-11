"""
MCP server exposing GitHub + local-codebase inspection tools for the triage agent.
Step 6: adds search_code and list_similar_issues.
"""
from dotenv import load_dotenv
load_dotenv()

import os
from pathlib import Path
from github import Github, Auth
from mcp.server.fastmcp import FastMCP

token = os.getenv("GITHUB_TOKEN")
owner = os.getenv("GITHUB_REPO_OWNER")
name = os.getenv("GITHUB_REPO_NAME")
local_path = Path(os.getenv("RESEARCHPILOT_LOCAL_PATH"))

gh = Github(auth=Auth.Token(token))
repo = gh.get_repo(f"{owner}/{name}")

mcp = FastMCP("repo-triage-agent")

# folders we never want to search inside
SKIP_DIRS = {"venv", "__pycache__", "chroma_db", "data", ".git"}


@mcp.tool()
def get_issue(issue_number: int) -> str:
    """Fetch a GitHub issue's title, body, and comments by issue number."""
    issue = repo.get_issue(number=issue_number)
    comments = [c.body for c in issue.get_comments()]
    result = f"Title: {issue.title}\n\nBody:\n{issue.body}\n"
    if comments:
        result += "\nComments:\n" + "\n---\n".join(comments)
    return result


@mcp.tool()
def search_code(query: str, max_results: int = 15) -> str:
    """Search the ResearchPilot codebase (read-only) for a keyword or phrase.
    Returns matching file paths, line numbers, and the matching line text."""
    matches = []
    for py_file in local_path.rglob("*.py"):
        if any(skip in py_file.parts for skip in SKIP_DIRS):
            continue
        try:
            lines = py_file.read_text(encoding="utf-8", errors="ignore").splitlines()
        except Exception:
            continue
        for i, line in enumerate(lines, start=1):
            if query.lower() in line.lower():
                rel_path = py_file.relative_to(local_path)
                matches.append(f"{rel_path}:{i}: {line.strip()}")
                if len(matches) >= max_results:
                    return "\n".join(matches)
    if not matches:
        return f"No matches found for '{query}'."
    return "\n".join(matches)


@mcp.tool()
def list_similar_issues(keywords: str) -> str:
    """Find existing GitHub issues whose title/body overlap with the given
    space-separated keywords. Returns issue number, title, and match count."""
    kw_set = set(keywords.lower().split())
    scored = []
    for issue in repo.get_issues(state="all"):
        text = f"{issue.title} {issue.body or ''}".lower()
        score = sum(1 for kw in kw_set if kw in text)
        if score > 0:
            scored.append((score, issue.number, issue.title))
    scored.sort(reverse=True)
    if not scored:
        return "No overlapping issues found."
    return "\n".join(f"#{num} (score {score}): {title}" for score, num, title in scored[:5])

@mcp.tool()
def read_code_context(file_path: str, line_number: int, context_lines: int = 6) -> str:
    """Read a window of lines around a specific line in a file, so you can see
    the surrounding logic after search_code points you at a promising hit.
    file_path should be relative, e.g. 'ingestion/pdf_parser.py' (as shown by search_code)."""
    full_path = local_path / file_path
    if not full_path.exists():
        return f"File not found: {file_path}"
    lines = full_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    start = max(0, line_number - 1 - context_lines)
    end = min(len(lines), line_number + context_lines)
    numbered = [f"{i+1}: {lines[i]}" for i in range(start, end)]
    return "\n".join(numbered)

if __name__ == "__main__":
    mcp.run()