# Model Catalog

Per-model narrative metadata read by LLMs when choosing between providers and models. Closed-list providers (`openai`, `gemini`, `placeholder`) use exact-key lookup against `MODEL_STYLES`. SD WebUI uses the regex-ordered `CHECKPOINT_PATTERNS` table.

Source: `src/image_generation_mcp/providers/model_styles.py`. Regenerate with `uv run python scripts/render_model_catalog.py`.

## OpenAI

Models exposed by the `openai` provider. Each model resolves via exact-key lookup against the registry.

| Model ID               | Label                         | Lifecycle  |
| ---------------------- | ----------------------------- | ---------- |
| `chatgpt-image-latest` | OpenAI ChatGPT Image (latest) | current    |
| `dall-e-2`             | OpenAI DALL-E 2 (legacy)      | legacy     |
| `dall-e-3`             | OpenAI DALL-E 3 (deprecated)  | deprecated |
| `gpt-image-1`          | OpenAI GPT Image 1 (legacy)   | legacy     |
| `gpt-image-1-mini`     | OpenAI GPT Image 1 Mini       | current    |
| `gpt-image-1.5`        | OpenAI GPT Image 1.5          | current    |
| `gpt-image-2`          | OpenAI GPT Image 2            | current    |

### OpenAI ChatGPT Image (latest)

**Best for:** Floating alias that always points at the image model currently powering ChatGPT. Capabilities track whichever gpt-image model is latest (gpt-image-2 at time of writing). Use when you want 'always newest' without pinning a version. Same descriptive-paragraph prompt grammar as the gpt-image family.

**Avoid:** Its capability surface can shift under you as OpenAI moves the alias, so pin a concrete id (gpt-image-2 / gpt-image-1.5) for reproducible production workflows. Transparent backgrounds are not guaranteed (the alias currently resolves to gpt-image-2, which dropped alpha); pick gpt-image-1.5 if you need transparency. Avoid CLIP-style tag dumps and negative-prompt syntax; real-named-people likenesses are filtered.

**Good prompt:** `A cozy isometric illustration of a corner reading nook: overstuffed armchair, tall bookshelf, warm floor lamp, potted monstera, soft afternoon light. 1:1.`

**Bad prompt:** `reading nook, cozy, isometric, 8k (tag-soup — the gpt-image family wants descriptive sentences)`

### OpenAI DALL-E 2 (legacy)

> Use only for inpainting on legacy flows. Prefer gpt-image-1.5 for any new generation work.

**Best for:** Older OpenAI model retained mostly for inpainting / mask edits at low cost. Limited style fidelity vs current gpt-image-\* family. `1024x1024` only. Useful for cheap edits where new code paths can't be added.

**Avoid:** Don't use for new generation work. Lacks transparent background support, aspect ratios beyond 1:1, in-image text, and negative prompts. Quality is well below current OpenAI models.

**Good prompt:** `Inpaint a missing hand on an existing 1024x1024 image (mask edit only, not for new-from-scratch generation)`

**Bad prompt:** `Detailed photoreal product shot for a marketing campaign (use gpt-image-1.5 instead; DALL-E 2 quality is well behind)`

### OpenAI DALL-E 3 (deprecated)

> OpenAI API removal scheduled 2026-05-12. Migrate to gpt-image-1.5 for new long-lived workflows.

**Best for:** Strong creative interpretation and excellent compliance with multi-clause prompts. Good for stylised illustrations, cinematic concept art, and `vivid`-style hero images where you want the model to embellish. The `natural` style produces flatter, more photoreal output suitable for stock-photo and logo work.

**Avoid:** Don't use for in-image text: text rendering is unreliable. No edits, no inpainting, no transparent background, no negative prompts, no aspect ratios beyond `1024x1024` / `1024x1792` / `1792x1024`. Cannot render named real people. Silently rewrites short prompts, so inspect `revised_prompt` to see what was actually used.

