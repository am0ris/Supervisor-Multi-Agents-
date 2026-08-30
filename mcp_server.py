from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    "research-tools",
    stateless_http=True
)


@mcp.tool()
def search_web(query: str) -> str:
    """
    Search the web for information about a topic.
    """

    return f"Search results for: {query}"


if __name__ == "__main__":
    mcp.run(
        transport="streamable-http"
    )