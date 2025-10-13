import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Annotated, cast

import httpx
import typer
from jinja2 import Environment, FileSystemLoader
from pydantic import BaseModel, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict
from rich import print
from rich.console import Console
from rich.table import Table

from interactem.core.constants import (
    INTERACTEM_IMAGE_REGISTRY,
)
from interactem.core.models.canonical import PortType
from interactem.core.models.spec import (
    OperatorSpec,
    OperatorSpecInput,
    OperatorSpecOutput,
    OperatorSpecParameter,
    OperatorSpecTag,
    ParallelConfig,
    ParallelType,
    ParameterSpecType,
)

app = typer.Typer()
pipeline_app = typer.Typer(help="Manage pipelines.")
app.add_typer(pipeline_app, name="pipeline")
operator_app = typer.Typer(help="Manage operators.")
app.add_typer(operator_app, name="operator")


class Settings(BaseSettings):
    interactem_username: str
    interactem_password: str
    api_base_url: str = "http://localhost:8080/api/v1"

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False
    )


class PipelineData(BaseModel):
    operators: list[dict] = []
    ports: list[dict] = []
    edges: list[dict] = []


class PipelinePayload(BaseModel):
    data: PipelineData


class PipelineResponse(BaseModel):
    id: str
    name: str
    data: PipelineData
    owner_id: str
    created_at: datetime
    updated_at: datetime
    current_revision_id: int


class PipelinesListResponse(BaseModel):
    data: list[PipelineResponse]
    count: int


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


class TemplateContext(BaseModel):
    """Context data for Jinja2 templates."""

    spec: OperatorSpec
    name: str
    function_name: str
    base_image: str
    additional_packages: list[str] | None = None


@operator_app.command("new", help="Generate a new operator directory from templates.")
def new_operator(
    name: Annotated[
        str,
        typer.Option(
            "--name",
            "-n",
            help="Name of the operator",
            prompt="Name your operator (kebab-case, e.g. my-operator)",
        ),
    ],
    label: Annotated[
        str | None,
        typer.Option(
            "--label",
            "-l",
            help="Human-readable label for the operator",
            prompt="Label (for frontend display)",
        ),
    ] = None,
    description: Annotated[
        str,
        typer.Option(
            "--description", "-d", help="Operator description", prompt="Description"
        ),
    ] = "",
    registry: Annotated[
        str,
        typer.Option(
            "--registry",
            "-r",
            help="Container image registry",
            prompt="Image registry",
        ),
    ] = INTERACTEM_IMAGE_REGISTRY,
    parallel_type: Annotated[
        ParallelType,
        typer.Option(
            "--parallel-cfg",
            "-p",
            help="Parallel type",
            prompt="Parallel type",
        ),
    ] = ParallelType.NONE,
    base_image: Annotated[
        str,
        typer.Option("--base-image", "-b", help="Base container image"),
    ] = "ghcr.io/nersc/interactem/operator",
    output_dir: Annotated[
        Path,
        typer.Option(
            "--output-dir",
            "-o",
            help="Output directory for operators",
            prompt="Output directory?",
        ),
    ] = Path("operators"),
    dependencies: Annotated[
        str,
        typer.Option(
            "--dependencies",
            help="Additional Python dependencies (comma-separated)",
            prompt="Additional Python dependencies (comma-separated)?",
        ),
    ] = "",
):
    """Generate a new operator directory from templated files."""

    operator_dir = output_dir / name
    if operator_dir.exists():
        print(f"[red]Looks like that operator already exists in {operator_dir}![/red]")
        raise typer.Exit(1)

    # Parse dependencies from comma-separated string
    parsed_dependencies = None
    if dependencies and dependencies.strip():
        parsed_dependencies = [
            dep.strip() for dep in dependencies.split(",") if dep.strip()
        ]

    spec = OperatorSpec(
        id=uuid.uuid4(),
        label=label or name.replace("-", " ").title(),
        description=description,
        image=f"{registry}{name}:latest",
        inputs=cast(list[OperatorSpecInput], _collect_ports(type=PortType.input)),
        outputs=cast(list[OperatorSpecOutput], _collect_ports(type=PortType.output)),
        parameters=_collect_parameters(),
        parallel_config=ParallelConfig(type=parallel_type),
        tags=_collect_tags(),
    )

    ctx = TemplateContext(
        name=name,
        spec=spec,
        function_name=name.replace("-", "_"),
        base_image=base_image,
        additional_packages=parsed_dependencies,
    )

    _display_summary(ctx, output_dir)
    if not typer.confirm("Create operator with these settings?", default=True):
        print("[yellow]Operation cancelled.[/yellow]")
        raise typer.Exit(0)

    _create_operator_files(operator_dir, ctx)
    print(f"[bold green]Operator '{ctx.name}' created successfully![/bold green]")

    _print_next_steps(operator_dir)


