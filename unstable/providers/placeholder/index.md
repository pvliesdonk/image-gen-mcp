# Placeholder Provider

Zero-cost solid-color PNG generation for testing, drafts, and CI pipelines.

## Overview

The placeholder provider generates simple solid-color PNG images without any external dependencies or API keys. The color is selected from a palette of 6 predefined colors using a SHA-256 hash of the prompt as an index, so the same prompt always produces the same color.

## When to use

- **Testing:** verify your MCP client configuration without API costs
- **Drafts and mock-ups:** create placeholder images during development
- **CI pipelines:** test image generation workflows without external services
- **Demos:** show the image generation flow without requiring API keys

## Availability

The placeholder provider is **always registered**: no configuration or API key is needed.

## Aspect ratios

| Aspect ratio | Size      |
| ------------ | --------- |
| `1:1`        | `256x256` |
| `16:9`       | `640x360` |
| `9:16`       | `360x640` |
| `3:2`        | `480x320` |
| `2:3`        | `320x480` |

## Parameters

- **prompt:** used to determine the output color (via SHA-256 hash index into a 6-color palette)
- **negative_prompt:** ignored
- **quality:** ignored
- **resolution:** ignored. This provider has no higher-resolution tier; it reports "resolution": "standard" in provider metadata regardless of the requested tier.
- **aspect_ratio:** maps to pixel sizes above
- **background:** `"opaque"` (default) produces RGB PNG; `"transparent"` produces RGBA PNG with alpha channel set to 0

## Output

- **Format:** PNG (RGB for opaque, RGBA for transparent)
- **Content:** Solid color fill (fully transparent when `background="transparent"`)
- **Size:** ~1-2 KB per image
- **Generation time:** Instant (< 1 ms)
