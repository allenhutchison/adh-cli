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
from .ui.theme import get_themes


def get_adh_commands_provider():
    """Lazy load ADH command provider.

    Returns:
        ADHCommandProvider class
    """
    from .commands import ADHCommandProvider
    return ADHCommandProvider


def get_settings_commands_provider():
    """Lazy load settings command provider.

    Returns:
        SettingsCommandProvider class
    """
    from .commands import SettingsCommandProvider
    return SettingsCommandProvider


class ADHApp(App):
    """Main ADH CLI TUI Application with Policy-Aware Agent."""

    # Load global stylesheet
    CSS_PATH = Path(__file__).parent / "ui" / "styles.tcss"

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

    # Extend Textual's default commands with ADH CLI-specific providers
    # This preserves defaults (quit, toggle dark, show/hide keys, etc.)
    # while adding our custom commands (settings, policies, safety, clear)
    COMMANDS = App.COMMANDS | {get_adh_commands_provider, get_settings_commands_provider}

    TITLE = "ADH CLI - Policy-Aware Agent"
    SUB_TITLE = "Safe AI-assisted development"

    def __init__(self):
        """Initialize the application."""
        super().__init__()

        # Register custom themes
        for theme_name, theme in get_themes().items():
            self.register_theme(theme)

        # Set default theme to adh-dark
        self.theme = "adh-dark"

        self.agent = None
        self.api_key = None
        self.safety_enabled = True

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
        """Register the default set of tools from specs registry.

        All tools are registered; access control is handled by the policy engine.
        """
        if not self.agent:
            return

        # Load tool specs and register them with the agent
        from .tools.specs import register_default_specs
        from .tools.base import registry, ToolSpec
        from .core.agent_delegator import AgentDelegator
        from .tools.agent_tools import create_delegate_tool

        register_default_specs()

        # Register agent delegation tool dynamically (needs runtime config)
        delegator = AgentDelegator(
            api_key=self.api_key,
            policy_dir=self.policy_dir,
            audit_log_path=ConfigPaths.get_audit_log(),
            parent_agent=self.agent,  # Pass parent agent for callbacks
        )
        delegate_tool = create_delegate_tool(delegator)

        # Add to registry if not already present
        if registry.get("delegate_to_agent") is None:
            registry.register(
                ToolSpec(
                    name="delegate_to_agent",
                    description="Delegate a task to a specialist agent (planner, code_reviewer, etc.)",
                    parameters={
                        "agent": {"type": "string", "description": "Name of specialist agent"},
                        "task": {"type": "string", "description": "Task description for the agent"},
                        "context": {"type": "object", "description": "Additional context", "nullable": True},
                    },
                    handler=delegate_tool,
                    tags=["agent", "delegation"],
                    effects=["delegates_task"],
                )
            )

        # Register all tools - the policy engine controls access and confirmation requirements
        for spec in registry.all():
            self.agent.register_tool(
                name=spec.name,
                description=spec.description,
                parameters=spec.parameters,
                handler=spec.handler,
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
        self.theme = "adh-dark" if self.theme == "adh-light" else "adh-light"

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
