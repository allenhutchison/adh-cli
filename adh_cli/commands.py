"""Command palette providers for ADH CLI.

This module provides custom command providers for the Textual command palette,
adding ADH CLI-specific actions while preserving Textual's default commands
(quit, toggle dark mode, show/hide keys, etc.).
"""

from textual.command import Provider, Hit, Hits


class ADHCommandProvider(Provider):
    """Command provider for ADH CLI-specific actions.

    Provides commands for:
    - Opening settings
    - Showing policies
    - Toggling safety checks
    - Clearing chat
    """

    async def discover(self) -> Hits:
        """Provide default commands when palette first opens (empty query).

        Yields:
            All ADH CLI commands for discoverability
        """
        # Show all commands by default for discoverability
        commands = [
            (
                "Settings",
                "Open application settings (API key, model, agent)",
                self._run_settings,
            ),
            (
                "Show Policies",
                "Display active policy rules and preferences",
                self._run_show_policies,
            ),
            (
                "Toggle Safety",
                "Enable/disable safety checks for tool execution",
                self._run_toggle_safety,
            ),
            ("Clear Chat", "Clear the chat history", self._run_clear_chat),
        ]

        for name, help_text, callback in commands:
            yield Hit(
                1,  # All commands have equal priority in discover mode
                name,
                callback,
                help=help_text,
            )

    def _run_settings(self) -> None:
        """Run the show_settings action."""
        self.app.action_show_settings()

    def _run_show_policies(self) -> None:
        """Run the show_policies action."""
        # This action is on the ChatScreen
        if hasattr(self.screen, "action_show_policies"):
            self.screen.action_show_policies()

    def _run_toggle_safety(self) -> None:
        """Run the toggle_safety action."""
        # This action is on the ChatScreen
        if hasattr(self.screen, "action_toggle_safety"):
            self.screen.action_toggle_safety()

    def _run_clear_chat(self) -> None:
        """Run the clear_chat action."""
        # This action is on the ChatScreen
        if hasattr(self.screen, "action_clear_chat"):
            self.screen.action_clear_chat()

    async def search(self, query: str) -> Hits:
        """Search for ADH CLI commands matching the query.

        Args:
            query: The search query from command palette

        Yields:
            Command hits matching the query, scored by relevance
        """
        matcher = self.matcher(query)

        # ADH CLI-specific commands
        commands = [
            (
                "Settings",
                "Open application settings (API key, model, agent)",
                self._run_settings,
            ),
            (
                "Show Policies",
                "Display active policy rules and preferences",
                self._run_show_policies,
            ),
            (
                "Toggle Safety",
                "Enable/disable safety checks for tool execution",
                self._run_toggle_safety,
            ),
            ("Clear Chat", "Clear the chat history", self._run_clear_chat),
        ]

        for name, help_text, callback in commands:
            # Score the command name against the query
            score = matcher.match(name)
            if score > 0:
                yield Hit(
                    score,
                    matcher.highlight(name),
                    callback,
                    help=help_text,
                )


class SettingsCommandProvider(Provider):
    """Command provider for granular settings actions.

    Provides specific settings commands that all open the settings modal,
    but with more searchable/discoverable names for specific tasks.
    """

    async def discover(self) -> Hits:
        """Provide settings commands when palette first opens.

        Yields:
            All settings-related commands for discoverability
        """
        commands = [
            ("Configure API Key", "Set or update Google API key for Gemini"),
            ("Select Model", "Choose Gemini model (Flash, Flash Lite, Pro)"),
            (
                "Change Orchestrator Agent",
                "Select which agent to use for orchestration",
            ),
            ("Adjust Temperature", "Modify AI generation temperature"),
            ("Configure Max Tokens", "Set maximum output token limit"),
        ]

        for name, help_text in commands:
            yield Hit(
                1,  # Equal priority in discover mode
                name,
                self._open_settings,
                help=help_text,
            )

    async def search(self, query: str) -> Hits:
        """Search for settings-related commands.

        Args:
            query: The search query from command palette

        Yields:
            Settings command hits matching the query
        """
        matcher = self.matcher(query)

        # Specific settings commands for better discoverability
        commands = [
            ("Configure API Key", "Set or update Google API key for Gemini"),
            ("Select Model", "Choose Gemini model (Flash, Flash Lite, Pro)"),
            (
                "Change Orchestrator Agent",
                "Select which agent to use for orchestration",
            ),
            ("Adjust Temperature", "Modify AI generation temperature"),
            ("Configure Max Tokens", "Set maximum output token limit"),
        ]

        for name, help_text in commands:
            score = matcher.match(name)
            if score > 0:
                yield Hit(
                    score,
                    matcher.highlight(name),
                    self._open_settings,
                    help=help_text,
                )

    def _open_settings(self) -> None:
        """Open the settings modal."""
        self.app.action_show_settings()
