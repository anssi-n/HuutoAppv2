import httpx
from http import HTTPStatus
from schemas import huutonet_schema
from logger import logger
from types import TracebackType
from typing import Self
from config import settings
from functools import wraps
from typing import Callable
from image_utils import IMAGE_DIR

class HuutoAuthenticationFailed(Exception):
    def __init__(self, message: str | None = None):
        self.message = message
        self.parent_log_id: int | None = None
        super().__init__(self.message)

class HuutoItemError(Exception):
    def __init__(self, message: str, huuto_id: int | None = None):
        self.message = message
        self.huuto_id = huuto_id
        self.parent_log_id: int | None = None
        super().__init__(self.message)

def authenticated(fn: Callable) -> Callable:
    @wraps(fn)
    def wrapper(self: HuutoBot, *args, **kwargs):
        if not self.auth_token.is_valid:
            logger.info("Authentication token has expired. Re-authenticating.")
            self._authenticate()
        else:
            logger.info("Authentication token is still valid.")
        return fn(self, *args, **kwargs)
    return wrapper

class HuutoBot:
    def __init__(self) -> None:
        self.client = httpx.Client()
        self._authenticate()

    def __enter__(self) -> Self:
        # self.client = httpx.Client()
        # self._authenticate()
        return self
    
    def __exit__(self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: TracebackType | None) -> None:

        self.client.close()
        logger.info("HTTPX client closed.")
    
        if exc_val is not None:
            logger.critical(
                f"Exception {str(exc_val)} occured in HuutoBot context.")
            raise

    def close(self) -> None:
        self.client.close()
        logger.info("HTTPX client closed.")

    def _authenticate(self) -> None:
        resp = self.client.post(f"https://api.huuto.net/1.1/authentication?username={settings.huuto_username}&password={settings.huuto_password.get_secret_value()}")
        if resp.status_code not in (HTTPStatus.OK, HTTPStatus.CREATED):
            logger.error(f"Authentication failed with status code {resp.status_code}: {resp.json()}")
            raise HuutoAuthenticationFailed()

        auth_response = huutonet_schema.AuthenticationResponse(**resp.json())
        logger.info(f"Successfull authentication. Token valid until {auth_response.authentication.token.expires}")
        self.auth_token = auth_response.authentication.token
        self.client.headers["X-HuutoApiToken"] = self.auth_token.id

    def get_item(self, item_id: int) -> huutonet_schema.HuutoItem:

        resp = self.client.get(f"https://api.huuto.net/1.1/items/{item_id}")
                            
        if resp.status_code != HTTPStatus.OK:
            logger.error(f"Getting item data for Huuto item {item_id} failed with status code {resp.status_code}: {resp.json()}")
            raise HuutoItemError(f"Getting item data for Huuto item {item_id} failed with status code {resp.status_code}: {resp.json()}")
        
        return huutonet_schema.HuutoItem(**resp.json())

    @authenticated
    def add_item(self, item: huutonet_schema.HuutoItem) -> int:

        resp = self.client.post("https://api.huuto.net/1.1/items/", json=item.model_dump(by_alias=True, exclude_none=True))
                            
        if resp.status_code != HTTPStatus.CREATED:
            logger.error(f"Adding new item {item} failed with status code {resp.status_code}: {resp.json()}")
            raise HuutoItemError(f"Adding new item {item} failed with status code {resp.status_code}: {resp.json()}")
        
        item_response = huutonet_schema.ItemResponse(**resp.json())
        logger.info(f"Item {item} added successfully")
        return item_response.id

    @authenticated
    def add_image_to_item(self, item_id: int, image_file: str) -> int:

        if not ( IMAGE_DIR / image_file ).exists():
            logger.error(f"Image file {image_file} does not exists in image directory.")
            raise HuutoItemError(f"Image file {image_file} does not exists in image directory.", item_id)

        if not self.auth_token.is_valid:
            self._authenticate()

        with open(IMAGE_DIR / image_file, "rb") as image:
            files = {"image": image}
            resp = self.client.post(f"https://api.huuto.net/1.1/items/{item_id}/images", files=files, timeout=30)
                                
            if resp.status_code != HTTPStatus.CREATED:
                logger.error(f"Adding image {image_file} to item {item_id} failed with status code {resp.status_code}: {resp.json()}")
                raise HuutoItemError(f"Adding image {image_file} to item {item_id} failed with status code {resp.status_code}: {resp.json()}", item_id)

            image_response = huutonet_schema.ImageResponse(**resp.json())
            logger.info(f"Image {image_file} added successfully to item {item_id}. New image id is {image_response.image_id}.")
            return image_response.image_id

    @authenticated
    def edit_item(self, item_id: int, item_data: huutonet_schema.HuutoItem) -> None:
        resp = self.client.put(f"https://api.huuto.net/1.1/items/{item_id}", json=item_data.model_dump(by_alias=True, exclude_none=True))
                            
        if resp.status_code != HTTPStatus.OK:
            logger.error(f"Editing item {item_id} with data {item_data} failed with status code {resp.status_code}: {resp.json()}")
            raise HuutoItemError(f"Editing item {item_id} with data {item_data} failed with status code {resp.status_code}: {resp.json()}", item_id)

        logger.info(f"Item {item_id} edited successfully with data {item_data} successfully.")

    @authenticated
    def delete_draft(self, item_id: int) -> None:
        resp = self.client.delete(f"https://api.huuto.net/1.1/items/{item_id}")
                            
        if resp.status_code != HTTPStatus.NO_CONTENT:
            logger.error(f"Deleting draft {item_id} failed with status code {resp.status_code}: {resp.json()}")
            raise HuutoItemError(f"Deleting draft {item_id} failed with status code {resp.status_code}: {resp.json()}", item_id)
        logger.info(f"Draft {item_id} deleted successfully.")

    @authenticated
    def delete_image(self, item_id: int, image_id: int) -> bool:
        resp = self.client.delete(f"https://api.huuto.net/1.1/items/{item_id}/images/{image_id}")

        if resp.status_code != HTTPStatus.NO_CONTENT:
            logger.error(f"Deleting image {image_id} from item {item_id} failed with status code {resp.status_code}: {resp.json()}", item_id)
            return False

        logger.info(f"Image {image_id} deleted from item {item_id} successfully.")
        return True


