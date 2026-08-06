"""MCP prompt registrations — provider selection and prompt guidance.

Prompts provide reusable LLM instruction templates exposed to clients.
Write prompts should be tagged with ``tags={"write"}`` so they are hidden
in read-only mode alongside write tools.

See https://gofastmcp.com/servers/prompts for the full prompt API.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastmcp import FastMCP
from fastmcp.dependencies import Depends
from mcp.types import Icon

from image_generation_mcp._server_deps import get_service

if TYPE_CHECKING:
    from image_generation_mcp.domain import ImageService
    from image_generation_mcp.styles import StyleEntry

_SELECT_PROVIDER_PROMPT = """\
You have access to an image generation MCP server with multiple providers.
Choose the best provider for the user's request based on these guidelines.

> **Per-model detail:** these notes describe provider-level capabilities and
> selection rules. For per-model strengths, weaknesses, and lifecycle status
> (legacy / deprecated), call `list_providers` and read each entry's
> `style_profile` plus the top-level `warnings` array. The canonical
> per-model registry is at `src/image_generation_mcp/providers/model_styles.py`
> — keep this prompt's wording in sync when that registry changes.

## Provider Strengths

### OpenAI

- **Current flagship:** `gpt-image-2`. Highest-fidelity instruction following,
  photoreal still life, in-image text and logos. Drops transparent-background
  support — use `gpt-image-1.5` when you need alpha.
- **Transparency pick:** `gpt-image-1.5` (previous-generation flagship; same
  descriptive grammar as gpt-image-2 but keeps transparent backgrounds).
  `gpt-image-1-mini` is a cheaper current variant for high-volume drafts.
- **Alias:** `chatgpt-image-latest` tracks the newest ChatGPT image model (no
  guaranteed transparency); pin a concrete id for reproducible workflows.
- **Legacy / deprecated:** `gpt-image-1` (legacy), `dall-e-3` (deprecated, API
  removal 2026-05-12 — migrate new work to gpt-image-2 / gpt-image-1.5), and
  `dall-e-2` (legacy; useful only for cheap inpainting).
- **Best for:** Text rendering, logos, typography, transparent backgrounds.
- **Also strong at:** Photoreal still life, material fidelity (glass, metal,
  fabric), precise text on objects, complex multi-clause prompts.
- **Supports:** Negative prompt (as "Avoid:" clause — weaker than native),
  quality levels (`standard`=auto, `hd`=high). `resolution="high"`/`"max"`
  (up to 4K) is honored only by `gpt-image-2`; every other model renders at
  its standard size regardless of `resolution`.
- **Prompt style:** Descriptive natural-language paragraphs; tag-soup
  underperforms.

### Gemini

- **Default:** `gemini-3.1-flash-image` (GA; Nano Banana 2). Fast, versatile
  workhorse. Supports 14 aspect ratios from 21:9 to 9:16 (including ultra-wide
  4:1 / 8:1), multi-image compositing (up to 14 references on the Gemini 3
  models), reasoning ("thinking") for layout-heavy work, and conversational
  image editing. Outputs carry an invisible SynthID watermark.
- **Higher tiers:** `gemini-3-pro-image` (Nano Banana Pro — highest fidelity,
  best for dense typography and brand compliance) and `gemini-3.1-flash-lite-image`
  (Nano Banana 2 Lite — fastest, lowest cost). `gemini-2.5-flash-image` remains
  as a legacy GA option.
- **Best for:** Infographics, diagrams, structured layouts, complex
  illustrations, visual storytelling, multi-element compositions, character
  consistency across iterations.
- **Supports:** `quality="hd"` enables thinking (Pro/3.x variants) —
  dramatically improves output on complex prompts (10s → 55s). Independent
  of quality, `resolution="high"`/`"max"` selects 2K/4K output on
  `gemini-3.1-flash-image` and `gemini-3-pro-image`; `gemini-3.1-flash-lite-image`
  and `gemini-2.5-flash-image` clamp down to 1K regardless of the requested
  tier.
- **Cost:** Generous free tier at `standard` quality; `hd` uses thinking
  tokens (billed). Higher `resolution` tiers may bill more even on the free
  tier.
- **Prompt style:** Descriptive natural-language. Don't use SD-style
  comma-separated tag lists — Google's docs explicitly call this the wrong
  pattern.

### SD WebUI (Stable Diffusion / Forge / reForge / Forge-neo)

- **Best for:** Photorealism, portraits, product shots, artistic styles
  (anime / watercolor / oil painting / illustration).
