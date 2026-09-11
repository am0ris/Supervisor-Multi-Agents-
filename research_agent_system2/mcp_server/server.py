"""
MCP Server - Research Tools
تشغيل: python mcp_server/server.py
هيشتغل على: http://localhost:8000/mcp
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastmcp import FastMCP

from mcp_server.tools.search import search_web as _search_web
from mcp_server.tools.fetch import fetch_url as _fetch_url

mcp = FastMCP("research_tools")

mcp.tool()(_search_web)
mcp.tool()(_fetch_url)


if __name__ == "__main__":
    print("Starting MCP server with tools: search_web, fetch_url")
    mcp.run(transport="http", host="0.0.0.0", port=8000, path="/mcp")
