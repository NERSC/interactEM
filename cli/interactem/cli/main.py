import typer

from interactem.cli.operators import operator_app
from interactem.cli.pipeline import pipeline_app

app = typer.Typer()
app.add_typer(pipeline_app, name="pipeline")
app.add_typer(operator_app, name="operator")
