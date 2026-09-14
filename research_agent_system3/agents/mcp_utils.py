"""
Parses results returned by MCP tools invoked through langchain_mcp_adapters.

Tools registered with FastMCP that return a list or a plain dict often
come back through the adapter as a wire-format wrapper:
    [{"type": "text", "text": "<json string>", "id": "..."}]
rather than the native Python object the tool function actually
returned. This is easy to miss because it only shows up once a tool call
actually succeeds with non-trivial data - a tool that returns nothing
(e.g. blocked by sandbox network restrictions) never exposes the parsing
gap, which is exactly how this stayed hidden through earlier testing.

`parse_mcp_result` normalizes both shapes so every agent that calls an
MCP tool can just call this once and get back the real object.
"""
import json


def parse_mcp_result(result):
    """
    Returns the tool's actual return value (a dict or list), regardless
    of whether the adapter delivered it as a native Python object or as
    the [{"type": "text", "text": "<json>"}] wire-format wrapper.
    """
    if (
        isinstance(result, list)
        and len(result) == 1
        and isinstance(result[0], dict)
        and result[0].get("type") == "text"
        and "text" in result[0]
    ):
        try:
            return json.loads(result[0]["text"])
        except (json.JSONDecodeError, TypeError):
            return result

    return result
