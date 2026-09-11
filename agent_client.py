"""
CLI entry point for the repo triage agent.
Thin wrapper around agent_core.run_agent_investigation — prints the trace
to the console as it runs. Logic lives in agent_core.py so the Streamlit
UI (streamlit_app.py) can reuse it without duplication.
"""
import asyncio
import sys

from agent_core import run_agent_investigation


async def main(issue_number: int):
    trace = await run_agent_investigation(issue_number)

    print(f"Loaded {len(trace['tools_loaded'])} tools: {trace['tools_loaded']}\n")

    for r in trace["rounds"]:
        print(f"[Round {r['round']}] Calling tool: {r['tool']}({r['args']})")
        preview = r["result"] if len(r["result"]) <= 300 else r["result"][:300] + " ...[truncated, see agent_run_log.txt]"
        print(f"  -> {preview}\n")

    if trace["final_diagnosis"]:
        print("=== FINAL DIAGNOSIS ===")
        print(trace["final_diagnosis"])
    elif trace["stopped_without_answer"]:
        print("Stopped: hit max tool-call rounds without a final answer.")


if __name__ == "__main__":
    issue_num = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    asyncio.run(main(issue_num))
