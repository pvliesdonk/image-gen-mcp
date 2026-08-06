# MCP Resources

image-generation-mcp exposes resources for provider information and image access.

## info://providers

Provider capabilities and supported features.

**MIME type:** `application/json`

### Response

```json
{
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
  },
  "supported_aspect_ratios": ["1:1", "16:9", "9:16", "3:2", "2:3"],
  "supported_quality_levels": ["standard", "hd"],
  "supported_resolutions": ["standard", "high", "max"],
  "supported_backgrounds": ["opaque", "transparent"]
}
```

Only registered (configured) providers appear. Degraded providers (where capability discovery failed at startup) show `"degraded": true` with an empty `models` list; they remain available for generation.

The JSON envelope contains a top-level `warnings` array (always present, may be empty) listing deprecated or legacy models that are configured. Each entry in `models` may carry a `style_profile` sub-object with `label`, `style_hints`, `incompatible_styles`, `good_example`, `bad_example`, `lifecycle`, and (when set) `deprecation_note`. See [Model Catalog](providers/model-catalog.md) for the full registry.

---

## info://prompt-guide

Provider-specific prompt writing guidance for LLM clients. Read this resource to learn how to write effective prompts for each provider.

**MIME type:** `text/markdown`

### Content

Markdown document covering:

- **General tips:** aspect ratio selection and quality/resolution tiers; when and how to use negative prompts
- **OpenAI:** natural-language prompts, style keywords, and text rendering tips
- **SD WebUI (Stable Diffusion):** CLIP-tag prompting for SD 1.5/SDXL and natural-language prompting for Flux; negative prompts, BREAK syntax, and model-specific advice
- **Placeholder:** prompt-to-color mapping explanation

The `generate_image` tool description references this resource. LLM clients can read it before generating images to produce better prompts.

---

## style://list

List all available style presets with their names, tags, and default parameters.

**MIME type:** `application/json`

### Response

```json
[
  {
    "name": "website",
    "tags": ["brand", "web", "modern"],
    "description": "Minimalist flat illustration. Geometric shapes, clean lines.",
    "provider": "auto",
    "aspect_ratio": "16:9",
    "quality": "hd"
  },
  {
    "name": "social-media",
    "tags": ["social", "photography"],
    "description": "Vibrant, eye-catching photography style.",
    "provider": null,
    "aspect_ratio": "1:1",
    "quality": "hd"
  }
]
```

The `description` field is the first non-empty line of the style's body text. Styles are loaded from the styles directory at server startup.

---

## style://{name}

Read the full content of a style preset, including YAML frontmatter and creative brief body.

**URI template:** `style://{name}`

**MIME type:** `text/markdown`

### Response

Returns the raw markdown file content:

```markdown
---
name: website
tags: [brand, web, modern]
provider: auto
aspect_ratio: "16:9"
quality: hd
---

Minimalist flat illustration. Geometric shapes, clean lines.
Brand palette: deep teal (#0D4F4F), warm cream (#F5F0E8), coral accent (#FF6B5E).
Plenty of negative space. No photorealism, no gradients, no text in image.
Suitable for hero banners and section dividers.
```

Returns an error if the style name is not found.

---

## image://{id}/view

Image data with optional CDN-style transforms. This is a resource template (RFC 6570) with query parameters.

**URI template:** `image://{image_id}/view{?format,width,height,quality,crop_x,crop_y,crop_w,crop_h,rotate,flip}`

**MIME type:** varies (depends on original format or requested format)

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `format` | str | *(original)* | Convert to `png`, `webp`, or `jpeg` |
| `width` | int | *(original)* | Target width in pixels |
| `height` | int | *(original)* | Target height in pixels |
| `quality` | int | `90` | Compression quality for lossy formats (1-100) |
| `crop_x` | int | `0` | Left edge of crop box in pixels |
| `crop_y` | int | `0` | Top edge of crop box in pixels |
| `crop_w` | int | `0` | Width of crop box in pixels (0 = no region crop) |
| `crop_h` | int | `0` | Height of crop box in pixels (0 = no region crop) |
| `rotate` | int | `0` | Rotation in degrees: 90, 180, or 270 (lossless) |
| `flip` | str | *(none)* | Flip axis: `horizontal` or `vertical` (lossless) |

