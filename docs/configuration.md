# Configuration

All configuration is via environment variables prefixed with `IMAGE_GENERATION_MCP_`.

## Core

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `IMAGE_GENERATION_MCP_SCRATCH_DIR` | Path | `~/.image-generation-mcp/images/` | Directory for saved generated images. Created automatically on first use. |
| `IMAGE_GENERATION_MCP_READ_ONLY` | bool | `true` | When `true`, write-tagged tools (`generate_image`) are hidden from clients. Set to `false` to enable image generation. |
| `IMAGE_GENERATION_MCP_DEFAULT_PROVIDER` | str | `auto` | Default provider selection. Options: `auto` (keyword-based selection), `gemini`, `openai`, `sd_webui`, `placeholder`. |
| `IMAGE_GENERATION_MCP_STYLES_DIR` | Path | `~/.image-generation-mcp/styles/` | Directory for style preset files (`.md` with YAML frontmatter). Created automatically if it does not exist. See the [Style Library Guide](guides/styles.md). |

## Server identity

These two let an operator rename an instance or override its
instructions, with no configuration beyond the variable itself:

- `IMAGE_GENERATION_MCP_SERVER_NAME`: the server name reported to clients and
  by `get_server_info`. Defaults to `image-generation-mcp`.
- `IMAGE_GENERATION_MCP_INSTRUCTIONS`: replaces the default MCP instructions
  text. Unset, the scaffold builds the default (which advertises this
  override).

