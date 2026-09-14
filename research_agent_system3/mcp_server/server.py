"""
MCP Server - Research Tools

Run: python mcp_server/server.py
Serves at: http://localhost:8000/mcp

Exposed tools:
  - search_web:  general web search (provider-agnostic; see search/)
  - search_jobs: multi-source, multi-query job search (see jobs/)
  - fetch_url:   fetches a page's real content, with SSRF + robots.txt protection
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastmcp import FastMCP

from mcp_server.tools.search import search_web as _search_web
from mcp_server.tools.fetch import fetch_url as _fetch_url
from mcp_server.tools.jobs import search_jobs as _search_jobs

mcp = FastMCP("research_tools")

mcp.tool()(_search_web)
mcp.tool()(_fetch_url)
mcp.tool()(_search_jobs)


if __name__ == "__main__":
    print("Starting MCP server with tools: search_web, search_jobs, fetch_url")
    mcp.run(transport="http", host="0.0.0.0", port=8000, path="/mcp")
