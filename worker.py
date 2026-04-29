import redis
from config import settings
from logger import logger, LoggingConfigListener
from uuid import uuid4
import sys
import time
import os
import datetime
from typing import Callable
from sync_redis_queue import get_redis
from schemas import huutoapp_queue_schema, huutonet_schema, items_schema
from common import common_types
from pydantic import ValidationError
from huutobot import HuutoBot, HuutoAuthenticationFailed, HuutoItemError
from worker_utils import update_status, get_item, save_item, push_retry, generate_end_time, get_keywords, get_closed_items, create_queue_msg, get_parent_id, get_huuto_data, ItemNotFound, RetryLimitExceeded
from prometheus_client import start_http_server, Counter, Gauge
from prometheus_middleware import task_latency

TASK_COUNT = Counter(
    "task_count_total",
    "Total number of executed tasks",
    ["app_name", "task_name", "status"]
)

QUEUE_LENGTH = Gauge(
    "task_queue_lenght",
    "Length of the task queue",
    ["app_name", "queue_name"]
)

g = Gauge('my_inprogress_requests', 'Description of gauge')
@task_latency
def relist_all_items(queue: redis.Redis, message: huutoapp_queue_schema.QueueMessage) -> bool:
    items = get_closed_items()
    total_items = len(items)
    parent_id = str(uuid4())
    logger.info(f"Total number of closed items {total_items}.")
    for i, item in enumerate(items):
        print(i, item.title)
        details = {"parent_ref": parent_id, "last_item": True} if i == total_items-1 else {"parent_ref": parent_id, "last_item": False}
        _ = create_queue_msg(item.id,
                             common_types.TaskType.RelistItem,
                             0,
                             details,
                             queue)

    details = {"parent_id": parent_id, "total_items": total_items}
    update_status(message.task.log_id, common_types.TaskStatus.ongoing, details=details)
    return True

@task_latency
def relist_item(_: redis.Redis, message: huutoapp_queue_schema.QueueMessage) -> None:
    item = get_item(message.task.id)
    if item is None:
       raise  ItemNotFound(f"No item found with id {message.task.id}")
    if item.huuto_id is None:
        raise ItemNotFound(f"Item {item.id} is not yet published to Huuto.net. Unable to relist.")

    huuto_data = get_huuto_data(item.huuto_id)
    if "status" in huuto_data and huuto_data["status"] == "open":
        logger.error(f"Item {item.huuto_id} is still active in Huuto.net. Unable to relist.")
        details = {"details": {"retries": {f"{message.retries}": {"status": common_types.TaskStatus.success, "message": f"Item {item.huuto_id} is still active in Huuto.net. Unable to relist.", "item": items_schema.ItemResponse.model_validate(item).model_dump(exclude={'created_at','huuto_closing_time'})}}}}
        update_status(message.task.log_id, common_types.TaskStatus.success, end_time=datetime.datetime.now(), details=details)
        return

    full_item_description = f"<p>{item.description}</p>"
    if message.task.add_keywords:
        kws = get_keywords(item.title)
        item = save_item(item.id, keywords=kws)
    if item.keywords is not None:
        full_item_description += item.keywords

    parent_id, last_item, parent_log_id = get_parent_id(message.task.log_id)

    try:
        with HuutoBot() as bot:
            closing_time = generate_end_time()
            new_huuto_id = bot.add_item(huutonet_schema.HuutoItem(original_id=item.huuto_id))
            bot.edit_item(new_huuto_id, huutonet_schema.HuutoItem(closing_time=closing_time, description=full_item_description))
            bot.edit_item(new_huuto_id, huutonet_schema.HuutoItem(status=huutonet_schema.Status.PREVIEW))
            bot.edit_item(new_huuto_id, huutonet_schema.HuutoItem(status=huutonet_schema.Status.PUBLISHED))
            item = save_item(item.id, huuto_id=new_huuto_id, end_time=str(closing_time))
    except (HuutoAuthenticationFailed, HuutoItemError) as err:
        if parent_id is not None:
            err.parent_log_id = parent_log_id
            raise

    details = {"details": {"retries": {f"{message.retries}": {"status": common_types.TaskStatus.success, "item": items_schema.ItemResponse.model_validate(item).model_dump(exclude={'created_at','huuto_closing_time'})}}}}
    update_status(message.task.log_id, common_types.TaskStatus.success, end_time=datetime.datetime.now(), details=details)
    if parent_id is not None and last_item:
        if parent_log_id is not None:
            update_status(parent_log_id, common_types.TaskStatus.success, end_time=datetime.datetime.now())
        else: 
            logger.error(f"Parent log id not found with parent id {parent_id} and {last_item=}")        