**Good prompt:** `A wide cinematic painting in the style of Thomas Cole's "Desolation": overgrown classical ruins on a cliff at dusk, vines reclaiming marble columns, single shaft of warm light. Style: natural.`

**Bad prompt:** `A birthday cake that says "HAPPY BIRTHDAY SARAH" in elegant script (DALL-E 3 will likely garble the text; route to gpt-image-1.5 for typography-critical work)`

### OpenAI GPT Image 1 (legacy)

> Newer OpenAI image models (gpt-image-1.5) offer better fidelity. This model remains available for compatibility.

**Best for:** Earlier flagship; same descriptive-paragraph prompt grammar as gpt-image-1.5. Supports transparent backgrounds and the same three aspect ratios. Still capable for general work; newer siblings give better fidelity and instruction following.

**Avoid:** Avoid CLIP-style tag dumps. Negative-prompt syntax is not supported. Real-named-people likenesses are filtered. Prefer gpt-image-1.5 for new long-lived workflows.

**Good prompt:** `Studio portrait of a senior watchmaker examining a movement with a loupe, warm rim light from a window, shallow depth of field, no text in frame.`

**Bad prompt:** `watchmaker, masterpiece, 8k, ultradetailed (tag-soup style; use descriptive sentences instead)`

### OpenAI GPT Image 1 Mini

**Best for:** Cheaper variant of gpt-image-1 with similar capabilities at a lower per-image cost. Same descriptive-paragraph grammar; same three aspect ratios. Good default for high-volume drafts and iteration where small quality differences vs the full model are acceptable.

**Avoid:** Avoid CLIP-style tag dumps. Negative-prompt syntax is not supported. Same content filters as the full model. For final-grade output where small quality differences matter, prefer gpt-image-1.5.

**Good prompt:** `Quick draft sketch: a fox curled up on a windowsill at dusk, soft watercolour palette, simple background.`

**Bad prompt:** `fox, watercolour, ((masterpiece)), [blurry] (parenthetical weight syntax is SD-specific; gpt-image-* ignores it)`

### OpenAI GPT Image 1.5

**Best for:** Previous-generation OpenAI flagship; still the right pick when the work needs transparent backgrounds (gpt-image-2 dropped alpha support). Strong instruction following for photorealistic shots, illustrations, product mockups, infographics, and marketing assets where layout and typography matter. Excels with descriptive paragraphs ordered scene → subject → details → constraints, and with text in image given in quotes with explicit typography hints. Supports `1024x1024` / `1024x1536` / `1536x1024`.

**Avoid:** Avoid CLIP-style comma-separated tag dumps, which underperform vs descriptive sentences. Negative-prompt syntax is not supported; describe exclusions positively. Long, multi-element scenes with strict spatial composition can drift. Real-named-people likenesses are filtered. No identity consistency across calls.

**Good prompt:** `Editorial product photo of a beige ceramic coffee mug on a worn oak table, shallow depth of field, soft window light from the left, warm muted palette. No text, no logos.`

**Bad prompt:** `coffee mug, masterpiece, 8k, hyperdetailed, --no text (tag-soup + unsupported negative-prompt syntax — wastes tokens, mostly ignored)`

### OpenAI GPT Image 2

**Best for:** Current OpenAI flagship image model with the highest-fidelity instruction following in the family. Best for demanding production work, dense in-image typography, complex multi-element compositions, and prompts that require strict adherence to layout / brand / scene direction. Same descriptive-paragraph prompt grammar as gpt-image-1.5; same three aspect ratios. Drops transparent-background support, so use gpt-image-1.5 if you need transparency.

**Avoid:** Transparent backgrounds are not supported; pick gpt-image-1.5 for icons / stickers / logos that need alpha. Avoid CLIP-style tag dumps and negative-prompt syntax. Real-named-people likenesses are filtered. Cost per image is materially higher than gpt-image-1.5 / mini, so pick those for drafts.

