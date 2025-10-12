"""Tests for tool specifications and registration."""

import pytest

from adh_cli.tools import specs
from adh_cli.tools import google_tools
from adh_cli.tools.base import ToolSpec, registry


class DummyTool:
    """Simple placeholder tool for factory tests."""


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
            adk_tool_factory=lambda: DummyTool(),
        )

        tool = spec.create_adk_tool()

        assert isinstance(tool, DummyTool)


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
    def test_registers_google_tools(self, registry_snapshot):
        specs.register_default_specs()

        search_spec = registry.get("google_search")
        assert search_spec is not None
        assert search_spec.handler is google_tools.google_search
        assert search_spec.adk_tool_factory is None

        url_spec = registry.get("google_url_context")
        assert url_spec is not None
        assert url_spec.handler is google_tools.google_url_context
        assert url_spec.adk_tool_factory is None

        # Registry remains idempotent
        specs.register_default_specs()
        assert registry.get("google_search") is search_spec
        assert registry.get("google_url_context") is url_spec
