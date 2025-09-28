"""Tests for the prompt service."""

import pytest
from pathlib import Path
import tempfile
from adh_cli.services.prompt_service import PromptTemplate, PromptService


class TestPromptTemplate:
    """Test PromptTemplate class."""

    def test_from_string(self):
        """Test creating template from string."""
        content = "Hello {{name}}, welcome to {{place}}!"
        template = PromptTemplate.from_string(content)

        assert template.content == content
        assert template.variables == {"name", "place"}
        assert template.metadata == {}

    def test_from_string_with_metadata(self):
        """Test creating template with metadata."""
        content = "Hello {{name}}!"
        metadata = {"version": "1.0", "author": "test"}
        template = PromptTemplate.from_string(content, metadata)

        assert template.metadata == metadata

    def test_extract_variables(self):
        """Test variable extraction."""
        content = "{{var1}} and {{var2}} but not {var3} or {{var1}} again"
        variables = PromptTemplate._extract_variables(content)

        assert variables == {"var1", "var2"}

    def test_render_simple(self):
        """Test simple template rendering."""
        template = PromptTemplate.from_string("Hello {{name}}!")
        result = template.render({"name": "World"})

        assert result == "Hello World!"

    def test_render_multiple_variables(self):
        """Test rendering with multiple variables."""
        template = PromptTemplate.from_string("{{greeting}} {{name}}, welcome to {{place}}!")
        result = template.render({
            "greeting": "Hello",
            "name": "Alice",
            "place": "Wonderland"
        })

        assert result == "Hello Alice, welcome to Wonderland!"

    def test_render_missing_variable(self):
        """Test error when variable is missing."""
        template = PromptTemplate.from_string("Hello {{name}}!")

        with pytest.raises(ValueError, match="Missing required variables: {'name'}"):
            template.render({})

    def test_render_extra_variables(self):
        """Test that extra variables are ignored."""
        template = PromptTemplate.from_string("Hello {{name}}!")
        result = template.render({"name": "World", "extra": "ignored"})

        assert result == "Hello World!"

    def test_validate(self):
        """Test template validation."""
        template = PromptTemplate.from_string("Hello {{name}} from {{place}}!")

        assert template.validate({"name": "Alice", "place": "Wonderland"})
        assert template.validate({"name": "Bob", "place": "Earth", "extra": "ok"})
        assert not template.validate({"name": "Charlie"})
        assert not template.validate({})

    def test_from_file_simple(self, tmp_path):
        """Test loading template from file."""
        file_path = tmp_path / "test.md"
        file_path.write_text("Hello {{name}}!")

        template = PromptTemplate.from_file(file_path)

        assert template.content == "Hello {{name}}!"
        assert template.variables == {"name"}

    def test_from_file_with_frontmatter(self, tmp_path):
        """Test loading template with YAML frontmatter."""
        file_path = tmp_path / "test.md"
        content = """---
name: greeting
version: 1.0
temperature: 0.7
---
Hello {{name}}!
Welcome to {{place}}."""
        file_path.write_text(content)

        template = PromptTemplate.from_file(file_path)

        assert template.content == "Hello {{name}}!\nWelcome to {{place}}."
        assert template.variables == {"name", "place"}
        assert template.metadata["name"] == "greeting"
        assert template.metadata["version"] == 1.0
        assert template.metadata["temperature"] == 0.7

    def test_from_file_not_found(self):
        """Test error when file doesn't exist."""
        with pytest.raises(FileNotFoundError):
            PromptTemplate.from_file(Path("/nonexistent/file.md"))

    def test_from_file_invalid_yaml(self, tmp_path):
        """Test error with invalid YAML frontmatter."""
        file_path = tmp_path / "test.md"
        content = """---
invalid: yaml: syntax:
---
Content"""
        file_path.write_text(content)

        with pytest.raises(ValueError, match="Invalid YAML frontmatter"):
            PromptTemplate.from_file(file_path)


class TestPromptService:
    """Test PromptService class."""

    def test_init_default(self):
        """Test default initialization."""
        service = PromptService()
        assert service.base_path == Path.cwd()
        assert len(service._cache) == 0

    def test_init_with_base_path(self, tmp_path):
        """Test initialization with base path."""
        service = PromptService(base_path=tmp_path)
        assert service.base_path == tmp_path

    def test_load_prompt(self, tmp_path):
        """Test loading a prompt."""
        service = PromptService(base_path=tmp_path)

        # Create a prompt file
        prompt_file = tmp_path / "greeting.md"
        prompt_file.write_text("Hello {{name}}!")

        # Load the prompt
        template = service.load_prompt("greeting")

        assert template.content == "Hello {{name}}!"
        assert template.variables == {"name"}

    def test_load_prompt_with_cache(self, tmp_path):
        """Test prompt caching."""
        service = PromptService(base_path=tmp_path)

        # Create a prompt file
        prompt_file = tmp_path / "test.md"
        prompt_file.write_text("Original content")

        # Load the prompt
        template1 = service.load_prompt("test")
        assert template1.content == "Original content"

        # Modify the file
        prompt_file.write_text("Modified content")

        # Load again with cache (should get original)
        template2 = service.load_prompt("test", use_cache=True)
        assert template2.content == "Original content"

        # Load without cache (should get modified)
        template3 = service.load_prompt("test", use_cache=False)
        assert template3.content == "Modified content"

    def test_load_prompt_different_paths(self, tmp_path):
        """Test loading prompts from different path patterns."""
        service = PromptService(base_path=tmp_path)

        # Test name.md pattern
        file1 = tmp_path / "prompt1.md"
        file1.write_text("Pattern 1")
        assert service.load_prompt("prompt1").content == "Pattern 1"

        # Test name.prompt.md pattern
        file2 = tmp_path / "prompt2.prompt.md"
        file2.write_text("Pattern 2")
        assert service.load_prompt("prompt2").content == "Pattern 2"

        # Test name/prompt.md pattern
        (tmp_path / "prompt3").mkdir()
        file3 = tmp_path / "prompt3" / "prompt.md"
        file3.write_text("Pattern 3")
        assert service.load_prompt("prompt3").content == "Pattern 3"

    def test_load_prompt_not_found(self, tmp_path):
        """Test error when prompt not found."""
        service = PromptService(base_path=tmp_path)

        with pytest.raises(FileNotFoundError, match="Prompt not found: nonexistent"):
            service.load_prompt("nonexistent")

    def test_clear_cache(self, tmp_path):
        """Test clearing the cache."""
        service = PromptService(base_path=tmp_path)

        # Create and load a prompt
        prompt_file = tmp_path / "test.md"
        prompt_file.write_text("Cached content")
        service.load_prompt("test")

        assert len(service._cache) == 1

        # Clear cache
        service.clear_cache()
        assert len(service._cache) == 0

    def test_render_prompt(self, tmp_path):
        """Test loading and rendering a prompt."""
        service = PromptService(base_path=tmp_path)

        # Create a prompt file
        prompt_file = tmp_path / "greeting.md"
        prompt_file.write_text("Hello {{name}}, welcome to {{place}}!")

        # Render the prompt
        result = service.render_prompt("greeting", {
            "name": "Alice",
            "place": "Wonderland"
        })

        assert result == "Hello Alice, welcome to Wonderland!"