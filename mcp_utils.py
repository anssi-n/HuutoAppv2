import yaml
from functools import lru_cache
from config import settings
from logger import logger
from pathlib import Path

DOCS_PATH = Path(f"{settings.huutoapp_mcp_tool_docs_path}/tool-docs.yaml")

@lru_cache
def load_tool_docs() -> dict:
    with open(DOCS_PATH) as f:
        return yaml.safe_load(f)

def get_literal(*, literal_name: str) -> list[str]:
    docs = load_tool_docs()
    try:
        return docs["literals"][literal_name]
    except (KeyError, TypeError):
        logger.critical(f"Unknown literal {literal_name}")
        raise

def get_doc(tool: str, *, param: str | None = None) -> str:
    docs = load_tool_docs()
    try:
        if param:
            return docs["tools"][tool]["parameters"][param]
        return docs["tools"][tool]["description"]
    except (KeyError, TypeError):
        logger.critical(f"Unknown tool {tool}, description or parameter {param}")
        raise