# Claude Code

Connect image-generation-mcp to Claude Code as an MCP server.

## Configuration

Add a `.mcp.json` file to your project root:

### Placeholder only (no API keys)

```
{
  "mcpServers": {
    "image-gen": {
      "command": "image-generation-mcp",
      "args": ["serve"],
      "env": {
        "IMAGE_GENERATION_MCP_READ_ONLY": "false"
      }
    }
  }
}
```

### With Gemini

```
{
  "mcpServers": {
    "image-gen": {
      "command": "image-generation-mcp",
      "args": ["serve"],
      "env": {
        "IMAGE_GENERATION_MCP_READ_ONLY": "false",
        "IMAGE_GENERATION_MCP_GOOGLE_API_KEY": "AIza..."
      }
    }
  }
}
```

### With OpenAI

```
{
  "mcpServers": {
    "image-gen": {
      "command": "image-generation-mcp",
      "args": ["serve"],
      "env": {
        "IMAGE_GENERATION_MCP_READ_ONLY": "false",
        "IMAGE_GENERATION_MCP_OPENAI_API_KEY": "sk-..."
      }
    }
  }
}
```

### With all providers

```
{
  "mcpServers": {
    "image-gen": {
      "command": "image-generation-mcp",
      "args": ["serve"],
      "env": {
        "IMAGE_GENERATION_MCP_READ_ONLY": "false",
        "IMAGE_GENERATION_MCP_GOOGLE_API_KEY": "AIza...",
        "IMAGE_GENERATION_MCP_OPENAI_API_KEY": "sk-...",
        "IMAGE_GENERATION_MCP_SD_WEBUI_HOST": "http://localhost:7860"
      }
    }
  }
}
```

## Verify

After adding the configuration, restart Claude Code (or run `/mcp` to reload MCP servers). Then:

1. Ask Claude: "List the available image generation providers"
1. Ask Claude: "Generate a test image using the placeholder provider"

## Tips

- Use `provider="auto"` (the default) to let the server pick the best provider based on your prompt
- The `select_provider` prompt gives Claude guidance on provider strengths
- The `sd_prompt_guide` prompt helps Claude write effective Stable Diffusion prompts
- Generated images are saved to `~/.image-generation-mcp/images/` by default (configurable via `IMAGE_GENERATION_MCP_SCRATCH_DIR`)
