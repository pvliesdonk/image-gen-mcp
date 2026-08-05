# MCP Tools

image-generation-mcp exposes four domain tools plus two auto-generated resource-bridge tools to MCP clients.

## generate_image

Generate an image from a text prompt. Returns immediately with a `status: "generating"` response while the image is generated in the background (typically 30-90 seconds). Use `check_generation_status(image_id)` to wait for completion, then call `show_image(uri=original_uri)` **once** to display the result. Check each model's `prompt_style` in `list_providers` to choose CLIP tags vs. natural language prompts.

| Property | Value |
|----------|-------|
| **Tags** | `write` (hidden in read-only mode) |
| **Annotations** | `readOnlyHint: false`, `destructiveHint: false`, `openWorldHint: true` |
| **Task** | `task=True` (retained for forward compatibility; no longer blocks) |
| **Pattern** | Fire-and-forget: returns in under 1 second. Poll via `check_generation_status`. Display via `show_image`. |

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `prompt` | str | *(required)* | Text description of the desired image |
| `provider` | str | `"auto"` | Provider name (`openai`, `sd_webui`, `placeholder`) or `"auto"` for keyword-based selection |
| `negative_prompt` | str | `null` | Things to avoid in the image. Native support on SD WebUI (SD 1.5/SDXL only; Flux models do NOT support negative prompts); appended as "Avoid:" on OpenAI. |
| `aspect_ratio` | str | `"1:1"` | Desired ratio: `1:1`, `16:9`, `9:16`, `3:2`, `2:3`. Gemini also supports: `3:4`, `4:3`, `4:5`, `5:4`, `4:1`, `1:4`, `8:1`, `1:8`, `21:9` |
| `quality` | str | `"standard"` | Quality level: `standard` (fast, lower cost) or `hd` (higher quality, enables model reasoning on Gemini, `high` tier on OpenAI). Independent of `resolution`, which controls output size. |
| `resolution` | str | `"standard"` | Output size tier: `standard`, `high`, or `max`. `high`/`max` unlock higher resolutions where supported: on Gemini, 2K/4K (except the 1K-only `gemini-3.1-flash-lite-image` and `gemini-2.5-flash-image`, which clamp down to 1K); on OpenAI, only `gpt-image-2` goes beyond standard (up to 4K). Every other model ignores this. Check `supported_resolutions` in `list_providers` before relying on `high`/`max` for a specific model. |
| `background` | str | `"opaque"` | Background mode: `opaque` or `transparent`. Supported by OpenAI's `gpt-image-1` / `gpt-image-1.5` / `gpt-image-1-mini` (not `gpt-image-2` or `chatgpt-image-latest`, which drop transparency) and Placeholder. SD WebUI ignores this parameter. |
| `model` | str | `null` | Specific model to use (such as an SD WebUI checkpoint name or `"dall-e-3"` for OpenAI). Overrides the provider's default. Use `list_providers` to see available model IDs. |

### Return value

Returns immediately with a `ToolResult` containing:

1. **TextContent**: JSON metadata with `status: "generating"`:
2. **ResourceLink**: URI reference to `image://{id}/view` (image pending)

```json
{
  "status": "generating",
  "image_id": "a1b2c3d4e5f6",
  "prompt": "watercolor painting of a mountain landscape at sunset",
  "provider": "openai",
  "prompt_style": null,
  "original_uri": "image://a1b2c3d4e5f6/view",
  "metadata_uri": "image://a1b2c3d4e5f6/metadata",
  "resource_template": "image://a1b2c3d4e5f6/view{?format,width,height,quality,crop_x,crop_y,crop_w,crop_h,rotate,flip}"
}
```

Use `check_generation_status(image_id)` to poll for completion, then call `show_image(uri=original_uri)` **once** to display the finished image.

### Fire-and-forget workflow

The tool uses a fire-and-forget pattern to avoid client tool-execution timeouts (about 45 seconds on Claude.ai/Desktop/Android):

1. **`generate_image`** returns in under 1 second with `"status": "generating"` and a pre-allocated `image_id`
2. **Background task** generates the image and registers it in the scratch directory
3. **`check_generation_status`** polls for status (lightweight, no UI card):
    - `{"status": "generating", "progress": 0.3, "progress_message": "Step 9/30 (ETA 12s)", ...}`: still in progress
    - `{"status": "completed"}`: ready to display
    - `{"status": "failed", "error": "..."}`: generation failed
