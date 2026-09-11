"""
Shared agent logic used by both the CLI (agent_client.py) and the
Streamlit UI (streamlit_app.py). Runs the MCP + Gemini investigation loop
and returns a structured trace instead of just printing, so any frontend
can render it.
"""
import os
import sys
import datetime
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


async def run_agent_investigation(issue_number: int, log_to_file: bool = True) -> dict:
    """
    Runs the full MCP + Gemini investigation loop for a given issue.

    Returns a dict:
        {
            "tools_loaded": [str, ...],
            "rounds": [
                {"round": int, "tool": str, "args": dict, "result": str},
                ...
            ],
            "final_diagnosis": str | None,
            "stopped_without_answer": bool,
        }
    """
    trace = {
        "tools_loaded": [],
        "rounds": [],
        "final_diagnosis": None,
        "stopped_without_answer": False,
    }

    server_params = StdioServerParameters(
        command=sys.executable,
        args=["mcp_server.py"],
    )

    if log_to_file:
        with open("agent_run_log.txt", "a", encoding="utf-8") as log_f:
            log_f.write(
                f"\n{'='*60}\nNEW RUN: issue #{issue_number} | "
                f"{datetime.datetime.now().isoformat()}\n{'='*60}\n\n"
            )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            mcp_tools = (await session.list_tools()).tools
            trace["tools_loaded"] = [t.name for t in mcp_tools]

            gemini_tool = types.Tool(
                function_declarations=[mcp_tool_to_gemini_function(t) for t in mcp_tools]
            )

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
                    trace["final_diagnosis"] = response.text
                    return trace

                response_parts = []
                for fc in function_calls:
                    result = await session.call_tool(fc.name, arguments=dict(fc.args))
                    result_text = result.content[0].text if result.content else "(no output)"

                    trace["rounds"].append({
                        "round": round_num,
                        "tool": fc.name,
                        "args": dict(fc.args),
                        "result": result_text,
                    })

                    if log_to_file:
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

            trace["stopped_without_answer"] = True
            return trace