**Good prompt:** `Magazine cover layout with the headline 'Urban Foragers' set in a bold geometric serif, subhead 'A Field Guide to City Edibles', central full-bleed photo of a moss-covered tree stump in dappled afternoon light. 2:3.`

**Bad prompt:** `magazine, foragers, bold serif (single-line keyword set — gpt-image-2 shines on richly described prompts; underprompting wastes the cost premium)`

## Gemini

Models exposed by the `gemini` provider. Each model resolves via exact-key lookup against the registry.

| Model ID                      | Label                                            | Lifecycle |
| ----------------------------- | ------------------------------------------------ | --------- |
| `gemini-2.5-flash-image`      | Gemini 2.5 Flash Image (Nano Banana)             | legacy    |
| `gemini-3-pro-image`          | Gemini 3 Pro Image (Nano Banana Pro)             | current   |
| `gemini-3.1-flash-image`      | Gemini 3.1 Flash Image (Nano Banana 2)           | current   |
| `gemini-3.1-flash-lite-image` | Gemini 3.1 Flash Lite Image (Nano Banana 2 Lite) | current   |

### Gemini 2.5 Flash Image (Nano Banana) (legacy)

> Superseded by the Gemini 3 image models (gemini-3.1-flash-image and up). Still GA, but Google recommends migrating to the newer tiers for better quality, speed, and multi-image composition.

**Best for:** Fast, low-latency generation and conversational image editing with multi-turn refinement, multi-image compositing (up to 3 inputs), character consistency across iterations, in-image text, and natural-language local edits ('remove the stain', 'change pose to running'). Strong photorealism with photographic vocabulary (lens, lighting, aspect ratio). Supports 14 aspect ratios from 21:9 cinematic to 9:16 vertical. Cheap (~$0.04/image), making it a good default for high-volume ideation.

**Avoid:** Avoid Stable-Diffusion-style comma-separated tag lists, which underperform vs descriptive sentences. No negative-prompt parameter; phrase exclusions positively. Do not rely on transparent backgrounds. All outputs carry an invisible SynthID watermark, making them unsuitable for workflows requiring unmarked pixels. Not the strongest pick for dense professional typography. Limit reference inputs to 3 images.

**Good prompt:** `A worn leather-bound journal lying open on a rainy windowsill at dusk. Soft cyan rim-light from outside, warm tungsten lamp on the right. The left page reads, in handwritten script: "Day 42 — still no signal." Shot on 50mm, shallow depth of field. 16:9.`

**Bad prompt:** `journal, rainy, moody, cinematic, 8k, masterpiece, --no people (tags + unsupported negative — Google docs explicitly call this the wrong pattern)`

### Gemini 3 Pro Image (Nano Banana Pro)

**Best for:** GA Pro tier with reasoning: highest-fidelity option, suited to demanding production-grade work where Flash falls short. Best at dense typography, accurate localisation, and strict brand compliance. Accepts up to 14 reference images. Same prompt grammar as the Flash variants.

**Avoid:** Don't use for cheap drafts: cost per image is materially higher than Flash. Same SynthID-watermark caveat. Tag-soup still underperforms.

**Good prompt:** `Magazine cover layout for a quarterly architecture journal: headline 'Concrete Futures' in bold serif, subhead 'Brutalism Reconsidered', central full-bleed photo of a weathered Le Corbusier facade at golden hour. 3:4.`

**Bad prompt:** `magazine, architecture, brutalism (single-line keyword set — Gemini Pro shines on richly described prompts; underprompting wastes the cost premium)`

### Gemini 3.1 Flash Image (Nano Banana 2)

**Best for:** GA successor to 2.5 Flash with reasoning ('thinking') support and up to 14 reference images for multi-image composition. The general workhorse tier, good for prompts that benefit from layout reasoning: infographics, structured layouts, multi-element compositions where spatial relationships matter. Same descriptive-prose grammar as 2.5 Flash; same 14 aspect ratios.

