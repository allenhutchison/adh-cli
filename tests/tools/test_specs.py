"""Tests for tool specifications and registration."""

import pytest

from adh_cli.tools.base import ToolSpec, registry
from adh_cli.tools import specs
from adh_cli.tools.google_tools import create_google_search_tool


class TestToolSpecValidation:
    """Validate ToolSpec handler/factory constraints."""

    async def dummy_handler(self):  # pragma: no cover - simple stub
        return None

    def test_requires_handler_or_factory(self):
        with pytest.raises(ValueError, match="exactly one"):
            ToolSpec(
                name="invalid",
                description="Invalid spec",
                parameters={},
            )

    def test_rejects_both_handler_and_factory(self):
        with pytest.raises(ValueError, match="exactly one"):
            ToolSpec(
                name="invalid",
                description="Invalid spec",
                parameters={},
                handler=self.dummy_handler,
                adk_tool_factory=lambda: None,
            )

    def test_factory_instantiation(self):
        spec = ToolSpec(
            name="native",
            description="Native factory",
            parameters={},
            adk_tool_factory=create_google_search_tool,
        )

        tool = spec.create_adk_tool()
        from google.adk.tools.google_search_tool import GoogleSearchTool

        assert isinstance(tool, GoogleSearchTool)


@pytest.fixture
def registry_snapshot():
    """Temporarily snapshot the registry contents."""

    original = registry._tools.copy()  # type: ignore[attr-defined]
    try:
        registry._tools.clear()  # type: ignore[attr-defined]
        yield
    finally:
        registry._tools.clear()  # type: ignore[attr-defined]
        registry._tools.update(original)  # type: ignore[attr-defined]


class TestRegisterDefaultSpecs:
    def test_registers_google_search(self, registry_snapshot):
        specs.register_default_specs()

        search_spec = registry.get("google_search")
        assert search_spec is not None
        assert search_spec.handler is None
        assert search_spec.adk_tool_factory is not None

        tool_instance = search_spec.create_adk_tool()
        from google.adk.tools.google_search_tool import GoogleSearchTool

        assert isinstance(tool_instance, GoogleSearchTool)

        # Registry remains idempotent
        specs.register_default_specs()
        assert registry.get("google_search") is search_spec
