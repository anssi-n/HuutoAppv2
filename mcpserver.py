from fastmcp import FastMCP # type: ignore
from huutomcp import tools
from logger import logger
from db import engine
from fastmcp.server.auth import TokenVerifier
from fastmcp.server.auth.auth import AccessToken
from fastmcp.server.auth import require_scopes
import secrets

EXPECTED_TOKEN = "my-super-secret-api-key"

# In keycloak admin gets both public and admin scsopes. Normal user get only public scope
class StaticTokenVerifier(TokenVerifier):    
    async def verify_token(self, token: str) -> AccessToken | None:
        
        if secrets.compare_digest(token, EXPECTED_TOKEN):
            return AccessToken(
                token=token,
                client_id="static-client",
                scopes=["public", "admin"],
#                scopes=["public"]
            )
        return None

mcp = FastMCP("HuutoApp MCP Server", auth=StaticTokenVerifier())

@mcp.lifespan()
async def app_lifespan():
    try:
        yield 
    finally:
        await engine.dispose()

@mcp.tool(auth=require_scopes("public"))
async def public(user: str) -> dict[str,str]:
    """Public greeting """
    return {"public_greeting": f"Hello {user}"}

@mcp.tool(auth=require_scopes("admin"))
async def admin(user: str) -> dict[str,str]:
    """Admin greeting """
    return {"admin_greeting": f"Hello {user}"}