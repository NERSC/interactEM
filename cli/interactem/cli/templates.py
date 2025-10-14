import json
from pathlib import Path

import typer
from jinja2 import Environment, FileSystemLoader
from pydantic import ValidationError
from rich import print

from interactem.cli.models import TemplateContext
from interactem.core.models.spec import OperatorSpec


def create_operator_files(operator_dir: Path, context: TemplateContext):
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
    ]:
        template = env.get_template(template_name)
        content = template.render(context.model_dump())
        filename = operator_dir / output_name
        filename.write_text(content)
        print(f"[green]Generated {output_name}[/green]")

    operator_json_path = operator_dir / "operator.json"
    spec_dict = context.spec.model_dump(mode="json", exclude_none=True)
    operator_json_path.write_text(json.dumps(spec_dict, indent=2))
    print("[green]Generated operator.json[/green]")
    read_and_validate_operator_spec(operator_json_path)


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
