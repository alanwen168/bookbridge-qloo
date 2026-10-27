"""Official MCP SDK 2 stdio server: python -m bookbridge.mcp_server."""
from __future__ import annotations
from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import ValidationError
from bookbridge.core import find_shared
from bookbridge.models import RecommendationRequest, SearchRequest
from bookbridge.gateway import live_client
from bookbridge.qloo import QlooError

mcp = MCPServer("bookbridge")

@mcp.tool(annotations=ToolAnnotations(read_only_hint=True, destructive_hint=False, open_world_hint=True))
async def search_taste_anchors(query: str, kind: str) -> list[dict]:
    """Search live Qloo for user-confirmable anchor IDs (book, movie, or artist)."""
    try: body = SearchRequest(query=query, kind=kind)
    except ValidationError: raise ToolError("Invalid query or kind.") from None
    try: rows = await live_client().search(body.query, body.kind)
    except QlooError as exc: raise ToolError(str(exc)) from None
    return [x.__dict__ for x in rows]

@mcp.tool(annotations=ToolAnnotations(read_only_hint=True, destructive_hint=False, open_world_hint=True))
async def find_shared_read(member_one: list[dict], member_two: list[dict], top_k: int = 3) -> dict:
    """Find shared live-Qloo books from two members' confirmed anchor entities."""
    try: body = RecommendationRequest(members=[member_one, member_two], top_k=top_k)
    except ValidationError: raise ToolError("Invalid member anchors or top_k.") from None
    try: return await find_shared(live_client(), body.members, body.top_k)
    except QlooError as exc: raise ToolError(str(exc)) from None


if __name__ == "__main__":
    mcp.run(transport="stdio")
