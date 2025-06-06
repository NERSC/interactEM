import asyncio
import json
from pathlib import Path
from uuid import UUID

import typer
from rich import print
from rich.console import Console
from rich.table import Table

from interactem.core.constants import SUBJECT_PIPELINES_RUN, SUBJECT_PIPELINES_STOP
from interactem.core.events.pipelines import PipelineRunEvent, PipelineStopEvent
from interactem.core.nats import get_keys, get_pipelines_bucket, nc

app = typer.Typer()
pipeline_app = typer.Typer()
app.add_typer(pipeline_app, name="pipeline", help="Manage pipelines.")

@pipeline_app.command("run")
def run(
    file: Path = typer.Option(..., "--file", "-f", exists=True, readable=True, help="Path to pipeline.json"),
):
    """Run a pipeline from a file."""
    print(f"[bold green]Running pipeline from:[/] {file}")
    asyncio.run(run_pipeline(file))

async def run_pipeline(filepath: Path):
    pipeline_dict = json.loads(filepath.read_text())
    event = PipelineRunEvent(**pipeline_dict)
    event_json = event.model_dump_json()
    pipeline_id = event.id

    print("[yellow]Connecting to NATS...[/]")
    nats_client = await nc(servers=["nats://localhost:4222"], name="pipeline-starter")
    print("[green]Connected to NATS![/]")

    await nats_client.publish(SUBJECT_PIPELINES_RUN, event_json.encode())
    print(f"[blue]Published pipeline {pipeline_id} to {SUBJECT_PIPELINES_RUN}[/]")

    await nats_client.close()

@pipeline_app.command("stop")
def stop(
    pipeline_id: str = typer.Argument(..., help="Pipeline ID (UUID) to stop"),
):
    """Stop a running pipeline by ID."""
    try:
        uuid_obj = UUID(pipeline_id)
    except ValueError:
        print(f"[red]Invalid UUID: {pipeline_id}[/]")
        raise typer.Exit(code=1)
    asyncio.run(send_stop_pipeline(uuid_obj))

async def send_stop_pipeline(pipeline_id: UUID):
    print(f"[bold yellow]Stopping pipeline with ID:[/] {pipeline_id}")
    print("[yellow]Connecting to NATS...[/]")
    nats_client = await nc(servers=["nats://localhost:4222"], name="pipeline-stopper")
    print("[green]Connected to NATS![/]")
    js = nats_client.jetstream()

    pipeline_bucket = await get_pipelines_bucket(js)
    val = await pipeline_bucket.get(key=str(pipeline_id))
    if val is None:
        print(f"[red]Pipeline with ID {pipeline_id} not found.[/]")
        await nats_client.close()
        return

    if hasattr(val, 'revision'):
        revision_id = val.revision
    else:
        print(f"[red]Could not find revision_id for pipeline {pipeline_id}[/]")
        await nats_client.close()
        return

    stop_event = PipelineStopEvent(id=pipeline_id, revision_id=revision_id)
    stop_json = stop_event.model_dump_json()

    await nats_client.publish(SUBJECT_PIPELINES_STOP, stop_json.encode())
    print(f"[blue]Sent stop event to {SUBJECT_PIPELINES_STOP} for pipeline {pipeline_id}[/]")

    await nats_client.close()

@pipeline_app.command("ls")
def list_():
    """List pipelines."""
    asyncio.run(list_running_pipelines())

async def list_running_pipelines():
    print("[yellow]Connecting to NATS...[/]")
    nats_client = await nc(servers=["nats://localhost:4222"], name="pipeline-lister")
    print("[green]Connected to NATS![/]")
    js = nats_client.jetstream()

    pipeline_bucket = await get_pipelines_bucket(js)
    pipeline_keys = await get_keys(pipeline_bucket)
    await nats_client.close()

    if not pipeline_keys:
        print("[cyan]No pipelines found.[/]")
        return

    table = Table(title="Pipelines")
    table.add_column("S.No", style="magenta")
    table.add_column("Pipeline ID", style="cyan")
    for idx, pipeline_id in enumerate(pipeline_keys, start=1):
        table.add_row(str(idx), pipeline_id)
    console = Console()
    console.print(table)
