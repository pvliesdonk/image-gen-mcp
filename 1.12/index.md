# image-generation-mcp

Multi-provider image generation [MCP](https://modelcontextprotocol.io) server built on [FastMCP](https://gofastmcp.com). Generate images from Claude Desktop, Claude Code, or any MCP client using OpenAI, Stable Diffusion (SD WebUI), or a zero-cost placeholder provider.

## Features

- **Multi-provider**: OpenAI (gpt-image-2, dall-e-3), Google Gemini, SD WebUI (Stable Diffusion WebUI), and placeholder
- **Auto-selection**: keyword-based routing picks the best provider for your prompt
- **Image assets**: content-addressed registry with thumbnail previews and resource URI-based transforms
- **Background tasks**: hybrid foreground (progress streaming) and background (polling) execution
- **MCP native**: tools, resources, and prompts following the MCP specification
- **Authentication**: bearer token, OIDC, and multi-auth support
- **Docker ready**: multi-arch image with privilege dropping

## Architecture

```
MCP Client (Claude Desktop / Claude Code)
    |
    v
+---------------------------------------------+
|  MCP Layer                                   |
|  Tools:     generate_image, list_providers   |
|  Resources: info://providers                 |
|             image://{id}/view{?transforms}   |
|             image://{id}/metadata            |
|             image://list                     |
|  Prompts:   select_provider, sd_prompt_guide |
+------------------+---+----------------------+
                   |   |
  Depends(service) |   | processing.py
                   v   v
+---------------------------------------------+
|  ImageService                                |
|  - Provider registry (name -> instance)      |
|  - Image registry (content-addressed IDs)    |
|  - generate() -> dispatches to provider      |
|  - register_image() -> saves + indexes       |
+------+----------+----------+----------------+
       |          |          |
       v          v          v
  +---------+ +----------+ +--------------+
  | OpenAI  | | SD WebUI | | Placeholder  |
  |Provider | | Provider | | Provider     |
  +---------+ +----------+ +--------------+
```

## Quick start

```
# Install
pip install image-generation-mcp[all]

# Run with placeholder (no API keys needed)
IMAGE_GENERATION_MCP_READ_ONLY=false image-generation-mcp serve

# Run with OpenAI
IMAGE_GENERATION_MCP_READ_ONLY=false \
IMAGE_GENERATION_MCP_OPENAI_API_KEY=sk-... \
image-generation-mcp serve
```

## Navigation

- **Getting Started**

  ______________________________________________________________________

  Install, configure, and connect to Claude Desktop or Claude Code.

  [:octicons-arrow-right-24: Installation](https://pvliesdonk.github.io/image-generation-mcp/1.12/getting-started/installation/index.md)

- **Providers**

  ______________________________________________________________________

  Compare providers, set up OpenAI or SD WebUI, use the placeholder.

  [:octicons-arrow-right-24: Provider overview](https://pvliesdonk.github.io/image-generation-mcp/1.12/providers/index.md)

- **Configuration**

  ______________________________________________________________________

  All environment variables with types, defaults, and descriptions.

  [:octicons-arrow-right-24: Configuration reference](https://pvliesdonk.github.io/image-generation-mcp/1.12/configuration/index.md)

- **MCP Interface**

  ______________________________________________________________________

  Tools, resources, and prompts exposed to MCP clients.

  [:octicons-arrow-right-24: Tools](https://pvliesdonk.github.io/image-generation-mcp/1.12/tools/index.md) | [:octicons-arrow-right-24: Resources](https://pvliesdonk.github.io/image-generation-mcp/1.12/resources/index.md) | [:octicons-arrow-right-24: Prompts](https://pvliesdonk.github.io/image-generation-mcp/1.12/prompts/index.md)
