from pydantic import SecretStr, HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", 
                                        env_file_encoding="utf-8",
                                        case_sensitive=False,
                                        url_preserve_empty_path=True)

    database_user: SecretStr | None = None
    database_password: SecretStr | None = None
    database_host: str
    database_port: int
    database_name: str
    database_credential_dir: str
    redis_host: str
    redis_port: int
    redis_db_number: int
    redis_password: SecretStr 
    redis_queue_name: str
    max_image_size: int | None = None
    favicon_file: str | None = None
    logging_config_host: str | None = None
    logging_config_port: int | None = None
    huuto_username: str | None = None
    huuto_password: SecretStr | None = None
    huuto_user_id: int | None = None
    huutoapi_delay: float | None = 0.5
    postal_code: int | None = None
    delivery_terms: str | None = None
    payment_terms: str | None = None
    max_retries: int | None = None
    omdb_api_key: SecretStr | None = None
    worker_prometheus_port: int | None = None
    secret_key: SecretStr | None = None
    algorithm: str | None = "HS256"
    access_token_expire_minutes: int | None = 30
    auth_cookie_secure: bool | None = False  
    image_dir: str | None = "media/images"
    huutoapp_mcp_idp_url: HttpUrl | None = None
    huutoapp_mcp_idp_realm: str | None = None
    huutoapp_mcp_idp_audience: str | None = None
    huutoapp_mcp_server_url: HttpUrl | None = None
    huutoapp_mcp_tool_docs_path: str | None = None
    huutoapp_mcp_perform_auth: bool = False

settings = Settings() # type: ignore # Loaded from .env file