import logging
import logging.config
import json
from threading import Thread
from config import settings

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
