import os
from db import engine
from fastmcp import FastMCP
from fastmcp.server.auth import require_scopes
from fastmcp.server.auth.providers.jwt import JWTVerifier
from config import settings

verifier = JWTVerifier(
    jwks_uri=f"{settings.huutoapp_mcp_idp_url}/realms/{settings.huutoapp_mcp_idp_realm}/protocol/openid-connect/certs",
    issuer=f"{settings.huutoapp_mcp_idp_url}/realms/{settings.huutoapp_mcp_idp_realm}",
    audience=settings.huutoapp_mcp_idp_audience
)
   
mcp = FastMCP("HuutoApp MCP Server", auth=verifier)

@mcp.lifespan()
async def app_lifespan():
    try:
        yield 
    finally:
        await engine.dispose()

@mcp.tool(auth=require_scopes("mcp:huutoapp:public"))
async def public(user: str) -> dict[str,str]:
    """Public greeting """
    return {"public_greeting": f"Hello {user}"}

@mcp.tool(auth=require_scopes("mcp:huutoapp:admin"))
async def admin(user: str) -> dict[str,str]:
    """Admin greeting """
    return {"admin_greeting": f"Hello {user}"}

