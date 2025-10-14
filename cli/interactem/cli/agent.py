import asyncio
from pathlib import Path
from typing import Annotated

import typer
from dotenv import load_dotenv
from rich import print

agent_app = typer.Typer(help="Manage agents.")


@agent_app.command("start")
def start(
    env_file: Annotated[
        Path | None,
        typer.Option(
            "--dotenv",
            "-e",
            help="Path to .env file with agent configuration",
            exists=True,
            readable=True,
        ),
    ] = None,
):
    """
    Start an InteractEM agent.

    See backend/agent/.env.example for configuration options.
    """

    print("[yellow]Starting InteractEM agent...[/yellow]")

    if env_file:
        print(f"[cyan]Loading environment from: {env_file}[/cyan]")
        load_dotenv(dotenv_path=env_file)

    try:
        # Import after setting environment variables so config picks them up
        print("[green]Starting agent...[/green]")
        from interactem.agent.broker import app

        asyncio.run(app.run())
    except Exception as e:
        print(f"[red]Failed to start agent: {e}[/red]")
        raise typer.Exit(1)
