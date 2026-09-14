import redis
from config import settings
from logger import logger
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from db import sync_engine
from schemas import huutoapp_queue_schema
from common import common_types
from typing import Sequence, Any
import httpx
import re
import json
from sqlalchemy import select, text
from sqlalchemy.orm import Session, selectinload
from models import items_model, task_log_model
from sqlalchemy.orm.attributes import flag_modified

HELSINKI = ZoneInfo("Europe/Helsinki")
UTC = ZoneInfo("UTC")

class RetryLimitExceeded(Exception):
    pass

class ItemNotFound(Exception):
    def __init__(self, message: str, item_id: int | None = None):
        self.message = message
        self.item_id = item_id
        super().__init__(self.message)

def get_huuto_data(item_id: int | None) -> dict[str,Any]:

    if item_id is None:
        return {}
    with httpx.Client() as client:
        result = client.get(f"https://api.huuto.net/1.1/items/{item_id}", timeout=5)
        if result.status_code != 200:
            logger.error(f"Failed to get Huuto item data for id {item_id}. Response code {result.status_code}.")
            return {}
        return json.loads(result.text)

def get_keywords(title: str) -> str:

    title = title.split(", ")[0]
    title = title.split(" - ")[0]
    title = title.split(" aka ")[0]
    s_titles = [s.strip() for s in title.split('/')]

    # Serpico 4K + Blu-Ray limited edition steelbook
    years = {}
    for i, c_title in enumerate(s_titles):
        c_title = c_title.replace('4K', '').strip()
        c_title = c_title.replace('3D', '').strip()
        c_title = c_title.replace('steelbook', '').strip()
        year = None
        if y_match := re.search(r"\((\d{4}).*\)", c_title):
            year = y_match.groups()[0]
            c_title = re.sub(r"\((\d{4}).*\)", "", c_title).strip()
        c_title = re.sub(r"\(.+\)", "", c_title).strip()
        c_title = c_title.replace('&', '%26')
        s_titles[i] = c_title
        years[c_title] = year

    summary = ""
    with httpx.Client() as client:
        for t in s_titles:
            try:
                if years[t] is None:
                    r = client.get(f"https://www.omdbapi.com/?t={t}&apikey={settings.omdb_api_key.get_secret_value()}", timeout=60)
                else:
                    r = client.get(f"https://www.omdbapi.com/?t={t}&y={years[t]}&apikey={settings.omdb_api_key.get_secret_value()}", timeout=60)
                if r.status_code == 200 and json.loads(r.text)['Response'] == "True":
                    r_json = json.loads(r.text)
                    summary += f"<p><b>Nimi</b>:&#09;{r_json['Title']}<br>"
                    summary += f"<b>Genre</b>:&#09;{r_json['Genre']}<br>"
                    summary += f"<b>Vuosi</b>:&#09;{r_json['Year']}<br>"
                    summary += f"<b>Ohjaaja</b>:&#09;{r_json['Director']}<br>"
                    summary += f"<b>Näyttelijät</b>:&#09;{r_json['Actors']}<br>"
                    summary += f"<b>Juoni</b>:&#09;{r_json['Plot']}</p>"
                    if 'imdbID' in r_json and r_json["imdbID"] != "N/A":
                        imdb_id =  r_json["imdbID"]
                        summary += f"<p><a target=_blank href=https://www.imdb.com/title/{imdb_id} rel=nofollow>https://www.imdb.com/title/{imdb_id}</a></p>"
                else:
                    logger.info(f"OMDB data not found with {title=}")

            except httpx.ReadTimeout as err:
                logger.error(f"Httpx timeout occured! {err}")
    return summary

def merge_details(orig: dict[str,Any], details: dict[str,Any]) -> dict[str,Any]:
    if not details:
        return orig
    if "details" not in orig:
        return orig | details
    orig["details"]["retries"] = orig["details"]["retries"] | details["details"]["retries"]
    return orig


def create_queue_msg(id: int,
                     task_type: common_types.TaskType,
                     add_keywords: int,
                     details: dict[str,Any],
                     queue: redis.Redis) -> int:
    # Create task log entry
    task_log = task_log_model.TaskLog(
        task = task_type,
        status = common_types.TaskStatus.ongoing,
        details = details)

    with Session(sync_engine) as session:
        session.add(task_log)
        session.commit()
        session.refresh(task_log)

    queue_msg = huutoapp_queue_schema.QueueMessage(
        task = huutoapp_queue_schema.Task(
            task = task_type,
            log_id = task_log.id,
            id = id, 
            add_keywords = add_keywords
        ),
        created_at = datetime.now(UTC),
        retries = 0

    )
    queue.lpush(settings.redis_queue_name, queue_msg.model_dump_json()) # type: ignore 
    return task_log.id

def get_parent_id(log_id: int) -> tuple[str | None, bool | None, int | None]:
    with Session(sync_engine) as session:
        result = session.execute(text("SELECT details->>'parent_ref' AS parent_id, (details->>'last_item')::boolean AS last_item FROM task_log WHERE id = :id"), {'id': log_id}).first()

        if result is None:
            return None, None, None

        parent_result = session.execute(text("SELECT id FROM task_log WHERE details->>'parent_id' = :parent_id"), {'parent_id': result.parent_id}).first()
        if parent_result is None:
            return result.parent_id, result.last_item, None
  
        return result.parent_id, result.last_item, parent_result.id
    
    return None, None, None

