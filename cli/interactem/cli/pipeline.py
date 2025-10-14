import json
from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError
from rich import print
from rich.console import Console
from rich.table import Table

from interactem.cli.api import api_request, get_env_and_token
from interactem.cli.models import (
    PipelinePayload,
    PipelineResponse,
    PipelinesListResponse,
)

pipeline_app = typer.Typer(help="Manage pipelines.")


@pipeline_app.command("create", help="Create a new pipeline from a JSON file.")
def create(
    file: Annotated[
        Path,
        typer.Option(
            "--file", "-f", exists=True, readable=True, help="Path to pipeline.json"
        ),
    ],
):
    api_base, headers = get_env_and_token()

    try:
        pipeline_json = json.loads(file.read_text())
        payload = PipelinePayload(**pipeline_json)
    except json.JSONDecodeError as e:
        print(f"[red]Invalid JSON file: {e}[/red]")
        raise typer.Exit(1)
    except ValidationError as e:
        print("[red]Invalid pipeline data:[/red]")
        for error in e.errors():
            loc = " -> ".join(str(loc_part) for loc_part in error["loc"])
            msg = error["msg"]
            print(f"[red]  - {loc}: {msg}[/red]")
        raise typer.Exit(1)

    print("[yellow]Creating pipeline...[/yellow]")
    pipeline_url = f"{api_base}/pipelines/"
    pipeline_data = api_request(
        "POST", pipeline_url, headers=headers, json=payload.model_dump()
    )

    try:
        pipeline_response = PipelineResponse(**pipeline_data)
        pipeline_id = pipeline_response.id
    except ValidationError as e:
        print(f"[red]Unexpected response format: {e}[/red]")
        raise typer.Exit(1)

    revision_payload = payload.model_dump()
    revision_url = f"{api_base}/pipelines/{pipeline_id}/revisions"
    print(f"[yellow]Creating revision for pipeline {pipeline_id}...[/yellow]")
    revision = api_request("POST", revision_url, headers=headers, json=revision_payload)

    if pipeline_data and revision:
        print(f"[green]Pipeline created with ID: {pipeline_id}![/green]")
    else:
        print("[red]Failed to create pipeline")
        raise typer.Exit(1)


@pipeline_app.command("ls", help="List all pipelines.")
def ls():
    api_base, headers = get_env_and_token()
    url = f"{api_base}/pipelines/"
    print("[yellow]Fetching pipelines...[/yellow]")
    response = api_request("GET", url, headers=headers)

    try:
        pipelines_response = PipelinesListResponse(**response)
        pipelines = pipelines_response.data
    except ValidationError as e:
        print(f"[red]Unexpected response format: {e}[/red]")
        raise typer.Exit(1)

    if not pipelines:
        print("[yellow]No pipelines found.[/yellow]")
        return

    table = Table(title="Pipelines")
    table.add_column("Pipeline ID", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Current Revision ID", style="blue")
    table.add_column("Owner", style="yellow")
    table.add_column("Created At", style="white")

    for p in pipelines:
        table.add_row(
            p.id,
            p.name,
            str(p.current_revision_id),
            p.owner_id,
            p.created_at.isoformat(),
        )
    Console().print(table)


@pipeline_app.command("run", help="Run a pipeline revision.")
def run(
    pipeline_id: Annotated[str, typer.Argument(help="Pipeline ID")],
    revision_id: Annotated[str, typer.Argument(help="Revision ID")],
):
    api_base, headers = get_env_and_token()
    url = f"{api_base}/pipelines/{pipeline_id}/revisions/{revision_id}/run"
    print(f"[yellow]Running pipeline {pipeline_id} revision {revision_id}...[/yellow]")
    response = api_request("POST", url, headers=headers)

    if response:
        print("[green]Pipeline run started![/green]")
    else:
        print("[red]Failed to run pipeline[/red]")
        raise typer.Exit(1)


@pipeline_app.command("stop", help="Stop a pipeline revision.")
def stop(
    pipeline_id: Annotated[str, typer.Argument(help="Pipeline ID")],
    revision_id: Annotated[str, typer.Argument(help="Revision ID")],
):
    api_base, headers = get_env_and_token()
    url = f"{api_base}/pipelines/{pipeline_id}/revisions/{revision_id}/stop"
    print(f"[yellow]Stopping pipeline {pipeline_id} revision {revision_id}...[/yellow]")
    response = api_request("POST", url, headers=headers)

    if response:
        print("[green]Pipeline stop requested![/green]")
    else:
        print("[red]Failed to stop pipeline[/red]")
        raise typer.Exit(1)


@pipeline_app.command("rm", help="Delete a pipeline.")
def remove(
    pipeline_id: Annotated[str, typer.Argument(help="Pipeline ID")],
):
    api_base, headers = get_env_and_token()
    url = f"{api_base}/pipelines/{pipeline_id}"
    print(f"[yellow]Deleting pipeline {pipeline_id}...[/yellow]")
    response = api_request("DELETE", url, headers=headers)

    if response:
        print("[green]Pipeline deleted![/green]")
    else:
        print("[red]Failed to delete pipeline[/red]")
        raise typer.Exit(1)