**Avoid:** Avoid tag-soup; same SynthID-watermark caveat as 2.5 Flash. No negative-prompt parameter; phrase exclusions positively. Do not rely on transparent backgrounds.

**Good prompt:** `A clean infographic explaining the water cycle on a soft pastel background, four labelled stages arranged in a circle, minimalist line illustration with gentle shadows. 4:3.`

**Bad prompt:** `water cycle, infographic, 8k, ultra-detailed (tag style — use descriptive sentences for Gemini)`

### Gemini 3.1 Flash Lite Image (Nano Banana 2 Lite)

**Best for:** Fastest, cheapest Gemini 3.1 image tier, engineered for speed and scale where latency and cost are the primary constraints. Supports reasoning ('thinking') and multi-image composition. Same descriptive-prose grammar and 14 aspect ratios as the rest of the family; a strong default for high-volume ideation.

**Avoid:** Avoid tag-soup; same SynthID-watermark caveat. No negative-prompt parameter; phrase exclusions positively. For the highest-fidelity typography or brand work, prefer gemini-3-pro-image.

**Good prompt:** `A friendly flat-illustration app icon of a smiling coffee cup with steam, rounded corners, soft drop shadow, warm palette. 1:1.`

**Bad prompt:** `coffee cup icon, flat, vector, 8k (tag style — use descriptive sentences for Gemini)`

## Placeholder

Models exposed by the `placeholder` provider. Each model resolves via exact-key lookup against the registry.

| Model ID      | Label                   | Lifecycle |
| ------------- | ----------------------- | --------- |
| `placeholder` | Solid-color placeholder | current   |

### Solid-color placeholder

**Best for:** Returns a deterministic solid-color PNG at the requested aspect ratio. Use for testing pipeline plumbing, mocking generation in unit tests, or zero-cost demos without invoking a real provider.

**Avoid:** Not a real image generator. Do not use for any task that requires actual image content.

**Good prompt:** `any prompt — placeholder ignores prompt content and emits a solid-color PNG at the requested size`

**Bad prompt:** `any prompt where the user actually wants a generated image (use openai, gemini, or sd_webui instead)`

## SD WebUI

SD WebUI checkpoints resolve via the regex-ordered `CHECKPOINT_PATTERNS` table. **First match wins.** Patterns are ordered specific-before-generic, with an empty-pattern fallback as the final entry to guarantee a non-None match for every checkpoint name.

### Pattern catalog (in match order)