<!-- DOMAIN-CONFIG-VARS-START -->
## Providers

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `IMAGE_GENERATION_MCP_OPENAI_API_KEY` | str | (unset) | OpenAI API key. Enables the OpenAI provider (gpt-image-2, gpt-image-1.5, dall-e-3) when set. |
| `IMAGE_GENERATION_MCP_GOOGLE_API_KEY` | str | (unset) | Google API key. Enables the Gemini provider (gemini-3.1-flash-image and others) when set. Get a key at [Google AI Studio](https://aistudio.google.com/apikey). |
| `IMAGE_GENERATION_MCP_SD_WEBUI_HOST` | str | (unset) | SD WebUI base URL (such as `http://localhost:7860`). Enables the SD WebUI provider when set. Compatible with AUTOMATIC1111, Forge, reForge, and Forge-neo. Deprecated alias: `IMAGE_GENERATION_MCP_A1111_HOST`. |
| `IMAGE_GENERATION_MCP_SD_WEBUI_MODEL` | str | (unset) | SD WebUI checkpoint name. Used for model-aware preset detection (SD 1.5 vs SDXL vs Lightning) and checkpoint override. Deprecated alias: `IMAGE_GENERATION_MCP_A1111_MODEL`. |

## Authentication

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `IMAGE_GENERATION_MCP_AUTH_MODE` | str | auto | OIDC auth mode: `remote` (local JWT validation) or `oidc-proxy` (DCR emulation). Auto-detected from env vars when not set (see below). |
| `IMAGE_GENERATION_MCP_BEARER_TOKEN` | str | (unset) | Static bearer token for HTTP authentication. Enables bearer auth when set. |
| `IMAGE_GENERATION_MCP_BASE_URL` | str | (unset) | Public base URL of the server (such as `https://mcp.example.com`). Required for OIDC and for the capability-link transfer routes (`create_download_link` / `create_upload_link` and the `/transfer/{token}` endpoint). Include subpath prefix if applicable. |
| `IMAGE_GENERATION_MCP_OIDC_CONFIG_URL` | str | (unset) | OIDC discovery endpoint URL (such as `https://auth.example.com/.well-known/openid-configuration`). |
| `IMAGE_GENERATION_MCP_OIDC_CLIENT_ID` | str | (unset) | OIDC client ID registered with your identity provider. Required for `oidc-proxy` mode only. |
| `IMAGE_GENERATION_MCP_OIDC_CLIENT_SECRET` | str | (unset) | OIDC client secret. Required for `oidc-proxy` mode only. |
| `IMAGE_GENERATION_MCP_OIDC_JWT_SIGNING_KEY` | str | ephemeral | JWT signing key for session tokens. **Required on Linux/Docker for `oidc-proxy` mode**: the default ephemeral key invalidates all tokens on restart. Generate with `openssl rand -hex 32`. Not needed for `remote` mode. |
| `IMAGE_GENERATION_MCP_OIDC_AUDIENCE` | str | (unset) | Expected JWT audience claim. Leave unset if your provider does not set one. |
| `IMAGE_GENERATION_MCP_OIDC_REQUIRED_SCOPES` | str | (unset) | Comma-separated required OIDC scopes. For `oidc-proxy` mode, defaults to `openid`. |
| `IMAGE_GENERATION_MCP_OIDC_VERIFY_ACCESS_TOKEN` | bool | `false` | Set `true` to verify the upstream access token as JWT instead of the id token. Only applies to `oidc-proxy` mode. |

!!! note "Auth mode auto-detection"
    When `AUTH_MODE` is not set explicitly, the mode is auto-detected:

    - **`oidc-proxy`**: when all four OIDC variables (`BASE_URL`, `OIDC_CONFIG_URL`, `OIDC_CLIENT_ID`, `OIDC_CLIENT_SECRET`) are set. Backward compatible with existing deployments.
    - **`remote`**: when `BASE_URL` + `OIDC_CONFIG_URL` are set but `CLIENT_ID`/`CLIENT_SECRET` are not. Recommended for new deployments (avoids the [OIDCProxy session lifetime issue](guides/authentication.md#known-limitations-oidc-session-lifetime)).

    Set `AUTH_MODE` explicitly to override auto-detection (such as `AUTH_MODE=remote` even when client credentials are present).

!!! warning
    Authentication only works with HTTP transport (`--transport http` or `sse`). It has no effect with stdio transport.

## Cost Control

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `IMAGE_GENERATION_MCP_PAID_PROVIDERS` | str | `openai` | Comma-separated list of provider names that cost money. When the MCP client supports [elicitation](https://modelcontextprotocol.io/specification/2025-06-18/server/utilities/elicitation), `generate_image` asks for confirmation before using these providers. An empty value is treated as unset and falls back to the default (`openai`); to disable confirmation entirely, set a value that names no provider (such as `none`). Gemini `quality="hd"` uses thinking tokens which are billed; consider adding `gemini` if you use `hd` quality frequently. |

## Performance

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `IMAGE_GENERATION_MCP_TRANSFORM_CACHE_SIZE` | int | `64` | Maximum number of transformed image results (resize/crop/convert) to keep in memory. Repeated requests for the same transform parameters are served from cache. Set to `0` to disable caching. |

## Reference image input (`transform_image`)

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `IMAGE_GENERATION_MCP_ALLOW_LOCAL_FILE_INPUT` | bool | `false` | Enable local filesystem paths as `transform_image` reference images. When `false` (default), only gallery `image_id` values and `image://` URIs are accepted. |
| `IMAGE_GENERATION_MCP_MAX_INPUT_IMAGE_BYTES` | int | `20971520` | Per-reference maximum byte size for input images (default: 20 MiB). Applies to every reference, whether resolved from the gallery or a local file. References exceeding this limit are rejected before the provider call. |
| `IMAGE_GENERATION_MCP_FETCH_TIMEOUT_S` | float | `30.0` | HTTP fetch timeout in seconds, used when fetching remote image URLs. |

!!! warning "Security: local file input"
    Setting `ALLOW_LOCAL_FILE_INPUT=true` grants callers read access to any file readable by the server process (they can pass arbitrary paths). Enable only for trusted callers, such as a local single-user Claude Desktop installation. Leave disabled on shared or network-accessible deployments.

## Session persistence (HTTP transport)

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `IMAGE_GENERATION_MCP_EVENT_STORE_URL` | str | `file:///data/state/events` | EventStore backend for SSE session resumeability. `file:///path` stores events on disk (survives restarts); `memory://` keeps events in-process only (dev/test). |

## Capability-link transfer (HTTP transport)

The `create_download_link` and `create_upload_link` tools (and the backing `/transfer/{token}` HTTP route) come from pvl-core's shared capability-link transfer routes. They register only on an HTTP or SSE transport with `IMAGE_GENERATION_MCP_BASE_URL` set. One-time link tokens are stored in the KV store configured by `IMAGE_GENERATION_MCP_KV_STORE_URL` (a `file:///data/state` file store in the Docker image; `memory://` for dev). The knobs below tune link lifetime and upload limits.

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `IMAGE_GENERATION_MCP_TRANSFER_TTL_DEFAULT_S` | number | `3600` | Link lifetime (seconds) when the caller omits `ttl_s` (default 1 hour). |
| `IMAGE_GENERATION_MCP_TRANSFER_TTL_MAX_S` | number | `86400` | Ceiling (seconds) for a caller-requested `ttl_s`; larger values are clamped to this (default 24 hours). |
| `IMAGE_GENERATION_MCP_TRANSFER_GRACE_TTL_S` | number | `60` | Post-success grace window (seconds) during which a served-but-stalled transfer can retry. |
| `IMAGE_GENERATION_MCP_TRANSFER_LEASE_S` | number | `60` | Reclaim window (seconds) for an in-flight reservation left behind by a crashed handler. |
| `IMAGE_GENERATION_MCP_TRANSFER_MAX_UPLOAD_BYTES` | int | `104857600` | Per-upload size cap in bytes for `create_upload_link` POSTs (default 100 MiB). |

## Server

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `IMAGE_GENERATION_MCP_SERVER_NAME` | str | `image-generation-mcp` | Server name shown to MCP clients in the initialization response. |
| `IMAGE_GENERATION_MCP_INSTRUCTIONS` | str | (generated at startup) | System-level instructions injected into model context. Defaults to a description reflecting the read-only/read-write state. |
| `FASTMCP_LOG_LEVEL` | str | `INFO` | Log level: `DEBUG`, `INFO`, `WARNING`, `ERROR`. Controls FastMCP internals (auth, transport) directly; app loggers use `INFO` unless overridden by `--verbose`. |
| `IMAGE_GENERATION_MCP_HTTP_PATH` | str | `/mcp` | HTTP endpoint mount path for streamable-HTTP transport. |
| `IMAGE_GENERATION_MCP_APP_DOMAIN` | str | (auto) | MCP Apps widget sandbox domain. **Auto-computed from `BASE_URL`** for Claude when not set. Override for other hosts or custom domains (see below). |

!!! tip "MCP Apps domain (usually automatic)"
    When `BASE_URL` is set (which it should be for HTTP deployments), the
    Claude sandbox domain is **auto-computed**: no extra configuration needed.

    The computation is `sha256(BASE_URL + HTTP_PATH)[:32] + ".claudemcpcontent.com"`.
    Set `APP_DOMAIN` explicitly only if you need to override this (such as for
    a non-Claude host like ChatGPT, or a custom HTTP path).

    To compute manually:

    ```bash
    # Python
    python3 -c "import hashlib; print(hashlib.sha256(b'https://mcp.example.com/mcp').hexdigest()[:32] + '.claudemcpcontent.com')"

    # Node.js
    node -e "console.log(require('crypto').createHash('sha256').update('https://mcp.example.com/mcp').digest('hex').slice(0,32)+'.claudemcpcontent.com')"
    ```

## Example configurations

### Minimal (placeholder only)

```bash
IMAGE_GENERATION_MCP_READ_ONLY=false
```

### OpenAI

```bash
IMAGE_GENERATION_MCP_READ_ONLY=false
IMAGE_GENERATION_MCP_OPENAI_API_KEY=sk-...
```

### Gemini

```bash
IMAGE_GENERATION_MCP_READ_ONLY=false
IMAGE_GENERATION_MCP_GOOGLE_API_KEY=AIza...
```

### All providers

```bash
IMAGE_GENERATION_MCP_READ_ONLY=false
IMAGE_GENERATION_MCP_GOOGLE_API_KEY=AIza...
IMAGE_GENERATION_MCP_OPENAI_API_KEY=sk-...
IMAGE_GENERATION_MCP_SD_WEBUI_HOST=http://localhost:7860
IMAGE_GENERATION_MCP_SD_WEBUI_MODEL=realisticVisionV60B1_v51VAE.safetensors
```

### Production: remote mode (recommended)

```bash
IMAGE_GENERATION_MCP_READ_ONLY=false
IMAGE_GENERATION_MCP_OPENAI_API_KEY=sk-...
IMAGE_GENERATION_MCP_BASE_URL=https://mcp.example.com
IMAGE_GENERATION_MCP_OIDC_CONFIG_URL=https://auth.example.com/.well-known/openid-configuration
```

### Production: oidc-proxy mode (DCR emulation)

```bash
IMAGE_GENERATION_MCP_READ_ONLY=false
IMAGE_GENERATION_MCP_OPENAI_API_KEY=sk-...
IMAGE_GENERATION_MCP_BASE_URL=https://mcp.example.com
IMAGE_GENERATION_MCP_OIDC_CONFIG_URL=https://auth.example.com/.well-known/openid-configuration
IMAGE_GENERATION_MCP_OIDC_CLIENT_ID=image-generation-mcp
IMAGE_GENERATION_MCP_OIDC_CLIENT_SECRET=your-client-secret
IMAGE_GENERATION_MCP_OIDC_JWT_SIGNING_KEY=your-stable-hex-key
```
<!-- DOMAIN-CONFIG-VARS-END -->