- **Supports:** Native negative prompt on SD 1.5 / SDXL / SD3 (NOT Flux),
  fine-grained parameter control, optional checkpoint override per call.
- **Prompt grammar depends on the loaded checkpoint architecture:**
  - **SD 1.5 / SDXL** — Comma-separated CLIP tags (see `sd_prompt_guide`).
  - **Flux** (dev / schnell / FLUX.2) — Natural language descriptions, no
    negative prompts (CFG=1 distilled).
  - **SD 3 / 3.5** — Natural language (T5 stream); supports negative prompts.
  - **Pony Diffusion XL** — Mandatory `score_9, score_8_up, …` tag prefix;
    output collapses without it.
  - **Illustrious-XL / NoobAI-XL** — Danbooru-style tag grammar for anime,
    larger character/style coverage than Animagine.
- **Always check `list_providers`** for each loaded checkpoint's
  `style_profile.style_hints`, `incompatible_styles`, and `prompt_style`
  before composing the prompt.

### Placeholder

- Returns a deterministic solid-color PNG. Use for testing, mock-ups, or
  zero-cost demos without invoking a real provider.

## Selection Rules

1. If the request involves **text rendering, logos, or typography** → use
   **openai** (gpt-image-2).
2. If the request involves **transparent backgrounds** (icons, stickers) →
   use **openai** (gpt-image-1.5 / gpt-image-1-mini; not gpt-image-2).
3. If the request involves **infographics, diagrams, or structured layouts**
   → use **gemini** with `quality="hd"` on a Pro/3.x model.
4. If the request involves **complex illustrations, visual storytelling, or
   multi-element compositions** → use **gemini** with `quality="hd"`.
5. If the request involves **photorealism, still life, or product shots** →
   prefer **sd_webui** (RealVisXL / Juggernaut / Flux), fall back to
   **gemini** then **openai**.
6. If the request involves **anime, manga, or painting styles** → prefer
   **sd_webui** with **Illustrious-XL / NoobAI-XL** (modern anime SDXL
   bases that have largely supplanted Animagine for general anime work).
   Pick **Pony Diffusion XL** for highly-stylised character art (mandatory
   `score_*` tag prefix; output collapses without it). Animagine XL still
   works but is considered a previous-generation choice.
7. If the request is a **quick draft or iteration** → use **gemini** at
   `standard` quality (fast, free tier) or **sd_webui** with a Lightning /
   Schnell checkpoint.
8. If the request is a **quick test or placeholder** → use **placeholder**.
9. For **general requests** → default to **gemini** when available, then
   **openai**.

## Reference-Image Input (transform_image)

When the request supplies an existing image (edit, style transfer,
composition, or inpainting), use `transform_image` instead of
`generate_image`, and pick the provider by what the task needs:

- **Edit or style transfer** (one reference) → any image-input provider:
  **gemini**, **openai** (gpt-image), or **sd_webui** (img2img).
- **Multi-image composition** (several references) → **gemini** on a Gemini 3
  model (up to 14 references) or **openai** gpt-image (up to 16). **sd_webui**
  takes a single reference only.
- **Inpainting with a mask** → **openai** gpt-image (the only mask-capable
  family).
- **Fine-grained edit control** → **sd_webui**, using `strength` (denoising
  `0.0`-`1.0`; lower preserves the reference).

Check `supports_image_input`, `max_input_images`, and `supports_mask` on
`list_providers` for the authoritative per-model values; `provider="auto"`
already routes on them.

**Avoid deprecated models for new long-lived workflows.** Check the
`warnings` array on `list_providers`'s response — it lists every configured
model whose `lifecycle` is `legacy` or `deprecated`, including removal dates
when known.

## Usage

Call `generate_image` with `provider="auto"` for automatic selection, or
specify a provider name directly. For requests that supply an existing image
(editing, composition, or masking), call `transform_image` instead. Pass
`model="<id>"` to pin a specific model_id within the provider. Use
`list_providers` to see which providers are currently available, what models
each has loaded, and per-model narrative guidance.
"""

_SD_PROMPT_GUIDE = """\
Guide for writing SD WebUI prompts. The correct prompt style depends on the
checkpoint architecture and (sometimes) the specific fine-tune family —
check `list_providers` for each model's `prompt_style` field plus its
`style_profile.style_hints` / `incompatible_styles` / `good_example` /
`bad_example` for per-checkpoint nuance.

Architecture summary:

