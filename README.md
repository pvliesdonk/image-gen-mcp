# Image Generation MCP

<!-- mcp-name: io.github.pvliesdonk/image-generation-mcp -->

[![CI](https://github.com/pvliesdonk/image-generation-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/pvliesdonk/image-generation-mcp/actions/workflows/ci.yml) [![codecov](https://codecov.io/gh/pvliesdonk/image-generation-mcp/graph/badge.svg)](https://codecov.io/gh/pvliesdonk/image-generation-mcp) [![PyPI](https://img.shields.io/pypi/v/image-generation-mcp)](https://pypi.org/project/image-generation-mcp/) [![Python](https://img.shields.io/pypi/pyversions/image-generation-mcp)](https://pypi.org/project/image-generation-mcp/) [![License](https://img.shields.io/github/license/pvliesdonk/image-generation-mcp)](LICENSE) [![Docker](https://img.shields.io/github/v/release/pvliesdonk/image-generation-mcp?label=ghcr.io&logo=docker)](https://github.com/pvliesdonk/image-generation-mcp/pkgs/container/image-generation-mcp) [![Docs](https://img.shields.io/badge/docs-GitHub%20Pages-blue)](https://pvliesdonk.github.io/image-generation-mcp/) [![llms.txt](https://img.shields.io/badge/llms.txt-available-brightgreen)](https://pvliesdonk.github.io/image-generation-mcp/llms.txt) [![Template](https://img.shields.io/badge/dynamic/yaml?url=https://raw.githubusercontent.com/pvliesdonk/image-generation-mcp/main/.copier-answers.yml&query=%24._commit&label=template)](https://github.com/pvliesdonk/fastmcp-server-template)

Multi-provider image generation [MCP](https://modelcontextprotocol.io) server built on [FastMCP](https://gofastmcp.com). Generate images from Claude Desktop, Claude Code, or any MCP client using OpenAI, Google Gemini, Stable Diffusion (SD WebUI), or a zero-cost placeholder provider.

**[Documentation](https://pvliesdonk.github.io/image-generation-mcp/)** | **[Config wizard](https://pvliesdonk.github.io/image-generation-mcp/latest/configuration-generator/)** | **[PyPI](https://pypi.org/project/image-generation-mcp/)** | **[Docker](https://github.com/pvliesdonk/image-generation-mcp/pkgs/container/image-generation-mcp)**

## Features

<!-- DOMAIN-START -->

- **Multi-provider**: OpenAI (`gpt-image-2`, `gpt-image-1.5`, `dall-e-3`), Google Gemini (`gemini-3.1-flash-image`, `gemini-3-pro-image`, `gemini-3.1-flash-lite-image`), SD WebUI (Stable Diffusion / Forge / reForge), and a zero-cost placeholder for testing.
- **Per-model style metadata**: every model carries a `style_profile` (strengths, prompt grammar, lifecycle); `list_providers` includes a top-level `warnings` array for deprecated models. See [Model Catalog](https://pvliesdonk.github.io/image-generation-mcp/providers/model-catalog/).
- **Keyword-based auto-selection**: `provider="auto"` routes by prompt content (text/logo → OpenAI, photoreal/anime → SD WebUI, draft → placeholder).
- **CDN-style image transforms**: `image://{id}/view?format=webp&width=512&crop_x=...` resizes / re-encodes / crops on demand without re-generating.
- **Hybrid background tasks**: long-running SD generations run with `task=True` (poll for status); short OpenAI calls stream progress in the foreground.
- **MCP Apps gallery + viewer**: interactive UI surfaces (browse generated images, edit / crop / rotate) for clients that support `app:` resources.
- **Production deployment**: Docker (multi-arch), `.deb`/`.rpm` with hardened systemd, OIDC + bearer auth, persistent EventStore for HTTP session resumability.
<!-- DOMAIN-END -->

## What you can do with it

<!-- DOMAIN-START -->

With this server mounted in an MCP client, you can ask:

- **"Generate a coffee mug product photo on a worn oak table, 16:9, no text."** Routes to `gpt-image-1.5` for typography-aware photorealism.
- **"Create three concept-art variations of a cyberpunk alley at dusk."** Composes `generate_image` with `provider="sd_webui"` and a stylised checkpoint like `dreamshaperXL`.
- **"Crop this image to a 1:1 square centred on the subject and resize to 512px."** Uses `image://{id}/view?width=512&height=512&crop_x=...` resource transforms.
- **"Show me my recent generations."** Browses the gallery via the `image://list` resource and the MCP Apps gallery viewer.
- **"Save this style as 'cyberpunk-night' so I can apply it to future requests."** Uses the style library, whose markdown briefs the LLM interprets per-provider.
- **"Replace the background of my last photo with a sunset sky."** Uses `transform_image` with the gallery `image_id` as a reference (image-to-image via Gemini).
<!-- DOMAIN-END -->

<!-- ===== TEMPLATE-OWNED SECTIONS BELOW — DO NOT EDIT; CHANGES WILL BE OVERWRITTEN ON COPIER UPDATE ===== -->

## Installation

### From PyPI

```bash
pip install image-generation-mcp
```

If you add optional extras via the `PROJECT-EXTRAS-START` / `PROJECT-EXTRAS-END` sentinels in `pyproject.toml`, document them below:

<!-- DOMAIN-START -->

| Extra | Includes | Use when |
|-------|----------|----------|
| `mcp` | `fastmcp[tasks]>=3.0,<4` | Background-task support (`task=True`), required for long SD generations. |
| `openai` | `openai>=1.0` | Enables the OpenAI provider. |
| `google-genai` | `google-genai>=1.0` | Enables the Gemini provider. |
| `all` | `fastmcp[tasks]` + `openai` + `google-genai` | Everything except SD WebUI (which is HTTP-only, no extra needed). |

Example: `pip install image-generation-mcp[all]`.
<!-- DOMAIN-END -->

### From source

```bash
git clone https://github.com/pvliesdonk/image-generation-mcp.git
cd image-generation-mcp
uv sync --all-extras --all-groups
```

### Docker

```bash
docker pull ghcr.io/pvliesdonk/image-generation-mcp:latest
```

A `compose.yml` ships at the repo root as a starting point. Copy `.env.example` to `.env`, edit, and `docker compose up -d`.

To attach a remote Python debugger (development only; the protocol is unauthenticated), see [Remote debugging](docs/deployment/docker.md#remote-debugging).

### Linux packages (.deb / .rpm)

Download `.deb` or `.rpm` packages from the [GitHub Releases](https://github.com/pvliesdonk/image-generation-mcp/releases) page. Both install a hardened systemd unit; env configuration is sourced from `/etc/image-generation-mcp/env` (copy from the shipped `/etc/image-generation-mcp/env.example`).

### Claude Desktop (.mcpb bundle)

Download the `.mcpb` bundle from the [GitHub Releases](https://github.com/pvliesdonk/image-generation-mcp/releases) page and double-click to install, or run:

```bash
mcpb install image-generation-mcp-<version>.mcpb
```

Claude Desktop prompts for required env vars via a GUI wizard, with no manual JSON editing needed.

For manual Claude Desktop configuration and setup options, see [Claude Desktop deployment](docs/deployment/claude-desktop.md).

## Quick start

```bash
image-generation-mcp serve                                # stdio transport
image-generation-mcp serve --transport http --port 8000   # streamable HTTP
```

For library usage (embedding the domain logic without the MCP transport), import from the `image_generation_mcp` package directly. See the project's domain modules under `src/image_generation_mcp/` for entry points.

### Server info

The server registers a built-in `get_server_info` tool (via `fastmcp_pvl_core.register_server_info_tool`) so operators can confirm the deployed version with a single MCP call. The default response carries `server_name`, `server_version`, and `core_version`. Servers that talk to a remote upstream wire upstream version reporting inside the `DOMAIN-UPSTREAM-START` / `DOMAIN-UPSTREAM-END` sentinel in `src/image_generation_mcp/server.py`; see [`CLAUDE.md`](CLAUDE.md#server-info-tool-get_server_info) for the wiring pattern.

## Configuration

Core environment variables shared across all `fastmcp-pvl-core`-based services:

<!-- GENERATED-ENV-TABLE-CORE-START — generated by scripts/gen_config_surface.py; do not edit -->
| Variable | Default | Description |
|---|---|---|
| `IMAGE_GENERATION_MCP_KV_STORE_URL` | `file:///data/state` | Persistent-state backend URL shared by every pvl-core subsystem that needs state. `memory://` is in-process and lost on restart; `file:///path` persists on one server; `redis://`, `dynamodb://` and `mongodb://` each need their matching extra. Defaults to `file:///data/state` when unset. |
| `FASTMCP_LOG_LEVEL` | `INFO` | Log level for FastMCP internals and app loggers (DEBUG / INFO / WARNING / ERROR / CRITICAL). The -v CLI flag overrides to DEBUG. |
| `FASTMCP_ENABLE_RICH_LOGGING` | `true` | Set false for plain or structured JSON log output. |
<!-- GENERATED-ENV-TABLE-CORE-END -->

Domain-specific variables go below under [Domain configuration](#domain-configuration).

## Authentication

Callers authenticate via a bearer token or OIDC (mutually exclusive). See the [Authentication guide](docs/guides/authentication.md) for setup, mapped multi-subject tokens, OIDC, and troubleshooting.

## Post-scaffold checklist

After `copier copy` and `gh repo create --push`:

1. **Fill in the DOMAIN blocks** (every section marked with a `DOMAIN` sentinel comment) in this README and in `CLAUDE.md`. The `GENERATED-ENV-TABLE-*` regions are not DOMAIN blocks; the config generator owns them and rewrites them on every run.
2. Configure GitHub secrets (see below).
3. Install dev + docs tooling: `uv sync --all-extras --all-groups`.
4. Install pre-commit hooks: `uv run pre-commit install`.
5. Run the gate locally: `uv run pytest -x -q && uv run ruff check --fix . && uv run ruff format . && uv run mypy src/ tests/`.
6. Push the first commit. CI should be green.

## GitHub secrets

CI workflows reference three repository secrets. Configure them via **Settings → Secrets and variables → Actions** or with `gh secret set`:

| Secret | Used by | How to generate |
|---|---|---|
| `RELEASE_TOKEN` | `release.yml`, `copier-update.yml`, `renovate.yml`, `bootstrap.yml` | Fine-grained PAT at <https://github.com/settings/personal-access-tokens/new> with `contents: write`, `pull_requests: write`, and `administration: write` (bootstrap sets branch protection + auto-merge). Scoped to this repo. |
| `CODECOV_TOKEN` | `ci.yml` | <https://codecov.io>: sign in with GitHub and add the repo. The upload token is on its settings page. |
| `CLAUDE_CODE_OAUTH_TOKEN` | `claude.yml`, `claude-code-review.yml` | Run `claude setup-token` locally and paste the result. |

```bash
gh secret set RELEASE_TOKEN
gh secret set CODECOV_TOKEN
gh secret set CLAUDE_CODE_OAUTH_TOKEN
```

> Dependency updates are handled by **Renovate** (`renovate.yml`), which reuses
> `RELEASE_TOKEN`. It maintains `uv.lock` and auto-merges patch/minor bumps once
> the `CI Success` check is green; `bootstrap.yml` enables auto-merge and branch
> protection on first push. GitHub Actions are updated in the copier template
> and arrive via `copier update`, not per-repo.

`GITHUB_TOKEN` is auto-provided; no action needed.

## Local development

The PR gate (matches CI):

```bash
uv run pytest -x -q                                  # tests
uv run ruff check --fix . && uv run ruff format .    # lint + format
uv run mypy src/ tests/                              # type-check
```

Pre-commit runs a subset of the gate on each commit; see `.pre-commit-config.yaml` for details, or [`CLAUDE.md`](CLAUDE.md) for the full Hard PR Acceptance Gates.

## Troubleshooting

### Moving a scaffolded project

`uv sync` creates `.venv/bin/*` scripts with absolute shebangs pointing at the venv Python. If you move the repo after scaffolding (`mv /old/path /new/path`), `uv run pytest` fails with `ModuleNotFoundError: No module named 'fastmcp'` because the stale shebang resolves to a different interpreter than the venv's site-packages.

**Fix:**

```bash
rm -rf .venv
uv sync --all-extras --all-groups
```

`uv run python -m pytest` also works as a one-shot workaround (bypasses the stale entry-script shim).

### `uv.lock` refresh after `copier update`

When `copier update` introduces new dependencies (such as a new extra added to `pyproject.toml.jinja`), CI runs `uv sync --frozen` which fails against a stale lockfile. Run `uv lock` locally and commit the refreshed `uv.lock` alongside accepting the copier-update PR.

## Links

- [Documentation](https://pvliesdonk.github.io/image-generation-mcp/)
- [llms.txt](https://pvliesdonk.github.io/image-generation-mcp/llms.txt)
- [FastMCP](https://gofastmcp.com)
- [fastmcp-pvl-core](https://pypi.org/project/fastmcp-pvl-core/)

<!-- ===== TEMPLATE-OWNED SECTIONS END ===== -->

## Domain configuration

Domain environment variables use the `IMAGE_GENERATION_MCP_` prefix:

<!-- GENERATED-ENV-TABLE-DOMAIN-START — generated by scripts/gen_config_surface.py; do not edit -->
| Variable | Default | Required | Description |
|---|---|---|---|
| `IMAGE_GENERATION_MCP_A1111_HOST` | (none) | No | Deprecated alias for IMAGE_GENERATION_MCP_SD_WEBUI_HOST; logs a warning when used. |
| `IMAGE_GENERATION_MCP_A1111_MODEL` | (none) | No | Deprecated alias for IMAGE_GENERATION_MCP_SD_WEBUI_MODEL; logs a warning when used. |
| `IMAGE_GENERATION_MCP_READ_ONLY` | (none) | **Yes** |  |
| `IMAGE_GENERATION_MCP_SCRATCH_DIR` | (none) | **Yes** |  |
| `IMAGE_GENERATION_MCP_OPENAI_API_KEY` | (none) | **Yes** |  |
| `IMAGE_GENERATION_MCP_GOOGLE_API_KEY` | (none) | **Yes** |  |
| `IMAGE_GENERATION_MCP_SD_WEBUI_HOST` | (none) | **Yes** |  |
| `IMAGE_GENERATION_MCP_SD_WEBUI_MODEL` | (none) | **Yes** |  |
| `IMAGE_GENERATION_MCP_DEFAULT_PROVIDER` | (none) | **Yes** |  |
| `IMAGE_GENERATION_MCP_TRANSFORM_CACHE_SIZE` | (none) | **Yes** |  |
| `IMAGE_GENERATION_MCP_PAID_PROVIDERS` | (none) | **Yes** |  |
| `IMAGE_GENERATION_MCP_STYLES_DIR` | (none) | **Yes** |  |
| `IMAGE_GENERATION_MCP_ALLOW_LOCAL_FILE_INPUT` | (none) | **Yes** |  |
| `IMAGE_GENERATION_MCP_MAX_INPUT_IMAGE_BYTES` | (none) | **Yes** |  |
| `IMAGE_GENERATION_MCP_FETCH_TIMEOUT_S` | (none) | **Yes** |  |
| `IMAGE_GENERATION_MCP_TRANSFER_TTL_DEFAULT_S` | `3600.0` | No | Link lifetime in seconds when the caller requests no explicit TTL. |
| `IMAGE_GENERATION_MCP_TRANSFER_TTL_MAX_S` | `86400.0` | No | Ceiling in seconds a caller-requested link TTL is clamped to. |
| `IMAGE_GENERATION_MCP_TRANSFER_GRACE_TTL_S` | `60.0` | No | Post-success grace window in seconds: a served token's TTL shrinks to this so a stalled transfer can retry within it. |
| `IMAGE_GENERATION_MCP_TRANSFER_LEASE_S` | `60.0` | No | Crashed-handler reclaim window in seconds for an in-flight reservation. |
| `IMAGE_GENERATION_MCP_TRANSFER_MAX_UPLOAD_BYTES` | `104857600` | No | Maximum size in bytes of a single upload. |
<!-- GENERATED-ENV-TABLE-DOMAIN-END -->

The `create_download_link` / `create_upload_link` tools and the `/transfer/{token}` route register only on an HTTP or SSE transport with `BASE_URL` set, and store link tokens in `IMAGE_GENERATION_MCP_KV_STORE_URL`; the `IMAGE_GENERATION_MCP_TRANSFER_*` knobs above tune link lifetime and upload limits. **Security:** `IMAGE_GENERATION_MCP_ALLOW_LOCAL_FILE_INPUT` grants callers server-filesystem read access via reference-image paths; enable it only for trusted callers or local single-user deployments.

Domain-config fields are composed inside `src/image_generation_mcp/config.py` between the `CONFIG-FIELDS-START` / `CONFIG-FIELDS-END` sentinels; env reads go through `fastmcp_pvl_core.env(_ENV_PREFIX, "SUFFIX", default)` so naming stays consistent, and field invariants go in `__post_init__` between the `CONFIG-VALIDATE-START` / `CONFIG-VALIDATE-END` sentinels. Each field's `metadata` `help` and `tags` generate the table above directly, so keep them accurate and complete.

## Key design decisions

<!-- DOMAIN-START -->

- **Multi-provider with capability discovery, not feature flags.** Each provider's `discover_capabilities()` reports its actual supported aspect ratios / qualities / formats / negative-prompt support at startup; routing logic asks the capability surface, not a hard-coded enum. New providers slot in by satisfying the protocol, with no router edits needed. (See `docs/decisions/0001-…`, `0002-…`, `0007-…`.)
- **Per-model `style_profile` metadata, surfaced via `list_providers`.** Closed-list providers (OpenAI, Gemini, placeholder) use exact-key lookup; SD WebUI uses a regex-ordered pattern table. Profiles include lifecycle flags (`current` / `legacy` / `deprecated`) and feed an auto-built top-level `warnings` array. (See `docs/decisions/0009-…`.)
- **Hybrid background tasks.** Short calls (OpenAI ~5 s) stream progress in-line; long calls (SD WebUI 30-180 s) run as background tasks with `check_generation_status` polling; clients pick the mode via `task=True`. (See `docs/decisions/0005-…`.)
- **Image asset model: content-addressed registry + sidecar JSON metadata + on-demand transforms.** Generated images keep their full-resolution original; `image://{id}/view?format=webp&width=512&crop_x=…` resources do format conversion / resize / crop on demand without re-generating. Transforms are cached. (See `docs/decisions/0006-…`.)
- **Style library.** User-saved markdown briefs (with YAML frontmatter for tags / aspect ratio / quality) that the LLM interprets per-provider, not copy-pasted verbatim. Distinct from per-model `style_profile`: style library is the brief; `style_profile` describes the model. (See `docs/decisions/0008-…` and `0009-…` for disambiguation.)
- **Composes `fastmcp_pvl_core.ServerConfig`, never inherits.** Domain config goes between `CONFIG-FIELDS-START` / `CONFIG-FIELDS-END` sentinels; env reads route through `fastmcp_pvl_core.env(...)` to keep prefix naming consistent.
<!-- DOMAIN-END -->
