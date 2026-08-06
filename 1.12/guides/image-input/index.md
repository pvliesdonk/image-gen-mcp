# Image input: editing, composition, and masking

The [`transform_image`](https://pvliesdonk.github.io/image-generation-mcp/1.12/tools/#transform_image) tool feeds one or more existing images *into* generation. Use it to edit a picture from a text instruction, transfer a style, compose several references into one scene, or repaint a masked region. This is distinct from `generate_image` (text only, no reference image) and from `edit_image` (local geometry operations such as crop, rotate, and flip).

## How input images are supplied

Every reference is a string in the `reference_images` list (and the optional `mask`). Three forms are accepted:

1. A gallery `image_id`, the 12-character hex ID returned by a prior `generate_image` or `transform_image` call.
1. An `image://<id>/view` resource URI.
1. A local filesystem path, allowed only when `IMAGE_GENERATION_MCP_ALLOW_LOCAL_FILE_INPUT=true` (off by default). See [Configuration](https://pvliesdonk.github.io/image-generation-mcp/1.12/configuration/index.md).

A gallery `image_id` may itself be an **imported** image: one brought into the gallery from outside rather than produced by `generate_image` or `transform_image`. See [Getting an external image into the gallery](#getting-an-external-image-into-the-gallery) below.

`transform_image` runs as a background task. It returns immediately with a `status: "generating"` response and an `image_id`. Poll `check_generation_status(image_id)` until completion, then call `show_image(uri=original_uri)` once to display the result. Provenance is recorded: the response and the finished record carry `source_image_ids` listing every reference (and mask) the result derived from.

## Getting an external image into the gallery

An image the model did not generate (a URL, a user-supplied file, or inline bytes) becomes a first-class gallery entry through one of three ingestion tools, after which its `image_id` is referenced by `transform_image` exactly like a generated image:

- [`fetch_image(url)`](https://pvliesdonk.github.io/image-generation-mcp/1.12/tools/#fetch_image): download a remote `http`/`https` image into the gallery (SSRF-hardened, size-capped).
- [`ingest_base64_image(data)`](https://pvliesdonk.github.io/image-generation-mcp/1.12/tools/#ingest_base64_image): decode inline base64 bytes (raw, a `data:` URI, or line-wrapped) into the gallery.
- [`create_upload_link()`](https://pvliesdonk.github.io/image-generation-mcp/1.12/tools/#create_upload_link): mint a one-time HTTP upload link for a caller to POST bytes to (HTTP/SSE transport only, with `IMAGE_GENERATION_MCP_BASE_URL` set).

A reference image is just a gallery image, so an imported image works as a `transform_image` reference with no provider-specific handling. Imported entries carry `origin: "imported"` with an `origin_source` recording where they came from (see [image metadata](https://pvliesdonk.github.io/image-generation-mcp/1.12/resources/#origin)); generated images are `origin: "generated"`. The gallery viewer's origin filter groups imported and generated images separately.

The decoded/downloaded size is bounded by `IMAGE_GENERATION_MCP_MAX_INPUT_IMAGE_BYTES`, remote fetches time out after `IMAGE_GENERATION_MCP_FETCH_TIMEOUT_S`, and upload-link lifetime is governed by the `IMAGE_GENERATION_MCP_TRANSFER_*` knobs, all documented on the [Configuration](https://pvliesdonk.github.io/image-generation-mcp/1.12/configuration/index.md) page.

## Capability matrix

Reference-image support varies by provider and model. Call `list_providers` and read each model's `supports_image_input`, `max_input_images`, and `supports_mask` for the authoritative runtime values.

| Capability                | Gemini                       | OpenAI           | SD WebUI               |
| ------------------------- | ---------------------------- | ---------------- | ---------------------- |
| Image-to-image edit       | Yes                          | gpt-image family | Yes (img2img)          |
| Reference images per call | 3 (2.5-flash), 14 (Gemini 3) | up to 16         | 1                      |
| Multi-image composition   | Yes (Gemini 3)               | Yes              | No (single init image) |
| Inpainting mask           | No                           | gpt-image family | No                     |
| Denoising `strength`      | No                           | No               | Yes (`0.0`-`1.0`)      |

When `provider="auto"`, selection is capability-aware: it picks a provider whose model accepts the supplied reference count, and a mask request is routed only to a mask-capable model.

## Workflows

### Edit and style transfer

Pass a single reference and describe the change. Good for background swaps, restyles, and other description-driven edits.

```
transform_image(
  prompt="Repaint this photo in the style of a watercolor landscape",
  reference_images=["a1b2c3d4e5f6"]
)
```

Any image-input provider handles a single reference. See [Gemini](https://pvliesdonk.github.io/image-generation-mcp/1.12/providers/gemini/#image-input-image-to-image), [OpenAI](https://pvliesdonk.github.io/image-generation-mcp/1.12/providers/openai/#image-input-editing-and-composition), and [SD WebUI](https://pvliesdonk.github.io/image-generation-mcp/1.12/providers/sd-webui/#image-input-img2img).

### Multi-image composition

Supply several references to compose a scene from their elements or to keep a character consistent across generations. The Gemini 3 models accept up to 14 references; OpenAI's gpt-image family accepts up to 16.

```
transform_image(
  prompt="Place the character from the first image into the scene of the second",
  reference_images=["a1b2c3d4e5f6", "0f1e2d3c4b5a", "9a8b7c6d5e4f"],
  provider="gemini",
  model="gemini-3-pro-image"
)
```

See [Gemini multi-image composition](https://pvliesdonk.github.io/image-generation-mcp/1.12/providers/gemini/#multi-image-composition-and-character-consistency).

### Inpainting with a mask

Supply a `mask` to repaint only the masked region of the first reference image. Masks are an OpenAI gpt-image capability. The mask must match the first reference image's size and format and carry an alpha channel; OpenAI enforces this and returns an error on a mismatch.

```
transform_image(
  prompt="Replace the masked area with a vase of flowers",
  reference_images=["a1b2c3d4e5f6"],
  mask="b2c3d4e5f6a1",
  provider="openai"
)
```

See [OpenAI masks](https://pvliesdonk.github.io/image-generation-mcp/1.12/providers/openai/#masks).

### Controlling edit strength (SD WebUI)

For SD WebUI img2img, `strength` is the denoising strength, from `0.0` to `1.0`. Lower values preserve the reference image; higher values regenerate more of it. It defaults to `0.75` and has no effect on other providers or without a reference image.

```
transform_image(
  prompt="Turn this sketch into a finished oil painting",
  reference_images=["a1b2c3d4e5f6"],
  provider="sd_webui",
  strength=0.55
)
```

See [SD WebUI img2img](https://pvliesdonk.github.io/image-generation-mcp/1.12/providers/sd-webui/#image-input-img2img).

## Related pages

- [Tools: `transform_image`](https://pvliesdonk.github.io/image-generation-mcp/1.12/tools/#transform_image) for the full parameter reference.
- [Image Assets](https://pvliesdonk.github.io/image-generation-mcp/1.12/guides/image-assets/index.md) for how generated images are stored and addressed.
- [Providers overview](https://pvliesdonk.github.io/image-generation-mcp/1.12/providers/index.md) for per-provider detail.
