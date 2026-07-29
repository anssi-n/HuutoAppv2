import logging
import logging.config
import json
from threading import Thread
from config import settings
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

class HttpxRedactFilter(logging.Filter):
    SENSITIVE_KEYS = {"username", "password", "passwd", "secret", "token", "api_key", "auth"}

    def filter(self, record: logging.LogRecord) -> bool:
        if not record.args or len(record.args) < 2:
            return True

        url_obj = list(record.args)[1]

        try:
            url_str = str(url_obj)

            if "?" not in url_str:
                return True

            parsed = urlparse(url_str)
            if parsed.query:
                params = parse_qs(parsed.query, keep_blank_values=True)

                redacted = False
                for key in self.SENSITIVE_KEYS:
                    if key in params:
                        params[key] = ["REDACTED"]
                        redacted = True

                if redacted:
                    new_query = urlencode(params, doseq=True)
                    redacted_url = urlunparse(parsed._replace(query=new_query))

                    args_list = list(record.args)
                    args_list[1] = redacted_url
                    record.args = tuple(args_list)

        except Exception:
            pass

        return True

def configure_logger():
    with open("logger/logging_config.json","r",encoding="utf-8") as f:
        config = json.load(f)
        logging.config.dictConfig(config)

configure_logger()
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class LoggingConfigListener:
    listener: Thread | None = None

    @classmethod
    def start_listener(cls) -> None:
        logger.info(f"Logging config server is listening at port {settings.logging_config_port}")
        try:
            cls.listener = logging.config.listen(settings.logging_config_port)
            cls.listener.start()
            logger.info(f"Logging config listener started at port {settings.logging_config_port}")
        except BaseException as err:
            logger.error(f"Starting logging config listener at port {settings.logging_config_port} failed! {err}")

    @classmethod
    def stop_listener(cls) -> None:
        if cls.listener is not None:
            logging.config.stopListening()
            cls.listener.join()
            logger.info("Logging config listener stopped")
