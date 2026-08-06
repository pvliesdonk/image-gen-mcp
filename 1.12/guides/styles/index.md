# Style Library

Styles are reusable presets that capture a visual direction (palette, composition, mood, medium, and constraints) for consistent image generation across conversations.

## How Styles Work

A style is a **creative brief**, not a prompt template. When you apply a style, the LLM reads the brief and adapts it to the target provider's prompt format:

- **OpenAI** (gpt-image-1.5 / gpt-image-1 / gpt-image-1-mini): natural language description incorporating the style's direction.
- **Gemini** (gemini-3.1-flash-image / gemini-3-pro-image / gemini-3.1-flash-lite-image / gemini-2.5-flash-image): natural language, similar to OpenAI; can also incorporate the style brief into multi-image compositing or conversational refinement.
- **SD WebUI (SD 1.5 / SDXL / RealVisXL / Juggernaut)**: comma-separated CLIP tags with a separate negative prompt.
- **SD WebUI (Flux 1 / Flux Schnell / FLUX.2)**: natural language, similar to OpenAI; **no** native negative prompts (CFG=1 distilled).
- **SD WebUI (SD 3 / 3.5)**: natural language like Flux, but **with** native negative prompts (unlike Flux). Skip SDXL-style `(weight:1.2)` parens.
- **SD WebUI (Pony Diffusion XL / Illustrious-XL / NoobAI-XL)**: Booru-style tag grammar with a mandatory `score_*` prefix on Pony.

The style text is never copied verbatim into the generation prompt; the LLM rewrites it in the right grammar for the chosen model.

The per-model registry (`list_providers` → `style_profile.style_hints` / `incompatible_styles`) is the canonical source for what each model wants; cross-reference it from your style brief when you need provider-specific guidance.

> **`style_profile` vs style library.** The two are deliberately separate concerns:
>
> - **Style library** (this guide): a user-saved creative brief applied to a generation request. Describes the brief.
> - **`style_profile`** (set by the registry, surfaced via `list_providers`): per-model metadata describing what each model is best at. Describes the model.
>
> Both can use the word "style" in their everyday English sense and they don't interact. See [ADR-0009](https://github.com/pvliesdonk/image-generation-mcp/blob/main/docs/decisions/0009-model-style-metadata.md) for the disambiguation.

## Style File Format

Each style is a Markdown file with YAML frontmatter stored in the styles directory (default: `~/.image-generation-mcp/styles/`).

```
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

### Frontmatter Fields

| Field          | Type | Required | Default | Description                                             |
| -------------- | ---- | -------- | ------- | ------------------------------------------------------- |
| `name`         | str  | Yes      | (none)  | Style identifier (must match filename without `.md`)    |
| `tags`         | list | No       | `[]`    | Categorization tags for browsing/filtering              |
| `provider`     | str  | No       | `auto`  | Suggested provider (`auto`, `openai`, `sd_webui`, etc.) |
| `aspect_ratio` | str  | No       | (none)  | Default aspect ratio (`16:9`, `1:1`, etc.)              |
| `quality`      | str  | No       | (none)  | Default quality level (`standard` or `hd`)              |

### Body

The body is free-form Markdown prose describing the visual direction. Write it as you would a creative brief for a designer:

- **Palette**: specific colors with hex codes
- **Composition**: layout rules, negative space, framing
- **Medium**: illustration, photography, watercolor, etc.
- **Mood**: professional, playful, dramatic, etc.
- **Constraints**: what to avoid (photorealism, gradients, text, etc.)

## Creating Styles

### Manually (file on disk)

Create a `.md` file in the styles directory:

```
# Default location
mkdir -p ~/.image-generation-mcp/styles
cat > ~/.image-generation-mcp/styles/website.md << 'EOF'
---
name: website
tags: [brand, web]
aspect_ratio: "16:9"
quality: hd
---

Minimalist flat illustration with geometric shapes and clean lines.
EOF
```

### Via the `save_style` Tool

Save a style from within an MCP conversation:

```
User: Save this as my "social-media" style

Tool call: save_style
  name: "social-media"
  body: "Vibrant, eye-catching photography style. Bold saturated colors,
         high contrast. Square framing optimized for Instagram and Twitter.
         Clean backgrounds, single focal point."
  tags: ["social", "photography"]
  aspect_ratio: "1:1"
  quality: "hd"
```

## Browsing Styles

### Resources

- **`style://list`**: JSON array of all styles with names, tags, and descriptions
- **`style://{name}`**: full Markdown content of a specific style

### Example

```
Tool call: read_resource
  uri: "style://list"

→ [
    {
      "name": "website",
      "tags": ["brand", "web", "modern"],
      "description": "Minimalist flat illustration. Geometric shapes, clean lines.",
      "provider": "auto",
      "aspect_ratio": "16:9",
      "quality": "hd"
    }
  ]
```

## Applying Styles

Use the `apply_style` prompt to generate an image with a style:

```
User: Create a hero banner for the about page using the website style

Prompt: apply_style
  style_name: "website"
  user_request: "hero banner for the about page"

→ Claude reads the style brief, then calls generate_image with a
  provider-appropriate prompt incorporating the style's visual direction
```

### Example Conversation Flow

```
User: Show me what styles are available

Claude: [reads style://list]
  You have 3 styles saved:
  - website (brand, web) — minimalist flat illustrations
  - social-media (social) — vibrant photography
  - presentation (business) — clean corporate graphics

User: Generate a hero image for our pricing page using the website style

Claude: [loads apply_style prompt with style_name="website"]
  [reads the creative brief: "Minimalist flat illustration..."]
  [composes provider-appropriate prompt based on the brief]

Tool call: generate_image
  prompt: "Minimalist flat illustration of a pricing comparison layout,
           geometric shapes representing pricing tiers, deep teal and
           warm cream palette with coral accent highlights, clean lines,
           plenty of negative space, no text"
  aspect_ratio: "16:9"
  quality: "hd"
```

## Managing Styles

### Deleting a Style

```
Tool call: delete_style
  name: "old-style"

→ {"name": "old-style", "deleted": true}
```

### Updating a Style

Call `save_style` with the same name to overwrite:

```
Tool call: save_style
  name: "website"
  body: "Updated creative brief with new brand colors..."
  tags: ["brand", "web", "2024"]

→ {"name": "website", "created": false}
```

## Configuration

| Variable                          | Type | Default                           | Description                      |
| --------------------------------- | ---- | --------------------------------- | -------------------------------- |
| `IMAGE_GENERATION_MCP_STYLES_DIR` | Path | `~/.image-generation-mcp/styles/` | Directory for style preset files |

The directory is created automatically if it does not exist.