def _collect_tags() -> list[OperatorSpecTag]:
    """Interactively collect operator tags."""
    if not typer.confirm("Does this operator have tags?", default=False):
        return []
    tags = []
    print("[cyan]Add tags (leave value empty to finish):[/cyan]")

    while True:
        tag_value = typer.prompt(
            "  New tag (e.g., gpu, ncem-4dstem)", default="", type=str
        )
        if not tag_value:
            break

        try:
            tag_description = typer.prompt("  Description", default=f"{tag_value} tag")
            tags.append(
                OperatorSpecTag(
                    value=tag_value,
                    description=tag_description,
                )
            )
            print(f"  [green]Added tag: {tag_value}[/green]")
        except Exception as e:
            print(f"  [red]Error creating tag: {e}. Skipping tag.[/red]")
            continue

    return tags


def _collect_ports(
    type: PortType,
) -> list[OperatorSpecInput] | list[OperatorSpecOutput]:
    """Interactively collect operator ports."""
    if not typer.confirm(f"Does this operator have {type.value}s?", default=False):
        return []
    model_cls = OperatorSpecInput if type == PortType.input else OperatorSpecOutput
    ports = []
    print(f"[cyan]Add {type.value}s (leave name empty to finish):[/cyan]")

    while True:
        input_name = typer.prompt(f"  {type.value} name (snake_case)", default="")
        if not input_name:
            break

        try:
            input_label = typer.prompt(
                "  Label", default=input_name.replace("_", " ").title()
            )
            input_description = typer.prompt(
                "  Description", default=f"{input_label} {type.value}"
            )
            port_type = typer.prompt(
                "  Type (e.g., BatchedFrames, Frame, etc.)", type=str
            )
            ports.append(
                model_cls(
                    name=input_name,
                    type=port_type,
                    label=input_label,
                    description=input_description,
                )
            )
            print(f"  [green]Added {type.value}: {input_name}[/green]")
        except Exception as e:
            print(
                f"  [red]Error creating {type.value}: {e}. Skipping {type.value}.[/red]"
            )
            continue

    return ports


def _collect_parameters() -> list[OperatorSpecParameter]:
    """Interactively collect operator parameters."""
    if not typer.confirm(
        "Do you want to add parameters to this operator?", default=False
    ):
        return []

    parameters = []
    print("[cyan]Add parameters (leave name empty to finish):[/cyan]")

    while True:
        param_name = typer.prompt("  Parameter name (snake_case)", default="")
        if not param_name:
            break

        param = _create_parameter(param_name)
        if param:
            parameters.append(param)
            print(f"  [green]Added parameter: {param_name}[/green]")

    return parameters


def _create_parameter(param_name: str) -> OperatorSpecParameter | None:
    """Create a single parameter with validation."""
    param_label = typer.prompt("  Label", default=param_name.replace("_", " ").title())
    param_type_str = typer.prompt(
        f"  Type [{', '.join([t.value for t in ParameterSpecType])}]",
        type=ParameterSpecType,
        show_choices=True,
    )

    valid_types = [t.value for t in ParameterSpecType]
    if param_type_str not in valid_types:
        print(f"  [red]Invalid type. Must be one of: {', '.join(valid_types)}[/red]")
        return None

    param_type = ParameterSpecType(param_type_str)
    param_description = typer.prompt(
        "  Description", default=f"{param_label} parameter"
    )
    param_required = typer.confirm("  Required?", default=False)
    try:
        param_default = _get_parameter_default(param_type)
    except ValueError as e:
        print(f"  [red]{e} Skipping parameter.[/red]")
        return None
    param_options = None

    # Handle str-enum options
    if param_type == ParameterSpecType.STR_ENUM:
        try:
            options_input = typer.prompt("  Options (comma-separated)", default="")
            if not options_input:
                print(
                    "  [red]str-enum type requires options. Skipping parameter.[/red]"
                )
                return None
            param_options = [opt.strip() for opt in options_input.split(",")]
            if param_default not in param_options:
                print(
                    "  [yellow]Warning: Default not in options. Using first option.[/yellow]"
                )
                param_default = param_options[0]
        except Exception as e:
            print(f"  [red]Error parsing options: {e}. Skipping parameter.[/red]")
            return None

    try:
        return OperatorSpecParameter(
            name=param_name,
            label=param_label,
            type=param_type,
            default=param_default,
            description=param_description,
            required=param_required,
            options=param_options,
        )
    except ValidationError as e:
        print(f"  [red]Validation error: {e}. Skipping parameter.[/red]")
        return None


