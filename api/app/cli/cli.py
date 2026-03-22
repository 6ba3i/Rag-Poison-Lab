from __future__ import annotations

import typer

from api.app.cli.commands_attack import attack_app
from api.app.cli.commands_data import data_app
from api.app.cli.commands_eval import eval_app
from api.app.cli.commands_index import index_app
from api.app.cli.commands_report import report_app
from api.app.cli.wizard import run_wizard
from api.app.common.log import configure_logging


app = typer.Typer(help="RAGPoison CLI")
app.add_typer(data_app, name="data")
app.add_typer(attack_app, name="attack")
app.add_typer(index_app, name="index")
app.add_typer(eval_app, name="eval")
app.add_typer(report_app, name="report")


@app.command("wizard")
def wizard_command() -> None:
    """Run interactive wizard."""

    run_wizard()


def main() -> None:
    configure_logging()
    app()


if __name__ == "__main__":
    main()
