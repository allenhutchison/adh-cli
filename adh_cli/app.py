"""Main application module with policy-aware agent for ADH CLI."""

import os
from pathlib import Path
from dotenv import load_dotenv
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Header

from .screens.chat_screen import ChatScreen
from .core.policy_aware_llm_agent import PolicyAwareLlmAgent
from .core.config_paths import ConfigPaths
from .config.models import ModelRegistry
from .config.settings_manager import get_theme_setting, load_config_data, set_settings


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

    # Screens are now installed rather than registered in SCREENS dict

    # Extend Textual's default commands with ADH CLI-specific providers
    # This preserves defaults (quit, toggle dark, show/hide keys, etc.)
    # while adding our custom commands (settings, policies, safety, clear)
    COMMANDS = App.COMMANDS | {
        get_adh_commands_provider,
        get_settings_commands_provider,
    }

    TITLE = "ADH CLI - Policy-Aware Agent"
    SUB_TITLE = "Safe AI-assisted development"

    def __init__(self):
        """Initialize the application."""
        super().__init__()

        # Load persisted theme setting on startup <--- MODIFIED
        self.theme = get_theme_setting()

        self.agent = None
        self.api_key = None
        self.safety_enabled = True

        # Set policy directory using ConfigPaths
        self.policy_dir = ConfigPaths.get_policies_dir()

        # Check for API key in environment
        self._load_api_key()

    @property
    def theme(self) -> str:
        """Get current theme."""
        return super().theme

    @theme.setter
    def theme(self, value: str) -> None:
        """Set theme and persist to settings.

        This property override ensures that theme changes from any source
        (command palette, settings modal, keyboard shortcuts) are automatically
        saved to the settings file.

        Raises:
            IOError, OSError: If saving the theme preference fails
        """
        # Set the theme on the parent class first
        # Call the Reactive descriptor's __set__ method directly
        App.theme.__set__(self, value)

        # Save theme preference (let exceptions propagate for caller to handle)
        set_settings({"theme": value})

    def _load_api_key(self):
        """Load API key from environment."""
        # Load .env file if it exists
        load_dotenv()

        self.api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get(
            "GEMINI_API_KEY"
        )

    def _load_config(self):
        """Load configuration from config.json.

        Returns:
            Dict with configuration values
        """
        # Use the centralized settings manager to load config data <--- MODIFIED
        return load_config_data()

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header()

    def on_mount(self) -> None:
        """Initialize the app after mounting."""
        # Initialize the policy-aware agent
        self._initialize_agent()

        # Push chat screen (it has its own Footer for displaying bindings)
        self.push_screen(ChatScreen())

    def _initialize_agent(self):
        """Initialize the policy-aware ADK agent."""
        try:
            # Load configuration
            config = self._load_config()

            # Get orchestrator agent name from config (default to "orchestrator")
            agent_name = config.get("orchestrator_agent", "orchestrator")

            # Use ADK-based agent with automatic tool orchestration
            # Note: Execution manager callbacks will be registered by ChatScreen on mount
            configured_model = config.get("model")
            if configured_model and not ModelRegistry.get_by_id(configured_model):
                self.notify(
                    f"Unknown model '{configured_model}' in configuration. Using default instead.",
                    severity="warning",
                )
                configured_model = None

            self.agent = PolicyAwareLlmAgent(
                model_name=configured_model,
                api_key=self.api_key,
                policy_dir=self.policy_dir,
                confirmation_handler=self.handle_confirmation,
                notification_handler=self.show_notification,
                audit_log_path=ConfigPaths.get_audit_log(),
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
                        "agent": {
                            "type": "string",
                            "description": "Name of specialist agent",
                        },
                        "task": {
                            "type": "string",
                            "description": "Task description for the agent",
                        },
                        "context": {
                            "type": "object",
                            "description": "Additional context",
                            "nullable": True,
                        },
                    },
                    handler=delegate_tool,
                    tags=["agent", "delegation"],
                    effects=["delegates_task"],
                )
            )

        # Register all tools - the policy engine controls access and confirmation requirements
        for spec in registry.all():
            # Main orchestrator excludes google_search/google_url_context
            # (these are registered by AgentDelegator for specialist agents only)
            if spec.name in {"google_search", "google_url_context"}:
                continue

            if spec.adk_tool_factory is not None:
                self.agent.register_native_tool(
                    name=spec.name,
                    description=spec.description,
                    parameters=spec.parameters,
                    factory=spec.adk_tool_factory,
                )
            elif spec.handler is not None:
                self.agent.register_tool(
                    name=spec.name,
                    description=spec.description,
                    parameters=spec.parameters,
                    handler=spec.handler,
                )

    async def handle_confirmation(
        self, tool_call=None, decision=None, message=None, **kwargs
    ):
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
        """Toggle dark mode (theme property setter handles persistence)."""
        new_theme = "textual-dark" if self.theme == "textual-light" else "textual-light"
        # Setting theme property automatically saves via property setter
        self.theme = new_theme

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
                self.agent.set_user_preferences(
                    {
                        "auto_approve": ["*"],
                    }
                )
                self.notify("⚠️ Safety checks disabled", severity="warning")
            else:
                # Re-enable normal policy enforcement
                self.agent.set_user_preferences({})
                self.notify("✓ Safety checks enabled", severity="success")