### Transform behavior

Transforms are applied in this order: crop-region → rotate → flip → resize/crop → format conversion.

| Parameters provided | Behavior |
|--------------------|----------|
| None | Returns original bytes unchanged |
| `format` only | Format conversion (PNG to WebP) |
| `width` + `height` | Center-crop to exact dimensions |
| `width` only | Proportional resize (height calculated from aspect ratio) |
| `height` only | Proportional resize (width calculated from aspect ratio) |
| `format` + dimensions | Convert and resize/crop |
| `crop_x` + `crop_y` + `crop_w` + `crop_h` | Crop arbitrary rectangular region |
| `rotate` | Rotate 90°, 180°, or 270° (lossless via `Image.transpose`) |
| `flip` | Mirror horizontally or vertically (lossless via `Image.transpose`) |

### Examples

```
# Original image
image://a1b2c3d4e5f6/view

# Convert to WebP
image://a1b2c3d4e5f6/view?format=webp

# Resize to 512px wide (proportional)
image://a1b2c3d4e5f6/view?width=512

# Center-crop to 256x256
image://a1b2c3d4e5f6/view?width=256&height=256

# Convert to JPEG at quality 85
image://a1b2c3d4e5f6/view?format=jpeg&quality=85

# Crop a 200x100 region starting at (50, 30)
image://a1b2c3d4e5f6/view?crop_x=50&crop_y=30&crop_w=200&crop_h=100

# Rotate 90 degrees clockwise
image://a1b2c3d4e5f6/view?rotate=90

# Flip horizontally
image://a1b2c3d4e5f6/view?flip=horizontal
```

---

## image://{id}/metadata

Sidecar JSON metadata with generation provenance.

**MIME type:** `application/json`

### Response

```json
{
  "id": "a1b2c3d4e5f6",
  "content_type": "image/png",
  "provider": "openai",
  "prompt": "a watercolor painting of mountains at sunset",
  "negative_prompt": null,
  "aspect_ratio": "16:9",
  "quality": "standard",
  "original_dimensions": [1536, 1024],
  "provider_metadata": {
    "model": "gpt-image-1",
    "size": "1536x1024",
    "quality": "standard",
    "api_quality": "high"
  },
  "created_at": 1710777600.0
}
```

---

## image://list

List all registered images and pending generations.

**MIME type:** `application/json`

### Response

Each item includes a `status` field: `"completed"` for registered images, `"generating"` or `"failed"` for pending background generations.

