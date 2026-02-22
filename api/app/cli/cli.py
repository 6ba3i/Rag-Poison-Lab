from __future__ import annotations

import typer

from api.app.cli.commands_data import data_app
from api.app.cli.wizard import run_wizard


app = typer.Typer(help="RAGPoison CLI")
app.add_typer(data_app, name="data")


@app.command("wizard")
def wizard_command() -> None:
    """Run interactive wizard."""

    run_wizard()


def main() -> None:
    app()


if __name__ == "__main__":
    main()
