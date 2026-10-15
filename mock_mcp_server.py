"""
Fake MCP tool server for safe testing. Plain Python, nothing to install.

It looks like a real MCP server (for example an Odoo connector) to Claude Code, but every tool
returns pretend data from a JSON file and NOTHING real is touched. Every call is written to a log,
so tests can check which tools the agent called and with what arguments.

Usage (Claude Code starts it automatically from an MCP config file):
    python mock_mcp_server.py <tools.json> <calls.log>
"""
import json
import sys
from datetime import datetime

tools_file, log_file = sys.argv[1], sys.argv[2]
with open(tools_file, encoding="utf-8") as f:
    TOOLS = json.load(f)["tools"]
BY_NAME = {t["name"]: t for t in TOOLS}


def send(msg):
    sys.stdout.write(json.dumps(msg) + "\n")
    sys.stdout.flush()


def log_call(name, arguments):
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps({"time": datetime.now().isoformat(timespec="seconds"),
                            "tool": name, "arguments": arguments}) + "\n")


for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        msg = json.loads(line)
    except json.JSONDecodeError:
        continue
    method, msg_id = msg.get("method"), msg.get("id")
    if msg_id is None:            # notifications (like notifications/initialized) need no reply
        continue
    if method == "initialize":
        version = msg.get("params", {}).get("protocolVersion", "2025-06-18")
        send({"jsonrpc": "2.0", "id": msg_id, "result": {
            "protocolVersion": version,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "mock-tools", "version": "0.1"}}})
    elif method == "tools/list":
        send({"jsonrpc": "2.0", "id": msg_id, "result": {"tools": [
            {"name": t["name"], "description": t["description"],
             "inputSchema": t.get("input_schema", {"type": "object", "properties": {}})} for t in TOOLS]}})
    elif method == "tools/call":
        name = msg.get("params", {}).get("name")
        arguments = msg.get("params", {}).get("arguments", {})
        log_call(name, arguments)
        tool = BY_NAME.get(name)
        if tool is None:
            send({"jsonrpc": "2.0", "id": msg_id, "result": {
                "content": [{"type": "text", "text": f"Unknown tool {name}"}], "isError": True}})
        else:
            send({"jsonrpc": "2.0", "id": msg_id, "result": {
                "content": [{"type": "text", "text": tool["returns"]}], "isError": False}})
    elif method == "ping":
        send({"jsonrpc": "2.0", "id": msg_id, "result": {}})
    else:
        send({"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32601, "message": f"Method not found: {method}"}})
