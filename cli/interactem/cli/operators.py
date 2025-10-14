import uuid
from pathlib import Path
from typing import Annotated, cast

import typer
from pydantic import ValidationError
from rich import print

from interactem.cli.models import TemplateContext
from interactem.cli.templates import (
    create_operator_files,
    read_and_validate_operator_spec,
)
from interactem.core.constants import INTERACTEM_IMAGE_REGISTRY
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

operator_app = typer.Typer(help="Manage operators.")


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

    create_operator_files(operator_dir, ctx)
    print(f"[bold green]Operator '{ctx.name}' created successfully![/bold green]")

    _print_next_steps(operator_dir)


def _collect_tags() -> list[OperatorSpecTag] | None:
    """Interactively collect operator tags."""
    if not typer.confirm("Does this operator have tags?", default=False):
        return None
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

    if not tags:
        return None

    return tags


def _collect_ports(
    type: PortType,
) -> list[OperatorSpecInput] | list[OperatorSpecOutput] | None:
    """Interactively collect operator ports."""
    if not typer.confirm(f"Does this operator have {type.value}s?", default=False):
        return None
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


def _print_next_steps(operator_dir: Path):
    print("[cyan]Next steps:[/cyan]")
    print(f"  1. Edit {operator_dir}/run.py to implement operator logic")
    print(
        f"  2. Edit {operator_dir}/operator.json to configure parameters, inputs, and outputs"
    )
    print(f"  3. Edit {operator_dir}/Containerfile to add dependencies if needed")


@operator_app.command("validate", help="Validate an operator spec JSON file.")
def validate(
    file: Annotated[
        Path,
        typer.Argument(exists=True, readable=True, help="Path to operator.json"),
    ],
):
    read_and_validate_operator_spec(file)
