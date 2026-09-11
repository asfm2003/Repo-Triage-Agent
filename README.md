# 🔍 Repo Triage Agent

An MCP-based agent that autonomously investigates GitHub issues on a real codebase — it plans its own investigation, calls tools to gather evidence, and produces a diagnosis grounded in actual file/line citations. Built as a hands-on exploration of agentic AI patterns beyond simple RAG.

## Why this project

Most "agentic AI" portfolio demos are support chatbots wrapping a knowledge base. This is different: it's a **multi-tool orchestration agent** that has to plan, not just retrieve. Given a GitHub issue, it decides for itself whether to read the issue, search the codebase, check related issues, or inspect specific code — there's no fixed pipeline, just tools and a reasoning loop deciding how to use them.

## Architecture

```
GitHub repo (issues)
        │
        ▼
┌──────────────────────────┐
│      MCP SERVER          │  exposes tools the agent can call
│  - get_issue(id)         │  fetch issue title/body/comments
│  - search_code(q)        │  grep-style search over a local repo clone
│  - list_similar_issues() │  find past issues with overlapping keywords
│  - read_code_context()   │  inspect the logic around a search hit
└──────────────────────────┘
        ▲
        │  JSON-RPC over stdio (the MCP standard)
        ▼
┌──────────────────────────┐
│   MCP CLIENT + AGENT      │  the reasoning loop (Gemini)
│  1. take an issue         │
│  2. plan which tool to use│
│  3. call tools            │
│  4. synthesize a diagnosis│
│  5. (planned) stop for    │
│     human approval before │
│     drafting any PR       │
└──────────────────────────┘
```

**Why this shape:** MCP's core idea is separating *tools* (the server) from *the thing deciding which tool to call* (the agent). That separation — not just "a script that calls the GitHub API" — is what makes this a genuine agent architecture rather than a scripted pipeline.

## What it actually does

Given a GitHub issue number, the agent:
1. Fetches the issue via `get_issue`
2. Identifies specific technical terms worth searching for
3. Greps the local codebase via `search_code`
4. Inspects the surrounding logic at a promising hit via `read_code_context`
5. Produces a diagnosis that cites the specific file and line number it actually saw — not a guess

Every claim in the final diagnosis is required (by the system prompt) to trace back to real tool output, not the model's general knowledge of what a bug "usually" looks like.

## Demo

Run the Streamlit UI locally to see the agent's tool-calling trace live, round by round, followed by its grounded diagnosis:

```bash
streamlit run streamlit_app.py
```

## Setup

1. Clone the repo and create a virtual environment:
   ```bash
   python -m venv venv
   venv\Scripts\activate   # Windows
   pip install -r requirements.txt
   ```

2. Create a `.env` file (never commit this):
   ```
   GITHUB_TOKEN=your_fine_grained_pat
   GITHUB_REPO_OWNER=your_username
   GITHUB_REPO_NAME=your_test_repo
   RESEARCHPILOT_LOCAL_PATH=/path/to/local/clone
   GEMINI_API_KEY=your_gemini_key
   ```

   Your GitHub token should be a **fine-grained PAT** scoped to a single test repo with `Issues: read`, `Contents: read`, `Pull requests: write` — never a full-access token.

3. Run against a specific issue:
   ```bash
   python agent_client.py <issue_number>
   ```
   or launch the UI:
   ```bash
   streamlit run streamlit_app.py
   ```

## Safety design

The agent **never auto-merges or auto-writes code**. Diagnosis and (planned) PR-drafting are separate steps, and PR drafting will always stop for explicit human approval before anything is committed. This mirrors a realistic production stance: agents that can reason about code shouldn't be trusted to act on it unsupervised.

## Current limitations (known, not hidden)

- Tested against a small, curated set of issues on a single test repo — not yet evaluated at scale
- Uses Gemini's free tier during development, which caps daily request volume
- No automated eval harness yet — diagnoses are currently checked manually against actual file contents
- `search_code` is a simple grep — no semantic/embedding-based code search yet

## Roadmap

- [ ] **`draft_pr` tool** — agent proposes an actual code fix as a PR, with a hard human-approval gate before any branch/commit/PR is created
- [ ] **Eval harness** — a small labeled test set of issues with known root-cause files, scored on whether the agent's diagnosis correctly identifies the responsible file (Recall@k-style, mirroring how retrieval systems are evaluated)
- [ ] **Grounding check** — automated verification that every file:line cited in a diagnosis actually appeared in a tool result the model received, to catch hallucinated citations automatically
- [ ] **Semantic code search** — replace/augment grep-based `search_code` with embedding-based retrieval for codebases where keyword search misses relevant context
- [ ] **Multi-model comparison** — benchmark diagnosis quality and grounding rate across Gemini Flash-Lite vs Flash vs Claude, as a small ablation study
- [ ] **Cost/quota tracking** — surface real-time API call count and estimated cost per run in the UI

## Tech stack

- [Official MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) — tool/agent separation
- Google Gemini API (`gemini-3.5-flash-lite`) — reasoning engine
- PyGithub — GitHub API access
- Streamlit — demo UI

## License

MIT
