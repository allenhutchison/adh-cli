"""Main application module with policy-aware agent for ADH CLI."""

import os
import json
from pathlib import Path
from dotenv import load_dotenv
from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Header, Footer

from .screens.main_screen import MainScreen
from .screens.chat_screen import ChatScreen
from .core.policy_aware_llm_agent import PolicyAwareLlmAgent
from .core.config_paths import ConfigPaths


class ADHApp(App):
    """Main ADH CLI TUI Application with Policy-Aware Agent."""

    CSS = """
    Screen {
        background: $surface;
    }

    .container {
        padding: 1 2;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit", priority=True),
        Binding("d", "toggle_dark", "Toggle Dark Mode"),
        Binding("s", "show_settings", "Settings"),
        Binding("p", "show_policies", "Policy Settings"),
    ]

    SCREENS = {
        "main": MainScreen,
        "chat": ChatScreen,
    }

    TITLE = "ADH CLI - Policy-Aware Agent"
    SUB_TITLE = "Safe AI-assisted development"

    def __init__(self):
        """Initialize the application."""
        super().__init__()
        self.agent = None
        self.api_key = None
        self.safety_enabled = True

        # Migrate configuration from legacy location if needed
        migrated, error = ConfigPaths.migrate_if_needed()
        if migrated:
            self._migration_performed = True
        elif error:
            self._migration_error = error
        else:
            self._migration_performed = False

        # Set policy directory using ConfigPaths
        self.policy_dir = ConfigPaths.get_policies_dir()

        # Check for API key in environment
        self._load_api_key()

    def _load_api_key(self):
        """Load API key from environment."""
        # Load .env file if it exists
        load_dotenv()

        self.api_key = (
            os.environ.get("GOOGLE_API_KEY") or
            os.environ.get("GEMINI_API_KEY")
        )

    def _load_config(self):
        """Load configuration from config.json.

        Returns:
            Dict with configuration values
        """
        config_file = ConfigPaths.get_config_file()
        if config_file.exists():
            try:
                with open(config_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return {}

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header()
        yield Footer()

    def on_mount(self) -> None:
        """Initialize the app after mounting."""
        # Show migration notification if migration was performed
        if hasattr(self, '_migration_performed') and self._migration_performed:
            self.notify(
                "✓ Configuration migrated to ~/.config/adh-cli/\n"
                "Old location: ~/.adh-cli/ (safe to delete)",
                severity="information",
                timeout=10
            )
        elif hasattr(self, '_migration_error') and self._migration_error:
            self.notify(
                f"⚠️ Configuration migration failed: {self._migration_error}",
                severity="warning"
            )

        # Initialize the policy-aware agent
        self._initialize_agent()

        # Start with the chat screen
        self.push_screen("chat")

    def _initialize_agent(self):
        """Initialize the policy-aware ADK agent."""
        try:
            # Load configuration
            config = self._load_config()

            # Get orchestrator agent name from config (default to "orchestrator")
            agent_name = config.get("orchestrator_agent", "orchestrator")

            # Use ADK-based agent with automatic tool orchestration
            # Note: Execution manager callbacks will be registered by ChatScreen on mount
            # Note: Model settings from config are overridden by agent definition
            self.agent = PolicyAwareLlmAgent(
                model_name=config.get("model", "gemini-flash-latest"),
                api_key=self.api_key,
                policy_dir=self.policy_dir,
                confirmation_handler=self.handle_confirmation,
                notification_handler=self.show_notification,
                audit_log_path=ConfigPaths.get_audit_log(),
                temperature=config.get("temperature", 0.7),
                max_tokens=config.get("max_tokens", 2048),
                agent_name=agent_name,
            )

            # Register default tools
            self._register_default_tools()

        except Exception as e:
            self.notify(f"Failed to initialize agent: {str(e)}", severity="error")

    def _register_default_tools(self):
        """Register the default set of tools."""
        if not self.agent:
            return

        # Import and register shell tools
        from .tools import shell_tools

        # File operations
        self.agent.register_tool(
            name="read_file",
            description="Read contents of a text file",
            parameters={
                "file_path": {
                    "type": "string",
                    "description": "Path to the file to read"
                }
            },
            handler=shell_tools.read_file,
        )

        self.agent.register_tool(
            name="write_file",
            description="Write content to a file",
            parameters={
                "file_path": {
                    "type": "string",
                    "description": "Path to the file to write"
                },
                "content": {
                    "type": "string",
                    "description": "Content to write to the file"
                }
            },
            handler=shell_tools.write_file,
        )

        self.agent.register_tool(
            name="list_directory",
            description="List contents of a directory",
            parameters={
                "directory": {
                    "type": "string",
                    "description": "Directory path to list"
                }
            },
            handler=shell_tools.list_directory,
        )

        self.agent.register_tool(
            name="execute_command",
            description="Execute a shell command",
            parameters={
                "command": {
                    "type": "string",
                    "description": "Command to execute"
                }
            },
            handler=shell_tools.execute_command,
        )

        self.agent.register_tool(
            name="create_directory",
            description="Create a new directory",
            parameters={
                "directory": {
                    "type": "string",
                    "description": "Directory path to create"
                },
                "parents": {
                    "type": "boolean",
                    "description": "Create parent directories if they don't exist (default: true)"
                }
            },
            handler=shell_tools.create_directory,
        )

        self.agent.register_tool(
            name="delete_file",
            description="Delete a file (requires confirmation)",
            parameters={
                "file_path": {
                    "type": "string",
                    "description": "Path to the file to delete"
                },
                "confirm": {
                    "type": "boolean",
                    "description": "Confirmation flag - must be true to delete"
                }
            },
            handler=shell_tools.delete_file,
        )

        self.agent.register_tool(
            name="get_file_info",
            description="Get information about a file or directory",
            parameters={
                "file_path": {
                    "type": "string",
                    "description": "Path to the file or directory"
                }
            },
            handler=shell_tools.get_file_info,
        )

    async def handle_confirmation(self, tool_call=None, decision=None, message=None, **kwargs):
        """Handle confirmation requests from the policy engine.

        Args:
            tool_call: Tool call requiring confirmation
            decision: Policy decision
            message: Confirmation message
            **kwargs: Additional parameters

        Returns:
            True if confirmed, False otherwise
        """
        from .ui.confirmation_dialog import ConfirmationDialog

        if tool_call and decision:
            dialog = ConfirmationDialog(
                tool_name=tool_call.tool_name,
                parameters=tool_call.parameters,
                decision=decision,
            )
        else:
            # Simple confirmation without full context
            result = await self.push_screen_wait(
                ConfirmationDialog(
                    tool_name="Operation",
                    parameters={},
                    decision=None,
                )
            )
            return result

        # Push dialog and wait for result
        result = await self.push_screen_wait(dialog)
        return result if result is not None else False

    async def show_notification(self, message: str, level: str = "info"):
        """Show a notification to the user.

        Args:
            message: Notification message
            level: Notification level (info, warning, error, success)
        """
        severity = {
            "info": "information",
            "warning": "warning",
            "error": "error",
            "success": "information",
        }.get(level, "information")

        self.notify(message, severity=severity)

    def action_show_settings(self) -> None:
        """Show settings as a modal."""
        from .screens.settings_modal import SettingsModal
        self.push_screen(SettingsModal())

    def action_show_policies(self) -> None:
        """Show policy configuration screen."""
        # TODO: Implement PolicyConfigScreen
        self.notify("Policy configuration screen coming soon!", severity="information")

    def action_toggle_dark(self) -> None:
        """Toggle dark mode."""
        self.theme = "textual-dark" if self.theme == "textual-light" else "textual-light"

    def update_api_key(self, api_key: str):
        """Update the API key and reinitialize the agent.

        Args:
            api_key: New API key
        """
        self.api_key = api_key
        self._initialize_agent()
        self.notify("API key updated and agent reinitialized", severity="success")

    def update_safety_settings(self, enabled: bool):
        """Update safety settings.

        Args:
            enabled: Whether safety checks should be enabled
        """
        self.safety_enabled = enabled

        if self.agent:
            if not enabled:
                # Disable safety by auto-approving everything
                self.agent.set_user_preferences({
                    "auto_approve": ["*"],
                })
                self.notify("⚠️ Safety checks disabled", severity="warning")
            else:
                # Re-enable normal policy enforcement
                self.agent.set_user_preferences({})
                self.notify("✓ Safety checks enabled", severity="success")