def _get_parameter_default(param_type: ParameterSpecType) -> str:
    """Get default value based on parameter type."""
    msg = "  Enter default value"
    default_handlers = {
        "bool": lambda: str(typer.confirm(msg + " (bool)", default=False)),
        "int": lambda: str(typer.prompt(msg + " (int)", type=int)),
        "float": lambda: str(typer.prompt(msg + " (float)", type=float)),
        "mount": lambda: str(typer.prompt(msg + " (path)", type=Path)),
        "str": lambda: typer.prompt(msg + " (str)", type=str),
        "str-enum": lambda: typer.prompt(msg + " (str)", type=str),
    }
    handler = default_handlers.get(param_type, None)
    if handler is None:
        raise ValueError(f"Unsupported parameter type: {param_type}")
    return handler()


def _display_summary(templ: TemplateContext, output_dir: Path):
    """Display configuration summary."""
    templ_tmp = TemplateContext.model_validate(templ.model_dump())
    print("[bold]Summary:[/bold]")
    print(f"  Spec [cyan]{templ_tmp.spec}[/cyan]")
    print(f"  Template: [cyan]{templ_tmp.model_dump(exclude={'spec'})}[/cyan]")
    print(f"  Output Directory: [cyan]{output_dir / templ_tmp.name}[/cyan]")
    print()


def _create_operator_files(operator_dir: Path, context: TemplateContext):
    """Create operator directory and generate files."""
    try:
        operator_dir.mkdir(parents=True, exist_ok=False)
    except OSError as e:
        print(f"[red]Error creating directory {operator_dir}: {e}[/red]")
        raise typer.Exit(1)

    print(f"[green]Created operator directory: {operator_dir}[/green]")
    template_dir = Path(__file__).parent / "templates"
    env = Environment(loader=FileSystemLoader(template_dir))

    for template_name, output_name in [
        ("run.py.j2", "run.py"),
        ("Containerfile.j2", "Containerfile"),
        ("operator.json.j2", "operator.json"),
    ]:
        template = env.get_template(template_name)
        content = template.render(context.model_dump())
        filename = operator_dir / output_name
        filename.write_text(content)
        print(f"[green]Generated {output_name}[/green]")
        if not output_name == "operator.json":
            continue
        # Validate the generated spec
        read_and_validate_operator_spec(filename)


def _print_next_steps(operator_dir: Path):
    print("[cyan]Next steps:[/cyan]")
    print(f"  1. Edit {operator_dir}/run.py to implement operator logic")
    print(
        f"  2. Edit {operator_dir}/operator.json to configure parameters, inputs, and outputs"
    )
    print(f"  3. Edit {operator_dir}/Containerfile to add dependencies if needed")


def read_and_validate_operator_spec(file_path: Path) -> None:
    try:
        spec_json = json.loads(file_path.read_text())
        OperatorSpec(**spec_json)
        print(f"[green]Operator spec {file_path} is valid.[/green]")
    except json.JSONDecodeError as e:
        print(f"[red]Invalid JSON file: {e}[/red]")
    except ValidationError as e:
        print("[red]Operator spec validation failed:[/red]")
        for error in e.errors():
            loc = " -> ".join(str(loc_part) for loc_part in error["loc"])
            msg = error["msg"]
            print(f"[red]  - {loc}: {msg}[/red]")


@operator_app.command("validate", help="Validate an operator spec JSON file.")
def validate(
    file: Annotated[
        Path,
        typer.Argument(exists=True, readable=True, help="Path to operator.json"),
    ],
):
    read_and_validate_operator_spec(file)
