# Docker Deployment

## Quick start

```bash
docker compose up -d
```

The server listens on port 8000 with HTTP transport by default.

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `IMAGE_GENERATION_MCP_BEARER_TOKEN` | n/a | Enable bearer token auth |
| `FASTMCP_LOG_LEVEL` | `INFO` | Log level (`DEBUG` / `INFO` / `WARNING` / `ERROR`) |
| `IMAGE_GENERATION_MCP_INSTRUCTIONS` | (computed at startup) | System instructions for LLM context |
| `IMAGE_GENERATION_MCP_DEBUG_PORT` | N/A | Remote-debugger TCP port (see [Remote debugging](#remote-debugging); requires `--build-arg DEBUG=true` image) |
| `IMAGE_GENERATION_MCP_DEBUG_WAIT` | `false` | Block startup until IDE attaches (see [Remote debugging](#remote-debugging)) |

See [Configuration](../configuration.md) for the full environment variable reference.

For OIDC auth variables, see [Authentication](../guides/authentication.md).

## Volumes

| Path | Purpose |
|------|---------|
| `/data/service` | Image scratch directory (bind-mount or named volume) |
| `/data/state` | State files: FastMCP OIDC state + SSE event store (`/data/state/events`) |

## UID/GID

Set `PUID` and `PGID` in your `.env` file to match the owner of bind-mounted
directories (default 1000/1000).

## Remote debugging

Production images ship without `debugpy` to keep the image lean. To attach a remote Python debugger from VS Code or PyCharm:

1. **Build with the debug extra:**

    ```bash
    docker build --build-arg DEBUG=true -t image-generation-mcp:debug .
    ```

    This installs the `[debug]` optional-dependency group (which pulls `debugpy` transitively from `fastmcp-pvl-core`). Default builds (`DEBUG=false`) skip it.

2. **Run with the debug env vars set and the port mapped:**

    ```bash
    docker run --rm \
      -e IMAGE_GENERATION_MCP_DEBUG_PORT=5678 \
      -e IMAGE_GENERATION_MCP_DEBUG_WAIT=true \
      -p 127.0.0.1:5678:5678 \
      -p 8000:8000 \
      image-generation-mcp:debug
    ```

    | Env var | Effect |
    |---------|--------|
    | `IMAGE_GENERATION_MCP_DEBUG_PORT` | TCP port the debugger listens on (any value parsing to ``0`` disables; non-numeric or out-of-range values log a WARNING and the listener stays off) |
    | `IMAGE_GENERATION_MCP_DEBUG_WAIT` | When truthy (``1``/``true``/``yes``/``on``), block startup until the IDE attaches. Default is non-blocking. |

3. **Attach from VS Code**, adding a launch config:

    ```json
    {
      "name": "Attach to image-generation-mcp",
      "type": "debugpy",
      "request": "attach",
      "connect": { "host": "localhost", "port": 5678 }
    }
    ```

    PyCharm uses *Run → Edit Configurations → Python Debug Server* with the same host/port.

!!! danger "Never publish the debug port on a public network"
    The debug listener binds `0.0.0.0` inside the container so the IDE can reach it from the host, but **debugpy's DAP protocol is unauthenticated**: any peer that can reach the port has arbitrary code execution as the server process. Always bind the port mapping to localhost (`-p 127.0.0.1:5678:5678`) or tunnel via `kubectl port-forward` / SSH. Production images should be built with default `DEBUG=false`.

When the helper is invoked but `debugpy` isn't installed (say, someone sets `DEBUG_PORT` on a non-debug image), it logs a WARNING and continues; this is the safe failure mode.


<!-- DOMAIN-DOCKER-EXTRA-START -->
<!-- Project-specific notes for Docker deployment go here; kept across copier
     update. (E.g. "the /data/uploads volume must be writable by UID Y",
     "container needs cap_add: SYS_PTRACE for debugging tools".) -->
<!-- DOMAIN-DOCKER-EXTRA-END -->
