"""Model list dialog widget."""

from textual.app import ComposeResult
from textual.containers import Container, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Label, Static


class ModelListDialog(ModalScreen):
    """Modal dialog for displaying available ADK models."""

    CSS = """
    ModelListDialog {
        align: center middle;
    }

    ModelListDialog > Container {
        width: 60;
        height: auto;
        max-height: 80%;
        border: thick $background;
        background: $surface;
        padding: 1 2;
    }

    #model-table {
        height: 15;
        margin: 1 0;
    }
    """

    def compose(self) -> ComposeResult:
        """Create child widgets for the model list dialog."""
        with Container():
            yield Static("[bold]Available ADK Models[/bold]", id="dialog-title")
            yield DataTable(id="model-table")
            yield Button("Close", id="btn-close", variant="primary")

    def on_mount(self) -> None:
        """Load model information when dialog is mounted."""
        table = self.query_one("#model-table", DataTable)
        table.add_columns("Model Name", "Description", "Context Window")

        models_info = [
            ("gemini-2.0-flash-exp", "Latest experimental model", "1M tokens"),
            ("gemini-1.5-flash", "Fast, cost-effective", "1M tokens"),
            ("gemini-1.5-flash-8b", "Lightweight, efficient", "1M tokens"),
            ("gemini-1.5-pro", "Advanced capabilities", "2M tokens"),
        ]

        for model_info in models_info:
            table.add_row(*model_info)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press."""
        if event.button.id == "btn-close":
            self.dismiss()