@task_latency
def close_item(_: redis.Redis, message: huutoapp_queue_schema.QueueMessage) -> None:
    with HuutoBot() as bot:
        bot.edit_item(message.task.id, huutonet_schema.HuutoItem(status=huutonet_schema.Status.CLOSED))
        details = {"details": {"retries": {f"{message.retries}": {"status": common_types.TaskStatus.success, "huuto_item": message.task.id}}}}
        update_status(message.task.log_id, common_types.TaskStatus.success, end_time=datetime.datetime.now(), details=details)
    
@task_latency
def add_item(_: redis.Redis, message: huutoapp_queue_schema.QueueMessage) -> None:

    item = get_item(message.task.id)
    full_item_description = f"<p>{item.description}</p>"
    if message.task.add_keywords:
        kws = get_keywords(item.title)
        full_item_description += kws
        item = save_item(item.id, keywords=kws)

    # Create HuutoItem instance from SQL Item object
    huuto_item = huutonet_schema.HuutoItem(
        title = item.title,
        description= full_item_description,
        quantity = item.quantity,
        buy_now_price = item.price,
        condition = item.condition.value,
        category_id = item.huuto_category_id,
        offers_allowed = item.offers_allowed,
        postal_code = settings.postal_code,
        sale_method = huutonet_schema.SalesMethod.BUY_NOW,
        closing_time = generate_end_time(),
        payment_methods = [huutonet_schema.PaymentMethod.WIRE_TRANSFER, huutonet_schema.PaymentMethod.CASH, huutonet_schema.PaymentMethod.MOBILE_PAY],
        payment_terms = settings.payment_terms,
        delivery_methods = [huutonet_schema.DeliveryMethod.PICKUP, huutonet_schema.DeliveryMethod.SHIPMENT],
        delivery_price = item.shipping.value,
        delivery_terms = settings.delivery_terms)

    with HuutoBot() as bot:
        huuto_id = bot.add_item(huuto_item)
        images = { image.id: bot.add_image_to_item(huuto_id, image.filename) for image in item.images if image.file_type == "fullsize"}
        print(images)
        bot.edit_item(huuto_id, huutonet_schema.HuutoItem(status=huutonet_schema.Status.PUBLISHED))
        item = save_item(item.id, huuto_id=huuto_id, huuto_image_ids=images, end_time=str(huuto_item.closing_time))

        details = {"details": {"retries": {f"{message.retries}": {"status": common_types.TaskStatus.success, "item": items_schema.ItemResponse.model_validate(item).model_dump(exclude={'created_at','huuto_closing_time'})}}}}
        update_status(message.task.log_id, common_types.TaskStatus.success, end_time=datetime.datetime.now(), details=details)


def execute_task(fn: Callable, queue: redis.Redis, message: huutoapp_queue_schema.QueueMessage) -> bool:
    exception_occured: BaseException | None = None
    try:
        fn(queue, message)
        return True
    except ItemNotFound as err:
        logger.error(f"Item {err.item_id} not found: {str(err)}")
        exception_occured = err
        return False
    except HuutoAuthenticationFailed as err:
        logger.error(f"Huuto authentication failed! {str(err)}")
        if err.parent_log_id is not None:
            details = {"details": {"retries": {f"{message.retries}": {"status": common_types.TaskStatus.fail, "error": str(err)}}}}
            update_status(err.parent_log_id, common_types.TaskStatus.fail, end_time=datetime.datetime.now(), details={})
        exception_occured = err
        return False
    except HuutoItemError as err:
        logger.critical(f"Huutonet item operation failed: {str(err)}")
        # Delete failed draft if it exists
        if err.huuto_id is not None:
            try:
                with HuutoBot() as bot:
                    bot.delete_draft(err.huuto_id)
                    logger.info(f"Draft {err.huuto_id} deleted successfully. Retrying...")
                    details = {"details": {"retries": {f"{message.retries}": {"status": common_types.TaskStatus.fail, "error": str(err)}}}}
                    update_status(message.task.log_id, common_types.TaskStatus.ongoing, details=details)
                    message.retries += 1
                    push_retry(queue, message)
            except Exception as e:
                logger.critical(f"Unable to delete draft {err.huuto_id}. Retries cancelled.")
                details = {"details": {"retries": {f"{message.retries}": {"status": common_types.TaskStatus.fail, "error": str(err)+str(e)}}}}
                update_status(message.task.log_id, common_types.TaskStatus.fail, end_time=datetime.datetime.now(), details=details)
                if err.parent_log_id is not None:
                    details = {"details": {"retries": {f"{message.retries}": {"status": common_types.TaskStatus.fail, "error": str(err)+str(e)}}}}
                    update_status(err.parent_log_id, common_types.TaskStatus.fail, end_time=datetime.datetime.now(), details=details)
        exception_occured = err
        return False
    except Exception as err:
        logger.error(f"Unexpected error occured! {str(err)}")
        exception_occured = err
        return False
    finally:
        if exception_occured is None:
            TASK_COUNT.labels(
                app_name="huutoworker",
                task_name=fn.__qualname__,
                status="ok",
            ).inc()
        else:
            TASK_COUNT.labels(
                app_name="huutoworker",
                task_name=fn.__qualname__,
                status=f"nok, {type(exception_occured).__qualname__}",
            ).inc()

