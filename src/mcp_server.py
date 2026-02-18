"""
MCP (Model Context Protocol) server – IDE integration.

Exposes the Policy RAG agent as an MCP tool so that IDEs like VS Code
(Copilot / Claude extension) and Cursor can call it directly.

Run via:
    python -m src.mcp_server
  or after `pip install -e .`:
    rag-mcp

IDE configuration (.vscode/mcp.json or Cursor settings):

  {
    "servers": {
      "policy-rag": {
        "type": "stdio",
        "command": "python",
        "args": ["-m", "src.mcp_server"],
        "cwd": "<absolute-path-to-this-project>"
      }
    }
  }
"""
from __future__ import annotations

import asyncio
import json
import sys

# ── Graceful import of the `mcp` SDK ─────────────────────────────────────────
try:
    from mcp.server.fastmcp import FastMCP
    _MCP_AVAILABLE = True
except ImportError:
    _MCP_AVAILABLE = False

# ── Local imports ─────────────────────────────────────────────────────────────
# Support running both as `python -m src.mcp_server` (relative imports)
# and as a standalone script (absolute imports).
try:
    from .rag_core import query_rag
    from .ollama_client import ollama_health
except ImportError:
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from src.rag_core import query_rag          # type: ignore
    from src.ollama_client import ollama_health  # type: ignore


# ── Fallback: stdio JSON-RPC server (no `mcp` package needed) ────────────────

def _run_stdio_fallback():
    """
    Minimal JSON-RPC 2.0 / MCP protocol server over stdin/stdout.
    Supports: initialize, tools/list, tools/call
    """
    import io
    out = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", newline="\n")

    TOOLS = [
        {
            "name": "query_policies",
            "description": (
                "Query the local IT Policy & Procedures RAG system. "
                "Returns an answer grounded in the indexed policy documents, "
                "along with citations and any missing incident details."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "Question about IT policies or procedures."
                    },
                    "history": {
                        "type": "array",
                        "description": "Optional prior conversation turns [{role, content}].",
                        "items": {
                            "type": "object",
                            "properties": {
                                "role":    {"type": "string"},
                                "content": {"type": "string"}
                            },
                            "required": ["role", "content"]
                        }
                    }
                },
                "required": ["question"]
            }
        },
        {
            "name": "ollama_health",
            "description": "Check whether the local Ollama server is running and list available models.",
            "inputSchema": {"type": "object", "properties": {}}
        }
    ]

    def _send(obj: dict):
        out.write(json.dumps(obj) + "\n")
        out.flush()

    def _handle(req: dict) -> dict | None:
        method  = req.get("method", "")
        req_id  = req.get("id")
        params  = req.get("params", {})

        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "serverInfo": {"name": "policy-rag-agent", "version": "0.1.0"},
                    "capabilities": {"tools": {}}
                }
            }

        if method == "initialized":
            return None   # notification – no response

        if method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"tools": TOOLS}
            }

        if method == "tools/call":
            tool_name = params.get("name")
            args      = params.get("arguments", {})

            try:
                if tool_name == "query_policies":
                    result = query_rag(
                        question=args["question"],
                        history=args.get("history"),
                    )
                    text = json.dumps(result, ensure_ascii=False, indent=2)

                elif tool_name == "ollama_health":
                    result = ollama_health()
                    text = json.dumps(result, ensure_ascii=False, indent=2)

                else:
                    return {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "error": {"code": -32601, "message": f"Unknown tool: {tool_name}"}
                    }

                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [{"type": "text", "text": text}],
                        "isError": False
                    }
                }

            except Exception as exc:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [{"type": "text", "text": f"Error: {exc}"}],
                        "isError": True
                    }
                }

        # Unknown method
        if req_id is not None:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"}
            }
        return None

    for raw_line in sys.stdin:
        raw_line = raw_line.strip()
        if not raw_line:
            continue
        try:
            req = json.loads(raw_line)
        except json.JSONDecodeError as exc:
            _send({"jsonrpc": "2.0", "id": None,
                   "error": {"code": -32700, "message": f"Parse error: {exc}"}})
            continue

        response = _handle(req)
        if response is not None:
            _send(response)


# ── FastMCP path (preferred when `mcp` package is installed) ──────────────────

def _run_fastmcp():
    mcp = FastMCP("policy-rag-agent")

    @mcp.tool()
    def query_policies(question: str, history: list | None = None) -> str:
        """
        Query the local IT Policy & Procedures RAG system.
        Returns an answer grounded in the indexed policy documents,
        along with citations and missing incident details (if any).
        """
        result = query_rag(question, history=history)
        return json.dumps(result, ensure_ascii=False, indent=2)

    @mcp.tool()
    def check_ollama_health() -> str:
        """Check whether the local Ollama server is running and list available models."""
        return json.dumps(ollama_health(), ensure_ascii=False, indent=2)

    mcp.run()   # uses stdio transport by default


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    # Always use the built-in fallback: it correctly skips blank lines,
    # which FastMCP's stdio transport does not tolerate (raises parse errors).
    # The fallback implements the full MCP 2024-11-05 JSON-RPC protocol and
    # is what Cursor / VS Code communicate with over stdin/stdout.
    _run_stdio_fallback()


if __name__ == "__main__":
    main()
