"""Entry point for the policy-aware ADH CLI application."""

import click
from pathlib import Path


@click.command()
@click.option(
    '--debug',
    is_flag=True,
    help='Enable debug mode'
)
@click.option(
    '--policy-dir',
    type=click.Path(path_type=Path),
    default=None,
    help='Directory containing policy files'
)
@click.option(
    '--no-safety',
    is_flag=True,
    help='Disable safety checks (use with caution)'
)
def main(debug: bool, policy_dir: Path, no_safety: bool):
    """ADH CLI - Policy-Aware AI Development Helper

    A terminal-based interface for interacting with AI models
    using Google's ADK with integrated policy enforcement.
    """
    import os
    import sys

    # Set up environment
    if debug:
        os.environ['TEXTUAL_DEBUG'] = '1'

    # Import and run the policy-aware app
    from .app_policy import PolicyAwareADHApp

    app = PolicyAwareADHApp()

    # Configure policy directory if specified
    if policy_dir:
        app.policy_dir = policy_dir

    # Configure safety settings
    if no_safety:
        app.safety_enabled = False
        click.echo(click.style(
            "⚠️  WARNING: Running with safety checks disabled!",
            fg='yellow',
            bold=True
        ))

    # Run the application
    try:
        app.run()
    except KeyboardInterrupt:
        click.echo("\nExiting...")
        sys.exit(0)
    except Exception as e:
        if debug:
            raise
        else:
            click.echo(click.style(f"Error: {e}", fg='red'))
            sys.exit(1)


if __name__ == '__main__':
    main()