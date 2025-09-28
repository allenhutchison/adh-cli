---
name: shell
description: Shell command execution and file system operations
version: 1.0.0
---

# Shell Tools

This tool provides safe shell command execution and file system operations.

## Available Functions

### execute_command
Execute shell commands and capture their output.

**Parameters:**
- `command` (str): The shell command to execute
- `working_directory` (str, optional): Directory to run the command in
- `timeout` (int, optional): Maximum seconds to wait (default: 30)

**Returns:**
- `success` (bool): Whether the command succeeded
- `stdout` (str): Standard output
- `stderr` (str): Standard error output
- `return_code` (int): Exit code
- `error` (str): Error message if failed

**Examples:**
```python
# List files
execute_command("ls -la")

# Check git status
execute_command("git status")

# Run Python script
execute_command("python script.py", timeout=60)
```

### list_directory
List directory contents with detailed information.

**Parameters:**
- `path` (str): Directory path (default: current directory)
- `show_hidden` (bool): Show hidden files (default: False)
- `detailed` (bool): Show file details (default: True)

**Returns:**
- `success` (bool): Whether operation succeeded
- `path` (str): Directory path that was listed
- `files` (list): List of files with details
- `directories` (list): List of subdirectories
- `error` (str): Error message if failed

**Examples:**
```python
# List current directory
list_directory()

# List with hidden files
list_directory(".", show_hidden=True)

# List specific directory
list_directory("/home/user/documents")
```

### read_file
Read text file contents safely.

**Parameters:**
- `file_path` (str): Path to the file
- `max_lines` (int): Maximum lines to read (default: 1000)

**Returns:**
- `success` (bool): Whether file was read successfully
- `content` (str): File contents
- `line_count` (int): Number of lines read
- `truncated` (bool): Whether output was truncated
- `error` (str): Error message if failed

**Examples:**
```python
# Read configuration file
read_file("config.yaml")

# Read first 100 lines of log
read_file("app.log", max_lines=100)
```

## Safety Features

- Commands are checked for dangerous patterns
- File operations have size limits (10MB max)
- Commands have configurable timeouts
- All operations return structured error information

## Usage Guidelines

1. Always check the `success` field before using results
2. Use appropriate timeouts for long-running commands
3. Be mindful of file sizes when reading
4. Use `list_directory` instead of `ls` for structured output
5. Prefer `read_file` over `cat` for file reading