import typer
from pydantic import ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict
from rich import print


class Settings(BaseSettings):
    interactem_username: str
    interactem_password: str
    api_base_url: str = "http://localhost:8080/api/v1"

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False
    )


def get_settings() -> Settings:
    try:
        return Settings()  # type: ignore[call-arg]
    except ValidationError as e:
        print("[red]Configuration error:[/red]")
        for error in e.errors():
            field = error["loc"][0]
            msg = error["msg"]
            print(f"[red]  - {field}: {msg}[/red]")
        raise typer.Exit(1)
