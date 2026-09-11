"""
Step 7: the agent loop.
Connects to mcp_server.py as an MCP client, exposes its tools to Gemini,
and lets Gemini decide which tools to call to investigate a GitHub issue.
"""
import asyncio
import os
import datetime
import sys
from dotenv import load_dotenv
load_dotenv()

os.environ.pop("GOOGLE_API_KEY", None)

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from google import genai
from google.genai import types

GEMINI_MODEL = "gemini-3.5-flash-lite"
MAX_TOOL_ROUNDS = 7  # safety cap so a confused model can't loop forever

SYSTEM_PROMPT = """You are a repository triage agent investigating a GitHub issue
on the ResearchPilot codebase. You have tools to fetch the issue, search the
codebase, and find related issues.

    Strategy:
    1. First call get_issue to read the report.
    2. Extract the 2-3 most specific technical nouns from the issue -- ignore
       generic words and words that only match the issue's title.
    3. Search for those specific nouns with search_code.
    4. The MOMENT search_code returns a hit inside a real .py source file
   (not streamlit_app.py CSS, not an import line) — your VERY NEXT ACTION
   MUST be to call read_code_context on that exact file+line. Do not call
   search_code a second time in a row. If your last tool call was
   search_code and it found a real hit, this turn must be read_code_context.
    5. Once read_code_context shows you concrete logic (a conditional, a
       truncation/limit, a heuristic) that plausibly causes the reported
       behavior, STOP calling tools and write your Diagnosis immediately in
       your next response, even if you have budget left for more calls.

Rules:
- Use tools to gather real evidence before concluding anything.
- Every claim in your final diagnosis must cite a specific file and line number
  you actually saw via search_code.
- You should reach a conclusion within 4 tool calls. If you have found a
  concrete heuristic/function that plausibly explains the bug, stop and
  report it rather than continuing to search.
- If you truly cannot find clear evidence after 4 calls, say so explicitly
  rather than guessing.
- End with a clear "Diagnosis:" section summarizing the root cause and which
  file(s) are responsible.
"""

# --- Convert an MCP tool's JSON schema into Gemini's expected format ---
def mcp_tool_to_gemini_function(mcp_tool):
    props = {}
    for prop_name, prop_schema in mcp_tool.inputSchema.get("properties", {}).items():
        json_type = prop_schema.get("type", "string")
        type_map = {
            "string": types.Type.STRING,
            "integer": types.Type.INTEGER,
            "number": types.Type.NUMBER,
            "boolean": types.Type.BOOLEAN,
        }
        props[prop_name] = types.Schema(
            type=type_map.get(json_type, types.Type.STRING),
            description=prop_schema.get("description", ""),
        )
    return types.FunctionDeclaration(
        name=mcp_tool.name,
        description=mcp_tool.description or "",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties=props,
            required=mcp_tool.inputSchema.get("required", []),
        ),
    )


async def run_agent(issue_number: int):
    server_params = StdioServerParameters(
        command=sys.executable,  # uses THIS venv's python, no uv needed
        args=["mcp_server.py"],
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            with open("agent_run_log.txt", "a", encoding="utf-8") as log_f:
                log_f.write(f"\n{'='*60}\nNEW RUN: issue #{issue_number} | {datetime.datetime.now().isoformat()}\n{'='*60}\n\n")

            mcp_tools = (await session.list_tools()).tools
            gemini_tool = types.Tool(
                function_declarations=[mcp_tool_to_gemini_function(t) for t in mcp_tools]
            )
            print(f"Loaded {len(mcp_tools)} tools: {[t.name for t in mcp_tools]}\n")

            client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

            contents = [
                types.Content(
                    role="user",
                    parts=[types.Part(text=f"Investigate GitHub issue #{issue_number}.")],
                )
            ]

            for round_num in range(1, MAX_TOOL_ROUNDS + 1):
                response = client.models.generate_content(
                    model=GEMINI_MODEL,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT,
                        tools=[gemini_tool],
                    ),
                )
                candidate_content = response.candidates[0].content
                contents.append(candidate_content)

                function_calls = [
                    part.function_call for part in candidate_content.parts
                    if part.function_call is not None
                ]

                if not function_calls:
                    # Model gave a final answer, no more tools requested
                    print("=== FINAL DIAGNOSIS ===")
                    print(response.text)
                    return

                # Execute each requested tool call via the real MCP server
                response_parts = []
                for fc in function_calls:
                    print(f"[Round {round_num}] Calling tool: {fc.name}({dict(fc.args)})")
                    result = await session.call_tool(fc.name, arguments=dict(fc.args))
                    result_text = result.content[0].text if result.content else "(no output)"

                    # Console: short preview only, clearly marked as truncated
                    preview = result_text if len(result_text) <= 300 else result_text[:300] + " ...[truncated, see agent_run_log.txt]"
                    print(f"  -> {preview}\n")

                    # Full log file: complete, untruncated record of what the model actually saw
                    with open("agent_run_log.txt", "a", encoding="utf-8") as log_f:
                        log_f.write(f"=== Round {round_num} | Tool: {fc.name}({dict(fc.args)}) ===\n")
                        log_f.write(result_text)
                        log_f.write("\n\n")

                    response_parts.append(
                        types.Part.from_function_response(
                            name=fc.name,
                            response={"result": result_text},
                        )
                    )

                contents.append(types.Content(role="user", parts=response_parts))

            print("Stopped: hit max tool-call rounds without a final answer.")


if __name__ == "__main__":
    issue_num = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    asyncio.run(run_agent(issue_num))