Completed images also carry an `origin` field: `"generated"` for images produced by a provider (the case today), or `"imported"` for images added to the gallery from an external source. For imported images, `origin_source` records provenance and `provider`/`prompt` are empty; generated images have `origin_source: null`.
{ #origin }

```json
[
  {
    "image_id": "a1b2c3d4e5f6",
    "origin": "generated",
    "origin_source": null,
    "provider": "openai",
    "prompt": "a watercolor painting of mountains at sunset",
    "aspect_ratio": "16:9",
    "created_at": 1710777600.0,
    "status": "completed"
  },
  {
    "image_id": "c3d4e5f6a7b8",
    "provider": "sd_webui",
    "prompt": "a cyberpunk cityscape",
    "status": "generating",
    "progress": 0.3,
    "progress_message": "Step 9/30 (ETA 12s)"
  },
  {
    "image_id": "b2c3d4e5f6a7",
    "provider": "placeholder",
    "prompt": "test image",
    "aspect_ratio": "1:1",
    "created_at": 1710777500.0,
    "status": "completed"
  }
]
```

Pending generations (status `"generating"` or `"failed"`) appear in the list alongside completed images. They are cleaned up automatically after a 10-minute TTL.

---

## ui://image-viewer/view.html

Interactive image viewer rendered by MCP Apps-capable clients (Claude Desktop, claude.ai).

**MIME type:** `text/html;profile=mcp-app`

This resource is an [MCP App](https://modelcontextprotocol.io/specification/2025-06-18/server/utilities/apps): a custom HTML page loaded in a sandboxed iframe via the `@modelcontextprotocol/ext-apps` SDK. It is wired to the `show_image` tool via `AppConfig(resourceUri=...)`.

### Sandbox domain

When `IMAGE_GENERATION_MCP_BASE_URL` is set, the Claude sandbox domain is auto-computed as `sha256(BASE_URL + HTTP_PATH)[:32].claudemcpcontent.com`. Override with `IMAGE_GENERATION_MCP_APP_DOMAIN` for other hosts or custom setups. When neither is set (stdio transport), the host assigns its own sandbox origin.

### Viewer states

| State | Trigger | Display |
|-------|---------|---------|
| Waiting | Widget loaded, no tool result yet | "Waiting for image…" |
| Generating | `show_image` returns `{"status": "generating", ...}` | Spinner, progress bar, provider info |
| Failed | `show_image` returns `{"status": "failed", ...}` | Error message |
| Completed | `show_image` returns image + metadata | Image, prompt, provider, dimensions, file size |
| Cancelled | Host cancels the tool call | "Cancelled" message |

### Features

- **Host theming:** applies `applyDocumentTheme()`, `applyHostStyleVariables()`, and `applyHostFonts()` from the ext-apps SDK; CSS uses host variables (`--color-text-primary`, `--font-sans`, etc.)
- **Safe area insets:** respects `safeAreaInsets` from `onhostcontextchanged` for mobile notch/status bar
- **localStorage cache:** persists rendered images (keyed by image ID, LRU-capped at 5 entries); restores cached state on `ontoolinput` before the tool result arrives
- **Download button:** uses the ext-apps `downloadFile` API with a `resource_link` to `image://{id}/view` for the full-resolution image; when the host does not support `downloadFile`, it falls back to calling `create_download_link` on demand and opening the returned `url` via `openLink`

Clients without MCP Apps support ignore this resource entirely.

---

## ui://image-gallery/view.html

Interactive image gallery rendered by MCP Apps-capable clients (Claude Desktop, claude.ai).

**MIME type:** `text/html;profile=mcp-app`

This resource is an [MCP App](https://modelcontextprotocol.io/specification/2025-06-18/server/utilities/apps) wired to the `browse_gallery` tool via `AppConfig(resourceUri=...)`. It shares the same sandbox domain configuration as `ui://image-viewer/view.html`.

### Features

- **Thumbnail grid:** responsive grid using CSS `auto-fill` with 140 px minimum card width; 3×3 at typical inline size, adapts to available width (4×3 at wider sizes)
- **Page size:** fixed at 12 items per page, set server-side by `browse_gallery` and propagated via `data.page_size`
- **Pagination:** Prev/Next buttons call the `gallery_page` app-only tool; page indicator shows current/total
- **Hover overlay:** prompt excerpt (2-line clamp) and provider badge on thumbnail hover; keyboard-accessible (`:focus-within`)
- **Download button:** uses `resource_link` to `image://{id}/view` with `downloadFile` → `openLink` fallback
- **Lightbox:** clicking a thumbnail opens a full-resolution overlay via `gallery_full_image` (app-only); prev/next navigation with cross-page support; close via ✕ button, Escape key, or backdrop click; fullscreen toggle when `requestDisplayMode("fullscreen")` is available from the host
- **Pending items:** in-progress generations appear with spinner overlay and prompt label
- **Empty state:** friendly message with `generate_image` call-to-action when no images exist
- **Host theming:** same theme/CSS-variable/safe-area integration as the image viewer

Clients without MCP Apps support receive the raw JSON response from `browse_gallery` instead.
