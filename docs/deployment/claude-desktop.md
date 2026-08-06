# Claude Desktop

Image Generation MCP integrates with [Claude Desktop](https://claude.ai/download) via the stdio transport.

## Setup

### 1. Install

From PyPI:

```bash
pip install image-generation-mcp
```

Or with uv (installs `image-generation-mcp` as a global command on your PATH):

```bash
uv tool install image-generation-mcp
```

Or download the `.mcpb` bundle from the [GitHub Releases](https://github.com/pvliesdonk/image-generation-mcp/releases) page and double-click to install; Claude Desktop prompts for required env vars via a GUI wizard, no manual JSON editing needed.

### 2. Configure Claude Desktop

If you installed via `.mcpb`, skip this step. Claude Desktop was configured automatically by the wizard.

Otherwise, add the server to your Claude Desktop configuration file. The path varies by operating system:

- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
- **Linux:** `~/.config/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "image-generation-mcp": {
      "command": "image-generation-mcp",
      "args": ["serve"],
      "env": {}
    }
  }
}
```

### 3. Restart Claude Desktop

Restart the application to pick up the new configuration. If the server connects successfully, `Image Generation MCP` tools appear in Claude's tool list. If not, see [Troubleshooting](#troubleshooting) below.

## Configuration examples

<!-- DOMAIN-CLAUDE-DESKTOP-START -->
<!-- Add domain-specific Claude Desktop configuration examples here.
     Kept across copier update. -->
<!-- DOMAIN-CLAUDE-DESKTOP-END -->

## Troubleshooting

### Server not appearing in Claude Desktop

1. Check the config file path is correct for your OS
2. Ensure the JSON is valid (no trailing commas)
3. Restart Claude Desktop completely (quit and reopen)
4. Check Claude Desktop logs for error messages

### "Command not found"

Ensure `image-generation-mcp` is on your PATH. If installed in a virtualenv, use the full path to the binary. Replace only the `"command"` value in your existing config and keep `"args"` and `"env"` as-is.

macOS/Linux:

```json
{
  "mcpServers": {
    "image-generation-mcp": {
      "command": "/Users/me/.venvs/mcp/bin/image-generation-mcp",
      "args": ["serve"],
      "env": {}
    }
  }
}
```

Windows (`Scripts\` not `bin\`, `.exe` suffix):

```json
{
  "mcpServers": {
    "image-generation-mcp": {
      "command": "C:\\Users\\me\\.venvs\\mcp\\Scripts\\image-generation-mcp.exe",
      "args": ["serve"],
      "env": {}
    }
  }
}
```
