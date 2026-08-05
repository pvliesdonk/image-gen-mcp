# Provider System Design

## Overview

The image generation MCP server uses a multi-provider architecture where each
provider implements a common protocol and is registered at startup based on
available configuration (API keys, service URLs). A central `ImageService`
orchestrates provider selection, image generation, image registry management,
and scratch storage.

## Architecture

```
MCP Client (Claude)
    |
    v
+---------------------------------------------+
|  MCP Layer                                   |
|  _server_tools.py    generate_image          |
|                      show_image              |
|                      list_providers          |
|                      create_download_link    |
|  _server_prompts.py  select_provider         |
|                      sd_prompt_guide         |
|  _server_resources.py                        |
|    info://providers                          |
|    info://prompt-guide                       |
|    image://{id}/view{?format,w,h,quality}    |
|    image://{id}/metadata                     |
|    image://list                              |
+------------------+---+----------------------+
                   |   |
  Depends(service) |   | processing.py
                   v   v
+---------------------------------------------+
|  ImageService (service.py)                   |
|  - Provider registry (name -> instance)      |
|  - Image registry (_images dict + sidecars)  |
|  - generate() -> dispatches to provider      |
|  - register_image() -> saves + indexes       |
|  - get_image() / list_images()               |
|  - _load_registry() -> rebuilds from disk    |
+------+----------+----------+----------+----------------+
       |          |          |          |
       v          v          v          v
  +---------+ +--------+ +----------+ +--------------+
  | OpenAI  | | Gemini | | SD WebUI | | Placeholder  |
  |Provider | |Provider| | Provider | | Provider     |
  +---------+ +--------+ +----------+ +--------------+
```

## ImageProvider Protocol

All providers implement the `ImageProvider` protocol (runtime-checkable):

```python
ProgressCallback = Callable[[float, str], None]

@runtime_checkable
class ImageProvider(Protocol):
    async def generate(
        self,
        prompt: str,
        *,
        negative_prompt: str | None = None,
        aspect_ratio: str = "1:1",
        quality: str = "standard",
        resolution: str = "standard",
        background: str = "opaque",
        model: str | None = None,
        reference_images: Sequence[InputImage] | None = None,
        strength: float | None = None,
        mask: InputImage | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> ImageResult: ...

    async def discover_capabilities(self) -> ProviderCapabilities: ...
```

## Image-input primitive

Reference-image input (image-to-image, composition, masking) extends the same
`generate()` method rather than adding a parallel method. Three optional
parameters carry it:

- `reference_images`: a sequence of `InputImage` value objects (decoded bytes
  plus content type and optional `source_id` provenance). Empty or `None`
  means text-to-image.
- `strength`: denoising strength for SD WebUI img2img (`0.0`-`1.0`). Other
  providers ignore it with a debug log; it has no effect without a reference
  image.
- `mask`: a single `InputImage` inpainting mask. Only OpenAI gpt-image models
  consume it; the other providers raise `ImageProviderError` when a mask is
  supplied.

Input resolution lives in `_input_images.py`, the only module aware of input
sources. It maps a gallery `image_id`, an `image://` URI, or a gated local
file path to an `InputImage`. The `transform_image` tool resolves references,
then routes on three capability fields exposed by `discover_capabilities`:
`supports_image_input`, `max_input_images`, and `supports_mask`. Auto-routing
selects a provider whose model accepts the supplied reference count, and a
mask request is routed only to a mask-capable model. Result provenance is
generalized to `source_image_ids: list[str]`.

The optional `model` parameter allows per-call model selection. When set, it
overrides the provider's constructor default. SD WebUI uses it for both preset
detection and `override_settings.sd_model_checkpoint`. OpenAI uses it as the
API `model` parameter with automatic size table switching.