| Family | Encoder | Grammar | Negative prompts |
|---|---|---|---|
| SD 1.5, SDXL | CLIP | Comma-separated tags | Yes (native) |
| Flux 1 / FLUX.2 | T5 | Descriptive prose | No (CFG=1 distilled) |
| Flux Schnell | T5 | Descriptive prose, 1-4 steps | No |
| SD 3 / 3.5 | CLIP + T5 | Descriptive prose | Yes |
| Pony Diffusion XL | SDXL+CLIP | Tags + mandatory `score_*` prefix | Yes |
| Illustrious-XL / NoobAI-XL | SDXL+CLIP | Danbooru-style tags | Yes |

## SD 1.5 / SDXL — CLIP Tag Format

These models use a CLIP text encoder. Format prompts as comma-separated
descriptive tags ordered by importance:

```
subject, medium, style, lighting, camera, quality tags
```

### Example Prompts

**Portrait:**
```
1girl, long hair, blue eyes, school uniform, standing, cherry blossoms,
soft lighting, detailed face, masterpiece, best quality
```

**Landscape:**
```
mountain landscape, sunset, dramatic clouds, lake reflection,
cinematic lighting, wide angle, 8k, highly detailed
```

**Product shot:**
```
white sneakers, product photography, studio lighting, white background,
sharp focus, commercial photography, high resolution
```

### Quality Tags

Add these to improve output quality:
- `masterpiece, best quality` — general quality boost
- `highly detailed, sharp focus` — detail enhancement
- `8k, ultra high res` — resolution boost (use sparingly)
- `professional, award winning` — style refinement

### Negative Prompt

Always include a negative prompt to avoid common artifacts:

**General-purpose negative:**
```
lowres, bad anatomy, bad hands, text, error, missing fingers,
extra digit, fewer digits, cropped, worst quality, low quality,
normal quality, jpeg artifacts, signature, watermark, blurry
```

**For photorealism, add:**
```
cartoon, anime, illustration, painting, drawing, art, sketch
```

**For anime/illustration, add:**
```
photo, realistic, 3d render
```

### CLIP Token Limits

- **SD 1.5:** 77 tokens per CLIP chunk. Use `BREAK` to start a new chunk.
- **SDXL:** 77 tokens per chunk, but two CLIP encoders (ViT-L + ViT-bigG).

Keep prompts concise. Front-load the most important tags — tokens beyond
the first 77-token chunk have diminishing influence.

### BREAK Syntax

Use `BREAK` to separate prompt concepts into different CLIP chunks:

```
1girl, detailed face, blue eyes BREAK
forest background, sunlight through trees BREAK
masterpiece, best quality, sharp focus
```

## Flux — Natural Language Format

Flux models (flux-dev, flux-schnell) use a T5 text encoder, NOT CLIP.
Write prompts as natural language descriptions — the same style as OpenAI.

**Key differences from SD 1.5 / SDXL:**
- Use complete sentences, not comma-separated tags
- Do NOT include quality tags (`masterpiece`, `best quality`) — they are meaningless to Flux
- Do NOT write a negative prompt — Flux does not support them (the server omits them automatically)
- Do NOT use `BREAK` syntax — Flux does not use CLIP chunking
- CFG scale and sampler are handled automatically by the server

### Flux Example Prompts

**Portrait:**
```
A young woman with long flowing hair and striking blue eyes wearing a
school uniform, standing beneath cherry blossom trees with soft natural
light filtering through the petals
```

**Landscape:**
```
A dramatic mountain landscape at sunset with towering peaks reflected in
a perfectly still alpine lake, storm clouds lit orange and purple by the
setting sun
```

**Product shot:**
```
A pair of pristine white sneakers on a clean white background, shot from
a three-quarter angle with professional studio lighting and crisp focus
```

### Flux Schnell vs Flux Dev vs FLUX.2

- **Flux Schnell:** 1-4 steps, fastest generation (~5-10s). Good for drafts;
  do not rely on it for final-grade detail.
- **Flux Dev:** 20 steps, higher quality (~60-120s). Use for final output.
- **FLUX.2:** Newest BFL generation. Same prose grammar; same no-negative-
  prompts limitation. Even better in-scene text and architectural detail.

All Flux variants use Euler sampler, Simple scheduler, CFG 1.0, and
distilled CFG 3.5 (set automatically by the server).

## SD 3 / 3.5 — Triple-encoder, prose-friendly

SD 3 and 3.5 use a triple-encoder architecture (CLIP-L + OpenCLIP-bigG +
T5-XXL). They benefit from descriptive prose for the T5 stream — same
profile as Flux — but **do** support negative prompts (unlike Flux).

