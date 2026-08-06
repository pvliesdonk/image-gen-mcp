# Providers

image-generation-mcp supports multiple image generation providers. Each provider is registered at startup based on available configuration (API keys, service URLs).

See the [Model Catalog](https://pvliesdonk.github.io/image-generation-mcp/1.12/providers/model-catalog/index.md) for narrative guidance on every model: strengths, known weaknesses, prompt grammar examples, and lifecycle status.

## Provider comparison

|                        | Gemini                                                                                          | OpenAI                                                                      | SD WebUI (Stable Diffusion)                             | Placeholder          |
| ---------------------- | ----------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------- | ------------------------------------------------------- | -------------------- |
| **Best for**           | General-purpose, free tier                                                                      | Text, logos, typography                                                     | Photorealism, portraits, anime, artistic styles         | Testing, drafts, CI  |
| **Models**             | gemini-3.1-flash-image, gemini-3-pro-image, gemini-3.1-flash-lite-image, gemini-2.5-flash-image | gpt-image-2, gpt-image-1.5, gpt-image-1, dall-e-3                           | SD 1.5, SDXL, SDXL Lightning/Turbo                      | N/A                  |
| **Quality**            | High                                                                                            | High                                                                        | Varies by model and steps                               | N/A (solid color)    |
| **Speed**              | 5-15 s                                                                                          | 5-15 s                                                                      | 10-60 s (depends on GPU)                                | Instant              |
| **Cost**               | Free tier available                                                                             | Per-image API pricing                                                       | Self-hosted (GPU cost)                                  | Free                 |
| **Negative prompt**    | Appended as "Avoid:" clause                                                                     | Appended as "Avoid:" clause                                                 | Native support                                          | Ignored              |
| **Background control** | Not supported (ignored)                                                                         | Supported (gpt-image-1 / gpt-image-1.5 / gpt-image-1-mini; not gpt-image-2) | Not supported (ignored)                                 | Supported (RGBA PNG) |
| **Requires**           | `IMAGE_GENERATION_MCP_GOOGLE_API_KEY`                                                           | `IMAGE_GENERATION_MCP_OPENAI_API_KEY`                                       | Running SD WebUI + `IMAGE_GENERATION_MCP_SD_WEBUI_HOST` | Nothing              |

## Which provider should I use?

**Start with placeholder** if you're testing the setup or building automations. It generates instantly with zero cost.

**Use Gemini** for:

- General-purpose image generation with a free tier
- When you don't have a GPU and want an alternative to OpenAI
- Creative scenes, illustrations, and photography

**Use OpenAI** for:

- Text rendering, logos, and typography (OpenAI handles text best)
- When you need the most reliable cloud API

**Use SD WebUI** for:

- Photorealistic images (portraits, product shots, photography)
- Anime, manga, and illustration styles
- Fine-grained control over generation parameters
- When you have a local GPU and want unlimited generations

## Auto-selection

When `provider="auto"` (the default), the server analyzes your prompt using keyword matching and selects the best available provider:

| Prompt keywords                                                        | Preferred provider chain                    |
| ---------------------------------------------------------------------- | ------------------------------------------- |
| realistic, photo, photography, portrait photo, product shot, headshot  | sd_webui -> gemini -> openai                |
| text, logo, typography, poster, banner, signage, lettering, font       | openai -> gemini                            |
| quick, draft, test, placeholder, mock                                  | placeholder                                 |
| art, painting, illustration, watercolor, oil painting, sketch, drawing | sd_webui -> gemini -> openai                |
| anime, manga, kawaii, chibi                                            | sd_webui -> gemini -> openai                |
| *(no match)*                                                           | gemini -> openai -> sd_webui -> placeholder |

The first matching rule wins. Within a rule, the first available provider is selected. If no provider in the chain is available, any registered provider is returned as a fallback.

When `background="transparent"` is requested, providers with transparent background support are preferred within each selection rule. This is a secondary filter; keyword heuristics still determine the rule.

## Provider registration

Providers are registered automatically at startup based on environment variables:

1. **Placeholder**: always registered (zero cost, no configuration)
1. **OpenAI**: registered when `IMAGE_GENERATION_MCP_OPENAI_API_KEY` is set
1. **Gemini**: registered when `IMAGE_GENERATION_MCP_GOOGLE_API_KEY` is set
1. **SD WebUI**: registered when `IMAGE_GENERATION_MCP_SD_WEBUI_HOST` is set
