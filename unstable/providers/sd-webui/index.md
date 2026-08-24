# SD WebUI (Stable Diffusion WebUI)

Image generation via the [Stable Diffusion WebUI](https://github.com/AUTOMATIC1111/stable-diffusion-webui) REST API. Best for photorealism, portraits, anime, and artistic styles.

> **Compatible with** AUTOMATIC1111, Forge, reForge, and Forge-neo.

## Setup

1. Install and start one of the compatible WebUI forks with API access enabled:

   ```
   # Start WebUI with API enabled
   python launch.py --api
   ```

1. Set the host URL:

   ```
   IMAGE_GENERATION_MCP_SD_WEBUI_HOST=http://localhost:7860
   ```

The provider registers automatically when `IMAGE_GENERATION_MCP_SD_WEBUI_HOST` is set.

> **Compatibility:** SD WebUI version 1.6 (or equivalent Forge/reForge version) or later is required. The split `sampler_name` + `scheduler` API was introduced in 1.6; earlier versions do not support the `scheduler` field.

## Model-aware presets

The provider auto-detects the SD architecture from the checkpoint name and applies optimized generation parameters:

### SD 1.5 (default)

Used when no XL/Lightning/Turbo tag is found in the checkpoint name.

| Parameter       | Value    |
| --------------- | -------- |
| Base resolution | 768px    |
| Steps           | 30       |
| CFG scale       | 7.0      |
| Sampler         | DPM++ 2M |
| Scheduler       | Karras   |

| Aspect ratio | Size      |
| ------------ | --------- |
| `1:1`        | `768x768` |
| `16:9`       | `912x512` |
| `9:16`       | `512x912` |
| `3:2`        | `768x512` |
| `2:3`        | `512x768` |

### SDXL

Used when checkpoint name contains `sdxl`, `xl_`, `_xl`, or `-xl`.

| Parameter       | Value    |
| --------------- | -------- |
| Base resolution | 1024px   |
| Steps           | 35       |
| CFG scale       | 7.5      |
| Sampler         | DPM++ 2M |
| Scheduler       | Karras   |

| Aspect ratio | Size        |
| ------------ | ----------- |
| `1:1`        | `1024x1024` |
| `16:9`       | `1344x768`  |
| `9:16`       | `768x1344`  |
| `3:2`        | `1216x832`  |
| `2:3`        | `832x1216`  |

### SDXL Lightning/Turbo

Used when checkpoint name contains XL tags AND `lightning` or `turbo`.

| Parameter       | Value     |
| --------------- | --------- |
| Base resolution | 1024px    |
| Steps           | 6         |
| CFG scale       | 2.0       |
| Sampler         | DPM++ SDE |
| Scheduler       | Karras    |

Sizes are the same as standard SDXL.

### Flux Dev

Used when checkpoint name contains `flux` (without `schnell`). Requires [Forge](https://github.com/lllyasviel/stable-diffusion-webui-forge) or compatible fork with Flux support.

| Parameter           | Value                |
| ------------------- | -------------------- |
| Base resolution     | 1024px               |
| Steps               | 20                   |
| CFG scale           | 1.0                  |
| Distilled CFG scale | 3.5 (Forge-specific) |
| Sampler             | Euler                |
| Scheduler           | Simple               |
| Negative prompt     | Not supported        |

Sizes are the same as SDXL.

### Flux Schnell

Used when checkpoint name contains both `flux` and `schnell`. Optimized for fast inference.

| Parameter           | Value                |
| ------------------- | -------------------- |
| Base resolution     | 1024px               |
| Steps               | 4                    |
| CFG scale           | 1.0                  |
| Distilled CFG scale | 3.5 (Forge-specific) |
| Sampler             | Euler                |
| Scheduler           | Simple               |
| Negative prompt     | Not supported        |

Sizes are the same as SDXL.

## Prompt style

Different SD architectures use different prompt styles. Check `list_providers` to see each model's `prompt_style` field.

### SD 1.5 / SDXL / Lightning (`prompt_style: "clip"`)

Use comma-separated CLIP tags ordered by importance. Include quality tags (`masterpiece, best quality`) and a negative prompt for best results. See the [Prompt Writing Guide](https://pvliesdonk.github.io/image-generation-mcp/unstable/guides/prompt-writing/index.md) for detailed tag recommendations and BREAK syntax.

### Flux (`prompt_style: "natural_language"`)

Flux models use a T5 text encoder instead of CLIP. Write prompts as natural language descriptions: complete sentences, not comma-separated tags.

**Do NOT use with Flux:**

- Quality tags (`masterpiece`, `best quality`): meaningless to T5
- Negative prompts: Flux does not support them (the server omits them automatically)
- `BREAK` syntax: Flux does not use CLIP chunking

**Example:**

```
A dramatic mountain landscape at sunset with towering peaks reflected
in a perfectly still alpine lake, storm clouds lit orange and purple
by the setting sun
```

## Checkpoint override

### Server default (env var)

To set a default checkpoint for all generation requests:

```
IMAGE_GENERATION_MCP_SD_WEBUI_MODEL=realisticVisionV60B1_v51VAE.safetensors
```

When `SD_WEBUI_MODEL` is set, the provider sends `override_settings.sd_model_checkpoint` in the API payload and uses the checkpoint name for preset detection.

### Per-call override (model parameter)

The `model` parameter on `generate_image` overrides the server default for a single request. Preset detection (steps, CFG, sampler, sizes) uses the per-call model name, not the constructor default:

```
generate_image(prompt="...", provider="sd_webui", model="dreamshaperXL_v21.safetensors")
```

Use `list_providers` to discover available checkpoints and their model IDs.

## Image input (img2img)

Any discovered SD WebUI checkpoint accepts a single reference image through the `transform_image` tool. When a reference image is supplied, the provider calls `/sdapi/v1/img2img` instead of `/sdapi/v1/txt2img`.

The `strength` parameter controls `denoising_strength` in the SD WebUI API payload. Values range from 0.0 to 1.0 (default 0.75 when omitted). Lower values preserve more of the reference image; higher values allow the model to regenerate more of the output.

`list_providers` reports `supports_image_input: true` and `max_input_images: 1` for every discovered checkpoint. Pass exactly one reference image; passing more than one returns an error.

## Background transparency

The `background` parameter is **not supported** by SD WebUI. When `background="transparent"` is passed, it is silently ignored (a debug log is emitted). Stable Diffusion does not natively support transparent background generation.

## Resolution

The `resolution` parameter is **not supported** by SD WebUI. The provider always renders at the checkpoint/preset size for the requested aspect ratio (see the per-architecture size tables above) and reports "resolution": "standard" in provider metadata, regardless of the requested tier. When a non-standard tier (`high` or `max`) is requested, it is clamped to `standard` and a WARNING-level `resolution_clamped` log is emitted (matching the Gemini and OpenAI providers).

## Capability discovery

At startup, the provider calls:

- `GET /sdapi/v1/sd-models`: lists all installed checkpoints
- `GET /sdapi/v1/options`: identifies the currently active checkpoint

Each checkpoint is mapped to a `ModelCapabilities` object with architecture-specific defaults (resolution, steps, CFG, sampler) based on the same name detection used for generation presets.

If the SD WebUI server is unreachable (connection error or timeout), the provider is marked as **degraded**: it remains available for generation but with an empty model list in the capabilities response. This prevents a slow or offline SD WebUI instance from blocking server startup.

## Negative prompts

SD WebUI has native negative prompt support via the `negative_prompt` field in the API payload. This is more effective than OpenAI's "Avoid:" workaround.

Flux models do not support negative prompts. When a Flux checkpoint is detected, the `negative_prompt` field is omitted from the API payload entirely. If a negative prompt is provided, it is silently ignored with a debug log.

See the [Prompt Writing Guide](https://pvliesdonk.github.io/image-generation-mcp/unstable/guides/prompt-writing/index.md) for recommended negative prompts.

## Progress polling

During image generation, the provider concurrently polls `GET /sdapi/v1/progress` every 2 seconds to report step-level progress. Progress updates are surfaced through `show_image` polling responses as `progress` (0.0 to 1.0) and `progress_message` (such as `"Step 9/30 (ETA 12s)"`).

- **First poll fires immediately** (poll-then-sleep pattern): even fast generations receive at least one progress update
- **Polling failures are silently handled**: if the progress endpoint returns an error or is unreachable, generation continues uninterrupted (failures logged at debug level)
- **Polling stops automatically** when generation completes (the polling task is cancelled in a `finally` block)

No additional configuration is required. Progress polling activates whenever the fire-and-forget pattern is used (which is always, as of v1.1.0).

## Metadata

The provider extracts from the SD WebUI response:

- **seed**: the random seed used for generation (useful for reproducibility)
- **model name**: the active checkpoint name (from response `info` JSON)
- **size**: pixel dimensions used
- **steps**: number of diffusion steps

## Timeout

The default timeout is **180 seconds**. SDXL at high resolution on consumer GPUs can take 30-60+ seconds. If you experience timeouts, ensure your WebUI is responding.

## Deprecated env var aliases

The previous `A1111_HOST` and `A1111_MODEL` env var names are still accepted as deprecated aliases:

| Deprecated                         | Current                               |
| ---------------------------------- | ------------------------------------- |
| `IMAGE_GENERATION_MCP_A1111_HOST`  | `IMAGE_GENERATION_MCP_SD_WEBUI_HOST`  |
| `IMAGE_GENERATION_MCP_A1111_MODEL` | `IMAGE_GENERATION_MCP_SD_WEBUI_MODEL` |

## Troubleshooting

| Error            | Cause                 | Resolution                                                       |
| ---------------- | --------------------- | ---------------------------------------------------------------- |
| Connection error | Cannot reach SD WebUI | Verify WebUI is running with `--api` flag at the configured host |
| Timeout (180 s)  | Generation too slow   | Check GPU load; consider a faster model or lower resolution      |
| HTTP 404         | Wrong API endpoint    | Verify the WebUI version supports `/sdapi/v1/txt2img`            |
