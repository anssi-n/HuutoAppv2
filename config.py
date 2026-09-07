from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", 
                                        env_file_encoding="utf-8",
                                        case_sensitive=False)

    database_user: SecretStr
    database_password: SecretStr
    database_host: str
    database_port: int
    database_name: str
    database_credential_dir: str
    redis_host: str
    redis_port: int
    redis_db_number: int
    redis_password: SecretStr 
    redis_queue_name: str
    max_image_size: int
    favicon_file: str
    logging_config_host: str
    logging_config_port: int
    huuto_username: str
    huuto_password: SecretStr
    postal_code: int
    delivery_terms: str
    payment_terms: str
    max_retries: int
    omdb_api_key: SecretStr
    worker_prometheus_port: int

settings = Settings() # type: ignore # Loaded from .env file