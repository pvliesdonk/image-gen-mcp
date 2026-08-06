# Installation

## Prerequisites

- Python 3.11 or later
- `pip` or [`uv`](https://docs.astral.sh/uv/) package manager

## From PyPI

```
# Core + MCP server
pip install image-generation-mcp[mcp]

# With OpenAI provider
pip install image-generation-mcp[all]
```

```
# Core + MCP server
uv pip install image-generation-mcp[mcp]

# With OpenAI provider
uv pip install image-generation-mcp[all]
```

### Available extras

| Extra    | Includes                                      | When to use                                 |
| -------- | --------------------------------------------- | ------------------------------------------- |
| `mcp`    | `fastmcp[tasks]>=3.0,<4`                      | Minimal MCP server (SD WebUI + placeholder) |
| `openai` | `openai>=1.0`                                 | OpenAI provider only (no MCP server)        |
| `all`    | `fastmcp[tasks]` + `openai`                   | Full installation with all providers        |
| `dev`    | All above + pytest, ruff, mypy, pip-audit     | Development and testing                     |
| `docs`   | mkdocs-material, mkdocstrings, mkdocs-llmstxt | Documentation site build                    |

## From source

```
git clone https://github.com/pvliesdonk/image-generation-mcp.git
cd image-generation-mcp
uv sync --extra all --extra dev
```

## Docker

```
docker pull ghcr.io/pvliesdonk/image-generation-mcp:latest
```

See [Docker deployment](https://pvliesdonk.github.io/image-generation-mcp/1.12/deployment/docker/index.md) for Docker Compose setup.

## Verify installation

```
# Check the CLI is available
image-generation-mcp --help

# Start with placeholder provider (no API keys needed)
IMAGE_GENERATION_MCP_READ_ONLY=false image-generation-mcp serve
```

The server starts in stdio mode by default. Press Ctrl+C to stop.