| #   | Pattern                       | Label                                             |
| --- | ----------------------------- | ------------------------------------------------- |
| 1   | `flux[._-]?2`                 | FLUX.2 (current photorealistic flagship)          |
| 2   | \`flux.\*schnell              | schnell.\*flux\`                                  |
| 3   | `flux`                        | Flux 1 dev/pro (photorealistic / highly detailed) |
| 4   | \`pony                        | score_9                                           |
| 5   | \`illustrious                 | noob.?ai\`                                        |
| 6   | `animagine`                   | Animagine XL (anime SDXL)                         |
| 7   | `coloring.?book`              | Coloring Book (line-art SD1.5)                    |
| 8   | `juggernaut(?!.*illustrious)` | Juggernaut XL (photorealistic SDXL)               |
| 9   | \`dreamshaperxl.\*lightning   | dreamshaperxl.\*alpha\`                           |
| 10  | \`dreamshaperxl               | dreamshaper.\*xl\`                                |
| 11  | `dreamshaper`                 | DreamShaper (adaptable SD1.5)                     |
| 12  | \`sd3                         | sd_3                                              |
| 13  | \`sd_xl_base                  | sdxl_base                                         |
| 14  | \`realvisxl                   | realvis\`                                         |
| 15  | \`v1[-\_]5                    | sd\[-_\]?1\[-._\]?5\`                             |
| 16  | *(default fallback)*          | Unknown checkpoint (SD general-purpose defaults)  |

#### Pattern: `flux[._-]?2`

### FLUX.2 (current photorealistic flagship)

**Best for:** Newest BFL Flux generation. Photorealistic imagery with extreme fine detail; coherent in-scene text; strong architectural and product photography. Natural-language prose prompts; T5 encoder.

**Avoid:** FLUX.2 does not support negative prompts (CFG=1 distilled). Anime / cel-shaded / low-detail illustration styles fight the model. Don't use SD-style weighted parens or BREAK.

**Good prompt:** `style="cinematic urban photography", medium="digital photograph with shallow DOF"`

**Bad prompt:** `style="watercolor wash", medium="hand-painted ink" (FLUX.2 is tuned for photorealism; painterly media will fight the model)`

#### Pattern: `flux.*schnell|schnell.*flux`

### Flux Schnell (1-4 step distilled)

**Best for:** Distilled Flux variant for rapid drafts (1-4 steps, CFG=1). Same natural-language prompt style as Flux dev. Best for ideation passes where iteration speed dominates.

**Avoid:** No negative prompts (CFG=1, fully distilled). Quality below Flux dev / FLUX.2; don't use for final-grade output. Highly detailed textures suffer at 1-4 step counts.

**Good prompt:** `style="cinematic environment concept", medium="painterly digital art, broad strokes" (4 steps)`

**Bad prompt:** `style="hyperreal skin pores at 4K", medium="macro photograph" (Schnell sacrifices fine detail for speed)`

#### Pattern: `flux`

### Flux 1 dev/pro (photorealistic / highly detailed)

**Best for:** Strong photorealistic output with extreme fine detail. Suited to architectural photography, natural lighting, product shots, documentary portraiture, and coherent text in scene. Natural-language prose; T5 encoder; CFG=1 distilled.

**Avoid:** Negative prompts are unsupported (CFG=1 distilled). Anime / cel-shading / heavy painterly textures fight the model. Don't use SD-style weighted parens or BREAK.

**Good prompt:** `style="cinematic urban photography", medium="digital photograph with shallow DOF"`

**Bad prompt:** `style="watercolor wash", medium="hand-painted ink" (Flux is tuned for photorealism; painterly media will fight the model)`

#### Pattern: `pony|score_9|autismmix`

### Pony Diffusion XL (mandatory score\_\* tag prefix)

**Best for:** Wide-ranging SDXL fine-tune. Excellent for stylised character art, anime, and varied art styles when prompted with the mandatory leading tag block: 'score_9, score_8_up, score_7_up, score_6_up, score_5_up, score_4_up, source_anime, rating_safe' (or source_pony/source_furry, rating_questionable, etc.). Without the score\_\* prefix, output quality collapses.

**Avoid:** Bare prompts without the score\_\* prefix produce visibly degraded results. Photorealistic catalog work is out of scope: Pony is stylised by design. Natural-language prose underperforms vs Booru-style tag grammar.

**Good prompt:** `score_9, score_8_up, score_7_up, score_6_up, source_anime, rating_safe, 1girl, school uniform, cherry blossoms, soft lighting`

**Bad prompt:** `1girl, anime, cherry blossoms (missing score_* prefix — output collapses)`

#### Pattern: `illustrious|noob.?ai`

### Illustrious-XL / NoobAI-XL (modern anime SDXL bases)

**Best for:** Current-generation anime SDXL bases that have largely supplanted Animagine in 2025-26. Danbooru-style tag grammar (artist tags, character tags, e6/Danbooru-style). Much larger character/style dataset than Animagine 3.x. Strong cel-shading and expressive character art.

**Avoid:** Photorealism (these bases are anime-specialised). NoobAI v-prediction variants need the v-prediction sampler config; wrong sampler produces noise. Natural-language prose underperforms vs tag grammar.

**Good prompt:** `1girl, long hair, blue eyes, school uniform, cherry blossoms, masterpiece, best quality, very aesthetic`

**Bad prompt:** `style="documentary photograph", medium="35mm film" (Illustrious/NoobAI are anime-specialised; photographic styles produce off-distribution outputs)`

#### Pattern: `animagine`

### Animagine XL (anime SDXL)

**Best for:** Anime illustration base. Danbooru-style tag vocabulary, clean cel shading, expressive character art, vivid saturated palette, manga panel compositions. Animagine 4.x recommends '1girl/1boy, character (series), rating, …, masterpiece, high score, great score, absurdres'.

**Avoid:** Photorealism, photography-style lighting, gritty texture, oil painting, detailed backgrounds without anime stylisation. For broader character/style coverage, consider Illustrious-XL or NoobAI-XL.

**Good prompt:** `1girl, long hair, school uniform, cherry blossoms, masterpiece, high score, absurdres`

**Bad prompt:** `style="documentary photograph", medium="35mm film" (Animagine is anime-specialised; photographic styles produce off-distribution outputs)`

#### Pattern: `coloring.?book`

### Coloring Book (line-art SD1.5)

**Best for:** Clean outlines on white background, no fill colors, strong linework, simple shapes, children's-book-friendly compositions, decorative borders.

**Avoid:** Photorealism, color renders, painterly textures, complex shading, dark backgrounds, photographic lighting.

**Good prompt:** `style="bold ink linework", medium="black-and-white outline drawing"`

**Bad prompt:** `style="photorealistic portrait", medium="oil paint with rich color" (this checkpoint is fine-tuned for line-art only; color renders will fail)`

#### Pattern: `juggernaut(?!.*illustrious)`

### Juggernaut XL (photorealistic SDXL)

**Best for:** Photorealistic SDXL checkpoint. Strong at rendering skin pores, fabric weave, and fine material textures under cinematic or dramatic rim lighting, with good environmental storytelling. Recent Juggernaut X / XI handle some stylised work too.

**Avoid:** Anime, cartoon, flat illustration. Watercolor and comic-ink styles are weaker than dedicated stylised checkpoints (usable but not the model's strength).

**Good prompt:** `style="gritty photorealistic urban", medium="digital photo"`

**Bad prompt:** `style="watercolor wash", medium="traditional ink" (Juggernaut is tuned for photorealism; stylised media will underperform)`

#### Pattern: `dreamshaperxl.*lightning|dreamshaperxl.*alpha`

### DreamShaperXL Lightning / Alpha (fast fantasy SDXL)

**Best for:** Suited to fantasy concept art and painterly illustration with rich color and dramatic character portraits. Run at 3-6 steps with CFG ~2 and DPM++ SDE Karras (per Civitai). Fast ideation pass for stylised work.

**Avoid:** Photorealism (stylised by design) and strict architectural accuracy are a poor fit. Highly detailed textures suffer at low step counts.

**Good prompt:** `style="dramatic fantasy concept art", medium="painterly digital illustration"`

**Bad prompt:** `style="hyperrealistic skin detail at 4K", medium="macro photograph" (Lightning checkpoints sacrifice fine detail for speed)`

#### Pattern: `dreamshaperxl|dreamshaper.*xl`

### DreamShaperXL (all-purpose fantasy SDXL)

**Best for:** Fantasy illustration, painterly portraits, concept-art style, stylised environments, strong use of negative space.

**Avoid:** Strict photorealism, clinical document photography, flat-color infographic styles.

**Good prompt:** `style="painterly fantasy illustration", medium="digital concept art"`

**Bad prompt:** `style="clinical product photography", medium="catalog studio shot" (DreamShaperXL is stylised by design; strict photo-real fights the model)`

#### Pattern: `dreamshaper`

### DreamShaper (adaptable SD1.5)

**Best for:** General-purpose stylised illustration, fantasy character art, soft painterly lighting, portrait and environmental compositions. Adapts well across style tags rather than locking to a single category.

**Avoid:** Extreme photorealism (slightly stylised by design), Danbooru/anime tag grammar (use natural descriptors).

**Good prompt:** `style="painterly fantasy character portrait", medium="soft digital illustration"`

**Bad prompt:** `style="Danbooru anime tags", medium="cel-shading" (DreamShaper SD1.5 expects natural descriptors, not anime tag grammar)`

#### Pattern: `sd3|sd_3|sd3_5|sd3\.5`

### SD 3 / 3.5 (triple-encoder; natural-language)

**Best for:** Triple-encoder architecture (CLIP-L + OpenCLIP-bigG + T5-XXL). Benefits from natural-language prose for the T5 stream, sharing a prose-friendly profile with Flux. Supports negative prompts (unlike Flux). 3.5 Large Turbo is 4-step distilled.

**Avoid:** CLIP tag-soup underperforms vs descriptive prose. Architecturally distinct from SDXL, so don't expect SDXL fine-tune behaviour to carry over.

**Good prompt:** `A weathered fishing boat moored at a stone harbour at dawn, gulls circling overhead, soft cool light, painterly yet photoreal, 16:9 cinematic framing.`

**Bad prompt:** `fishing boat, harbour, dawn, masterpiece, 8k, ((highly detailed)) (tag-soup with weighted parens — SD3 wants prose, parens are SDXL/SD1.5 syntax)`

#### Pattern: `sd_xl_base|sdxl_base|sdxl-base`

### SDXL Base (general-purpose SDXL)

**Best for:** Broad style range, photography, illustration, concept art. Responds well to explicit style tokens. Works at 25-30+ steps for coherence.

**Avoid:** Anime-specific Danbooru vocabulary without style priming. Low step counts produce incoherent output (needs 25-30+ for coherence). The SDXL refiner is rarely used in 2026 workflows; modern fine-tunes drop it in favour of hires-fix / upscalers.

**Good prompt:** `style="cinematic illustration with explicit style tokens", medium="digital art"`

**Bad prompt:** `style="anime without style priming", medium="bare Danbooru tags" (SDXL base needs explicit style direction; bare anime grammar underperforms)`

#### Pattern: `realvisxl|realvis`

### RealVisXL (photorealistic SDXL)

**Best for:** Current-generation SDXL photorealism fine-tune. Sharp textural detail, skin/fabric/material fidelity, cinematic lighting. Has eclipsed Juggernaut share in 2026 SDXL photoreal work.

**Avoid:** Anime, cel-shading, watercolor, comic-ink. Painterly stylisation fights the photorealistic tuning.

**Good prompt:** `style="documentary photorealism", medium="digital photo, sharp focus, natural light"`

**Bad prompt:** `style="cel-shaded anime", medium="flat colour" (RealVisXL is photoreal-tuned; stylised media underperforms)`

#### Pattern: `v1[-_]5|sd[-_]?1[-._]?5`

### SD 1.5 (general-purpose base)

**Best for:** Broad style range. Native latent at 512px; commonly used at `512x768` / `768x512` before hires-fix. With hires-fix or upscaler chains routinely produces `1024x1536`+. Well-supported by community LoRAs.

**Avoid:** Photorealistic skin detail at high resolution without hires-fix; SDXL-native aspect ratios. Don't expect SDXL-tier coherence at SDXL resolutions without upscaling.

**Good prompt:** `style="watercolor portraiture", medium="ink illustration"`

**Bad prompt:** `style="hyperrealistic skin at 1024px", medium="macro studio photograph" (SD 1.5 native latent is 512²; use SDXL or run hires-fix)`

#### Pattern: *(default fallback, empty pattern)*

### Unknown checkpoint (SD general-purpose defaults)

**Best for:** Stable Diffusion is well suited to stylised work such as fantasy environments and character art. Use explicit style tokens (such as 'watercolor painting', 'cinematic photograph') for best results.

**Avoid:** Coherent embedded text and photographic product catalogs without specialised fine-tuning.

**Good prompt:** `style="painterly fantasy illustration with explicit style tokens", medium="digital concept art"`

**Bad prompt:** `style="coherent embedded text", medium="document scan with readable signage" (Stable Diffusion generally cannot render legible text)`