# closed_item = 640794800
# with HuutoBot() as bot:
#     relist = {"original_id":closed_item}
#     item = HuutoItem(original_id=closed_item)
#     new_item_id = bot.add_item(item)
#     print(new_item_id)
#     #relisted item now in draft state
#     #edit new closing time
#     closing_time = {
#         "closingTime": "2026-04-22 12:00:00",
#         "paymentTerms": "Tilisiirto, MobilePay tai käteinen",
#     }
#     if new_item_id:
#         ok = bot.edit_item(new_item_id, HuutoItem(**closing_time))
#         print(ok)

#     # change item status -> preview -> published
#     if ok:
#         ok = bot.edit_item(new_item_id, HuutoItem(status=Status.PREVIEW))
#         print(ok)

#     if ok:
#         ok = bot.edit_item(new_item_id, HuutoItem(status=Status.PUBLISHED))
#         print(ok)



# with HuutoBot() as bot:
#     item = HuutoItem(**new_item)
#     item_id = bot.add_item(item)
#     print(item_id)
#     images = ["IMG_20260326_200904_resized.jpg"]
#     for image in images:
#         image_id = bot.add_image_to_item(item_id, image)
#         print(image, image_id)
#     ok = bot.set_item_status(item_id,Status.PUBLISHED)
#     print(ok)

# import json
# target_categories = ("DVD","Blu-ray","4K Ultra HD")
# result = {}
# with open("categories.json","r",encoding="utf-8") as file:
#     categories = json.loads(file.read())
#     for category in categories["categories"]:
#         if category["title"] == "Elokuvat":
#             for subcategory in category["subcategories"]:
#                 if subcategory["title"] in target_categories:
# #                    result[subcategory["title"]]=[]
#                     result[subcategory["title"]]={}
#                     for cat in subcategory["subcategories"]:
#                         # result[subcategory["title"]].append((cat["title"],cat["id"]))
#                         result[subcategory["title"]][cat["title"]]=cat["id"]
# print(result)
# with open("movie_categories.json","w",encoding="utf-8") as file:
#     json.dump(result, file)

# from DatabaseConnection import DatabaseConnection
# import json
# # categories = {}
# # with open("movie_categories.json","r",encoding="utf-8") as file:
# #     categories = json.loads(file.read())
# # print(categories)
# with DatabaseConnection(localhost=True) as (db_conn, cursor):
#     formats = {}
#     query = "SELECT * FROM media_categories"
#     cursor.execute(query)
#     #, (self.title, self.images, self.price, self.slipcover, self.description,
#     #                             self.format, self.condition, self.shipping, self.region, self.genre, self.subtitles, self.country, self.packaging, self.discount_info))
#     #        db_conn.commit()
#     for row in cursor.fetchall():
#         formats[row[0]] = row[1]
#     print(formats)
#     for id, label in formats.items():
#         print(label, id)
#         query = "INSERT INTO genres (id, label) VALUES (%s, %s)"
#         cursor.execute(query, (id, label))
#         db_conn.commit()