# OpenAI Provider

Image generation via OpenAI's Images API. Best for text rendering, logos, typography, and general-purpose generation.

## Setup

Set your OpenAI API key:

```
IMAGE_GENERATION_MCP_OPENAI_API_KEY=sk-...
```

The provider registers automatically when this variable is set.

## Supported models

| Model                  | Status             | Formats         | Notes                                                                                           |
| ---------------------- | ------------------ | --------------- | ----------------------------------------------------------------------------------------------- |
| `gpt-image-2`          | Flagship (default) | PNG, JPEG, WebP | Highest fidelity; no transparent-background support (use `gpt-image-1.5` if you need alpha)     |
| `gpt-image-1.5`        | Current            | PNG, JPEG, WebP | Production flagship with transparent-background support                                         |
| `gpt-image-1-mini`     | Current            | PNG, JPEG, WebP | Cheaper variant; capabilities assumed to match gpt-image-1                                      |
| `gpt-image-1`          | Legacy             | PNG, JPEG, WebP | Native format selection; superseded by 1.5 / 2                                                  |
| `chatgpt-image-latest` | Current (alias)    | PNG, JPEG, WebP | Floating alias to the current ChatGPT image model; pin a concrete id for reproducible workflows |
| `dall-e-3`             | Legacy             | PNG only        | Deprecated May 2026                                                                             |

## Aspect ratios and sizes

### gpt-image-1

| Aspect ratio | Size        |
| ------------ | ----------- |
| `1:1`        | `1024x1024` |
| `16:9`       | `1536x1024` |
| `9:16`       | `1024x1536` |
| `3:2`        | `1536x1024` |
| `2:3`        | `1024x1536` |

### dall-e-3

| Aspect ratio | Size        |
| ------------ | ----------- |
| `1:1`        | `1024x1024` |
| `16:9`       | `1792x1024` |
| `9:16`       | `1024x1792` |
| `3:2`        | `1792x1024` |
| `2:3`        | `1024x1792` |

## Quality levels

| Quality param | gpt-image-1 API value       | dall-e-3 API value |
| ------------- | --------------------------- | ------------------ |
| `standard`    | `auto` (lets OpenAI choose) | `standard`         |
| `hd`          | `high`                      | `hd`               |