The optional `progress_callback` parameter enables fine-grained progress
reporting during generation. When provided, it is called with
`(fraction, message)` where `fraction` is 0.0-1.0 and `message` is a
human-readable status string (e.g., `"Step 15/30 (ETA 12s)"`). Only SD WebUI
implements this (via `/sdapi/v1/progress` polling); other providers accept
but ignore the parameter.

The `discover_capabilities()` method is called once during server lifespan
after provider construction. Results are cached for the server lifetime
(frozen dataclasses). See [ADR-0007](../decisions/0007-provider-capability-model.md)
for the full design.

## Resolution Tiers

The `resolution` parameter (`"standard"` / `"high"` / `"max"`) is a
generate-time size knob, independent of `quality` (which controls model
reasoning/response modalities, not output size) and independent of the
read-time `image://{id}/view?width=&height=` resize/crop transforms
described under [Image Asset Model](#image-asset-model) below — those act on
already-generated bytes; `resolution` selects what the provider renders in
the first place.

- **Capability field:** `ModelCapabilities.supported_resolutions` (a tuple,
  default `("standard",)`) is the vocabulary a given model actually honors,
  beyond the always-supported `"standard"`. It is declared independently of
  `max_resolution` (the pixel ceiling); neither is derived from the other.
- **Clamp, not reject:** requesting a tier a model does not support does not
  raise. Each provider clamps the request down to the highest tier the
  resolved model actually supports (Gemini: `_resolution_capabilities()`
  picks the model's ceiling via
  `max(model_resolutions, key=list(_RESOLUTION_TO_IMAGE_SIZE).index)`; OpenAI:
  `_effective_resolution()` returns `"standard"` for every model outside the
  gpt-image-2 family regardless of the requested tier). This mirrors the
  MCP tool layer's own posture: the tool validates `resolution` against the
  global `SUPPORTED_RESOLUTIONS` vocabulary (`"standard"`/`"high"`/`"max"`,
  raising `ValueError` for anything outside it), while a valid-but-unsupported
  tier for a specific *model* is a provider-level clamp, not a tool-level
  rejection.
- **Fail-closed unknown-model default:** a model absent from a provider's
  per-model resolution table is treated as `standard`-only rather than
  assumed to support the full range. New models must be added explicitly
  before `high`/`max` reach them; this mirrors the same provider modules'
  existing conservative default for undocumented models (e.g. Gemini's
  `_DEFAULT_MAX_INPUT_IMAGES` posture).
- **Delivered-tier persistence:** the provider reports the tier it actually
  delivered (after any clamp) in `ImageResult.provider_metadata["resolution"]`.
  `ImageService.register_image()` persists that delivered value on the
  `ImageRecord.resolution` field when the provider sets one, falling back to
  the requested `resolution` otherwise, so a client reading back a generated
  image sees what was actually rendered, not merely what was asked for. Every
  live provider sets this key uniformly: Gemini and OpenAI report the
  post-clamp tier; Placeholder and SD WebUI have no tier above `"standard"`
  and always report `"standard"` regardless of what was requested. The
  requested-value fallback in `register_image()` therefore only applies to
  genuinely legacy or imported records that predate this contract.

### ImageResult

Frozen dataclass returned by all providers:

| Field | Type | Description |
|-------|------|-------------|
| `image_data` | `bytes` | Raw image bytes (PNG, JPEG, or WebP) |
| `content_type` | `str` | MIME type, default `"image/png"` |
| `provider_metadata` | `dict[str, Any]` | Provider-specific metadata (model, seed, size, etc.) |

Provides:
- `size_bytes` property -- length of `image_data`
- `from_base64()` classmethod -- construct from base64-encoded string + keyword metadata

### Exception Hierarchy

```
ImageProviderError(Exception)
+-- ImageContentPolicyError    # Content policy violation (OpenAI)
+-- ImageProviderConnectionError  # Network/timeout errors
```

All exceptions carry `provider: str` and `message: str` for clear error reporting.

## Capability Discovery

At startup, after all providers are registered, the server calls
`discover_capabilities()` on each provider. Results are stored in
`ImageService._capabilities` as frozen `ProviderCapabilities` dataclasses.

### Per-Provider Strategy

| Provider | Discovery method | Notes |
|----------|-----------------|-------|
| **Placeholder** | Static return | Hardcoded capabilities, always succeeds |
| **OpenAI** | `client.models.list()` | Filters to known image models (gpt-image-1, dall-e-3, dall-e-2) |
| **Gemini** | Static return | Returns known image models (`_KNOWN_IMAGE_MODELS`); `models.list()` doesn't filter image-generation models |
| **SD WebUI** | `GET /sdapi/v1/sd-models` + `/sdapi/v1/options` | Maps checkpoints to architecture-specific capabilities |

### Degraded Mode

If `discover_capabilities()` raises an exception, the provider is marked
`degraded=True` with an empty model list. Server startup is **not blocked** --
degraded providers can still generate images, but a warning is logged on each
generation request. This prevents a slow or unreachable SD WebUI instance from
blocking the entire server.

### Capability-Aware Selection

When `provider="auto"`, the selector uses capabilities as a **secondary filter**
alongside keyword heuristics. For example, when `background="transparent"` is
requested, providers without `supports_background=True` are deprioritized but
not excluded. Keywords remain the primary selection mechanism.

## Providers

### Placeholder Provider

- **Purpose:** Zero-cost solid-color PNG generation for testing and drafts
- **No dependencies:** Pure Python PNG encoder (zlib + struct)
- **Color:** Selected from 6-color palette via SHA-256 hash of prompt
- **Aspect ratios:** Maps to pixel sizes (256x256, 640x360, etc.)
- **Background:** Supports transparent (RGBA PNG with alpha=0)
- **Always registered** -- no API key or service needed

### Gemini Provider

- **Models:** `gemini-2.5-flash-image` (default), `gemini-3.1-flash-image-preview`, `gemini-3-pro-image-preview`
- **API:** Gemini native `generateContent` with `responseModalities=["IMAGE"]` via `google-genai` SDK
- **Negative prompt:** Appended as `"\n\nAvoid: {negative_prompt}"` (no native support)
- **Quality:** Accepted and recorded in `provider_metadata`; `generateContent` has no quality/resolution parameter (unlike Imagen), so the value is not sent to the API
- **Aspect ratios:** All 5 project ratios passed through directly (all natively supported)
- **Background:** Not supported — ignored; debug log emitted
- **Discovery:** Returns static list of known image models; `models.list()` does not reliably filter image-generation models
- **Error handling:** Converts safety/policy errors to `ImageContentPolicyError`; connection errors to `ImageProviderConnectionError`
- **Watermark:** All outputs include Google's SynthID invisible watermark (automatic, cannot be disabled)
- **Registered when:** `IMAGE_GENERATION_MCP_GOOGLE_API_KEY` is set

### OpenAI Provider

- **Models:** `gpt-image-1` (default), `dall-e-3`
- **API:** OpenAI Images API with `output_format` (gpt-image-1) or `response_format="b64_json"` (dall-e-3)
- **Negative prompt:** Appended as `"\n\nAvoid: {negative_prompt}"` to the prompt
- **Quality mapping:** gpt-image-1: `"standard"` -> `"high"`, `"hd"` -> `"high"`; dall-e-3: passed through unchanged
- **Size mapping:** Per-model aspect ratio -> pixel size tables
- **Background:** `gpt-image-1` supports `background` parameter natively; ignored for `dall-e-3`
- **Discovery:** Calls `client.models.list()`, filters to known image models, maps to `ModelCapabilities`
- **Error handling:** Converts `APIConnectionError`, `APIStatusError` (with content policy detection)
- **Registered when:** `IMAGE_GENERATION_MCP_OPENAI_API_KEY` is set

### SD WebUI Provider (Stable Diffusion WebUI)

Compatible with AUTOMATIC1111, Forge, reForge, and Forge-neo.

- **API:** HTTP POST to `/sdapi/v1/txt2img`
- **Model-aware presets:** Auto-detects SD architecture from checkpoint name:
  - **SD 1.5** (default): 768px base, 30 steps, CFG 7.0, DPM++ 2M sampler, Karras scheduler
  - **SDXL**: 1024px base, 35 steps, CFG 7.5, DPM++ 2M sampler, Karras scheduler
  - **SDXL Lightning/Turbo**: 1024px base, 6 steps, CFG 2.0, DPM++ SDE sampler, Karras scheduler
  - **Flux Dev**: 1024px base, 20 steps, CFG 1.0, Euler sampler, Simple scheduler, distilled_cfg_scale 3.5, no negative prompt
  - **Flux Schnell**: 1024px base, 4 steps, CFG 1.0, Euler sampler, Simple scheduler, distilled_cfg_scale 3.5, no negative prompt
- **Checkpoint override:** When `model` is specified, sends `override_settings.sd_model_checkpoint`
- **Negative prompt:** Native support via `negative_prompt` field in payload
- **Background:** Ignored (SD does not support native transparent backgrounds); debug log emitted
- **Discovery:** Calls `/sdapi/v1/sd-models` + `/sdapi/v1/options`, maps checkpoints to architecture-specific `ModelCapabilities`; `prompt_style` is populated per-architecture (`"clip"` for SD 1.5/SDXL, `"natural_language"` for Flux)
- **Metadata:** Extracts seed and active model name from response `info` JSON
- **Progress polling:** When `progress_callback` is provided, polls `GET /sdapi/v1/progress` every 2 seconds concurrently with the `/sdapi/v1/txt2img` call. Reports `(fraction, "Step N/M (ETA Xs)")`. Polling failures are logged at debug level and do not interrupt generation. The polling task is cancelled when txt2img completes.
- **Timeout:** 180s (SDXL at high res on consumer GPUs)
- **Registered when:** `IMAGE_GENERATION_MCP_SD_WEBUI_HOST` is set (deprecated alias: `IMAGE_GENERATION_MCP_A1111_HOST`)

## Provider Selection

When `provider="auto"` (default), the selector (`providers/selector.py`) analyzes
the prompt using keyword matching with word boundaries:

| Prompt Keywords | Preferred Provider Chain |
|----------------|------------------------|
| realistic, photo, photography, headshot, portrait photo, product shot | sd_webui -> gemini -> openai |
| text, logo, typography, poster, banner, signage, lettering, font | openai -> gemini |
| quick, draft, test, placeholder, mock | placeholder |
| art, painting, illustration, watercolor, oil painting, sketch, drawing | sd_webui -> gemini -> openai |
| anime, manga, kawaii, chibi | sd_webui -> gemini -> openai |
| *(no match)* | gemini -> openai -> sd_webui -> placeholder |

First matching rule wins. Within a rule, the first available provider is selected.
If no rule matches, the default fallback chain is used. If no provider in the
chain is available, any registered provider is returned as last resort.

When capabilities are available and `background="transparent"` is requested,
providers with `supports_background=True` are tried first within each candidate
set. This is a secondary filter -- keyword heuristics still determine the rule,
but capable providers are preferred within that rule.

## ImageService

The `ImageService` is the central orchestrator, created during server lifespan
and injected via FastMCP's `Depends()` system.

### Responsibilities

1. **Provider registry** -- `register_provider(name, provider)` at startup
2. **Capability discovery** -- `discover_all_capabilities()` introspects each provider (graceful degradation)
3. **Generation dispatch** -- `generate(prompt, *, provider, ..., reference_images=..., strength=..., mask=..., progress_callback=...)` resolves provider and delegates (forwards reference-image input and `progress_callback` to the provider)
4. **Image registry** -- `register_image()` saves original + sidecar JSON, indexes in memory
5. **Image retrieval** -- `get_image(id)` and `list_images()` for registered images
6. **Startup rebuild** -- `_load_registry()` reconstructs in-memory registry from sidecar files
7. **Base64 encoding** -- `get_image_base64(result)` for MCP `ImageContent`
8. **Provider listing** -- `list_providers()` returns availability + capability info

### Image Asset Model

See [ADR-0006](../decisions/0006-image-asset-model.md) for the full decision.

**Image ID:** Content-addressed via `SHA-256(image_data)[:12]` (48 bits,
collision-safe for local store).

**Scratch layout:** Each image produces two files:
- `{id}-original.{ext}` -- the image bytes as returned by the provider
- `{id}.json` -- sidecar metadata (prompt, provider, dimensions, provider_metadata)

**Registry rebuild:** On startup, `_load_registry()` globs `*.json` in the
scratch directory, parses each sidecar, and populates `_images`. Corrupt JSON
is logged and skipped.

**Resolution is a read-time concern.** Providers generate at native resolution;
exact pixel dimensions are requested via the resource template query params.

### Provider Registration (Lifespan)

Registration happens in `_server_deps.py` during server startup:

1. **Placeholder** -- always registered (zero cost, no API key)
2. **OpenAI** -- registered if `config.openai_api_key` is set
3. **Gemini** -- registered if `config.google_api_key` is set
4. **SD WebUI** -- registered if `config.sd_webui_host` is set

After all providers are registered, `discover_all_capabilities()` is called.
This introspects each provider and caches the results for the server lifetime.
Failures are handled gracefully -- the provider is marked degraded but remains
available for generation.

### Scratch Directory

Every generated image is saved to `IMAGE_GENERATION_MCP_SCRATCH_DIR` (default
`~/.image-generation-mcp/images/`) with the `{id}-original.{ext}` naming scheme.

## MCP Interface

### Tools

| Tool | Tags | Task | Description |
|------|------|------|-------------|
| `generate_image` | `write` | `task=True` | Generate image, return metadata + `ResourceLink` |
| `show_image` | *(none)* | -- | Display a registered image with optional transforms |
| `list_providers` | *(none)* | -- | List available providers with availability info |
| `create_download_link` | *(none)* | -- | Mint a one-time `/transfer/{token}` URL serving a gallery image's original bytes. Registered by `fastmcp_pvl_core.register_transfer_routes` (HTTP transport + `base_url` only) |
| `create_upload_link` | `write` | -- | Mint a one-time `/transfer/{token}` URL that ingests posted bytes as an imported gallery image. Registered by `register_transfer_routes` (HTTP transport + `base_url` only) |

`generate_image` uses a fire-and-forget pattern
(see [ADR-0005](../decisions/0005-hybrid-background-tasks.md)). It returns
in <1s with `{"status": "generating", "image_id": "..."}` while the image is
generated as a background `asyncio.Task`. The client polls `show_image` to
check progress and retrieve the result. For SD WebUI, the background task
includes concurrent `/sdapi/v1/progress` polling that updates
`PendingGeneration.progress` and `PendingGeneration.progress_message`,
surfaced via `show_image` polling responses.

`generate_image` returns a `ToolResult` with:
- `TextContent` -- JSON metadata with `status`, `image_id`, `original_uri`,
  `resource_template`, `provider`
- `ResourceLink` -- URI reference to `image://{id}/view`

`show_image` doubles as both display tool and polling endpoint. For completed
images, it returns:
- `ImageContent` -- WebP thumbnail preview (max 512px, under 1 MB)
- `TextContent` -- JSON metadata with `image_id`, `prompt`, `provider`,
  `dimensions`, `original_size_bytes`, `format`, `transforms_applied`

For in-progress generations, it returns:
- `TextContent` -- JSON with `status`, `progress`, `progress_message`, `elapsed_seconds`

`show_image` is wired to the MCP Apps image viewer via
`AppConfig(resourceUri="ui://image-viewer/view.html")`.

`create_download_link` (serve an existing gallery image's original bytes) and
`create_upload_link` (ingest posted bytes as an imported gallery image) are
registered by `fastmcp_pvl_core.register_transfer_routes()` in `make_server()`
(`server.py`), which also mounts the one-time `/transfer/{token}` HTTP route.
pvl-core owns the token store, route, size caps, and TTL; the project
supplies only the two domain hooks in `_transfer_sink.py` — a `TransferSink`
(`read` serves via `ImageService.get_image`; `write` commits via
`register_imported_image`) and a `TransferValidator`. Wiring is gated on a
non-stdio transport with `IMAGE_GENERATION_MCP_BASE_URL` set. Tokens live in a
KV-backed store (`IMAGE_GENERATION_MCP_KV_STORE_URL`) with TTLs configurable via
the `IMAGE_GENERATION_MCP_TRANSFER_*` env vars. This replaces the previous
bespoke `ArtifactStore` / `/artifacts/{token}` download path (issue #307); see
[ADR 0001](https://github.com/pvliesdonk/fastmcp-pvl-core/blob/main/docs/adr/0001-transfer-lift.md)
in `fastmcp-pvl-core`.

In read-only mode (`IMAGE_GENERATION_MCP_READ_ONLY=true`), `generate_image` is hidden.

### Resources

| URI | Description |
|-----|-------------|
| `info://providers` | JSON of provider capabilities, models, supported features |
| `info://prompt-guide` | Markdown prompt writing guide for each provider |
| `image://{id}/view{?format,width,height,quality}` | Image with optional transforms (CDN-style) |
| `image://{id}/metadata` | Sidecar JSON with generation provenance |
| `image://list` | JSON array of all registered images |

The `image://{id}/view` resource template supports:
- No params -> original bytes unchanged
- `format` -> convert to png/webp/jpeg via `processing.convert_format()`
- `width` + `height` -> center-crop via `processing.crop_to_dimensions()`
- `width` only or `height` only -> proportional resize
- `quality` -> compression quality for lossy formats (default 90)

### Prompts

| Prompt | Description |
|--------|-------------|
| `select_provider` | Guides Claude on provider strengths and selection criteria |
| `sd_prompt_guide` | Guides Claude on SD prompt writing: CLIP tag format for SD 1.5/SDXL, natural language for Flux, negative prompts, BREAK syntax |

## Configuration

All environment variables use the `IMAGE_GENERATION_MCP_` prefix.

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `IMAGE_GENERATION_MCP_SCRATCH_DIR` | Path | `~/.image-generation-mcp/images/` | Scratch directory for saved images |
| `IMAGE_GENERATION_MCP_OPENAI_API_KEY` | str | *(none)* | OpenAI API key; enables OpenAI provider |
| `IMAGE_GENERATION_MCP_GOOGLE_API_KEY` | str | *(none)* | Google API key; enables Gemini provider |
| `IMAGE_GENERATION_MCP_SD_WEBUI_HOST` | str | *(none)* | SD WebUI URL; enables SD WebUI provider (deprecated alias: `A1111_HOST`) |
| `IMAGE_GENERATION_MCP_DEFAULT_PROVIDER` | str | `"auto"` | Default provider (`auto`, `gemini`, `openai`, `sd_webui`, `placeholder`) |
| `IMAGE_GENERATION_MCP_READ_ONLY` | bool | `true` | When true, hides write-tagged tools |

## Future Work

- **More providers:** BFL/FLUX, Stability, Ideogram, FAL, Replicate
- **ComfyUI provider:** Workflow-based API with CLIP text encode nodes
- **Background removal:** Automated subject isolation (editing, composition, and masking shipped in epic #256)
- **Rate limiting:** Per-provider request throttling
- **Auto-cleanup:** TTL-based scratch directory cleanup
- **Response caching:** Cache frequently-requested transforms
