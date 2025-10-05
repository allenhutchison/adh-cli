# Tools Reference

This document is generated from `ToolSpec` entries. Edit `adh_cli/tools/specs.py` to change metadata or add new tools.

## `create_directory`

Create a new directory

- Tags: filesystem, write
- Effects: writes_fs

Parameters:

| Name | Type | Default | Description |
|---|---|---|---|
| `directory` | `string` |  | Directory path to create |
| `parents` | `boolean` | true | Create parent dirs |


## `delete_file`

Delete a file (requires confirmation)

- Tags: filesystem, write, destructive
- Effects: writes_fs, deletes_fs

Parameters:

| Name | Type | Default | Description |
|---|---|---|---|
| `file_path` | `string` |  | Path to the file to delete |
| `confirm` | `boolean` |  | Must be true to delete |


## `execute_command`

Execute a shell command

- Tags: process, shell
- Effects: executes_process

Parameters:

| Name | Type | Default | Description |
|---|---|---|---|
| `command` | `string` |  | Command to execute |
| `cwd` | `string` | true | Working directory |
| `timeout` | `integer` | 30 | Timeout seconds |
| `shell` | `boolean` | true | Use shell execution |


## `fetch_url`

Fetch content from a URL (GET) with size/time limits

- Tags: network, http, fetch
- Effects: network_read

Parameters:

| Name | Type | Default | Description |
|---|---|---|---|
| `url` | `string` |  | HTTP/HTTPS URL to fetch |
| `timeout` | `integer` | 20 | Timeout seconds |
| `max_bytes` | `integer` | 500000 | Max bytes to read |
| `as_text` | `boolean` | true | Decode text instead of base64 |
| `encoding` | `string` | true | Text encoding override |
| `headers` | `object` | true | Optional request headers |


## `get_file_info`

Get information about a file or directory

- Tags: filesystem, read
- Effects: reads_fs

Parameters:

| Name | Type | Default | Description |
|---|---|---|---|
| `file_path` | `string` |  | Path to the file or directory |


## `google_search`

Search the public web using Google's search index via Gemini's built-in tool.

- Tags: network, search, web
- Effects: network_read, external_search

Parameters:

| Name | Type | Default | Description |
|---|---|---|---|
| `query` | `string` |  | Search query describing what to look up |


## `google_url_context`

Fetch and ground responses in the content of provided URLs via Gemini's built-in tool.

- Tags: network, web, context
- Effects: network_read, external_content

Parameters:

| Name | Type | Default | Description |
|---|---|---|---|
| `urls` | `array` |  | List of URLs to provide as context |


## `list_directory`

List contents of a directory

- Tags: filesystem, read
- Effects: reads_fs

Parameters:

| Name | Type | Default | Description |
|---|---|---|---|
| `directory` | `string` | . | Directory path |
| `show_hidden` | `boolean` | false | Include dotfiles |


## `read_file`

Read contents of a text file

- Tags: filesystem, read
- Effects: reads_fs

Parameters:

| Name | Type | Default | Description |
|---|---|---|---|
| `file_path` | `string` |  | Path to the file to read |
| `max_lines` | `integer` | true | Optional max lines to read |


## `write_file`

Write content to a file

- Tags: filesystem, write
- Effects: writes_fs

Parameters:

| Name | Type | Default | Description |
|---|---|---|---|
| `file_path` | `string` |  | Path to the file to write |
| `content` | `string` |  | Content to write |
| `create_dirs` | `boolean` | true | Create parent dirs if missing |