def process_message(queue: redis.Redis, message_json: str) -> None:
    try:
        message = huutoapp_queue_schema.QueueMessage.model_validate_json(message_json)   
        logger.info(f"Valid message received: {message}")

        if message.retries <= settings.max_retries:
            match message.task.task:
                case common_types.TaskType.AddItem:
                    logger.info("Processing AddItem task.")
                    result = execute_task(add_item, queue, message)
                case common_types.TaskType.CloseItem:
                    logger.info("Processing CloseItem task.")
                    result = execute_task(close_item, queue, message)
                case common_types.TaskType.RelistItem:
                    logger.info("Processing RelistItem task.")
                    result = execute_task(relist_item, queue, message)
                case common_types.TaskType.UpdateItem:
                    logger.error("UpdateItem task is not yet implemented.")
                case common_types.TaskType.RelistAllItems:
                    logger.info("Processing RelistAllItems task.")
                    result = execute_task(relist_all_items, queue, message)
                case common_types.TaskType.AddImage:  
                    logger.error("AddImage task is not yet implemented.")
                case common_types.TaskType.DeleteImage:
                    logger.error("DeleteImage task is not yet implemented.")
                case _:
                    logger.error(f"Unknown task type {message.task.task}")

            if result:
                logger.info(f"Task {message.task.task} executed successfully.")
            else:
                logger.error(f"Execution of task {message.task.task} failed!")            
        else:
            logger.info(f"Retry limit exceeded. Updating task {message.task.log_id} status")
            details = {"details": {"retries": {f"{message.retries}": {"status": common_types.TaskStatus.fail, "error": f"Retry limit {settings.max_retries} exceeded."}}}}
            update_status(message.task.log_id, common_types.TaskStatus.fail, end_time=datetime.datetime.now(), details=details)
            raise RetryLimitExceeded(f"Retry limit {settings.max_retries} exceeded.")

    except ValidationError as err:
        logger.critical(f"Malformed queue message received: {str(err)}")
    except RetryLimitExceeded as err:
        logger.critical(f"Retry limit exceeded: {str(err)}")

def main(queue: redis.Redis) -> None:

    logger.info("Starting main loop")
    while True:
        message = queue.brpop(settings.redis_queue_name, timeout=5) # type: ignore
        q_len = queue.llen(settings.redis_queue_name)
        QUEUE_LENGTH.labels(
            app_name="huutoworker",
            queue_name=settings.redis_queue_name
        ).set(float(q_len)) # type: ignore
 
        if message is not None:
            _, message_json = message # type: ignore
            logger.debug(f"Raw message from queue: {message_json}")
            process_message(queue, message_json)
            time.sleep(1)

if __name__ == "__main__":
    LoggingConfigListener.start_listener()

    try:
        queue = get_redis()
    except RetryLimitExceeded as e:
        logger.critical(f"{e}")
        exit(1)

    try:
        server, t = start_http_server(settings.worker_prometheus_port)
        main(queue)
    except KeyboardInterrupt:
        logger.info("Interrupted")
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)
    finally:
        queue.close()
        LoggingConfigListener.stop_listener()        
        server.shutdown()
        server.server_close()
        t.join()
