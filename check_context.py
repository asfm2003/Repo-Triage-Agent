from mcp_server import read_code_context

result = read_code_context("ingestion/pdf_parser.py", 26, 30)
print(result)
print(f"\n--- Total lines returned: {len(result.splitlines())} ---")