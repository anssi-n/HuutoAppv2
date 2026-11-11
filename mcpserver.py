from db import get_fastmcp_db, engine
from redis_queue import get_redis, redis_client
from common import common_types
from redis.asyncio import Redis
from models import items_model
from schemas import items_schema
from typing import Annotated, Literal, Optional, Callable
from functools import wraps
from datetime import datetime, UTC
from zoneinfo import ZoneInfo
from pydantic import Field, AnyHttpUrl
from sqlalchemy import select, func, desc, and_, or_, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from fastmcp import FastMCP
from fastmcp.server.lifespan import lifespan
from fastmcp.dependencies import Depends
from fastmcp.exceptions import ToolError
from fastmcp.server.auth import require_scopes
from fastmcp.server.auth.providers.jwt import JWTVerifier
from fastmcp.server.auth import RemoteAuthProvider
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse
from config import settings
from logger import logger
from mcp_utils import get_doc, get_literal
from routers.items_route import create_queue_msg

HELSINKI = ZoneInfo("Europe/Helsinki")
UTC = ZoneInfo("UTC")

if settings.huutoapp_mcp_perform_auth:
    logger.info("MCP Server performs authentication & authorization")
    token_verifier = JWTVerifier(
        jwks_uri=f"{settings.huutoapp_mcp_idp_url}/realms/{settings.huutoapp_mcp_idp_realm}/protocol/openid-connect/certs",
        issuer=f"{settings.huutoapp_mcp_idp_url}/realms/{settings.huutoapp_mcp_idp_realm}",
        audience=settings.huutoapp_mcp_idp_audience
    )

    auth = RemoteAuthProvider(
        token_verifier=token_verifier,
        authorization_servers=[AnyHttpUrl(f"{settings.huutoapp_mcp_idp_url}/realms/{settings.huutoapp_mcp_idp_realm}")],
        base_url=settings.huutoapp_mcp_server_url,
    )

    logger.info(f"AuthN & AuthZ: authorization server={AnyHttpUrl(f"{settings.huutoapp_mcp_idp_url}/realms/{settings.huutoapp_mcp_idp_realm}")}")
    logger.info(f"AuthN & AuthZ: JWKS URL={settings.huutoapp_mcp_idp_url}/realms/{settings.huutoapp_mcp_idp_realm}/protocol/openid-connect/certs")
    logger.info(f"AuthN & AuthZ: Issuer={settings.huutoapp_mcp_idp_url}/realms/{settings.huutoapp_mcp_idp_realm}")
    logger.info(f"AuthN & AuthZ: Audience={settings.huutoapp_mcp_idp_audience}")
    logger.info(f"AuthN & AuthZ: MCP Server base url: {settings.huutoapp_mcp_server_url}")

    auth=auth
    public_tool_auth = require_scopes(settings.public_tool_scope)
    admin_tool_auth = require_scopes(settings.admin_tool_scope)

else:
    logger.info("MCP Server doesn't perform authentication & authorization")
    auth=None
    public_tool_auth = None
    admin_tool_auth = None

def log_toolcall(fn: Callable) -> Callable:
    @wraps(fn)
    def wrapper(*args, **kwargs):
        arguments = ", ".join([f"{k}={v}" for k,v in kwargs.items() if (not isinstance(v, Redis) and not isinstance(v, AsyncSession))])
        logger.info(f"Tool call: name={fn.__qualname__}, {arguments=}")
        return fn(*args, **kwargs)
    return wrapper

@lifespan
async def app_lifespan(server):
    try:
        await redis_client.connect()
        yield {} 
    finally:
        await engine.dispose()
        await redis_client.disconnect() 

mcp = FastMCP("HuutoApp MCP Server", 
              auth=auth,
              lifespan=app_lifespan)

MediaFormat = Literal[*get_literal(literal_name="media_format")]
Condition = Literal[*get_literal(literal_name="condition")]
Status = Literal[*get_literal(literal_name="status")]

@mcp.tool(auth=public_tool_auth,
          description=get_doc("list_titles"),)
@log_toolcall
async def list_titles(*,
                      media_format: Annotated[Optional[MediaFormat], Field(            # pyright: ignore[reportInvalidTypeForm]
                          description=get_doc("list_titles", param="media_format")
                      )] = None,
                      condition: Annotated[Optional[Condition], Field(                 # pyright: ignore[reportInvalidTypeForm]
                          description=get_doc("list_titles", param="condition")
                      )] = None,
                      status: Annotated[Optional[Status] | None, Field(                # pyright: ignore[reportInvalidTypeForm]
                          description=get_doc("list_titles", param="status")
                      )] = None,
                      db: AsyncSession = Depends(get_fastmcp_db)) -> list[items_schema.ItemResponse]:

    select_stm = select(items_model.HuutoItem).options(selectinload(items_model.HuutoItem.shipping),
                                      selectinload(items_model.HuutoItem.country),
                                      selectinload(items_model.HuutoItem.subtitle),
                                      selectinload(items_model.HuutoItem.region),
                                      selectinload(items_model.HuutoItem.condition),
                                      selectinload(items_model.HuutoItem.packaging),
                                      selectinload(items_model.HuutoItem.discount_info),
                                      selectinload(items_model.HuutoItem.media_format),
                                      selectinload(items_model.HuutoItem.genre),
                                      selectinload(items_model.HuutoItem.condition),
                                      selectinload(items_model.HuutoItem.images))

    if media_format is not None:
        select_stm = select_stm.where(items_model.HuutoItem.media_format.has(value=media_format))
    if condition is not None:
        select_stm = select_stm.where(items_model.HuutoItem.condition.has(value=condition))

    now = datetime.now(HELSINKI).astimezone(UTC)
    if status == "draft":
        select_stm = select_stm.where(or_(
            items_model.HuutoItem.huuto_id.is_(None),
            items_model.HuutoItem.huuto_closing_time.is_(None)))
    elif status == "closed":
        select_stm = select_stm.where(items_model.HuutoItem.huuto_closing_time < now)
    elif status == "open":
        select_stm = select_stm.where(and_(
            items_model.HuutoItem.huuto_id.is_not(None),
            items_model.HuutoItem.huuto_closing_time.is_not(None),
            items_model.HuutoItem.huuto_closing_time >= now))

    result = await db.execute(select_stm)
    items = [items_schema.ItemResponse.model_validate(item) for item in result.scalars().all()]
    return items