`quality` does not control output size. Use `resolution` for that (see [Resolution tiers](#resolution-tiers) below).

## Resolution tiers

The `resolution` parameter controls output size, independently of `quality`. Only `gpt-image-2` honors `high`/`max`; every other model (including `gpt-image-1.5`, `gpt-image-1-mini`, `gpt-image-1`, `chatgpt-image-latest`, and both dall-e models) ignores `resolution` and always renders at its standard size.

| Aspect ratio | `standard`  | `high`      | `max`       |
| ------------ | ----------- | ----------- | ----------- |
| `1:1`        | `1024x1024` | `1920x1920` | `2880x2880` |
| `16:9`       | `1536x1024` | `2560x1440` | `3840x2160` |
| `9:16`       | `1024x1536` | `1440x2560` | `2160x3840` |
| `3:2`        | `1536x1024` | `2304x1536` | `3504x2336` |
| `2:3`        | `1024x1536` | `1536x2304` | `2336x3504` |

`max` reaches up to 4K (`3840x2160`) for landscape and portrait ratios; output beyond `2560x1440` total pixels is documented by OpenAI as experimental. Use `high` for a more conservative print-resolution target before reaching for `max`.

**Standard-tier sizing is not aspect-ratio-exact.** The `standard` size table above predates the `resolution` parameter and was chosen for convenient round numbers rather than exact ratio matches: `16:9` at `1536x1024` is actually 1.5:1, not 1.778:1. Raising `resolution` to `high` or `max` on `gpt-image-2` selects a different size table with its own approximation, so the output can reframe slightly when you switch tiers. This is tracked as issue #340.

## Negative prompts

OpenAI does not have native negative prompt support. When a `negative_prompt` is provided, it is appended to the prompt as:

```
{prompt}

Avoid: {negative_prompt}
```

## Background transparency

The `background` parameter controls whether the generated image has a transparent or opaque background.

| Model         | `background` support                                               |
| ------------- | ------------------------------------------------------------------ |
| `gpt-image-1` | Supported (passed to the API as-is: `"opaque"` or `"transparent"`) |
| `dall-e-3`    | Not supported (parameter is ignored)                               |

When `background="transparent"` is used with `gpt-image-1`, the output PNG includes an alpha channel.

## Revised prompt

`dall-e-3` may rewrite your prompt for better results. The rewritten prompt is included in the response metadata as `revised_prompt`. `gpt-image-1` does not rewrite prompts.

## Prompt style

OpenAI models work best with natural language descriptions:

```
A professional product photo of white sneakers on a clean white background,
studio lighting, sharp focus, commercial photography style
```

For text rendering:

```
A minimalist logo for "Acme Corp" with clean sans-serif typography,
blue and white color scheme, modern design
```

## Per-call model selection

The `model` parameter on `generate_image` overrides the provider's default model for a single request. Size table and format selection adjust automatically:

```
generate_image(prompt="...", provider="openai", model="dall-e-3")
```

When switching to `dall-e-3`, the larger DALL-E 3 size table is used and output format is forced to PNG (the only format DALL-E 3 supports). When switching to `gpt-image-1`, the standard size table and configured output format are used.

Use `list_providers` to discover available models.

## Capability discovery

At startup, the provider calls `client.models.list()` to discover which image models are available on your API key. It filters to known image models (`gpt-image-2`, `gpt-image-1.5`, `gpt-image-1`, `gpt-image-1-mini`, `chatgpt-image-latest`, `dall-e-3`, `dall-e-2`) and maps each to a capabilities object with model-specific defaults (supported sizes, formats, features).

If the API call fails (network error, invalid key), the provider is marked as **degraded**: it remains available for generation but with an empty model list in the capabilities response.

## Cost

OpenAI charges per image generated. Pricing varies by model, size, and quality level. See the [OpenAI pricing page](https://openai.com/api/pricing/) for current rates.

`gpt-image-1` is generally more expensive than `dall-e-3` but produces higher quality output with more flexible format options.

## Image input (editing and composition)

The gpt-image family (`gpt-image-2`, `gpt-image-1.5`, `gpt-image-1`, `gpt-image-1-mini`) accepts reference images through the `transform_image` tool. The provider routes these requests through OpenAI's `images.edit` endpoint, supporting both single-image edits and multi-image composition with up to 16 reference images per call.

`dall-e-3` and `dall-e-2` do not support reference-image input. Supplying reference images to either model raises an unsupported-input error (`ImageInputUnsupported`).

### Capability fields

The `list_providers` response includes two fields on each model entry that clients use to determine routing:

| Field                  | Type | Meaning                                                    |
| ---------------------- | ---- | ---------------------------------------------------------- |
| `supports_image_input` | bool | `true` for all gpt-image models; `false` for dall-e models |
| `max_input_images`     | int  | `16` for gpt-image models; absent for dall-e models        |

Use these fields to decide which provider and model to pass to `transform_image`. When `supports_image_input` is `false`, pass the images to a Gemini provider instead.

### Supported reference image formats

The endpoint accepts PNG, JPEG, and WebP references. Each reference image is sent as a named file tuple using the source image's content type.

### Masks

The `transform_image` tool accepts a `mask` parameter for region-targeted inpainting on gpt-image models. When supplied, the mask is forwarded to OpenAI's `images.edit` endpoint alongside the reference images. When no mask is supplied, edits apply globally using the reference images as compositional context.

The mask must match the first reference image's dimensions and format and carry an alpha channel. OpenAI enforces this at the API level; a mismatch returns an HTTP 400 error.

Use `list_providers` to check the `supports_mask` field on each model before passing a mask. Currently `true` for all gpt-image models (`gpt-image-1`, `gpt-image-1.5`, `gpt-image-1-mini`, `gpt-image-2`); `false` for dall-e models. Passing a mask to a provider or model that does not support it raises an error.

## Error handling

| Error                    | Cause                                 | Resolution                                               |
| ------------------------ | ------------------------------------- | -------------------------------------------------------- |
| Content policy rejection | Prompt violates OpenAI content policy | Modify the prompt to comply with OpenAI's usage policies |
| Connection error         | Cannot reach OpenAI API               | Check network connectivity and API key validity          |
| API error (HTTP 429)     | Rate limited                          | Wait and retry; consider reducing request frequency      |
