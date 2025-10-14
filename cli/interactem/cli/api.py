import httpx
import typer
from rich import print

from interactem.cli.settings import get_settings


def get_token(api_base: str, username: str, password: str) -> str:
    url = f"{api_base}/login/access-token"
    data = {"username": username, "password": password}
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    resp = httpx.post(url, data=data, headers=headers)
    resp.raise_for_status()
    return resp.json()["access_token"]


def get_auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def get_env_and_token():
    settings = get_settings()
    try:
        token = get_token(
            settings.api_base_url,
            settings.interactem_username,
            settings.interactem_password,
        )
    except Exception as e:
        print(f"[red]Login failed: {e}[/red]")
        raise typer.Exit(1)
    return settings.api_base_url, get_auth_headers(token)


def api_request(
    method: str, url: str, headers: dict | None = None, json: dict | None = None
) -> dict:
    try:
        resp = httpx.request(method, url, headers=headers, json=json)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as e:
        print(f"[red]HTTP Error: {e.response.status_code} - {e.response.text}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)