**Key differences from SDXL:**
- Use complete sentences, not comma-separated tags.
- Skip SDXL-style `(weight:1.2)` parens — wrong syntax for SD3.
- Negative prompts work natively; use them for excluded elements.
- 3.5 Large Turbo is 4-step distilled, similar speed/quality tradeoff to
  Flux Schnell.

**Example:**
```
A weathered fishing boat moored at a stone harbour at dawn, gulls
circling overhead, soft cool light, painterly yet photoreal.
```

## Pony Diffusion XL — score_* prefix mandatory

Pony Diffusion XL (and AutismMix, Pony Realism, etc.) is an SDXL fine-tune
with a strict tag grammar requirement. The leading tag block is mandatory:

```
score_9, score_8_up, score_7_up, score_6_up, score_5_up, score_4_up,
source_anime, rating_safe, <your subject and description>
```

Variants of the source/rating tags:
- `source_anime` / `source_pony` / `source_furry`
- `rating_safe` / `rating_questionable` / `rating_explicit`

Without the `score_*` prefix, output quality collapses visibly. Pony also
underperforms vs other SDXL fine-tunes for photorealism — it's tuned for
stylised character art.

## Illustrious-XL / NoobAI-XL — modern anime SDXL

Illustrious-XL and NoobAI-XL have largely supplanted Animagine for anime
SDXL work. Same Danbooru-style tag grammar as Animagine but with a much
larger character / style dataset.

```
1girl, long hair, blue eyes, school uniform, cherry blossoms,
masterpiece, best quality, very aesthetic
```

**NoobAI v-prediction variants** need the v-prediction sampler config
(epsilon-prediction is wrong for those weights and produces noise) — check
the checkpoint's documentation.

## Aspect Ratios

Supported aspect ratios: `1:1`, `16:9`, `9:16`, `3:2`, `2:3`.
The server maps these to optimal pixel dimensions for each SD model.

## Workflow

1. Check `list_providers` to see available models, their `prompt_style`
   (`"clip"` for SD 1.5/SDXL/Pony/Illustrious/NoobAI, `"natural_language"`
   for Flux/SD3), and their per-checkpoint `style_profile.style_hints` for
   any fine-tune-specific guidance.
2. Write your prompt in the appropriate style for the model:
   - **SD 1.5 / SDXL** — add quality tags and a negative prompt.
   - **Flux 1 / Flux Schnell / FLUX.2** — write natural language; skip
     negative prompt (CFG=1 distilled, unsupported).
   - **SD 3 / 3.5** — write natural language; **do** include a negative
     prompt (SD3 supports them natively, unlike Flux); skip SDXL-style
     `(weight:1.2)` parens.
   - **Pony Diffusion XL** — prepend the mandatory `score_9, score_8_up,
     score_7_up, …` block before all other tags. Add `source_anime` /
     `source_pony` / `source_furry` and a `rating_*` tag. Without the
     `score_*` prefix, output collapses.
   - **Illustrious-XL / NoobAI-XL** — Danbooru-style tags
     (`1girl, long hair, …, masterpiece, best quality, very aesthetic`).
     For NoobAI v-prediction variants, ensure the v-prediction sampler
     config is set on the WebUI side (epsilon-prediction is wrong for
     those weights and produces noise).
3. Call `generate_image` with `provider="sd_webui"`:

**SD 1.5 / SDXL example:**
```
generate_image(
    prompt="1girl, long hair, school uniform, cherry blossoms, masterpiece, best quality",
    negative_prompt="lowres, bad anatomy, bad hands, worst quality, low quality",
    provider="sd_webui",
    aspect_ratio="2:3"
)
```

**Flux example:**
```
generate_image(
    prompt="A young woman with long hair in a school uniform standing beneath cherry blossom trees",
    provider="sd_webui",
    model="flux1-dev-bnb-nf4-v2.safetensors",
    aspect_ratio="2:3"
)
```
"""


_LUCIDE = "https://unpkg.com/lucide-static/icons/{}.svg"


def _build_apply_style_text(entry: StyleEntry, user_request: str) -> str:
    """Build the combined prompt text for applying a style.

    Extracted as a module-level function for testability.

    Args:
        entry: The style to apply.
        user_request: The user's image generation request.

    Returns:
        Combined text with style body, defaults, and adaptation instructions.
    """
    defaults = []
    if entry.provider:
        defaults.append(f"- Suggested provider: {entry.provider}")
    if entry.aspect_ratio:
        defaults.append(f"- Aspect ratio: {entry.aspect_ratio}")
    if entry.quality:
        defaults.append(f"- Quality: {entry.quality}")
    if entry.tags:
        defaults.append(f"- Tags: {', '.join(entry.tags)}")

    defaults_text = "\n".join(defaults) if defaults else "- (no defaults set)"

    return f"""\
