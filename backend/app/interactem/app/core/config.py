import secrets
import warnings
from pathlib import Path
from typing import Annotated, Any, Literal
from urllib.parse import quote_plus

from nats.aio.client import Client as NATSClient
from pydantic import (
    AnyUrl,
    AnyWebsocketUrl,
    BeforeValidator,
    Field,
    HttpUrl,
    NatsDsn,
    PostgresDsn,
    computed_field,
    model_validator,
)
from pydantic_core import MultiHostUrl
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing_extensions import Self


def parse_cors(v: Any) -> list[str] | str:
    if isinstance(v, str) and not v.startswith("["):
        return [i.strip() for i in v.split(",")]
    elif isinstance(v, list | str):
        return v
    raise ValueError(v)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="APP_",
        env_ignore_empty=True,
        extra="ignore",
    )
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = secrets.token_urlsafe(32)
    # 60 minutes * 24 hours * 8 days = 8 days
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8
    DOMAIN: str = "localhost"
    ENVIRONMENT: Literal["local", "staging", "production"] = "local"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def server_host(self) -> str:
        # Use HTTPS for anything other than local development
        if self.ENVIRONMENT == "local":
            return f"http://{self.DOMAIN}"
        return f"https://{self.DOMAIN}"

    BACKEND_CORS_ORIGINS: Annotated[
        list[AnyUrl] | str, BeforeValidator(parse_cors)
    ] = []

    PROJECT_NAME: str
    SENTRY_DSN: HttpUrl | None = None
    POSTGRES_SERVER: str
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str = ""
    POSTGRES_DB: str = ""

    @computed_field  # type: ignore[prop-decorator]
    @property
    def SQLALCHEMY_DATABASE_URI(self) -> PostgresDsn:
        return MultiHostUrl.build(
            scheme="postgresql+psycopg",
            username=self.POSTGRES_USER,
            password=quote_plus(self.POSTGRES_PASSWORD),
            host=self.POSTGRES_SERVER,
            port=self.POSTGRES_PORT,
            path=self.POSTGRES_DB,
        )

    FIRST_SUPERUSER_USERNAME: str
    FIRST_SUPERUSER_PASSWORD: str

    def _check_default_secret(self, var_name: str, value: str | None) -> None:
        if value == "changethis":
            message = (
                f'The value of {var_name} is "changethis", '
                "for security, please change it, at least for deployments."
            )
            if self.ENVIRONMENT == "local":
                warnings.warn(message, stacklevel=1)
            else:
                raise ValueError(message)

    @model_validator(mode="after")
    def _enforce_non_default_secrets(self) -> Self:
        self._check_default_secret("SECRET_KEY", self.SECRET_KEY)
        self._check_default_secret("POSTGRES_PASSWORD", self.POSTGRES_PASSWORD)
        self._check_default_secret(
            "FIRST_SUPERUSER_PASSWORD", self.FIRST_SUPERUSER_PASSWORD
        )

        # Require GitHub credentials for staging/production
        if self.ENVIRONMENT in ("staging", "production"):
            if not self.GITHUB_USERNAME or not self.GITHUB_TOKEN:
                raise ValueError(
                    "GITHUB_USERNAME and GITHUB_TOKEN are required in "
                    f"{self.ENVIRONMENT} environment"
                )

        return self

    # NATS
    NATS_SERVER_URL: AnyWebsocketUrl | NatsDsn = NatsDsn("nats://nats1:4222")

    # External auth
    EXTERNAL_SECRET_KEY: str
    EXTERNAL_ALGORITHM: str
    NATS_FRONTEND_CREDS: Path = Path("/frontend.creds")
    NATS_JWT: str = ""

    @model_validator(mode="after")
    def extract_jwt_from_creds(self) -> Self:
        user_jwt = NATSClient()._read_creds_user_jwt(str(self.NATS_FRONTEND_CREDS))
        self.NATS_JWT = user_jwt.decode()
        return self

    # Container Registry
    CONTAINER_REGISTRY_URL: HttpUrl = Field(default="https://ghcr.io")
    GITHUB_USERNAME: str | None = None
    GITHUB_TOKEN: str | None = None
    CONTAINER_REGISTRY_NAMESPACE: str = "nersc"
    OPERATOR_CONTAINER_PREFIX: str = "interactem"

    # Local operators - mount your local operators directory to make
    # changes to operator specs locally
    LOCAL_OPERATORS_DIR: Path = Path("/operators")

    # Internal API key
    ORCHESTRATOR_API_KEY: str = "changeme"


settings = Settings()  # type: ignore