@mcp.tool(auth=public_tool_auth,
          description=get_doc("search_titles"),) 
@log_toolcall
async def search_titles(*,
                        search_criteria: Annotated[str, 
                                                   Field(
                                                       description=get_doc("search_titles", param="search_criteria"),
                                                       min_length=1,
                                                       max_length=20,
                                                   )],
                        db: AsyncSession = Depends(get_fastmcp_db))  -> list[items_schema.ItemResponse]:

    select_stm = select(items_model.HuutoItem).options(selectinload(items_model.HuutoItem.shipping),
                                      selectinload(items_model.HuutoItem.country),
                                      selectinload(items_model.HuutoItem.subtitle),
                                      selectinload(items_model.HuutoItem.region),
                                      selectinload(items_model.HuutoItem.condition),
                                      selectinload(items_model.HuutoItem.packaging),
                                      selectinload(items_model.HuutoItem.discount_info),
                                      selectinload(items_model.HuutoItem.media_format),
                                      selectinload(items_model.HuutoItem.genre),
                                      selectinload(items_model.HuutoItem.condition),
                                      selectinload(items_model.HuutoItem.images))
    select_stm = select_stm.where(func.concat(items_model.HuutoItem.keywords,items_model.HuutoItem.title,items_model.HuutoItem.description).ilike(f"%{search_criteria}%"))
    result = await db.execute(select_stm)
    items = [items_schema.ItemResponse.model_validate(item) for item in result.scalars().all()]
    return items

@mcp.tool(auth=admin_tool_auth,
          description=get_doc("publish_draft_title")) 
@log_toolcall
async def publish_draft_title(*,
                             title_id: Annotated[int, 
                                                   Field(
                                                       description=get_doc("publish_draft_title", param="title_id")
                                                   )],
                             add_keywords: Annotated[bool, 
                                                   Field(
                                                       description=get_doc("publish_draft_title", param="add_keywords")
                                                   )],
                             redis: Redis = Depends(get_redis),
                             db: AsyncSession = Depends(get_fastmcp_db))  -> items_schema.PublishResponse:

    result = await db.execute(select(items_model.HuutoItem).where(items_model.HuutoItem.id == title_id))
    item = result.scalars().first()

    if item is None:
        raise ToolError(f"No title found with title id {title_id}.")

    if item.huuto_id is not None:
        raise ToolError(f"Title with title id {title_id} is not in draft state. It already has huuto_id {item.huuto_id}.")

    task_id = await create_queue_msg(
        item.id,
        common_types.TaskType.AddItem,
        int(add_keywords),
        {"item_id": item.id},
        db,
        redis
    )

    return items_schema.PublishResponse(task_id=task_id, item_id=item.id, title=item.title)

@mcp.tool(auth=admin_tool_auth,
          description=get_doc("republish_title")) 
@log_toolcall
async def republish_title(*,
                          title_id: Annotated[int, 
                                                   Field(
                                                       description=get_doc("republish_title", param="title_id")
                                                   )],
                          add_keywords: Annotated[bool, 
                                                   Field(
                                                       description=get_doc("republish_title", param="add_keywords")
                                                   )],
                          redis: Redis = Depends(get_redis),
                          db: AsyncSession = Depends(get_fastmcp_db))  -> items_schema.PublishResponse:

    result = await db.execute(select(items_model.HuutoItem).where(items_model.HuutoItem.id == title_id))
    item = result.scalars().first()

    if item is None:
        raise ToolError(f"No title found with title id {title_id}.")

    if item.huuto_closing_time is None:
        raise ToolError(f"Title with title id {title_id} is not yet published to Huuto.net. Unable to republish.")

    task_id = await create_queue_msg(
        item.id,
        common_types.TaskType.RelistItem,
        int(add_keywords),
        {"item_id": item.id},
        db,
        redis
    )

    return items_schema.PublishResponse(task_id=task_id, item_id=item.id, title=item.title)


@mcp.custom_route("/health", methods=["GET"]) 
async def liveness(_: Request) -> PlainTextResponse:
    return PlainTextResponse("OK", status_code=200)

@mcp.custom_route("/ready", methods=["GET"])
async def readiness(_: Request) -> JSONResponse:
    try:
        async with get_fastmcp_db() as db:
            result = await db.execute(text("SELECT 1"))
            if result.scalar_one_or_none() != 1:
                return JSONResponse(
                    {"status": "not_ready"},
                    status_code=503
                )
    except Exception as err:
        print(err)
        return JSONResponse(
            {"status": "not_ready"},
            status_code=503
        )
    return JSONResponse({"status": "ready"}, status_code=200)