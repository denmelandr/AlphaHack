from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://conveyor:conveyor@localhost:5432/conveyor"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret: str = "dev-secret-change-me"
    bank_invitation_code: str = ""
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 12
    integrations_url: str = "http://localhost:8001"
    cors_origins: str = "http://localhost:5173"

    # Копилот андеррайтера. По умолчанию работает в шаблонном режиме, чтобы демо
    # не зависело от GPU и платных ресурсов. Для LLM поднимите Ollama с моделью
    # с открытыми весами (Qwen, Mistral, T-lite) и включите llm_enabled.
    llm_enabled: bool = False
    ollama_url: str = "http://ollama:11434"
    llm_model: str = "qwen2.5:7b-instruct"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
