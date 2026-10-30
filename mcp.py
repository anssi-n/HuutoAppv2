from fastmcp import FastMCP
from huutomcp import tools
from logger import logger

mcp = FastMCP("HuutoApp MCP Server")

# Register tools (or just import the modules if they use @mcp.tool on the shared instance)
# Common pattern: pass the mcp instance or use a shared one

if __name__ == "__main__":
    mcp.run()          # defaults to stdio