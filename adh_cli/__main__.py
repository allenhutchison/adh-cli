"""Main entry point for the ADH CLI application."""

import click
from .app import ADHApp


@click.command()
def main() -> None:
    """Launch the ADH CLI TUI application."""
    app = ADHApp()
    app.run()


if __name__ == "__main__":
    main()