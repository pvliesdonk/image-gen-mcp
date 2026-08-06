# MCP Prompts

image-generation-mcp provides three prompts that give LLM clients guidance on provider selection, prompt formatting, and style application.

## select_provider

Guidelines for selecting the best image generation provider based on the user's request.

### When to use

MCP clients (like Claude) can load this prompt to understand provider strengths before calling `generate_image`. It helps the client make informed decisions about which provider to use.

### Content summary

The prompt covers:

- **Provider strengths:** what each provider (OpenAI, SD WebUI, Placeholder) is best at
- **Selection rules:** ordered decision logic:
  1. Text/logos/typography -> use OpenAI
  1. Photorealism/portraits/product shots -> prefer SD WebUI (fall back to OpenAI)
  1. Art/illustration/anime -> prefer SD WebUI (fall back to OpenAI)
  1. Quick test/placeholder -> use placeholder
  1. General requests -> default to OpenAI
- **Usage guidance:** how to call `generate_image` with `provider="auto"` or a specific provider name

______________________________________________________________________

## sd_prompt_guide

Guide for writing effective Stable Diffusion prompts using the CLIP-based tag format.

### When to use

MCP clients should load this prompt when generating images with the SD WebUI provider. Stable Diffusion models respond better to comma-separated tags than natural language descriptions.

### Content summary

The prompt covers:

- **Tag format:** comma-separated descriptive tags ordered by importance: `subject, medium, style, lighting, camera, quality tags`
- **Example prompts:** portrait, landscape, and product shot examples
- **Quality tags:** `masterpiece, best quality`, `highly detailed, sharp focus`, `8k, ultra high res`
- **Negative prompts:** general-purpose negative prompt for avoiding common artifacts, plus photorealism and anime-specific additions
- **CLIP token limits:** SD 1.5: 77 tokens per chunk, SDXL: 77 tokens per chunk with two encoders
- **BREAK syntax:** how to separate concepts into different CLIP chunks
- **Aspect ratios:** supported ratios: `1:1`, `16:9`, `9:16`, `3:2`, `2:3`

### Example prompt format

```
1girl, long hair, blue eyes, school uniform, standing, cherry blossoms,
soft lighting, detailed face, masterpiece, best quality
```

See the [Prompt Writing Guide](https://pvliesdonk.github.io/image-generation-mcp/1.12/guides/prompt-writing/index.md) for more detailed examples and tips.

______________________________________________________________________

## apply_style

Apply a saved style preset to an image generation request. Loads the style's creative brief and instructs the LLM to interpret it as creative direction, not copy it verbatim.

### When to use

Use when a user references a saved style (such as "use the website style") or you want to apply consistent visual direction across multiple generations.

### Arguments

| Argument       | Type | Required | Description                         |
| -------------- | ---- | -------- | ----------------------------------- |
| `style_name`   | str  | Yes      | Name of the style preset to apply   |
| `user_request` | str  | Yes      | The user's image generation request |

### Behavior

The prompt:

1. Loads the style's full creative brief from the style library
1. Presents the style body and frontmatter defaults to the LLM
1. Instructs the LLM to interpret the style as creative direction, not a prompt template
1. Provides provider-specific adaptation guidance:
   - **OpenAI:** compose in natural language
   - **SD WebUI (SD 1.5/SDXL):** compose as CLIP tags with negative prompts
   - **SD WebUI (Flux):** compose in natural language
1. Uses frontmatter defaults (provider, aspect_ratio, quality) unless the user overrides

### Example

```
User: Create a hero banner using my website style

Prompt: apply_style
  style_name: "website"
  user_request: "hero banner for the landing page"

→ LLM receives the style brief + adaptation instructions,
  then calls generate_image with a provider-appropriate prompt
```

If the style is not found, returns an error message suggesting `style://list` to browse available styles.

See the [Style Library Guide](https://pvliesdonk.github.io/image-generation-mcp/1.12/guides/styles/index.md) for more details on creating and managing styles.