4. **`show_image`** displays the finished image **once** when status is `"completed"`

The `image://list` resource also includes pending generations with their status.

!!! tip "Why a separate polling tool?"
    `show_image` renders a full image viewer card with thumbnail. Calling it repeatedly to poll creates a distracting stack of cards in the conversation UI. `check_generation_status` returns minimal JSON text, keeping polling invisible to the user.

### Cost confirmation (elicitation)

When all of these conditions are met, `generate_image` asks the user to confirm before calling the provider:

1. The resolved provider is in `IMAGE_GENERATION_MCP_PAID_PROVIDERS` (default: `"openai"`)
2. The MCP client supports [elicitation](https://modelcontextprotocol.io/specification/2025-06-18/server/utilities/elicitation) (advertised via `ClientCapabilities.elicitation`)

If the user declines or cancels, the tool returns a cancellation message without making the API call. If the client does not support elicitation, generation proceeds without confirmation (current behavior preserved).

!!! tip "Elicitation client support"
    Elicitation was added in the MCP spec 2025-06-18 revision. As of this writing, few clients support it. The confirmation is a progressive enhancement that activates automatically on capable clients and is invisible on others.

### Example

```
User: Generate a watercolor painting of a mountain landscape at sunset

Tool call: generate_image
  prompt: "watercolor painting of a mountain landscape at sunset,
           warm colors, dramatic sky"
  aspect_ratio: "16:9"
  quality: "hd"
```

When picking `model`, consult each entry's `style_profile.style_hints` and `style_profile.incompatible_styles` from `list_providers`; check the top-level `warnings` array to avoid deprecated models for new work. The [Model Catalog](providers/model-catalog.md) lists all known models with their full profiles.

---

## transform_image

Edit or transform an existing image using a model that accepts image input (image-to-image). Accepts one or more reference images alongside a prompt describing the desired change. Returns immediately with a `status: "generating"` response while the transformation runs in the background. Use `check_generation_status(image_id)` to wait for completion, then call `show_image(uri=original_uri)` **once** to display the result.

`transform_image` is distinct from `edit_image` (which applies local geometry transforms such as crop, rotate, and flip directly in the server) and from `generate_image` (text-only, no reference image).

For task-oriented walkthroughs (editing, composition, masking, and SD `strength`), see the [Image input guide](guides/image-input.md).

| Property | Value |
|----------|-------|
| **Tags** | `write` (hidden in read-only mode) |
| **Annotations** | `readOnlyHint: false`, `destructiveHint: false`, `openWorldHint: true` |
| **Task** | `task=True` |
| **Pattern** | Fire-and-forget: returns in under 1 second. Poll via `check_generation_status`. Display via `show_image`. |

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `prompt` | str | *(required)* | Description of the desired edit or transformation (natural language) |
| `reference_images` | list[str] | *(required)* | One or more gallery `image_id` values, `image://` URIs, or (when `IMAGE_GENERATION_MCP_ALLOW_LOCAL_FILE_INPUT=true`) local file paths to use as source images; check `max_input_images` in `list_providers` for each provider's reference-count limit (some accept one, others up to 16 for composition) |
| `provider` | str | `"auto"` | Provider to use, or `"auto"`. Image-to-image needs a provider that reports `supports_image_input` in `list_providers` |
| `negative_prompt` | str | `null` | Things to avoid in the result (provider support varies) |
| `aspect_ratio` | str | `"1:1"` | Desired aspect ratio of the output image |
| `quality` | str | `"standard"` | Quality level: `standard` or `hd`. Independent of `resolution`, which controls output size. |
| `resolution` | str | `"standard"` | Output size tier: `standard`, `high`, or `max`. `high`/`max` unlock higher resolutions where supported: on Gemini, 2K/4K (except the 1K-only `gemini-3.1-flash-lite-image` and `gemini-2.5-flash-image`, which clamp down to 1K); on OpenAI, only `gpt-image-2` goes beyond standard (up to 4K). Every other model ignores this. Check `supported_resolutions` in `list_providers` before relying on `high`/`max` for a specific model. |
| `background` | str | `"opaque"` | Background mode: `opaque` or `transparent` (provider-dependent) |
| `model` | str | `null` | Specific model ID; see `list_providers` |
| `strength` | float | `null` | SD WebUI only: denoising strength for image-to-image (0.0 to 1.0, default 0.75 when omitted). Lower values preserve more of the reference image; higher values regenerate more. Other providers ignore it. Has no effect without a reference image. |
| `mask` | str | `null` | Inpainting mask: a gallery `image_id`, `image://` URI, or local file path (when `IMAGE_GENERATION_MCP_ALLOW_LOCAL_FILE_INPUT=true`). The mask defines the region to repaint and is applied against the first reference image. Only providers with `supports_mask: true` in `list_providers` accept this parameter (currently OpenAI gpt-image models). At least one `reference_images` entry is required when a mask is supplied. Providers without mask support return an error if a mask is passed. |

### Reference image input forms

Each entry in `reference_images` is resolved in order:

1. **Gallery `image_id`**: a 12-character hex ID from a prior `generate_image` or `transform_image` call, such as `"a1b2c3d4e5f6"`.
2. **`image://` URI**: a full resource URI, such as `"image://a1b2c3d4e5f6/view"`.
3. **Local file path**: absolute path on the server host, such as `"/home/user/photo.png"`. Only accepted when `IMAGE_GENERATION_MCP_ALLOW_LOCAL_FILE_INPUT=true`; rejected with an error otherwise.

A gallery `image_id` may itself be an **imported** image, brought into the
gallery from a URL, an upload, or inline bytes via `fetch_image`,
`ingest_base64_image`, or `create_upload_link`, not only a `generate_image` /
`transform_image` output. See [Image input](guides/image-input.md#getting-an-external-image-into-the-gallery).

Call `list_providers` and inspect `supports_image_input` and `max_input_images` on each model to confirm which provider can handle your input count. Reference-count limits vary by model: SD WebUI is limited to a single reference, while Gemini supports several (more on the Gemini 3 models) and OpenAI's gpt-image family supports the most for multi-image composition. `max_input_images` carries the authoritative per-model value; `dall-e-3` and `dall-e-2` do not accept reference images. See the [Image input guide](guides/image-input.md) for the current capability matrix.

### Return value

Returns immediately with a `ToolResult` containing:

1. **TextContent**: JSON metadata with `status: "generating"`:
2. **ResourceLink**: URI reference to `image://{id}/view` (image pending)

```json
{
  "status": "generating",
  "image_id": "b2c3d4e5f6a1",
  "prompt": "replace the background with a sunset sky",
  "provider": "gemini",
  "source_image_ids": ["a1b2c3d4e5f6"],
  "original_uri": "image://b2c3d4e5f6a1/view",
  "metadata_uri": "image://b2c3d4e5f6a1/metadata"
}
```

The `source_image_ids` field records the gallery IDs of the resolved reference images for provenance.

Use `check_generation_status(image_id)` to poll for completion, then call `show_image(uri=original_uri)` **once** to display the finished image.

### Example

```
User: Replace the background of my last image with a sunset sky

Tool call: transform_image
  prompt: "Replace the background with a dramatic sunset sky, warm orange and pink tones"
  reference_images: ["a1b2c3d4e5f6"]
  provider: "gemini"
  aspect_ratio: "16:9"
```

---

## check_generation_status

Lightweight status check for background image generation. Returns a short JSON string with `status`, `image_id`, and progress info (no image data, no heavy UI card).

| Property | Value |
|----------|-------|
| **Tags** | *(none, always visible)* |
| **Annotations** | `readOnlyHint: true`, `destructiveHint: false`, `openWorldHint: false`, `idempotentHint: true` |

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `image_id` | str | *(required)* | The `image_id` returned by `generate_image` |

### Return values

| Status | Meaning | Next step |
|--------|---------|-----------|
| `"generating"` | Still in progress | Wait and check again |
| `"completed"` | Image ready | Call `show_image(uri=original_uri)` |
| `"failed"` | Generation failed | Report `error` to the user |
| `"unknown"` | ID not found | Invalid or expired `image_id` |

---

## show_image

Display a completed image with optional on-demand transforms. Accepts a full `image://` resource URI with transforms encoded in the query string.

**Only call this for completed images.** Use `check_generation_status` to poll, then call `show_image` once when status is `"completed"`.

| Property | Value |
|----------|-------|
| **Tags** | *(none, always visible, read-only operation)* |
| **Annotations** | `readOnlyHint: true`, `destructiveHint: false`, `openWorldHint: false` |
| **Task** | No |
| **MCP App** | `ui://image-viewer/view.html` (interactive viewer in supported clients) |

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `uri` | str | *(required)* | Full `image://` resource URI, such as `image://a1b2c3/view?format=webp&width=512` |

Transforms are encoded in the URI query string using the same parameters as the `image://{id}/view` resource template: `format`, `width`, `height`, `quality`.

### Return value

Returns a `ToolResult` with:

1. **ImageContent**: a WebP thumbnail preview (max 512 px, always under 1 MB) for inline display in MCP clients. This is always WebP regardless of the requested format.
2. **TextContent**: JSON metadata with the full-resolution details:

```json
{
  "image_id": "a1b2c3d4e5f6",
  "prompt": "watercolor painting of a mountain landscape at sunset",
  "provider": "openai",
  "model": "gpt-image-1",
  "prompt_style": null,
  "dimensions": [1024, 683],
  "thumbnail_dimensions": [512, 342],
  "original_size_bytes": 3145728,
  "format": "image/png",
  "transforms_applied": {}
}
```

The `model` field contains the specific model used by the provider (such as `"gpt-image-1"` or `"dreamshaper_xl"`), or `null` if the provider does not report a model name.

`show_image` returns metadata and an inline thumbnail only; it does not mint a download URL. For an out-of-band full-resolution URL, call `create_download_link` with the image's `image://` URI or bare id (HTTP transport only). For in-band full-resolution access, read the `image://{id}/view` resource, optionally with `format`/`width`/`height`/`quality` transforms.

The `dimensions` field reports the actual image size (or the transformed size if transforms were requested). The `thumbnail_dimensions` field reports the size of the inline preview, which is capped at 512 px. When `dimensions` and `thumbnail_dimensions` differ, the inline preview is a downscaled version; use the `image://` resource URI or `create_download_link` for full resolution.

### Examples

```
# Show the original image
show_image(uri="image://a1b2c3d4e5f6/view")

# Show resized to 512px wide as WebP
show_image(uri="image://a1b2c3d4e5f6/view?format=webp&width=512")

# Show center-cropped to 256x256
show_image(uri="image://a1b2c3d4e5f6/view?width=256&height=256")
```

---

## edit_image

Open an image for interactive editing (crop, rotate, flip) in the image viewer UI. The user edits in the viewer widget and saves as a new image. Always edits the original image (resource template transforms are ephemeral and model-facing; editor transforms are persistent and user-facing).

| Property | Value |
|----------|-------|
| **Tags** | *(none, read-only, always visible)* |
| **Annotations** | `readOnlyHint: true`, `destructiveHint: false`, `openWorldHint: false` |
| **MCP App** | Opens `ui://image-viewer/view.html` widget |

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `image_id` | str | *(required)* | ID of the image to edit. Use `image://list` to browse available image IDs. |

### Return value

Returns a `ToolResult` with:

1. **TextContent**: JSON metadata with `editable: true` to activate the editor UI:

```json
{
  "editable": true,
  "image_id": "a1b2c3d4e5f6",
  "content_type": "image/png",
  "dimensions": [640, 360],
  "prompt": "watercolor painting of a mountain landscape",
  "provider": "openai"
}
```

2. **ImageContent**: Full-resolution image as base64 (not a thumbnail). The viewer UI uses this to initialize the Cropper.js editor.

### Editor UI

When `editable: true` is received by the MCP Apps widget, it activates the Cropper.js-based editor with:

- **Crop**: Interactive crop box with aspect ratio presets (Free, 1:1, 16:9, 4:3)
- **Rotate**: 90° counter-clockwise / clockwise buttons (lossless)
- **Flip**: Horizontal and vertical flip buttons (lossless)
- **Reset**: Resets all pending edits
- **Save as new image**: Applies transforms server-side and saves as a new image record with `source_image_id` provenance
- **Cancel**: Returns to the waiting state

Saving calls the internal `_save_edited_image` app-only tool and then shows the new image via `show_image`.

### Saved image provenance

Saved images include a `source_image_id` field in their sidecar JSON referencing the original. The `image://{id}/metadata` resource exposes this field.

---

## browse_gallery

Open an interactive visual gallery of all generated images. The gallery renders a responsive thumbnail grid directly in Claude Desktop / claude.ai via the MCP Apps widget.

| Property | Value |
|----------|-------|
| **Tags** | *(none, read-only, always visible)* |
| **Annotations** | `readOnlyHint: true`, `destructiveHint: false`, `openWorldHint: false` |
| **MCP App** | Opens `ui://image-gallery/view.html` widget |

### Parameters

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `origin` | `generated` \| `imported` \| `all` | `generated` | Which images to show. `generated` shows images produced by `generate_image`/`edit_image` plus any in-progress generations; `imported` shows images brought in via upload, fetch, or base64 ingestion; `all` shows both. |

### Return value

JSON with gallery data (for non-UI clients):

```json
{
  "total": 42,
  "page": 1,
  "page_size": 12,
  "origin": "generated",
  "items": [
    {
      "image_id": "a1b2c3d4e5f6",
      "status": "completed",
      "prompt": "a mountain landscape",
      "provider": "openai",
      "dimensions": [1024, 1024],
      "created_at": "2026-03-24T10:00:00+00:00",
      "thumbnail_b64": "<base64-encoded 128px WebP>",
      "content_type": "image/png",
      "origin": "generated"
    }
  ]
}
```

For MCP Apps-capable clients, the gallery widget is rendered inline with:
- Responsive thumbnail grid (3×3 default, adaptive to available width)
- Hover overlay showing prompt excerpt and provider badge
- Download button (`downloadFile` → `openLink` fallback)
- Prev/Next pagination
- Lightbox view on thumbnail click (see below)

---

## gallery_full_image (app-only)

Load full-resolution image data for the gallery lightbox. App-only (not shown to the model); called internally by the gallery UI when a thumbnail is clicked.

| Property | Value |
|----------|-------|
| **Tags** | *(none)* |
| **Annotations** | `readOnlyHint: true`, `destructiveHint: false`, `openWorldHint: false` |
| **MCP App** | `ui://image-gallery/view.html` (app-only, `visibility=["app"]`) |

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `image_id` | str | *(required)* | Image ID to load |

### Return value

```json
{
  "image_id": "a1b2c3d4e5f6",
  "b64": "<base64-encoded image bytes>",
  "content_type": "image/png",
  "dimensions": [1024, 1024],
  "prompt": "a mountain landscape",
  "provider": "openai",
  "created_at": "2026-03-24T10:00:00+00:00"
}
```

Images larger than 1 MB are resized to 1024 px wide WebP before encoding.


---

## delete_image

Permanently delete an image from the scratch directory. Removes the image file and its metadata sidecar. Hidden in read-only mode.

| Property | Value |
|----------|-------|
| **Tags** | `write` (hidden in read-only mode) |
| **Annotations** | `readOnlyHint: false`, `destructiveHint: true`, `openWorldHint: false` |

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `image_id` | str | *(required)* | Image ID to delete (12-character hex string) |

### Return value

Text confirmation with the deleted image's prompt and provider, e.g.:

```
Deleted image a1b2c3d4e5f6 (prompt: 'a mountain landscape', provider: openai)
```

Raises an error if the image ID is not found.

---

## save_style

Save a reusable style preset as a markdown file. Styles are creative briefs that the model interprets per-provider (not prompt fragments). Use to capture a visual direction for reuse across conversations.

| Property | Value |
|----------|-------|
| **Tags** | `write` (hidden in read-only mode) |
| **Annotations** | `readOnlyHint: false`, `destructiveHint: false`, `openWorldHint: false` |

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | str | *(required)* | Style identifier, used as the filename (`{name}.md`). Allowed characters: letters, numbers, hyphens, and `_` (underscore character). |
| `body` | str | *(required)* | Markdown prose describing the visual direction (the creative brief) |
| `tags` | list[str] | `null` | Optional categorization tags for browsing/filtering |
| `provider` | str | `null` | Suggested provider (`auto`, `openai`, `sd_webui`) |
| `aspect_ratio` | str | `null` | Default aspect ratio (such as `16:9`) |
| `quality` | str | `null` | Default quality level (`standard` or `hd`) |

### Return value

```json
{
  "name": "website",
  "created": true
}
```

`created` is `true` for new styles, `false` when overwriting an existing style.

### Example

```
User: Save this as my website style

Tool call: save_style
  name: "website"
  body: "Minimalist flat illustration. Geometric shapes, clean lines.
         Brand palette: deep teal, warm cream, coral accent."
  tags: ["brand", "web"]
  aspect_ratio: "16:9"
  quality: "hd"
```

---

## delete_style

Delete a style preset from disk. Permanently removes the style file and its in-memory entry. Hidden in read-only mode.

| Property | Value |
|----------|-------|
| **Tags** | `write` (hidden in read-only mode) |
| **Annotations** | `readOnlyHint: false`, `destructiveHint: true`, `openWorldHint: false` |

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | str | *(required)* | Style identifier to delete |

### Return value

```json
{
  "name": "website",
  "deleted": true
}
```

Raises an error if the style is not found.

---

## fetch_image

Fetch an image from an `http`/`https` URL into the gallery as an imported entry you can then show, edit, or reference in `transform_image`.

| Property | Value |
|----------|-------|
| **Tags** | `write` (hidden in read-only mode) |
| **Annotations** | `readOnlyHint: false`, `destructiveHint: false`, `openWorldHint: true` |

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `url` | str | *(required)* | The `http(s)` URL of the image to fetch. |

### Return value

Text confirmation with the gallery URI on success:

```
Fetched image into the gallery: image://a1b2c3d4e5f6/view
```

On failure, a message describing why the fetch was rejected, such as an SSRF-blocked target, an HTTP error, a timeout, an oversized body, or content that is not a decodable image.

The fetch is SSRF-hardened: URLs targeting private, loopback, link-local, or cloud-metadata addresses are refused, and redirects are not followed. The download is capped at `IMAGE_GENERATION_MCP_MAX_INPUT_IMAGE_BYTES` (default 20 MiB) with a request timeout of `IMAGE_GENERATION_MCP_FETCH_TIMEOUT_S` (default 30 seconds). The stored provenance is the fetched URL with userinfo, query, and fragment stripped, so a secret-bearing URL never persists to the image's sidecar metadata.

### Example

```
User: Fetch this image and add it to the gallery: https://example.com/photo.png

Tool call: fetch_image
  url: "https://example.com/photo.png"
```

---

## ingest_base64_image

Add an inline base64-encoded image to the gallery as an imported entry you can then show, edit, or reference in `transform_image`.

| Property | Value |
|----------|-------|
| **Tags** | `write` (hidden in read-only mode) |
| **Annotations** | `readOnlyHint: false`, `destructiveHint: false`, `openWorldHint: false` |

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `data` | str | *(required)* | The base64-encoded image bytes. Raw base64, a `data:<type>;base64,...` URI, or line-wrapped base64 are all accepted. |

### Return value

Text confirmation with the gallery URI on success:

```
Ingested image into the gallery: image://a1b2c3d4e5f6/view
```

On failure, a message describing why the image could not be ingested: invalid base64 or an oversized image, or bytes that don't decode as an image.

The decoded size is capped at `IMAGE_GENERATION_MCP_MAX_INPUT_IMAGE_BYTES` (default 20 MiB); oversized or invalid base64 is rejected.

### Example

```
User: Here's a base64 image, add it to the gallery: iVBORw0KGgoAAAANSUhEUgAA...

Tool call: ingest_base64_image
  data: "iVBORw0KGgoAAAANSUhEUgAA..."
```

---

## list_providers

List available image generation providers and their status.

| Property | Value |
|----------|-------|
| **Tags** | *(none, always visible)* |
| **Annotations** | `readOnlyHint: true`, `destructiveHint: false`, `openWorldHint: true`, `idempotentHint: false` |
| **Task** | No |

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `force_refresh` | bool | `false` | When `true`, re-runs capability discovery on all providers before returning. Use when providers may have changed (such as after loading new SD WebUI checkpoints). |

### Return value

JSON object with a `refreshed_at` ISO 8601 timestamp and provider names, availability, and capability information:

```json
{
  "refreshed_at": "2024-03-18T12:00:00+00:00",
  "providers": {
    "placeholder": {
      "available": true,
      "description": "Zero-cost solid-color PNG — instant, no API key, for testing and drafts",
      "capabilities": {
        "provider_name": "placeholder",
        "models": [
          {
            "model_id": "placeholder",
            "display_name": "Placeholder (solid-color PNG)",
            "can_generate": true,
            "can_edit": false,
            "supports_mask": false,
            "supported_aspect_ratios": ["1:1", "16:9", "9:16", "3:2", "2:3"],
            "supported_qualities": ["standard"],
            "supported_resolutions": ["standard"],
            "supported_formats": ["png"],
            "supports_negative_prompt": false,
            "supports_background": true,
            "max_resolution": 640,
            "default_steps": null,
            "default_cfg": null,
            "prompt_style": null
          }
        ],
        "supports_background": true,
        "supports_negative_prompt": false,
        "discovered_at": 1710777600.0,
        "degraded": false
      }
    },
    "openai": {
      "available": true,
      "description": "OpenAI (gpt-image-2 / dall-e-3) — best for text, logos, and general-purpose generation",
      "capabilities": {
        "provider_name": "openai",
        "models": [
          {
            "model_id": "gpt-image-1",
            "display_name": "GPT Image 1",
            "can_generate": true,
            "can_edit": true,
            "supports_mask": true,
            "supported_aspect_ratios": ["1:1", "16:9", "9:16", "3:2", "2:3"],
            "supported_qualities": ["standard", "hd"],
            "supported_resolutions": ["standard"],
            "supported_formats": ["png", "jpeg", "webp"],
            "supports_negative_prompt": false,
            "supports_background": true,
            "max_resolution": 1536,
            "default_steps": null,
            "default_cfg": null,
            "prompt_style": null
          }
        ],
        "supports_background": true,
        "supports_negative_prompt": false,
        "discovered_at": 1710777600.0,
        "degraded": false
      }
    }
  }
}
```

The response is wrapped in an object with `refreshed_at` (ISO 8601 timestamp of when the data was produced) and `providers` (the provider map). Only registered (configured) providers appear in the response. The `capabilities` key is present after startup discovery completes. Degraded providers (where capability discovery failed) show `"degraded": true` with an empty model list.

The `prompt_style` field on each model indicates the recommended prompt format: `"clip"` for SD 1.5/SDXL checkpoints (tag-based), `"natural_language"` for Flux checkpoints, and `null` for providers that do not set a preference (OpenAI, Placeholder).

The JSON envelope contains a top-level `warnings` array (always present, may be empty) listing deprecated or legacy models that are configured. Each entry in `models` may carry a `style_profile` sub-object with `label`, `style_hints`, `incompatible_styles`, `good_example`, `bad_example`, `lifecycle`, and (when set) `deprecation_note`. See [Model Catalog](providers/model-catalog.md) for the full registry.


A `watermark` field is included on models whose outputs carry a persistent identifier. Currently `"synthid"` applies to the Google Gemini Image family (Flash + Pro tiers; all variants embed an invisible Google SynthID watermark on every generation). The field is omitted on models without a declared watermark. Surface this to users when bit-perfect originals are required (forensic chain of custody, certain regulatory contexts).

### Example

```
User: Which image providers are available?

Tool call: list_providers

User: I just loaded a new checkpoint, refresh the list

Tool call: list_providers
  force_refresh: true
```

---

## list_resources / read_resource (auto-generated)

These tools are automatically generated by the [ResourcesAsTools](https://gofastmcp.com/servers/transforms/resources-as-tools) transform. They bridge the gap for MCP clients that only support tools (Claude web chat is one such client) and cannot access resources directly.

| Tool | Description |
|------|-------------|
| `list_resources` | Returns JSON describing all available resources and templates |
| `read_resource` | Reads a specific resource by URI |

### Usage

```
Tool call: list_resources
  → returns JSON array of all image:// and info:// resources

Tool call: read_resource
  uri: "image://a1b2c3d4e5f6/view"
  → returns the full-resolution image

Tool call: read_resource
  uri: "image://a1b2c3d4e5f6/metadata"
  → returns generation metadata JSON

Tool call: read_resource
  uri: "image://list"
  → returns JSON array of all generated images
```

These tools provide access to the same resources documented in [Resources](resources.md), including on-the-fly image transforms via URI template parameters.

---

## create_download_link

Mint a one-time HTTP download URL for a gallery image. Enables server-to-server image transfer between MCP servers (such as saving to a vault or attaching to email). The link expires after a single download or after `ttl_s`, whichever comes first.

Provided by pvl-core's shared capability-link transfer routes. Available only on an HTTP or SSE transport with `IMAGE_GENERATION_MCP_BASE_URL` configured.

| Property | Value |
|----------|-------|
| **Tags** | *(none)* |
| **Annotations** | `readOnlyHint: true` |
| **Task** | No |
| **Transport** | HTTP/SSE only (not available on stdio) |
| **Requires** | `IMAGE_GENERATION_MCP_BASE_URL` |

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `ref` | str | *(required)* | The image to serve: an `image://<id>` URI or a bare 12-hex image id. |
| `ttl_s` | number | (`TRANSFER_TTL_DEFAULT_S`, 3600) | Link lifetime in seconds. Clamped to `TRANSFER_TTL_MAX_S` (default 24 hours). |

### Return value

```json
{
  "url": "https://mcp.example.com/transfer/7f3a...e9b1",
  "expires_in_s": 3600
}
```

The download URL:
- Serves the image's **original bytes** once with the appropriate `Content-Type` (no transforms; for a transformed rendering read the `image://{id}/view` resource with `format`/`width`/`height`/`quality`)
- Returns HTTP 404 after the first download or after the TTL expires
- Does not require bearer token or OIDC auth (the random token is the auth)

### Example workflow

```
User: Generate a photo and save it to my vault

1. generate_image(prompt="sunset photo")
   → {image_id: "a1b2c3...", status: "generating", ...}
2. check_generation_status(image_id="a1b2c3...")
   → status: "completed"
3. create_download_link(ref="image://a1b2c3d4e5f6/view")
   → {url: "https://mcp.example.com/transfer/7f3a...", expires_in_s: 3600}
4. vault-mcp: save_artifact_from_url(url="https://...", path="photos/sunset.jpg")
```

---

## create_upload_link

Mint a one-time HTTP upload URL. The caller POSTs image bytes to the URL, and the server ingests them as an imported gallery image (`origin="imported"`, `origin_source="upload"`). Enables another MCP server or client to push an image into the gallery without a shared filesystem.

Provided by pvl-core's shared capability-link transfer routes. Available only on an HTTP or SSE transport with `IMAGE_GENERATION_MCP_BASE_URL` configured.

| Property | Value |
|----------|-------|
| **Tags** | `write` (hidden in read-only mode) |
| **Annotations** | `readOnlyHint: false` |
| **Task** | No |
| **Transport** | HTTP/SSE only (not available on stdio) |
| **Requires** | `IMAGE_GENERATION_MCP_BASE_URL` |

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `ref` | str | *(required)* | Intended filename or label for the uploaded image (a `.png`/`.jpg`/`.jpeg`/`.webp` extension is checked when present). |
| `ttl_s` | number | (`TRANSFER_TTL_DEFAULT_S`, 3600) | Link lifetime in seconds. Clamped to `TRANSFER_TTL_MAX_S` (default 24 hours). |

### Return value

The tool returns the upload URL:

```json
{
  "url": "https://mcp.example.com/transfer/9c2b...a1d4",
  "expires_in_s": 3600
}
```

After the caller POSTs (or PUTs) the image bytes to that URL, the HTTP response is JSON describing the imported gallery entry:

```json
{
  "image_id": "b7e9c1a2d3f4",
  "uri": "image://b7e9c1a2d3f4/view",
  "origin": "imported"
}
```

The upload URL accepts a single successful upload, then expires. The transfer route is capped at the smaller of `TRANSFER_MAX_UPLOAD_BYTES` (default 100 MiB) and `IMAGE_GENERATION_MCP_MAX_INPUT_IMAGE_BYTES` (default 20 MiB), so an oversized body is rejected with a `413` at the route boundary rather than accepted and then failed during ingestion. The effective image-upload cap is 20 MiB by default.

---

## MCP Apps: Image Viewer

Clients that support [MCP Apps](https://modelcontextprotocol.io/specification/2025-06-18/server/utilities/apps) (Claude Desktop, claude.ai) render an interactive image viewer alongside `show_image` results.

The viewer is a custom HTML resource at `ui://image-viewer/view.html` that:

- Listens for `show_image` tool results via the `@modelcontextprotocol/ext-apps` SDK
- Displays the image with metadata (prompt, provider, model name, dimensions, file size)
- Shows generating, failed, and cancelled states with progress indicators
- Integrates with host theming (colors, fonts, safe area insets) via ext-apps SDK
- Caches rendered images in `localStorage` for instant restore on revisit
- Offers a download button (uses `downloadFile` API or `openLink` fallback) for the full-resolution image

No configuration is needed. The viewer activates automatically on MCP Apps-capable clients. The Claude sandbox domain is auto-computed from `BASE_URL` (see [Configuration](configuration.md#server)). Clients without Apps support see the standard base64 image + metadata response.