def push_retry(queue: redis.Redis, message: huutoapp_queue_schema.QueueMessage) -> None:
    queue.lpush(settings.redis_queue_name, message.model_dump_json())

def update_status(id: int, status: common_types.TaskStatus, *, details: dict[str,Any] | None = {}, end_time: datetime | None = None ) -> None:
    with Session(sync_engine) as session:
        result = session.execute(select(task_log_model.TaskLog).
                                 where(task_log_model.TaskLog.id == id))
        log_entry = result.scalars().first()
        if log_entry is not None:
            log_entry.status = status
            if end_time is not None:
                log_entry.end_time = end_time
            log_entry.details = merge_details(log_entry.details,details) # type: ignore
            flag_modified(log_entry, "details")
            session.commit()
        else:
            logger.error(f"No log entry found with id {id} in db.")

def save_item( item_id: int, *, 
               huuto_id: int | None = None,
               huuto_image_ids: dict[int,int] | None = None, 
               end_time: datetime | None = None,
               keywords: str | None = None) -> items_model.HuutoItem:
    with Session(sync_engine) as session:
        result = session.execute(select(items_model.HuutoItem).
                                 options(selectinload(items_model.HuutoItem.images)).
                                 where(items_model.HuutoItem.id == item_id))
        item = result.scalars().first()
        if item is not None:
            item.huuto_id = huuto_id if huuto_id is not None else item.huuto_id
            # item.huuto_closing_time = datetime.fromisoformat(end_time).astimezone() if end_time is not None else item.huuto_closing_time
            item.huuto_closing_time = end_time if end_time is not None else item.huuto_closing_time
            item.keywords = keywords if keywords is not None else item.keywords
            if huuto_image_ids is not None:
                for image in item.images:
                    if image.id in huuto_image_ids:
                        image.huuto_image_id = huuto_image_ids[image.id]
            session.commit()
            session.refresh(item, attribute_names=["images","shipping", "country", "subtitle", "region", "condition", "packaging", "discount_info", "media_format", "genre"])
            return item
        else:
            logger.error(f"Item {item_id} not found in db.")
            raise ItemNotFound(f"No item found with id {item_id}", item_id)
        
def get_closed_items() -> Sequence[items_model.HuutoItem]:
    # dt = datetime.now(UTC)
    # dt_new = (dt.replace(day=2) + timedelta(days=32)
    #               ).replace(day=1).replace(hour=12, minute=00, second=00)
    with Session(sync_engine) as session:
        result = session.execute(select(items_model.HuutoItem).
                              options(selectinload(items_model.HuutoItem.shipping),
                                      selectinload(items_model.HuutoItem.country),
                                      selectinload(items_model.HuutoItem.subtitle),
                                      selectinload(items_model.HuutoItem.region),
                                      selectinload(items_model.HuutoItem.condition),
                                      selectinload(items_model.HuutoItem.packaging),
                                      selectinload(items_model.HuutoItem.discount_info),
                                      selectinload(items_model.HuutoItem.media_format),
                                      selectinload(items_model.HuutoItem.genre),
                                      selectinload(items_model.HuutoItem.images)).
                                      where(items_model.HuutoItem.huuto_closing_time < datetime.now(UTC)))
        items = result.scalars().all()
        return items


def get_item(item_id: int) -> items_model.HuutoItem:
    with Session(sync_engine) as session:
        result = session.execute(select(items_model.HuutoItem).
                              options(selectinload(items_model.HuutoItem.shipping),
                                      selectinload(items_model.HuutoItem.country),
                                      selectinload(items_model.HuutoItem.subtitle),
                                      selectinload(items_model.HuutoItem.region),
                                      selectinload(items_model.HuutoItem.condition),
                                      selectinload(items_model.HuutoItem.packaging),
                                      selectinload(items_model.HuutoItem.discount_info),
                                      selectinload(items_model.HuutoItem.media_format),
                                      selectinload(items_model.HuutoItem.genre),
                                      selectinload(items_model.HuutoItem.images)
                                      ).
                                  where(items_model.HuutoItem.id == item_id))
        item = result.scalars().first()
        if item is None:
            raise ItemNotFound(f"No item found with id {item_id}", item_id)
        return item

def generate_end_time() -> tuple[datetime, str]:

    now = datetime.now(HELSINKI)
    first_of_next_month = ((now.replace(day=1) + timedelta(days=32)).replace(day=1, hour=12, minute=0, second=0, microsecond=0))
    end_time_utc = first_of_next_month.astimezone(UTC)    

    if (end_time_utc-now).days < 1:
        end_time_utc = (end_time_utc.replace(day=1) + timedelta(days=32)).replace(day=1).replace(hour=12, minute=00, second=00)
        logger.info("Less than one day remaining. New end date and time increased by one month.")

    end_date = f"{str(end_time_utc.year)}-{str(end_time_utc.month).zfill(2)}-{str(end_time_utc.day).zfill(2)} {str(end_time_utc.hour).zfill(2)}:{str(end_time_utc.minute).zfill(2)}:{str(end_time_utc.second).zfill(2)}"
    logger.info(f"Ending date and time for the new item: {end_date}")
    return end_time_utc, end_date