# Apply Style: {entry.name}

## User Request

{user_request}

## Style Creative Brief

{entry.body}

## Style Defaults

{defaults_text}

## Instructions

You are applying the style "{entry.name}" to the user's request above.

**Important: Styles are creative briefs, not prompt fragments.**

1. Read the style's creative brief above and extract the visual direction:
   palette, composition, mood, medium, constraints.
2. Combine that direction with the user's specific request.
3. Compose a provider-appropriate prompt for `generate_image`:
   - **For OpenAI / Gemini:** Compose in natural language. Describe the
     scene incorporating the style's visual direction.
   - **For SD WebUI (SD 1.5 / SDXL / RealVisXL / Juggernaut):** Compose as
     comma-separated CLIP tags. Translate the style's concepts into
     appropriate tags. Include a negative prompt based on the style's
     constraints.
   - **For SD WebUI (Flux 1 / Flux Schnell / FLUX.2):** Compose in natural
     language. Skip the negative prompt (Flux is CFG=1 distilled).
   - **For SD WebUI (SD 3 / 3.5):** Compose in natural language; **do**
     include a negative prompt for excluded elements (SD3 supports them
     natively).
   - **For SD WebUI (Pony Diffusion XL):** Compose Danbooru-style tags with
     the mandatory `score_9, score_8_up, score_7_up, score_6_up,
     score_5_up, score_4_up` prefix, plus a `source_*` and `rating_*` tag.
     Without the `score_*` prefix the output collapses.
   - **For SD WebUI (Illustrious-XL / NoobAI-XL):** Compose Danbooru-style
     anime tags (artist, character, series, descriptors).
   - Check `list_providers` for each model's `prompt_style` field plus
     `style_profile.style_hints` for fine-tune-specific guidance.
4. **Do NOT copy the style text verbatim into the prompt.** Interpret and
   adapt it for the target provider's format.
5. Use the style's frontmatter defaults (provider, aspect_ratio, quality)
   as starting parameters, unless the user explicitly overrides them.
6. Use `select_provider` guidance for provider choice when provider is
   "auto" or not specified in the style."""


def register_prompts(mcp: FastMCP) -> None:
    """Register all MCP prompts on *mcp*.

    Args:
        mcp: The :class:`~fastmcp.FastMCP` instance to register prompts on.
    """

    @mcp.prompt(
        name="select_provider",
        description=(
            "Use when choosing a specific provider instead of auto-selection. "
            "Not needed when provider='auto' (the default)."
        ),
        icons=[Icon(src=_LUCIDE.format("route"), mimeType="image/svg+xml")],
    )
    def select_provider() -> str:
        """Return provider selection guidance."""
        return _SELECT_PROVIDER_PROMPT

    @mcp.prompt(
        name="sd_prompt_guide",
        description=(
            "Guide for writing SD WebUI prompts — "
            "CLIP tags (SD 1.5 / SDXL / Pony / Illustrious / NoobAI), "
            "prose (Flux 1 / FLUX.2 / Schnell / SD 3 / 3.5)"
        ),
        icons=[Icon(src=_LUCIDE.format("book-open-text"), mimeType="image/svg+xml")],
    )
    def sd_prompt_guide() -> str:
        """Return Stable Diffusion prompt writing guide."""
        return _SD_PROMPT_GUIDE

    @mcp.prompt(
        name="apply_style",
        description=(
            "Apply a saved style preset to an image generation request. "
            "Loads the style's creative brief and instructs the LLM to "
            "interpret it per-provider — not copy it verbatim."
        ),
        icons=[Icon(src=_LUCIDE.format("palette"), mimeType="image/svg+xml")],
    )
    def apply_style(
        style_name: str,
        user_request: str,
        service: ImageService = Depends(get_service),
    ) -> str:
        """Return combined prompt text for applying a style to a request.

        Args:
            style_name: Name of the style preset to apply.
            user_request: The user's image generation request.

        Returns:
            Combined text with style body, defaults, and adaptation
            instructions for the LLM.
        """
        entry = service.get_style(style_name)
        if entry is None:
            return (
                f"Style '{style_name}' not found. "
                "Use style://list to browse available styles, "
                "or save_style to create a new one."
            )

        return _build_apply_style_text(entry, user_request)
