"""Tests for the tool registry."""

import pytest
from pathlib import Path
import tempfile
from adh_cli.tools.tool_registry import Tool, ToolRegistry
from adh_cli.services.prompt_service import PromptTemplate


class TestTool:
    """Test Tool class."""

    def test_init(self):
        """Test tool initialization."""
        tool = Tool(
            name="test_tool",
            path=Path("/test/path"),
            functions={"func1": lambda: None},
            prompt=None,
            metadata={"version": "1.0"}
        )

        assert tool.name == "test_tool"
        assert tool.path == Path("/test/path")
        assert "func1" in tool.functions
        assert tool.prompt is None
        assert tool.metadata["version"] == "1.0"


class TestToolRegistry:
    """Test ToolRegistry class."""

    def test_init_default(self):
        """Test default initialization."""
        registry = ToolRegistry()
        assert registry.tools_dir.name == "tools"

    def test_init_custom_dir(self, tmp_path):
        """Test initialization with custom directory."""
        registry = ToolRegistry(tools_dir=tmp_path)
        assert registry.tools_dir == tmp_path

    def test_discover_tools(self, tmp_path):
        """Test tool discovery."""
        # Create a tool directory structure
        tool_dir = tmp_path / "test_tool"
        tool_dir.mkdir()

        # Create tool.py
        tool_file = tool_dir / "tool.py"
        tool_file.write_text("""
def test_function(arg1, arg2):
    '''Test function docstring.'''
    return arg1 + arg2

def another_function():
    '''Another function.'''
    pass

# This should not be discovered
_private_function = lambda: None
""")

        # Create prompt.md
        prompt_file = tool_dir / "prompt.md"
        prompt_file.write_text("""---
name: test_tool
version: 1.0
---

# Test Tool

This is a test tool.""")

        registry = ToolRegistry(tools_dir=tmp_path)

        # Check tool was discovered
        assert "test_tool" in registry.list_tools()

        tool = registry.get_tool("test_tool")
        assert tool is not None
        assert tool.name == "test_tool"
        assert "test_function" in tool.functions
        assert "another_function" in tool.functions
        assert "_private_function" not in tool.functions

        # Check prompt was loaded
        assert tool.prompt is not None
        assert tool.prompt.metadata["version"] == 1.0

    def test_register_tool(self):
        """Test manual tool registration."""
        registry = ToolRegistry()

        tool = Tool(
            name="manual",
            path=Path("/manual"),
            functions={"func": lambda: None},
            prompt=None,
            metadata={}
        )

        registry.register_tool("manual", tool)
        assert registry.get_tool("manual") == tool

    def test_get_tool_not_found(self):
        """Test getting non-existent tool."""
        registry = ToolRegistry()
        assert registry.get_tool("nonexistent") is None

    def test_get_functions(self, tmp_path):
        """Test getting functions from multiple tools."""
        # Create two tools
        for tool_name in ["tool1", "tool2"]:
            tool_dir = tmp_path / tool_name
            tool_dir.mkdir()
            tool_file = tool_dir / "tool.py"
            tool_file.write_text(f"""
def {tool_name}_func():
    pass
""")

        registry = ToolRegistry(tools_dir=tmp_path)

        functions = registry.get_functions(["tool1", "tool2"])
        func_names = [f.__name__ for f in functions]

        assert "tool1_func" in func_names
        assert "tool2_func" in func_names

    def test_get_functions_missing_tool(self, tmp_path):
        """Test getting functions with missing tool."""
        # Create one tool
        tool_dir = tmp_path / "existing"
        tool_dir.mkdir()
        tool_file = tool_dir / "tool.py"
        tool_file.write_text("def existing_func(): pass")

        registry = ToolRegistry(tools_dir=tmp_path)

        # Request functions from existing and non-existing tools
        functions = registry.get_functions(["existing", "nonexistent"])
        func_names = [f.__name__ for f in functions]

        # Should only get functions from existing tool
        assert "existing_func" in func_names
        assert len(func_names) == 1

    def test_get_tool_descriptions_with_prompt(self, tmp_path):
        """Test getting tool descriptions from prompt files."""
        tool_dir = tmp_path / "described"
        tool_dir.mkdir()
        tool_file = tool_dir / "tool.py"
        tool_file.write_text("def func(): pass")
        prompt_file = tool_dir / "prompt.md"
        prompt_file.write_text("""---
name: described
---
This is the tool description.""")

        registry = ToolRegistry(tools_dir=tmp_path)

        descriptions = registry.get_tool_descriptions(["described"])
        assert "## described" in descriptions
        assert "This is the tool description." in descriptions

    def test_get_tool_descriptions_from_docstrings(self, tmp_path):
        """Test getting tool descriptions from function docstrings."""
        tool_dir = tmp_path / "docstring_tool"
        tool_dir.mkdir()
        tool_file = tool_dir / "tool.py"
        tool_file.write_text("""
def func1():
    '''Function 1 description.'''
    pass

def func2():
    '''Function 2 description.'''
    pass
""")

        registry = ToolRegistry(tools_dir=tmp_path)

        descriptions = registry.get_tool_descriptions(["docstring_tool"])
        assert "## docstring_tool" in descriptions
        assert "### func1" in descriptions
        assert "Function 1 description." in descriptions
        assert "### func2" in descriptions
        assert "Function 2 description." in descriptions

    @pytest.mark.skip(reason="Module reloading in tests is complex due to Python's import cache")
    def test_reload_tool(self, tmp_path):
        """Test reloading a tool."""
        tool_dir = tmp_path / "reload_test"
        tool_dir.mkdir()
        tool_file = tool_dir / "tool.py"

        # Initial tool content
        tool_file.write_text("def original(): pass")

        registry = ToolRegistry(tools_dir=tmp_path)
        tool = registry.get_tool("reload_test")
        assert "original" in tool.functions

        # Modify tool content
        tool_file.write_text("def modified(): pass")

        # Reload the tool
        registry.reload_tool("reload_test")
        tool = registry.get_tool("reload_test")
        assert "modified" in tool.functions
        assert "original" not in tool.functions

    def test_skip_pycache(self, tmp_path):
        """Test that __pycache__ directories are skipped."""
        # Create __pycache__ directory
        pycache_dir = tmp_path / "__pycache__"
        pycache_dir.mkdir()
        tool_file = pycache_dir / "tool.py"
        tool_file.write_text("def should_not_load(): pass")

        registry = ToolRegistry(tools_dir=tmp_path)
        assert "__pycache__" not in registry.list_tools()

    def test_skip_private_dirs(self, tmp_path):
        """Test that private directories (starting with _) are skipped."""
        # Create private directory
        private_dir = tmp_path / "_private"
        private_dir.mkdir()
        tool_file = private_dir / "tool.py"
        tool_file.write_text("def should_not_load(): pass")

        registry = ToolRegistry(tools_dir=tmp_path)
        assert "_private" not in registry.list_tools()