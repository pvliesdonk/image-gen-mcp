"""MCP resource registrations.

Exposes provider capabilities, image assets, metadata, and the MCP Apps
image viewer as MCP resources.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import UTC, datetime

from fastmcp import FastMCP
from fastmcp.apps import AppConfig
from fastmcp.dependencies import Depends
from fastmcp.resources import ResourceContent, ResourceResult
from mcp.types import Icon

from image_generation_mcp._server_deps import get_service
from image_generation_mcp._vendored_sdk import (
    IMPORT_SPECIFIER as _SDK_SPECIFIER,
)
from image_generation_mcp._vendored_sdk import (
    SDK_BASE64 as _SDK_B64,
)
from image_generation_mcp.config import _ENV_PREFIX
from image_generation_mcp.domain import ImageService
from image_generation_mcp.providers.types import (
    SUPPORTED_ASPECT_RATIOS,
    SUPPORTED_BACKGROUNDS,
    SUPPORTED_QUALITY_LEVELS,
    SUPPORTED_RESOLUTIONS,
    ImageProviderError,
)

logger = logging.getLogger(__name__)

_LUCIDE = "https://unpkg.com/lucide-static/icons/{}.svg"
_IMAGE_VIEWER_URI = "ui://image-viewer/view.html"
_IMAGE_GALLERY_URI = "ui://image-gallery/view.html"

# Import-map that resolves the bare specifier to the vendored SDK bundle,
# eliminating the runtime CDN dependency on unpkg.com.
_SDK_IMPORT_MAP = (
    '  <script type="importmap">\n'
    "  "
    + json.dumps(
        {
            "imports": {
                _SDK_SPECIFIER: f"data:text/javascript;base64,{_SDK_B64}",
            }
        }
    )
    + "\n  </script>\n"
)


def _inject_sdk(html: str) -> str:
    """Insert the vendored SDK import-map before the module script tag."""
    target = '  <script type="module">'
    if target not in html:
        msg = "HTML template missing expected module script tag"
        raise ValueError(msg)
    return html.replace(target, _SDK_IMPORT_MAP + target, 1)


_PROMPT_GUIDE = """\
# Image Generation Prompt Guide

## General Tips

**Aspect ratio:** Choose based on content — `16:9` for landscapes and banners,
`9:16` for portraits and mobile, `3:2` for photos, `1:1` for icons and avatars.

**Quality levels:** Use `standard` for fast drafts and iteration. Use `hd` for
final output — on **Gemini**, enables model reasoning (thinking) for
significantly better composition; on **OpenAI**, selects the `high` quality
tier. SD WebUI and placeholder ignore this parameter.

**Resolution tiers:** Independent of `quality`, use `resolution` to control
output size. `standard` (default) uses each provider's normal size. `high`
and `max` unlock higher resolutions where supported — on **Gemini**, 2K and
4K, except the 1K-only `gemini-3.1-flash-lite-image` and
`gemini-2.5-flash-image`, which clamp down to 1K; on **OpenAI**, only
`gpt-image-2` goes beyond standard (up to 4K). Every other model ignores
this. Check `supported_resolutions` in `list_providers` before relying on
`high`/`max` for a specific model.

**Negative prompts:** Use them when you want to explicitly exclude unwanted
elements. Most effective on SD WebUI (native CLIP support). On OpenAI and
Gemini, they are appended as an "Avoid:" clause with weaker effect. Placeholder
ignores them.

**Background:** Set `background="transparent"` when generating assets for
compositing (logos, icons, stickers). Supported by OpenAI's `gpt-image-1` /
`gpt-image-1.5` / `gpt-image-1-mini` and placeholder (not `gpt-image-2` or
`chatgpt-image-latest`, which drop transparency). SD WebUI ignores this
parameter.

## OpenAI

**Lineup:** `gpt-image-2` (current flagship — highest fidelity, but drops
transparent-background support), `gpt-image-1.5` (previous-generation flagship;
the transparency pick), `gpt-image-1-mini` (cheaper current variant for
drafts), `chatgpt-image-latest` (floating alias to the newest ChatGPT image
model — pin a concrete id for reproducibility), `gpt-image-1` (legacy),
`dall-e-3` (deprecated — API removal 2026-05-12, migrate new work to
gpt-image-2 / gpt-image-1.5), `dall-e-2` (legacy; useful for cheap inpainting
only).
Check the `warnings` array on `list_providers` for the canonical lifecycle
state.

Natural language descriptions work well — write prompts as you would describe a
scene to a person. No need for comma-separated tags.

**Negative prompts:** Use an `"Avoid:"` clause appended to the prompt text,
e.g. `"Avoid: blurry, low resolution, watermark"`. The effect is weaker than
native negative prompt support.

**Strengths:** Text rendering, logos, typography, transparent backgrounds.
Also excels at photorealistic still life with high material fidelity (glass,
metal, fabric) and precise text on objects. Strong general-purpose generation.

**Style keywords:** Include style direction in natural language — "photorealistic",
"cinematic", "watercolor", "digital art", "minimalist", "flat design", "isometric",
"pixel art". These steer the aesthetic without needing CLIP tags.

**Text rendering tips:** Enclose exact text in quotes within the prompt, e.g.
`'a coffee shop sign that says "OPEN"'`. Specify font style if needed:
"bold sans-serif", "handwritten", "neon sign lettering".

**Quality levels:** `standard` maps to OpenAI's `auto` quality (lets the model
choose). `hd` maps to `high` for maximum detail.

**Resolution tiers:** Only `gpt-image-2` honors `resolution="high"`/`"max"`
(up to 4K, print-oriented output); every other model renders at its standard
size regardless of `resolution`.

## Gemini

**Lineup:** `gemini-3.1-flash-image` (default GA — Nano Banana 2, fast
versatile workhorse with reasoning / "thinking" support and multi-image
compositing up to 14 inputs), `gemini-3-pro-image` (Nano Banana Pro —
highest fidelity for layout-heavy or dense-typography work),
`gemini-3.1-flash-lite-image` (Nano Banana 2 Lite — fastest, lowest cost),
and `gemini-2.5-flash-image` (legacy GA, up to 3 inputs). All Gemini outputs
carry an invisible **SynthID watermark** — unsuitable for workflows requiring
bit-perfect originals.

Natural language descriptions work best — similar to OpenAI prompting style.

**Strengths:** Infographics, diagrams, structured layouts, complex
illustrations, and visual storytelling. Excels at character consistency, colour
palette adherence, and multi-element compositions. The `hd` quality level
activates model reasoning (thinking) which plans composition before rendering —
dramatically improves output on complex prompts.

**Quality levels:** `standard` uses minimal thinking (fast, free tier). `hd`
enables thinking (High) and text+image response modalities for significantly
better output quality and prompt adherence. Note: `hd` uses thinking tokens
which are billed.

**Resolution tiers:** Independent of `quality`, `resolution` controls output
size: `standard` is 1K, `high` is 2K, `max` is 4K. Only
`gemini-3.1-flash-image` and `gemini-3-pro-image` support the full range;
`gemini-3.1-flash-lite-image` and `gemini-2.5-flash-image` clamp down to 1K
regardless of the requested tier. Higher tiers may bill more even on the free
tier.

**Aspect ratios:** Gemini supports 14 aspect ratios including ultra-wide options
(`4:1`, `8:1`, `21:9`) useful for banners and panoramas.

**Negative prompts:** Appended as an "Avoid:" clause (same as OpenAI).

## SD WebUI (Stable Diffusion / Forge / reForge / Forge-neo)

SD WebUI supports multiple model architectures with different prompt styles.
Check `list_providers` to see each model's `prompt_style` field (`"clip"` or
`"natural_language"`) plus `style_profile.style_hints` for fine-tune-specific
guidance.

### SD 1.5 / SDXL (CLIP-based models)

Use comma-separated CLIP tags for best results. Order tags by importance —
tokens near the front of the prompt have the most influence.

**Tag order:** `subject, medium, style, lighting, camera, quality tags`

**Example prompts:**

Portrait:
```
1girl, long hair, blue eyes, school uniform, standing, cherry blossoms,
soft lighting, detailed face, masterpiece, best quality
```

Landscape:
```
mountain landscape, sunset, dramatic clouds, lake reflection,
cinematic lighting, wide angle, 8k, highly detailed
```

Product shot:
```
white sneakers, product photography, studio lighting, white background,
sharp focus, commercial photography, high resolution
```

**Quality tags:** Add these to improve output quality:
- `masterpiece, best quality` — general quality boost
- `highly detailed, sharp focus` — detail enhancement
- `8k, ultra high res` — resolution boost (use sparingly)
- `professional, award winning` — style refinement

**Negative prompt template:**

General-purpose:
```
lowres, bad anatomy, bad hands, text, error, missing fingers,
extra digit, fewer digits, cropped, worst quality, low quality,
normal quality, jpeg artifacts, signature, watermark, blurry
```

For photorealism, add: `cartoon, anime, illustration, painting, drawing, art, sketch`

For anime/illustration, add: `photo, realistic, 3d render`

**BREAK syntax:** Use `BREAK` to split long prompts into separate CLIP chunks,
giving each concept its own 77-token budget:
```
1girl, detailed face, blue eyes BREAK
forest background, sunlight through trees BREAK
masterpiece, best quality, sharp focus
```

**CLIP token limits:**
- SD 1.5: 77 tokens per chunk. Front-load the most important tags.
- SDXL: 77 tokens per chunk, two CLIP encoders (ViT-L + ViT-bigG).

**Model-specific advice:**
- **SD 1.5** — Best at 768px base resolution, 30 steps, CFG 7.0. Good for anime,
  illustration, and stylized content. Smaller model, faster generation.
- **SDXL** — Best at 1024px base resolution, 35 steps, CFG 7.5. Better for
  photorealism and high-detail scenes. Use for final-quality output.
- **SDXL Lightning/Turbo** — Distilled models, only 6 steps needed, CFG 2.0.
  Very fast but less controllable. Good for rapid iteration.

### Flux (natural language)

Flux models use a T5 text encoder, NOT CLIP. Write prompts as natural language
descriptions — the same style as OpenAI.

**Key differences from SD 1.5 / SDXL:**
- Use complete sentences, not comma-separated tags
- Do NOT include quality tags (`masterpiece`, `best quality`) — meaningless to Flux
- Do NOT write a negative prompt — Flux does not support them
- Do NOT use `BREAK` syntax — Flux does not use CLIP chunking
- CFG scale and sampler are handled automatically by the server

**Example prompts:**

Portrait:
```
A young woman with long flowing hair and striking blue eyes wearing a
school uniform, standing beneath cherry blossom trees with soft natural
light filtering through the petals
```

Landscape:
```
A dramatic mountain landscape at sunset with towering peaks reflected in
a perfectly still alpine lake, storm clouds lit orange and purple by the
setting sun
```

Product shot:
```
A pair of pristine white sneakers on a clean white background, shot from
a three-quarter angle with professional studio lighting and crisp focus
```

**Flux Schnell vs Flux Dev vs FLUX.2:**
- **Flux Schnell:** 1-4 steps, fastest generation. Good for drafts.
- **Flux Dev:** 20 steps, higher quality. Use for final output.
- **FLUX.2:** Newest BFL generation. Same grammar; better in-scene text and
  architectural detail. No negative prompts (CFG=1 distilled).

### SD 3 / 3.5 (T5 + CLIP triple-encoder)

SD 3 / 3.5 use a triple-encoder architecture (CLIP-L + OpenCLIP-bigG +
T5-XXL). Use descriptive prose for the T5 stream — same profile as Flux —
but **negative prompts work natively** (unlike Flux). Skip SDXL-style
`(weight:1.2)` parens; that's the wrong syntax for SD3. The 3.5 Large
Turbo variant is 4-step distilled.

```
A weathered fishing boat moored at a stone harbour at dawn, gulls
circling overhead, soft cool light, painterly yet photoreal.
```

### Pony Diffusion XL (mandatory score_* prefix)

Pony Diffusion XL family (incl. AutismMix, Pony Realism) has a strict
required tag prefix. Output collapses visibly without it:

```
score_9, score_8_up, score_7_up, score_6_up, score_5_up, score_4_up,
source_anime, rating_safe, 1girl, school uniform, cherry blossoms
```

Variants: `source_anime` / `source_pony` / `source_furry` and
`rating_safe` / `rating_questionable` / `rating_explicit`. Pony underperforms
vs RealVisXL / Juggernaut for photorealism — it's tuned for stylised
character art.

### Illustrious-XL / NoobAI-XL (modern anime SDXL)

Illustrious-XL and NoobAI-XL have largely supplanted Animagine for anime
SDXL in 2026. Same Danbooru-style tag grammar with a much larger
character / style dataset.

```
1girl, long hair, blue eyes, school uniform, cherry blossoms,
masterpiece, best quality, very aesthetic
```

NoobAI v-prediction variants need the v-prediction sampler config — wrong
sampler produces noise. Check the checkpoint's notes.

## Placeholder

Use for quick testing, mock-ups, and zero-cost placeholders. The placeholder
provider produces solid-color PNG images — the color is selected from a
6-color palette via SHA-256 hash of the prompt text, so the same prompt
always produces the same color. Supports `background="transparent"` for
RGBA output with alpha=0.

## Provider Selection

1. **Text, logos, typography** → `openai` (gpt-image-1.5).
2. **Transparent backgrounds** (icons, stickers) → `openai`
   (gpt-image-1.5 / gpt-image-1).
3. **Infographics, diagrams, structured layouts** → `gemini` with
   `quality="hd"` on a Pro/3.x model.
4. **Complex illustrations, visual storytelling, or multi-element
   compositions** → `gemini` with `quality="hd"`.
5. **Photorealism, portraits, product shots** → prefer `sd_webui`
   (RealVisXL / Juggernaut / Flux), fall back to `gemini` then `openai`.
6. **Anime, illustration, painting, art** → prefer `sd_webui` with
   **Illustrious-XL** or **NoobAI-XL** (modern anime SDXL bases that have
   largely supplanted Animagine). Pick **Pony Diffusion XL** for
   highly-stylised character art (mandatory `score_*` prefix). Animagine
   XL is a previous-generation fallback.
7. **Quick draft or iteration** → `gemini` at `standard` quality (fast,
   free tier) or `sd_webui` with a Lightning / Schnell checkpoint.
8. **Quick test or placeholder** → `placeholder`.
9. **General requests** → `gemini` when available, then `openai`.

Use `provider="auto"` for automatic selection, or specify a provider
directly. Call `list_providers` to see which providers are available, what
models each has loaded, and per-model `style_profile` narrative guidance.
The top-level `warnings` array on `list_providers` lists deprecated /
legacy models — avoid those for new long-lived workflows.
"""

_IMAGE_VIEWER_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="color-scheme" content="light dark">
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    html, body { overflow: hidden; background: transparent; }
    body {
      font-family: var(--font-sans, system-ui, -apple-system, sans-serif);
      color: var(--color-text-primary, #333);
    }
    .main {
      display: flex; flex-direction: column; align-items: center;
      padding: 12px; width: 100%;
    }

    /* --- State: waiting (before any tool result) --- */
    .state-waiting {
      color: var(--color-text-tertiary, #999);
      font-size: var(--font-text-sm-size, 13px);
      padding: 32px 16px; text-align: center;
    }

    /* --- State: generating (progress) --- */
    .state-generating {
      display: none; width: 100%; max-width: 480px;
      text-align: center; padding: 24px 16px;
    }
    .state-generating .spinner {
      width: 24px; height: 24px; margin: 0 auto 12px;
      border: 3px solid var(--color-border-primary, #ddd);
      border-top-color: var(--color-text-secondary, #666);
      border-radius: 50%; animation: spin 0.8s linear infinite;
    }
    @keyframes spin { to { transform: rotate(360deg); } }
    .state-generating .gen-label {
      font-size: var(--font-text-sm-size, 13px);
      font-weight: 600;
      color: var(--color-text-secondary, #666);
    }
    .state-generating .gen-detail {
      font-size: var(--font-text-xs-size, 12px);
      color: var(--color-text-tertiary, #999);
      margin-top: 4px;
    }
    .state-generating .gen-progress {
      margin-top: 8px; height: 4px;
      background: var(--color-background-tertiary, #eee);
      border-radius: var(--border-radius-full, 9999px);
      overflow: hidden;
    }
    .state-generating .gen-progress-fill {
      height: 100%; width: 0%;
      background: var(--color-text-secondary, #666);
      border-radius: var(--border-radius-full, 9999px);
      transition: width 0.3s ease;
    }

    /* --- State: failed --- */
    .state-failed {
      display: none; width: 100%; max-width: 480px;
      text-align: center; padding: 24px 16px;
    }
    .state-failed .fail-label {
      font-size: var(--font-text-sm-size, 13px);
      font-weight: 600; color: #c33;
    }
    .state-failed .fail-detail {
      font-size: var(--font-text-xs-size, 12px);
      color: var(--color-text-tertiary, #999);
      margin-top: 4px; word-break: break-word;
    }

    /* --- State: completed (image + metadata) --- */
    .state-completed {
      display: none; width: 100%; max-width: 640px;
    }
    .state-completed img {
      width: 100%; height: auto;
      border-radius: var(--border-radius-md, 8px);
      box-shadow: var(--shadow-md, 0 2px 12px rgba(0,0,0,0.12));
    }
    .meta {
      margin-top: 10px; width: 100%;
      font-size: var(--font-text-xs-size, 12px);
      color: var(--color-text-secondary, #666);
      line-height: 1.5;
      display: flex; align-items: flex-start; gap: 8px;
    }
    .meta-text { flex: 1; min-width: 0; }
    .meta-prompt {
      font-style: italic; margin-bottom: 4px;
      color: var(--color-text-primary, #333);
    }
    .meta-details {
      color: var(--color-text-tertiary, #999);
    }
    .dl-btn {
      display: none; flex-shrink: 0;
      background: none; border: none; cursor: pointer;
      color: var(--color-text-tertiary, #999);
      padding: 2px; margin-top: -2px;
      border-radius: var(--border-radius-sm, 4px);
      transition: color 0.15s;
    }
    .dl-btn:hover { color: var(--color-text-primary, #333); }
    .dl-btn svg { width: 18px; height: 18px; display: block; }

    /* --- Cancelled --- */
    .state-cancelled {
      display: none; width: 100%; max-width: 480px;
      text-align: center; padding: 24px 16px;
      font-size: var(--font-text-sm-size, 13px);
      color: var(--color-text-tertiary, #999);
    }

    /* --- Edit mode --- */
    .state-editing { display: none; width: 100%; max-width: 640px; }
    .edit-canvas-wrap { position: relative; width: 100%; background: #111; border-radius: var(--border-radius-md, 8px); overflow: hidden; }
    .edit-canvas-wrap img { display: block; max-width: 100%; }
    .edit-toolbar {
      display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px;
      align-items: center;
    }
    .edit-toolbar select, .edit-toolbar button {
      font-size: var(--font-text-xs-size, 12px);
      padding: 4px 8px; border-radius: var(--border-radius-sm, 4px);
      border: 1px solid var(--color-border-primary, #ccc);
      background: var(--color-background-secondary, #f5f5f5);
      color: var(--color-text-primary, #333);
      cursor: pointer;
    }
    .edit-toolbar button:hover { background: var(--color-background-tertiary, #e8e8e8); }
    .edit-actions { display: flex; gap: 8px; margin-top: 8px; }
    .edit-save-btn {
      flex: 1; padding: 8px 16px;
      background: var(--color-text-secondary, #666);
      color: #fff; border: none; border-radius: var(--border-radius-sm, 4px);
      font-size: var(--font-text-sm-size, 13px); font-weight: 600;
      cursor: pointer;
    }
    .edit-save-btn:hover { opacity: 0.85; }
    .edit-save-btn:disabled { opacity: 0.5; cursor: not-allowed; }
    .edit-cancel-btn {
      padding: 8px 16px;
      background: none; border: 1px solid var(--color-border-primary, #ccc);
      border-radius: var(--border-radius-sm, 4px);
      font-size: var(--font-text-sm-size, 13px);
      color: var(--color-text-secondary, #666);
      cursor: pointer;
    }
    .edit-source-badge {
      font-size: var(--font-text-xs-size, 12px);
      color: var(--color-text-tertiary, #999);
      margin-top: 4px;
    }
  </style>
</head>
<body>
  <div class="main">
    <div class="state-waiting" id="waiting">Waiting for image&hellip;</div>
    <div class="state-generating" id="generating">
      <div class="spinner"></div>
      <div class="gen-label" id="gen-label">Generating&hellip;</div>
      <div class="gen-detail" id="gen-detail"></div>
      <div class="gen-progress"><div class="gen-progress-fill" id="gen-fill"></div></div>
    </div>
    <div class="state-failed" id="failed">
      <div class="fail-label">Generation failed</div>
      <div class="fail-detail" id="fail-detail"></div>
    </div>
    <div class="state-cancelled" id="cancelled">Cancelled</div>
    <div class="state-editing" id="editing">
      <div class="edit-canvas-wrap">
        <img id="edit-img" alt="Image to edit">
      </div>
      <div class="edit-toolbar">
        <label style="font-size:var(--font-text-xs-size,12px);color:var(--color-text-tertiary,#999)">Aspect:</label>
        <select id="edit-aspect">
          <option value="NaN">Free</option>
          <option value="1">1:1</option>
          <option value="1.7778">16:9</option>
          <option value="1.3333">4:3</option>
        </select>
        <button id="edit-rot-ccw" title="Rotate 90\u00b0 counter-clockwise">\u21ba 90\u00b0</button>
        <button id="edit-rot-cw" title="Rotate 90\u00b0 clockwise">\u21bb 90\u00b0</button>
        <button id="edit-flip-h" title="Flip horizontal">\u21c4 H</button>
        <button id="edit-flip-v" title="Flip vertical">\u21c5 V</button>
        <button id="edit-reset" title="Reset all edits">Reset</button>
      </div>
      <div class="edit-actions">
        <button class="edit-save-btn" id="edit-save">Save as new image</button>
        <button class="edit-cancel-btn" id="edit-cancel">Cancel</button>
      </div>
    </div>
    <div class="state-completed" id="completed">
      <img id="image" alt="Generated image">
      <div class="meta">
        <div class="meta-text">
          <div class="meta-prompt" id="meta-prompt"></div>
          <div class="meta-details" id="meta-details"></div>
          <div class="edit-source-badge" id="edit-source-badge" style="display:none"></div>
        </div>
        <button class="dl-btn" id="dl-btn" title="Download full-resolution image">
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none"
            stroke="currentColor" stroke-width="2" stroke-linecap="round"
            stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
            <polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
        </button>
      </div>
    </div>
  </div>

  <script type="module">
    import { App, applyDocumentTheme, applyHostStyleVariables, applyHostFonts }
      from "@modelcontextprotocol/ext-apps";

    const app = new App(
      { name: "Image Viewer", version: "2.0.0" },
      {},
      { autoResize: false }
    );

    // --- DOM refs ---
    const mainEl = document.querySelector(".main");

    // --- Size reporting ---
    function updateSize() {
      requestAnimationFrame(() => {
        app.sendSizeChanged({ height: mainEl.scrollHeight });
      });
    }
    const sections = {
      waiting:    document.getElementById("waiting"),
      generating: document.getElementById("generating"),
      failed:     document.getElementById("failed"),
      cancelled:  document.getElementById("cancelled"),
      editing:    document.getElementById("editing"),
      completed:  document.getElementById("completed"),
    };

    // --- State management ---
    let imageKey = null;
    let currentMeta = null;   // metadata for download
    const STORE = "imgview:";
    const MAX_ENTRIES = 5;

    function show(state) {
      for (const [k, el] of Object.entries(sections)) {
        el.style.display = k === state ? "block" : "none";
      }
      updateSize();
    }

    function extractImageKey(uri) {
      if (!uri) return null;
      const m = uri.match(/^image:\\/\\/([^/?]+)/);
      return m ? m[1] : null;
    }

    // --- localStorage cache (LRU, quota-safe) ---
    function storeKeys() {
      const keys = [];
      for (let i = 0; i < localStorage.length; i++) {
        const k = localStorage.key(i);
        if (k && k.startsWith(STORE)) keys.push(k);
      }
      return keys;
    }

    // Returns store keys sorted oldest-first by timestamp for correct LRU eviction.
    // localStorage.key(i) has no guaranteed iteration order, so we read the stored ts field.
    function storeKeysByAge() {
      return storeKeys().map(k => {
        try {
          const d = JSON.parse(localStorage.getItem(k));
          return { k, ts: (d && d.ts) ? d.ts : 0 };
        } catch (_) { return { k, ts: 0 }; }
      }).sort((a, b) => a.ts - b.ts).map(e => e.k);
    }

    function saveState(key, img, text) {
      if (!key) return;
      const fullKey = STORE + key;
      const value = JSON.stringify({ img, text, ts: Date.now() });
      try {
        localStorage.setItem(fullKey, value);
      } catch (e) {
        const keys = storeKeysByAge().filter(k => k !== fullKey);
        while (keys.length > 0) {
          localStorage.removeItem(keys.shift());
          try { localStorage.setItem(fullKey, value); return; } catch (_) {}
        }
        console.warn('localStorage full — could not save state after eviction');
        return;
      }
      const all = storeKeysByAge().filter(k => k !== fullKey);
      while (all.length >= MAX_ENTRIES) localStorage.removeItem(all.shift());
    }

    function loadState(key) {
      if (!key) return null;
      try {
        const raw = localStorage.getItem(STORE + key);
        return raw ? JSON.parse(raw) : null;
      } catch (e) { return null; }
    }

    // --- Rendering ---
    function renderGenerating(meta) {
      show("generating");
      const elapsed = meta.elapsed_seconds
        ? ` (${Math.round(meta.elapsed_seconds)}s)` : "";
      document.getElementById("gen-label").textContent =
        "Generating" + elapsed;
      const parts = [];
      if (meta.provider) parts.push(meta.provider);
      if (meta.progress_message) parts.push(meta.progress_message);
      else if (meta.prompt) parts.push("\\u201c" + meta.prompt + "\\u201d");
      document.getElementById("gen-detail").textContent =
        parts.join(" \\u00b7 ");
      const pct = (meta.progress || 0) * 100;
      document.getElementById("gen-fill").style.width =
        pct > 0 ? pct + "%" : "0%";
    }

    function renderFailed(meta) {
      show("failed");
      document.getElementById("fail-detail").textContent =
        meta.error || "Unknown error";
    }

    function renderCompleted(img, text) {
      show("completed");
      const imgEl = document.getElementById("image");
      if (img) {
        const allowed = ["image/png","image/jpeg","image/webp","image/gif"];
        const mime = allowed.includes(img.mimeType) ? img.mimeType : "image/png";
        imgEl.src = "data:" + mime + ";base64," + img.data;
        imgEl.onload = updateSize;
      }
      if (text) {
        try {
          const m = JSON.parse(text.text);
          currentMeta = m;
          if (m.prompt) {
            imgEl.alt = m.prompt;
            document.getElementById("meta-prompt").textContent =
              "\\u201c" + m.prompt + "\\u201d";
          }
          const parts = [];
          if (m.provider) {
            let s = m.provider;
            if (m.model) s += " (" + m.model + ")";
            parts.push(s);
          }
          if (m.dimensions)
            parts.push(m.dimensions[0] + "\\u00d7" + m.dimensions[1]);
          if (m.original_size_bytes) {
            const kb = (m.original_size_bytes / 1024).toFixed(1);
            parts.push(kb + " KB");
          }
          document.getElementById("meta-details").textContent =
            parts.join(" \\u00b7 ");
        } catch (e) { console.warn("Failed to parse metadata", e); }
      }
    }

    // --- Handlers (registered BEFORE connect) ---
    app.ontoolinput = (params) => {
      imageKey = extractImageKey(params?.arguments?.uri);
      // Restore cached image while waiting for result
      if (imageKey) {
        const saved = loadState(imageKey);
        if (saved) {
          renderCompleted(saved.img, saved.text);
          return;
        }
      }
      show("waiting");
    };

    app.ontoolresult = ({ content }) => {
      const img = content?.find(c => c.type === "image");
      const text = content?.find(c => c.type === "text");

      // Status-only results (generating / failed)
      if (!img && text) {
        try {
          const meta = JSON.parse(text.text);
          if (meta.status === "generating") { renderGenerating(meta); return; }
          if (meta.status === "failed") { renderFailed(meta); return; }
        } catch (e) { /* not status JSON */ }
      }

      // Edit mode
      if (text && img) {
        try {
          const meta = JSON.parse(text.text);
          if (meta.editable) { enterEditMode(meta, img); return; }
        } catch (e) { /* not edit JSON */ }
      }

      // Completed image
      renderCompleted(img, text);
      let key = imageKey;
      if (!key && text) {
        try { key = JSON.parse(text.text).image_id; } catch (e) { console.warn('Could not parse image_id from result text', e); }
      }
      if (key) saveState(key, img, text);
    };

    app.ontoolcancelled = (params) => {
      document.getElementById("cancelled").textContent =
        "Cancelled" + (params?.reason ? ": " + params.reason : "");
      show("cancelled");
    };

    function handleHostContext(ctx) {
      if (ctx.theme) applyDocumentTheme(ctx.theme);
      if (ctx.styles?.variables) applyHostStyleVariables(ctx.styles.variables);
      if (ctx.styles?.css?.fonts) applyHostFonts(ctx.styles.css.fonts);
      if (ctx.safeAreaInsets) {
        const { top, right, bottom, left } = ctx.safeAreaInsets;
        mainEl.style.paddingTop = top + "px";
        mainEl.style.paddingRight = right + "px";
        mainEl.style.paddingBottom = bottom + "px";
        mainEl.style.paddingLeft = left + "px";
      }
    }

    app.onhostcontextchanged = handleHostContext;
    app.onerror = console.error;

    // --- Download button ---
    const dlBtn = document.getElementById("dl-btn");
    let dlMode = null; // "downloadFile" | "openLink" | null

    async function tryDownloadFile() {
      if (!currentMeta?.image_id) return false;
      const id = currentMeta.image_id;
      const mime = currentMeta.format || "image/png";
      const ext = mime.split("/").pop() || "png";
      const res = await app.downloadFile({
        contents: [{
          type: "resource_link",
          uri: "image://" + id + "/view",
          name: id + "." + ext,
          mimeType: mime,
        }],
      });
      if (res.isError) console.warn("downloadFile failed", res.content?.find(c => c.type === "text")?.text);
      return !res.isError;
    }

    async function tryOpenLink() {
      if (!currentMeta?.image_id) return false;
      try {
        // Mint a one-time download URL on demand via the transfer framework.
        const result = await app.callServerTool({
          name: "create_download_link",
          arguments: { ref: "image://" + currentMeta.image_id + "/view" },
        });
        if (result.isError) {
          console.warn("create_download_link failed", result.content?.find(c => c.type === "text")?.text);
          return false;
        }
        const textItem = result.content?.find(c => c.type === "text");
        const url = textItem ? JSON.parse(textItem.text).url : null;
        if (!url) return false;
        const { isError } = await app.openLink({ url });
        return !isError;
      } catch (e) { console.warn("create_download_link failed", e); return false; }
    }

    dlBtn.addEventListener("click", async () => {
      if (!currentMeta) return;
      let ok = false;
      try {
        // Try downloadFile first (full-res via MCP), fall back to openLink.
        if (dlMode === "downloadFile") {
          ok = (await tryDownloadFile()) || (await tryOpenLink());
        } else {
          ok = await tryOpenLink();
        }
      } catch (e) { console.warn("Download failed", e); }
      if (!ok) alert("Download failed — please try again.");
    });

    // --- Cropper.js (loaded on demand) ---
    let cropperLoaded = false;
    let cropper = null;
    let pendingRotate = 0;
    let pendingFlipH = false;
    let pendingFlipV = false;
    let editMeta = null;
    let priorEditImg = null;   // img content to restore on cancel
    let priorEditText = null;  // text content to restore on cancel

    async function loadCropper() {
      if (cropperLoaded) return;
      // Load Cropper.js CSS (version-pinned with SRI)
      const link = document.createElement("link");
      link.rel = "stylesheet";
      link.href = "https://unpkg.com/cropperjs@1.6.2/dist/cropper.min.css";
      link.integrity = "sha384-6LFfkTKLRlzFtgx8xsWyBdKGpcMMQTkv+dB7rAbugeJAu1Ym2q1Aji1cjHBG12Xh";
      link.crossOrigin = "anonymous";
      document.head.appendChild(link);
      // Load Cropper.js script (version-pinned with SRI)
      await new Promise((resolve, reject) => {
        const s = document.createElement("script");
        s.src = "https://unpkg.com/cropperjs@1.6.2/dist/cropper.min.js";
        s.integrity = "sha384-jrOgQzBlDeUNdmQn3rUt/PZD+pdcRBdWd/HWRqRo+n2OR2QtGyjSaJC0GiCeH+ir";
        s.crossOrigin = "anonymous";
        s.onload = resolve;
        s.onerror = reject;
        document.head.appendChild(s);
      });
      cropperLoaded = true;
    }

    function destroyCropper() {
      if (cropper) { cropper.destroy(); cropper = null; }
    }

    function initCropper(imgEl, aspectRatio) {
      destroyCropper();
      cropper = new Cropper(imgEl, {
        viewMode: 1,
        autoCropArea: 1,
        aspectRatio: isNaN(aspectRatio) ? NaN : aspectRatio,
        responsive: true,
        background: false,
      });
    }

    async function enterEditMode(meta, imgItem) {
      pendingRotate = 0;
      pendingFlipH = false;
      pendingFlipV = false;
      editMeta = meta;
      currentMeta = meta;
      // Save content refs so cancel can restore the completed view
      priorEditImg = imgItem;
      priorEditText = { type: "text", text: JSON.stringify(meta) };

      const editImg = document.getElementById("edit-img");
      editImg.src = "data:" + imgItem.mimeType + ";base64," + imgItem.data;

      show("editing");

      await loadCropper();
      const aspect = parseFloat(document.getElementById("edit-aspect").value);
      initCropper(editImg, aspect);
    }

    document.getElementById("edit-aspect").addEventListener("change", (e) => {
      if (!cropper) return;
      const v = parseFloat(e.target.value);
      cropper.setAspectRatio(isNaN(v) ? NaN : v);
    });

    document.getElementById("edit-rot-ccw").addEventListener("click", () => {
      if (!cropper) return;
      pendingRotate = (pendingRotate + 270) % 360;
      cropper.rotate(-90);
    });

    document.getElementById("edit-rot-cw").addEventListener("click", () => {
      if (!cropper) return;
      pendingRotate = (pendingRotate + 90) % 360;
      cropper.rotate(90);
    });

    document.getElementById("edit-flip-h").addEventListener("click", () => {
      if (!cropper) return;
      pendingFlipH = !pendingFlipH;
      cropper.scaleX(pendingFlipH ? -1 : 1);
    });

    document.getElementById("edit-flip-v").addEventListener("click", () => {
      if (!cropper) return;
      pendingFlipV = !pendingFlipV;
      cropper.scaleY(pendingFlipV ? -1 : 1);
    });

    document.getElementById("edit-reset").addEventListener("click", () => {
      if (!cropper) return;
      pendingRotate = 0;
      pendingFlipH = false;
      pendingFlipV = false;
      cropper.reset();
      cropper.scaleX(1);
      cropper.scaleY(1);
    });

    document.getElementById("edit-cancel").addEventListener("click", () => {
      destroyCropper();
      // Restore the image that was displayed before edit mode was entered
      if (priorEditImg) {
        renderCompleted(priorEditImg, priorEditText);
      } else {
        show("waiting");
      }
      priorEditImg = null;
      priorEditText = null;
      updateSize();
    });

    document.getElementById("edit-save").addEventListener("click", async () => {
      if (!cropper) return;
      const saveBtn = document.getElementById("edit-save");
      saveBtn.disabled = true;
      saveBtn.textContent = "Saving\\u2026";

      try {
        const cropData = cropper.getData(true);
        const imgData = cropper.getImageData();
        const args = { source_image_id: editMeta?.image_id };

        const isFullImage = (
          cropData.x <= 0 && cropData.y <= 0 &&
          cropData.width >= imgData.naturalWidth &&
          cropData.height >= imgData.naturalHeight
        );
        if (!isFullImage) {
          args.crop = { x: cropData.x, y: cropData.y, w: cropData.width, h: cropData.height };
        }
        if (pendingRotate) args.rotate = pendingRotate;
        if (pendingFlipH) args.flip_horizontal = true;
        if (pendingFlipV) args.flip_vertical = true;

        const result = await app.callServerTool({ name: "_save_edited_image", arguments: args });
        if (result.isError) {
          alert("Save failed: " + JSON.stringify(result.content));
          return;
        }
        const textItem = result.content?.find(c => c.type === "text");
        if (!textItem) { alert("Save failed: empty response"); return; }
        const saved = JSON.parse(textItem.text);

        destroyCropper();

        const showResult = await app.callServerTool({
          name: "show_image",
          arguments: { uri: "image://" + saved.image_id + "/view" }
        });
        if (!showResult.isError) {
          const showImg  = showResult.content?.find(c => c.type === "image");
          const showText = showResult.content?.find(c => c.type === "text");
          renderCompleted(showImg, showText);
          document.getElementById("edit-source-badge").style.display = "block";
          document.getElementById("edit-source-badge").textContent =
            "Edited from " + saved.source_image_id;
        } else {
          show("completed");
          document.getElementById("edit-source-badge").style.display = "block";
          document.getElementById("edit-source-badge").textContent =
            "Edited from " + saved.source_image_id;
        }
        updateSize();
      } catch (e) {
        alert("Save failed: " + e.message);
      } finally {
        saveBtn.disabled = false;
        saveBtn.textContent = "Save as new image";
      }
    });

    await app.connect();
    const ctx = app.getHostContext();
    if (ctx) handleHostContext(ctx);

    // Show download button: prefer downloadFile, fall back to openLink
    const caps = app.getHostCapabilities();
    if (caps?.downloadFile) {
      dlMode = "downloadFile";
      dlBtn.style.display = "block";
    } else if (caps?.openLinks) {
      dlMode = "openLink";
      dlBtn.style.display = "block";
    }
  </script>
</body>
</html>"""

_IMAGE_GALLERY_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="color-scheme" content="light dark">
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    html, body { overflow: hidden; background: transparent; }
    body {
      font-family: var(--font-sans, system-ui, -apple-system, sans-serif);
      color: var(--color-text-primary, #333);
    }
    .main { padding: 12px; width: 100%; }
    @keyframes spin { to { transform: rotate(360deg); } }
    .spinner {
      width: 20px; height: 20px; flex-shrink: 0;
      border: 2px solid var(--color-border-primary, #ddd);
      border-top-color: var(--color-text-secondary, #666);
      border-radius: 50%; animation: spin 0.8s linear infinite;
    }

    /* Loading */
    .state-loading {
      display: flex; flex-direction: column; align-items: center;
      padding: 40px 16px; gap: 10px;
      color: var(--color-text-tertiary, #999);
      font-size: var(--font-text-sm-size, 13px);
    }

    /* Empty */
    .state-empty { display: none; text-align: center; padding: 48px 16px; }
    .empty-icon { color: var(--color-text-tertiary, #ccc); margin-bottom: 12px; }
    .empty-title {
      font-size: var(--font-text-sm-size, 13px); font-weight: 600;
      color: var(--color-text-secondary, #666);
    }
    .empty-sub {
      font-size: var(--font-text-xs-size, 12px);
      color: var(--color-text-tertiary, #999); margin-top: 4px;
    }
    .empty-sub code {
      font-family: var(--font-mono, monospace); font-size: 11px;
      background: var(--color-background-secondary, #f0f0f0);
      padding: 1px 4px; border-radius: 3px;
    }

    /* Grid */
    .state-grid { display: none; }
    .gallery-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
      gap: 6px;
    }

    /* Card */
    .card {
      position: relative; aspect-ratio: 1;
      border-radius: var(--border-radius-md, 8px);
      overflow: hidden;
      background: var(--color-background-secondary, #f0f0f0);
      cursor: pointer; user-select: none;
    }
    .card img {
      width: 100%; height: 100%; object-fit: cover;
      display: block; transition: opacity 0.15s;
    }
    .card:hover img, .card:focus-within img { opacity: 0.82; }
    .card-overlay {
      position: absolute; inset: 0;
      background: linear-gradient(to top, rgba(0,0,0,0.72) 0%, transparent 55%);
      opacity: 0; transition: opacity 0.15s;
      display: flex; flex-direction: column; justify-content: flex-end;
      padding: 6px;
    }
    .card:hover .card-overlay, .card:focus-within .card-overlay { opacity: 1; }
    .card-prompt {
      font-size: 10px; color: #fff; line-height: 1.3;
      overflow: hidden; display: -webkit-box;
      -webkit-line-clamp: 2; -webkit-box-orient: vertical;
      margin-bottom: 4px;
    }
    .card-footer { display: flex; align-items: center; justify-content: space-between; }
    .card-provider {
      font-size: 9px; font-weight: 600; color: rgba(255,255,255,0.85);
      background: rgba(0,0,0,0.35); padding: 1px 4px; border-radius: 3px;
      max-width: 70%; overflow: hidden; white-space: nowrap; text-overflow: ellipsis;
    }
    .card-dl, .card-del {
      display: none; background: none; border: none; cursor: pointer;
      color: rgba(255,255,255,0.9); padding: 2px; line-height: 0;
    }
    .card-dl:hover { color: #fff; }
    .card-del:hover { color: #ff6b6b; }
    .card-dl svg, .card-del svg { width: 13px; height: 13px; }

    /* Pending card */
    .card-pending {
      position: absolute; inset: 0;
      display: flex; flex-direction: column; align-items: center; justify-content: center;
      gap: 6px; padding: 8px;
    }
    .card-pending .spinner { width: 18px; height: 18px; }
    .card-pending-label {
      font-size: 10px; color: var(--color-text-tertiary, #999);
      text-align: center; overflow: hidden; display: -webkit-box;
      -webkit-line-clamp: 2; -webkit-box-orient: vertical;
    }

    /* PiP toolbar (top-right of grid) */
    .pip-toolbar {
      display: flex; justify-content: flex-end; margin-bottom: 6px;
    }
    .pip-btn {
      display: none; /* shown via JS when host supports PiP */
      background: var(--color-background-secondary, #f0f0f0);
      border: 1px solid var(--color-border-primary, #ddd);
      border-radius: var(--border-radius-sm, 4px);
      padding: 3px 8px; cursor: pointer;
      color: var(--color-text-secondary, #666);
      font-size: var(--font-text-xs-size, 12px); line-height: 1;
    }
    .pip-btn:hover {
      background: var(--color-background-tertiary, #e8e8e8);
      color: var(--color-text-primary, #333);
    }

    .origin-filter { display: flex; gap: 4px; margin: 8px 0; }
    .seg { background: transparent; border: 1px solid var(--color-border, #444); color: var(--color-text-secondary, #aaa); border-radius: 6px; padding: 3px 10px; cursor: pointer; font-size: 12px; }
    .seg.active { background: var(--color-background-secondary, #333); color: var(--color-text-primary, #fff); }

    /* PiP compact layout */
    .main.pip-mode { padding: 4px; border-radius: 0; }
    .main.pip-mode .pip-toolbar { margin-bottom: 2px; }
    .main.pip-mode .gallery-grid {
      grid-template-columns: repeat(4, 1fr);
      gap: 3px;
    }
    .main.pip-mode .card { aspect-ratio: 1; border-radius: 4px; }
    .main.pip-mode .card-overlay { display: none; }
    .main.pip-mode .pagination { display: none; }
    .main.pip-mode .origin-filter { display: none; }

    /* Pagination */
    .pagination {
      display: flex; align-items: center; justify-content: center;
      gap: 10px; margin-top: 10px; padding-top: 4px;
    }
    .page-btn {
      background: var(--color-background-secondary, #f0f0f0);
      border: 1px solid var(--color-border-primary, #ddd);
      border-radius: var(--border-radius-sm, 4px);
      padding: 4px 12px;
      font-size: var(--font-text-xs-size, 12px);
      cursor: pointer; color: var(--color-text-primary, #333);
    }
    .page-btn:disabled { opacity: 0.35; cursor: default; }
    .page-btn:not(:disabled):hover {
      background: var(--color-background-tertiary, #e8e8e8);
    }
    .page-info {
      font-size: var(--font-text-xs-size, 12px);
      color: var(--color-text-secondary, #666);
      min-width: 90px; text-align: center;
    }

    /* Lightbox */
    #lightbox {
      position: fixed; inset: 0; z-index: 100;
      display: flex; align-items: center; justify-content: center;
    }
    #lightbox[hidden] { display: none; }
    .lb-backdrop {
      position: absolute; inset: 0; background: rgba(0,0,0,0.88); cursor: pointer;
    }
    .lb-panel {
      position: relative; z-index: 1;
      display: flex; flex-direction: column;
      max-width: min(95vw, 1100px); max-height: 95vh;
    }
    .lb-toolbar {
      display: flex; justify-content: flex-end; gap: 6px; padding-bottom: 6px;
    }
    .lb-btn {
      background: rgba(0,0,0,0.5); border: none; cursor: pointer;
      color: rgba(255,255,255,0.85); border-radius: var(--border-radius-sm, 4px);
      padding: 5px 10px; font-size: 14px; line-height: 1;
    }
    .lb-btn:hover { color: #fff; background: rgba(0,0,0,0.75); }
    .lb-del-btn:hover { color: #ff6b6b; }
    .lb-body { display: flex; align-items: center; gap: 8px; }
    .lb-nav-btn {
      flex-shrink: 0; background: rgba(0,0,0,0.5); border: none; cursor: pointer;
      color: rgba(255,255,255,0.85); border-radius: 50%;
      width: 36px; height: 36px; font-size: 18px;
      display: flex; align-items: center; justify-content: center;
    }
    .lb-nav-btn:disabled { opacity: 0.2; cursor: default; }
    .lb-nav-btn:not(:disabled):hover { background: rgba(0,0,0,0.75); color: #fff; }
    .lb-img-wrap {
      flex: 1; min-width: 0;
      display: flex; align-items: center; justify-content: center; position: relative;
      min-height: 60px;
    }
    .lb-loading {
      position: absolute;
      display: flex; align-items: center; justify-content: center;
      width: 60px; height: 60px;
    }
    .lb-loading .spinner { width: 28px; height: 28px; }
    #lb-img {
      max-width: 100%; max-height: 75vh; object-fit: contain;
      border-radius: var(--border-radius-sm, 4px); display: block;
    }
    #lb-img[hidden] { display: none; }
    .lb-meta {
      padding: 8px 0 0; color: rgba(255,255,255,0.85);
      max-width: 600px; margin: 0 auto;
    }
    .lb-meta-prompt {
      font-size: var(--font-text-sm-size, 13px); line-height: 1.4; margin-bottom: 4px;
    }
    .lb-meta-info {
      font-size: var(--font-text-xs-size, 12px); color: rgba(255,255,255,0.6);
    }
  </style>
</head>
<body>
  <div class="main" id="main">
    <div class="origin-filter" id="origin-filter" role="radiogroup" aria-label="Filter by image origin">
      <button class="seg active" data-origin="generated" role="radio" aria-checked="true" tabindex="0">Generated</button>
      <button class="seg" data-origin="imported" role="radio" aria-checked="false" tabindex="-1">Imported</button>
      <button class="seg" data-origin="all" role="radio" aria-checked="false" tabindex="-1">All</button>
    </div>
    <div class="state-loading" id="loading">
      <div class="spinner"></div>Loading gallery\u2026
    </div>
    <div class="state-empty" id="empty">
      <div class="empty-icon">
        <svg xmlns="http://www.w3.org/2000/svg" width="36" height="36" viewBox="0 0 24 24"
          fill="none" stroke="currentColor" stroke-width="1.5"
          stroke-linecap="round" stroke-linejoin="round">
          <rect x="3" y="3" width="18" height="18" rx="2"/>
          <circle cx="8.5" cy="8.5" r="1.5"/>
          <polyline points="21 15 16 10 5 21"/>
        </svg>
      </div>
      <div class="empty-title">No images yet</div>
      <div class="empty-sub">Use <code>generate_image</code> to create your first image.</div>
    </div>
    <div class="state-empty" id="error">
      <div class="empty-icon">
        <svg xmlns="http://www.w3.org/2000/svg" width="36" height="36" viewBox="0 0 24 24"
          fill="none" stroke="currentColor" stroke-width="1.5"
          stroke-linecap="round" stroke-linejoin="round">
          <path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
          <line x1="12" y1="9" x2="12" y2="13"/>
          <line x1="12" y1="17" x2="12.01" y2="17"/>
        </svg>
      </div>
      <div class="empty-title">Couldn't load the gallery</div>
      <div class="empty-sub">Something went wrong — try again.</div>
      <button class="seg" id="gallery-retry" type="button">Retry</button>
    </div>
    <div class="state-grid" id="grid-container">
      <div class="pip-toolbar"><button class="pip-btn" id="pip-btn" title="Picture-in-picture">\u25a3</button></div>
      <div class="gallery-grid" id="gallery-grid"></div>
      <div class="pagination" id="pagination"></div>
    </div>
  </div>

  <!-- Lightbox overlay -->
  <div id="lightbox" hidden aria-modal="true" role="dialog" aria-label="Image viewer">
    <div id="lb-backdrop" class="lb-backdrop"></div>
    <div class="lb-panel">
      <div class="lb-toolbar">
        <button class="lb-btn" id="lb-fullscreen" hidden title="Enter fullscreen">\u26f6</button>
        <button class="lb-btn lb-del-btn" id="lb-delete" title="Delete image"><svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4h6v2"/></svg></button>
        <button class="lb-btn" id="lb-close" title="Close (Esc)">\u2715</button>
      </div>
      <div class="lb-body">
        <button class="lb-nav-btn" id="lb-prev" title="Previous" disabled>&#10094;</button>
        <div class="lb-img-wrap">
          <div class="lb-loading" id="lb-loading"><div class="spinner"></div></div>
          <img id="lb-img" src="" alt="" hidden>
        </div>
        <button class="lb-nav-btn" id="lb-next" title="Next" disabled>&#10095;</button>
      </div>
      <div class="lb-meta" id="lb-meta" hidden>
        <div class="lb-meta-prompt" id="lb-prompt"></div>
        <div class="lb-meta-info" id="lb-info"></div>
      </div>
    </div>
  </div>

  <script type="module">
    import { App, applyDocumentTheme, applyHostStyleVariables, applyHostFonts }
      from "@modelcontextprotocol/ext-apps";

    const app = new App(
      { name: "Image Gallery", version: "1.0.0" },
      {},
      { autoResize: false }
    );

    const mainEl    = document.getElementById("main");
    const loadingEl = document.getElementById("loading");
    const emptyEl   = document.getElementById("empty");
    const errorEl   = document.getElementById("error");
    const gridEl    = document.getElementById("grid-container");
    const gridItems = document.getElementById("gallery-grid");
    const pagEl     = document.getElementById("pagination");

    // Lightbox DOM refs
    const lbOverlay  = document.getElementById("lightbox");
    const lbBackdrop = document.getElementById("lb-backdrop");
    const lbImg      = document.getElementById("lb-img");
    const lbLoading  = document.getElementById("lb-loading");
    const lbPrev     = document.getElementById("lb-prev");
    const lbNext     = document.getElementById("lb-next");
    const lbClose    = document.getElementById("lb-close");
    const lbDelBtn   = document.getElementById("lb-delete");
    const lbFsBtn    = document.getElementById("lb-fullscreen");
    const lbMeta     = document.getElementById("lb-meta");
    const lbPromptEl = document.getElementById("lb-prompt");
    const lbInfoEl   = document.getElementById("lb-info");

    const pipBtn    = document.getElementById("pip-btn");

    // --- Size reporting ---
    let currentDisplayMode = "inline";
    function updateSize() {
      // Don't report size in fullscreen — host controls sizing
      if (currentDisplayMode === "fullscreen") return;
      requestAnimationFrame(() => {
        app.sendSizeChanged({ height: mainEl.scrollHeight });
      });
    }

    let currentPage = 1;
    let currentOrigin = "generated";
    let galleryReqSeq = 0;
    let currentTotal = 0;
    let currentPageSize = 12;
    let dlMode = null; // "downloadFile" | "openLink" | null

    // Lightbox state
    let lbActive = false;
    let lbIndex  = 0;       // index within lbPageItems
    let lbPageItems = [];   // completed items on current page (for lightbox nav)
    let lbFsAvailable = false;

    // PiP state
    let pipAvailable = false;
    let pipActive = false;

    // --- Helpers ---
    function trunc(s, n) {
      s = String(s || "");
      return s.length > n ? s.slice(0, n) + "\\u2026" : s;
    }
    // --- Lightbox ---
    function updateLbNav() {
      const globalOffset = (currentPage - 1) * currentPageSize;
      const globalIdx = globalOffset + lbIndex;
      lbPrev.disabled = globalIdx <= 0;
      lbNext.disabled = globalIdx >= currentTotal - 1;
    }

    function openLightbox(pageIndex) {
      const item = lbPageItems[pageIndex];
      if (!item) return;
      lbActive = true;
      lbIndex  = pageIndex;
      lbOverlay.removeAttribute("hidden");
      lbLoading.style.display = "flex";
      lbMeta.setAttribute("hidden", "");
      if (lbFsAvailable) lbFsBtn.removeAttribute("hidden");
      updateLbNav();
      // Preview with thumbnail immediately
      if (item.thumbnail_b64) {
        lbImg.src = "data:image/webp;base64," + item.thumbnail_b64;
        lbImg.removeAttribute("hidden");
      } else {
        lbImg.setAttribute("hidden", "");
      }
      loadFullImage(item);
    }

    async function loadFullImage(item) {
      const capturedIndex = lbIndex;
      try {
        const result = await app.callServerTool({ name: "gallery_full_image", arguments: { image_id: item.image_id } });
        if (lbIndex !== capturedIndex) return; // navigated away while loading
        if (result.isError) return;
        const text = result.content?.find(c => c.type === "text")?.text;
        if (!text) return;
        const data = JSON.parse(text);
        lbImg.src = "data:" + (data.content_type || "image/webp") + ";base64," + data.b64;
        lbImg.removeAttribute("hidden");
        lbPromptEl.textContent = data.prompt || "";
        const parts = [data.provider];
        if (data.dimensions) parts.push(data.dimensions.join("\\u00d7") + "px");
        if (data.created_at) parts.push(new Date(data.created_at).toLocaleDateString());
        lbInfoEl.textContent = parts.filter(Boolean).join(" \\u00b7 ");
        lbMeta.removeAttribute("hidden");
      } catch (e) {
        console.warn("Failed to load full image", e);
      } finally {
        // Only hide the loader if we're still showing the same image.
        // If the user navigated away, the new loadFullImage owns the loader.
        if (lbIndex === capturedIndex) lbLoading.style.display = "none";
      }
    }

    function closeLightbox() {
      if (!lbActive) return;
      lbActive = false;
      lbOverlay.setAttribute("hidden", "");
      lbImg.setAttribute("hidden", "");
      lbImg.src = "";
      lbMeta.setAttribute("hidden", "");
      lbFsBtn.setAttribute("hidden", "");
    }

    async function navigateLb(delta) {
      const newIdx = lbIndex + delta;
      if (newIdx >= 0 && newIdx < lbPageItems.length) {
        openLightbox(newIdx);
      } else {
        // Cross-page: load adjacent page then open first/last item
        const targetPage = delta > 0 ? currentPage + 1 : currentPage - 1;
        if (targetPage < 1) return;
        lbLoading.style.display = "flex";
        lbImg.setAttribute("hidden", "");
        lbMeta.setAttribute("hidden", "");
        try {
          const ps = currentPageSize;
          const result = await app.callServerTool({ name: "gallery_page", arguments: { page: targetPage, page_size: ps, origin: currentOrigin } });
          if (result.isError) { lbLoading.style.display = "none"; return; }
          const text = result.content?.find(c => c.type === "text")?.text;
          if (!text) { lbLoading.style.display = "none"; return; }
          const data = JSON.parse(text);
          currentPage = data.page;
          currentTotal = data.total;
          currentPageSize = data.page_size;
          renderGrid(data);
          const newPageIdx = delta > 0 ? 0 : lbPageItems.length - 1;
          if (lbPageItems[newPageIdx]) openLightbox(newPageIdx);
        } catch (e) {
          console.warn("Cross-page lightbox nav failed", e);
          lbLoading.style.display = "none";
        }
      }
    }

    lbBackdrop.addEventListener("click", closeLightbox);
    lbClose.addEventListener("click", closeLightbox);
    lbDelBtn.addEventListener("click", deleteLightboxImage);
    lbPrev.addEventListener("click", () => navigateLb(-1));
    lbNext.addEventListener("click", () => navigateLb(1));
    lbFsBtn.addEventListener("click", async () => {
      const mode = lbFsBtn.dataset.active === "1" ? "inline" : "fullscreen";
      try {
        const res = await app.requestDisplayMode({ mode });
        const isFs = res.mode === "fullscreen";
        lbFsBtn.dataset.active = isFs ? "1" : "0";
        lbFsBtn.title = isFs ? "Exit fullscreen" : "Enter fullscreen";
      } catch (e) { console.warn("requestDisplayMode failed", e); }
    });
    window.addEventListener("keydown", (e) => {
      if (!lbActive) return;
      if (e.key === "Escape") closeLightbox();
      else if (e.key === "ArrowLeft")  navigateLb(-1);
      else if (e.key === "ArrowRight") navigateLb(1);
    });

    // --- PiP toggle ---
    pipBtn.addEventListener("click", async () => {
      const mode = pipActive ? "inline" : "pip";
      try {
        const res = await app.requestDisplayMode({ mode });
        applyDisplayMode(res.mode);
      } catch (e) { console.warn("requestDisplayMode failed", e); }
    });

    function applyDisplayMode(mode) {
      const wasPip = pipActive;
      currentDisplayMode = mode;
      pipActive = mode === "pip";
      mainEl.classList.toggle("pip-mode", pipActive);
      pipBtn.textContent = pipActive ? "\\u25a1" : "\\u25a3";
      pipBtn.title = pipActive ? "Exit picture-in-picture" : "Picture-in-picture";
      if (pipActive && lbPageItems.length > 0) {
        renderPipStrip();
      } else if (wasPip && !pipActive) {
        // Exiting PiP — reload full grid for current page
        goTo(currentPage);
      }
    }

    function renderPipStrip() {
      gridItems.innerHTML = "";
      const items = lbPageItems.slice(0, 4);
      for (let i = 0; i < items.length; i++) {
        const item = items[i];
        const card = document.createElement("div");
        card.className = "card";
        card.tabIndex = 0;
        card.setAttribute("role", "button");
        if (item.thumbnail_b64) {
          const img = document.createElement("img");
          img.src = "data:image/webp;base64," + item.thumbnail_b64;
          img.alt = item.prompt || "Generated image";
          card.appendChild(img);
        }
        const capturedIdx = i;
        const activatePipCard = async () => {
          try {
            const res = await app.requestDisplayMode({ mode: "inline" });
            applyDisplayMode(res.mode);
            if (res.mode === "inline") openLightbox(capturedIdx);
          } catch (e) { /* host denied — stay in PiP */ }
        }
        card.addEventListener("click", activatePipCard);
        card.addEventListener("keydown", (e) => {
          if (e.key === "Enter" || e.key === " ") { e.preventDefault(); activatePipCard(); }
        });
        gridItems.appendChild(card);
      }
      // Hide pagination in PiP (also enforced by CSS)
      pagEl.innerHTML = "";
      updateSize();
    }

    // --- Display states ---
    function show(which) {
      loadingEl.style.display = which === "loading" ? "flex" : "none";
      emptyEl.style.display   = which === "empty"   ? "block" : "none";
      errorEl.style.display   = which === "error"   ? "block" : "none";
      gridEl.style.display    = which === "grid"    ? "block" : "none";
      // For "grid", renderGrid/renderPipStrip call updateSize after populating
      if (which !== "grid") updateSize();
    }

    // --- Card builder ---
    function makeCard(item) {
      const card = document.createElement("div");
      card.className = "card";
      card.tabIndex = 0;

      if (item.status === "generating" || !item.thumbnail_b64) {
        const pend = document.createElement("div");
        pend.className = "card-pending";
        const sp = document.createElement("div");
        sp.className = "spinner";
        const lbl = document.createElement("div");
        lbl.className = "card-pending-label";
        lbl.textContent = item.progress_message
          || (item.prompt ? "\\u201c" + trunc(item.prompt, 40) + "\\u201d" : "Generating\\u2026");
        pend.appendChild(sp);
        pend.appendChild(lbl);
        card.appendChild(pend);
        return card;
      }

      const img = document.createElement("img");
      img.src = "data:image/webp;base64," + item.thumbnail_b64;
      img.alt = item.prompt || "Generated image";
      img.loading = "lazy";
      card.appendChild(img);

      const overlay = document.createElement("div");
      overlay.className = "card-overlay";

      const promptDiv = document.createElement("div");
      promptDiv.className = "card-prompt";
      promptDiv.textContent = item.prompt || "";
      overlay.appendChild(promptDiv);

      const footer = document.createElement("div");
      footer.className = "card-footer";

      const badge = document.createElement("span");
      badge.className = "card-provider";
      badge.textContent = item.provider || "";
      footer.appendChild(badge);

      const dlBtn = document.createElement("button");
      dlBtn.className = "card-dl";
      dlBtn.title = "Download";
      dlBtn.dataset.imageId = item.image_id;
      dlBtn.dataset.mime = item.content_type || "image/png";
      dlBtn.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>';
      if (dlMode === "downloadFile" || dlMode === "openLink") dlBtn.style.display = "block";
      footer.appendChild(dlBtn);

      const delBtn = document.createElement("button");
      delBtn.className = "card-del";
      delBtn.title = "Delete image";
      delBtn.dataset.imageId = item.image_id;
      delBtn.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4h6v2"/></svg>';
      delBtn.style.display = "block";
      footer.appendChild(delBtn);

      overlay.appendChild(footer);
      card.appendChild(overlay);
      return card;
    }

    // --- Grid render ---
    function renderGrid(data) {
      const { total, items } = data;
      currentTotal = total;
      gridItems.innerHTML = "";

      // Update lightbox page items (completed images only)
      lbPageItems = (items || []).filter(i => i.status === "completed" && i.image_id);

      if (!items || items.length === 0) {
        if (total === 0) { updateEmptyState(); show("empty"); return; }
        show("grid");
        if (!pipActive) renderPagination();
        return;
      }

      show("grid");
      // In PiP mode, render compact strip instead of full grid
      if (pipActive) { renderPipStrip(); return; }
      let lbIdx = 0;
      for (const item of items) {
        const card = makeCard(item);
        if (item.status === "completed" && item.image_id) {
          const capturedIdx = lbIdx++;
          card.setAttribute("role", "button");
          card.addEventListener("click", (e) => {
            if (!e.target.closest(".card-dl") && !e.target.closest(".card-del")) openLightbox(capturedIdx);
          });
          card.addEventListener("keydown", (e) => {
            if (e.key === "Enter" || e.key === " ") { e.preventDefault(); openLightbox(capturedIdx); }
          });
        }
        gridItems.appendChild(card);
      }
      renderPagination();
      updateSize();
    }

    function renderPagination() {
      const totalPages = Math.max(1, Math.ceil(currentTotal / currentPageSize));
      pagEl.innerHTML = "";
      if (totalPages <= 1) return;

      const prev = document.createElement("button");
      prev.className = "page-btn";
      prev.textContent = "\\u2190 Prev";
      prev.disabled = currentPage <= 1;
      prev.addEventListener("click", () => goTo(currentPage - 1));

      const info = document.createElement("span");
      info.className = "page-info";
      info.textContent = "Page " + currentPage + " of " + totalPages;

      const next = document.createElement("button");
      next.className = "page-btn";
      next.textContent = "Next \\u2192";
      next.disabled = currentPage >= totalPages;
      next.addEventListener("click", () => goTo(currentPage + 1));

      pagEl.append(prev, info, next);
    }

    // --- Paginate via app-only tool ---
    async function goTo(page) {
      const ps = currentPageSize;
      const seq = ++galleryReqSeq;
      show("loading");
      try {
        const result = await app.callServerTool({ name: "gallery_page", arguments: { page, page_size: ps, origin: currentOrigin } });
        if (seq !== galleryReqSeq) return;
        if (result.isError) { console.warn("gallery_page failed", result.content?.find(c => c.type === "text")?.text); show("error"); return; }
        const text = result.content?.find(c => c.type === "text")?.text;
        if (!text) { console.warn("gallery_page returned no text"); show("error"); return; }
        const data = JSON.parse(text);
        if (data.origin) syncOrigin(data.origin);
        currentPage = data.page || 1;
        currentTotal = data.total || 0;
        currentPageSize = data.page_size || 12;
        renderGrid(data);
      } catch (e) {
        if (seq !== galleryReqSeq) return;
        console.warn("gallery_page failed", e);
        show("error");
      }
    }

    function reflectOrigin(o) {
      document.querySelectorAll("#origin-filter .seg").forEach(s => {
        const on = s.dataset.origin === o;
        s.classList.toggle("active", on);
        s.setAttribute("aria-checked", on ? "true" : "false");
        s.setAttribute("tabindex", on ? "0" : "-1");
      });
    }

    function selectOrigin(o) {
      if (o === currentOrigin) return;
      currentOrigin = o;
      reflectOrigin(o);
      currentPage = 1;
      goTo(1);
    }

    function syncOrigin(o) {
      if (!o || (o === currentOrigin && document.querySelector("#origin-filter .seg.active")?.dataset.origin === o)) return;
      currentOrigin = o;
      reflectOrigin(o);
    }

    function updateEmptyState() {
      const titleEl = document.querySelector("#empty .empty-title");
      const subEl = document.querySelector("#empty .empty-sub");
      if (!titleEl || !subEl) return;
      if (currentOrigin === "imported") {
        titleEl.textContent = "No imported images";
        subEl.textContent = "Use fetch_image or ingest_base64_image to add one.";
      } else {
        titleEl.textContent = "No images yet";
        subEl.innerHTML = 'Use <code>generate_image</code> to create your first image.';
      }
    }

    document.getElementById("origin-filter").addEventListener("click", (e) => {
      const btn = e.target.closest(".seg");
      if (!btn) return;
      selectOrigin(btn.dataset.origin);
    });

    document.getElementById("origin-filter").addEventListener("keydown", (e) => {
      const segs = [...document.querySelectorAll("#origin-filter .seg")];
      const i = segs.indexOf(document.activeElement);
      if (i < 0) return;
      let j;
      switch (e.key) {
        case "ArrowRight": case "ArrowDown": j = (i + 1) % segs.length; break;
        case "ArrowLeft": case "ArrowUp": j = (i - 1 + segs.length) % segs.length; break;
        case "Home": j = 0; break;
        case "End": j = segs.length - 1; break;
        default: return;
      }
      e.preventDefault();
      const target = segs[j];
      selectOrigin(target.dataset.origin);
      target.focus();
    });

    document.getElementById("gallery-retry").addEventListener("click", () => { goTo(currentPage || 1); });

    // --- Download ---
    gridItems.addEventListener("click", async (e) => {
      const btn = e.target.closest(".card-dl");
      if (!btn || !dlMode) return;
      e.stopPropagation();
      const id   = btn.dataset.imageId;
      const mime = btn.dataset.mime || "image/png";
      if (!id) return;
      const ext = mime.split("/").pop() || "png";
      let ok = false;
      try {
        if (dlMode === "downloadFile") {
          const res = await app.downloadFile({
            contents: [{
              type: "resource_link",
              uri: "image://" + id + "/view",
              name: id + "." + ext,
              mimeType: mime,
            }],
          });
          if (res.isError) console.warn("downloadFile failed", res.content?.find(c => c.type === "text")?.text);
          ok = !res.isError;
        } else if (dlMode === "openLink") {
          // Mint a one-time download URL on demand via the transfer framework.
          const result = await app.callServerTool({
            name: "create_download_link",
            arguments: { ref: "image://" + id + "/view" },
          });
          if (result.isError) {
            console.warn("create_download_link failed", result.content?.find(c => c.type === "text")?.text);
          } else {
            const textItem = result.content?.find(c => c.type === "text");
            const url = textItem ? JSON.parse(textItem.text).url : null;
            if (url) ok = !(await app.openLink({ url })).isError;
          }
        }
      } catch (ex) { console.warn("Download failed", ex); }
      if (!ok) alert("Download failed — please try again.");
    });

    // --- Delete (grid) ---
    gridItems.addEventListener("click", async (e) => {
      const btn = e.target.closest(".card-del");
      if (!btn) return;
      e.stopPropagation();
      const id = btn.dataset.imageId;
      if (!id) return;
      if (!confirm("Delete this image? This cannot be undone.")) return;
      btn.disabled = true;
      try {
        const result = await app.callServerTool({ name: "delete_image", arguments: { image_id: id } });
        if (result.isError) {
          alert("Delete failed: " + (result.content?.find(c => c.type === "text")?.text || "Unknown error"));
          return;
        }
        // Reload current page; navigate back if this was the last item on a non-first page
        const newPage = (currentTotal - 1 <= (currentPage - 1) * currentPageSize && currentPage > 1)
          ? currentPage - 1 : currentPage;
        await goTo(newPage);
      } catch (ex) {
        console.warn("Delete failed", ex);
        alert("Delete failed: " + ex.message);
      } finally {
        btn.disabled = false;
      }
    });

    // --- Delete (lightbox) ---
    async function deleteLightboxImage() {
      const item = lbPageItems[lbIndex];
      if (!item || !item.image_id) return;
      if (!confirm("Delete this image? This cannot be undone.")) return;
      lbDelBtn.disabled = true;
      try {
        const result = await app.callServerTool({ name: "delete_image", arguments: { image_id: item.image_id } });
        if (result.isError) {
          alert("Delete failed: " + (result.content?.find(c => c.type === "text")?.text || "Unknown error"));
          return;
        }
        // Reload page; if last item on a non-first page, navigate back first
        const oldIndex = lbIndex;
        const newPage = (currentTotal - 1 <= (currentPage - 1) * currentPageSize && currentPage > 1)
          ? currentPage - 1 : currentPage;
        await goTo(newPage);
        if (lbPageItems.length === 0) {
          closeLightbox();
        } else {
          const newIdx = Math.min(oldIndex, lbPageItems.length - 1);
          openLightbox(newIdx);
        }
      } catch (ex) {
        console.warn("Lightbox delete failed", ex);
        alert("Delete failed: " + ex.message);
      } finally {
        lbDelBtn.disabled = false;
      }
    }

    // --- Lifecycle handlers (ALL before connect) ---
    app.ontoolinput = () => { ++galleryReqSeq; show("loading"); };

    app.ontoolresult = ({ content }) => {
      ++galleryReqSeq;
      const text = content?.find(c => c.type === "text");
      if (!text) { console.warn("gallery result had no text"); show("error"); return; }
      try {
        const data = JSON.parse(text.text);
        if (typeof data.total !== "number") { console.warn("gallery result missing numeric total"); show("error"); return; }
        if (data.origin) syncOrigin(data.origin);
        currentPage = data.page || 1;
        currentTotal = data.total;
        currentPageSize = data.page_size || 12;
        renderGrid(data);
      } catch (e) {
        console.warn("Failed to parse gallery data", e);
        show("error");
      }
    };

    // A cancelled host tool call fires ontoolcancelled (not ontoolresult), so
    // leave the loading spinner for the recoverable error state (retry button).
    app.ontoolcancelled = () => { show("error"); };

    function handleHostContext(ctx) {
      if (ctx.theme) applyDocumentTheme(ctx.theme);
      if (ctx.styles?.variables) applyHostStyleVariables(ctx.styles.variables);
      if (ctx.styles?.css?.fonts) applyHostFonts(ctx.styles.css.fonts);
      if (ctx.safeAreaInsets) {
        const { top, right, bottom, left } = ctx.safeAreaInsets;
        const basePad = pipActive ? 4 : 12;
        mainEl.style.paddingTop    = (basePad + top)    + "px";
        mainEl.style.paddingRight  = (basePad + right)  + "px";
        mainEl.style.paddingBottom = (basePad + bottom) + "px";
        mainEl.style.paddingLeft   = (basePad + left)   + "px";
      }
      lbFsAvailable = ctx.availableDisplayModes?.includes("fullscreen") ?? false;
      if (lbActive) {
        if (lbFsAvailable) lbFsBtn.removeAttribute("hidden");
        else lbFsBtn.setAttribute("hidden", "");
      }
      // PiP availability
      pipAvailable = ctx.availableDisplayModes?.includes("pip") ?? false;
      pipBtn.style.display = pipAvailable ? "block" : "none";
      // Respond to external display mode changes (e.g. host closes PiP)
      if (ctx.displayMode && ctx.displayMode !== (pipActive ? "pip" : "inline")) {
        applyDisplayMode(ctx.displayMode);
      }
    }

    app.onhostcontextchanged = handleHostContext;
    app.onerror = console.error;

    await app.connect();
    const ctx = app.getHostContext();
    if (ctx) handleHostContext(ctx);

    // Show download buttons: prefer downloadFile (native, full-res), else
    // fall back to an on-demand create_download_link + openLink.
    const caps = app.getHostCapabilities();
    if (caps?.downloadFile) {
      dlMode = "downloadFile";
      document.querySelectorAll(".card-dl").forEach(b => b.style.display = "block");
    } else if (caps?.openLinks) {
      dlMode = "openLink";
      document.querySelectorAll(".card-dl").forEach(b => b.style.display = "block");
    }
  </script>
</body>
</html>"""


def _compute_claude_app_domain() -> str | None:
    """Auto-compute Claude's MCP Apps sandbox domain from BASE_URL.

    Claude requires ``{sha256_prefix}.claudemcpcontent.com`` where the hash
    is derived from the full MCP endpoint URL the client connects to.

    Returns:
        The computed domain string, or ``None`` when ``BASE_URL`` is not set
        (e.g. stdio transport or local development).
    """
    base_url = os.environ.get(f"{_ENV_PREFIX}_BASE_URL", "").strip().rstrip("/")
    if not base_url:
        return None
    http_path = os.environ.get(f"{_ENV_PREFIX}_HTTP_PATH", "/mcp").strip() or "/mcp"
    if not http_path.startswith("/"):
        http_path = f"/{http_path}"
    if len(http_path) > 1:
        http_path = http_path.rstrip("/")
    mcp_url = f"{base_url}{http_path}"
    hash_prefix = hashlib.sha256(mcp_url.encode()).hexdigest()[:32]
    return f"{hash_prefix}.claudemcpcontent.com"


def register_resources(mcp: FastMCP) -> None:
    """Register all MCP resources on *mcp*.

    Args:
        mcp: The :class:`~fastmcp.FastMCP` instance to register resources on.
    """

    @mcp.resource(
        "info://prompt-guide",
        description=(
            "Provider-specific prompt writing tips. Covers CLIP tag "
            "format for SD 1.5/SDXL, Flux natural language style, "
            "OpenAI prompt guidance, quality tags, negative prompt "
            "templates, and provider selection."
        ),
        mime_type="text/markdown",
        icons=[Icon(src=_LUCIDE.format("book-open-text"), mimeType="image/svg+xml")],
    )
    def prompt_guide() -> str:
        """Return per-provider prompt writing guidance as Markdown.

        Returns:
            Markdown text with per-provider prompt writing tips.
        """
        return _PROMPT_GUIDE

    @mcp.resource(
        "info://providers",
        description=(
            "Discover configured providers, available models, each "
            "model's prompt_style, supported aspect ratios, quality "
            "levels, and background options."
        ),
        icons=[Icon(src=_LUCIDE.format("info"), mimeType="image/svg+xml")],
    )
    async def provider_capabilities(
        service: ImageService = Depends(get_service),
    ) -> str:
        """Available image generation providers and their capabilities.

        Returns:
            JSON with provider names, availability, and supported features.
        """
        providers = service.list_providers()
        return json.dumps(
            {
                "providers": providers,
                "supported_aspect_ratios": SUPPORTED_ASPECT_RATIOS,
                "supported_quality_levels": SUPPORTED_QUALITY_LEVELS,
                "supported_resolutions": SUPPORTED_RESOLUTIONS,
                "supported_backgrounds": SUPPORTED_BACKGROUNDS,
            },
            indent=2,
        )

    @mcp.resource(
        "image://{image_id}/view{?format,width,height,quality,crop_x,crop_y,crop_w,crop_h,rotate,flip}",
        mime_type="application/octet-stream",
        description=(
            "Retrieve a generated image with optional transforms. "
            "No query params returns the original. Add format, width, "
            "height, quality, crop_x/y/w/h, rotate, or flip params to "
            "transform on the fly."
        ),
        icons=[Icon(src=_LUCIDE.format("scan-eye"), mimeType="image/svg+xml")],
    )
    async def image_view(
        image_id: str,
        format: str = "",
        width: int = 0,
        height: int = 0,
        quality: int = 90,
        crop_x: int = 0,
        crop_y: int = 0,
        crop_w: int = 0,
        crop_h: int = 0,
        rotate: int = 0,
        flip: str = "",
        service: ImageService = Depends(get_service),
    ) -> ResourceResult:
        """Retrieve an image with optional format conversion and resize.

        No parameters returns the original bytes unchanged. Set ``format``
        for conversion, ``width``/``height`` for resize or crop,
        ``crop_x``/``crop_y``/``crop_w``/``crop_h`` for region crop,
        ``rotate`` for 90° rotation, or ``flip`` for mirroring.

        Both width and height → center-crop to exact dimensions.
        Only width → proportional resize by width.
        Only height → proportional resize by height.
        crop_x/y/w/h → crop an arbitrary rectangular region.
        rotate → rotate 90, 180, or 270 degrees (lossless).
        flip → mirror horizontally or vertically (lossless).

        Args:
            image_id: Image registry ID.
            format: Target format (``png``, ``webp``, ``jpeg``), or empty
                for original.
            width: Target width in pixels, or 0 for original.
            height: Target height in pixels, or 0 for original.
            quality: Compression quality for lossy formats (1-100).
            crop_x: Left edge of crop box in pixels.
            crop_y: Top edge of crop box in pixels.
            crop_w: Width of crop box in pixels (0 = no region crop).
            crop_h: Height of crop box in pixels (0 = no region crop).
            rotate: Rotation in degrees — 90, 180, or 270 (0 = no rotation).
            flip: Flip axis — ``"horizontal"`` or ``"vertical"`` (empty = no flip).

        Returns:
            Image bytes with appropriate MIME type.
        """
        data, content_type = service.get_transformed_image(
            image_id,
            format=format,
            width=width,
            height=height,
            quality=quality,
            crop_x=crop_x,
            crop_y=crop_y,
            crop_w=crop_w,
            crop_h=crop_h,
            rotate=rotate,
            flip=flip,
        )
        return ResourceResult([ResourceContent(content=data, mime_type=content_type)])

    @mcp.resource(
        "image://{image_id}/metadata",
        mime_type="application/json",
        description=(
            "Read generation provenance for an image — prompt, provider, "
            "parameters, and timestamps. Use after generate_image to "
            "inspect what was generated."
        ),
        icons=[Icon(src=_LUCIDE.format("file-json"), mimeType="image/svg+xml")],
    )
    async def image_metadata(
        image_id: str,
        service: ImageService = Depends(get_service),
    ) -> str:
        """Retrieve generation metadata for an image.

        Args:
            image_id: Image registry ID.

        Returns:
            JSON with generation provenance (prompt, provider, params).
        """
        record = service.get_image(image_id)

        # Read sidecar JSON directly
        sidecar_path = service.scratch_dir / f"{record.id}.json"
        try:
            return sidecar_path.read_text()
        except FileNotFoundError:
            raise ImageProviderError(
                "server",
                f"Metadata file missing for image '{image_id}'. "
                "Verify the image_id via image://list.",
            ) from None

    @mcp.resource(
        "image://list",
        mime_type="application/json",
        description=(
            "List all gallery images (generated and imported) with their "
            "IDs, resource URIs, and prompts. Read this to find image_ids "
            "for use with image://*/view and image://*/metadata resources."
        ),
        icons=[
            Icon(
                src=_LUCIDE.format("gallery-thumbnails"),
                mimeType="image/svg+xml",
            )
        ],
    )
    async def image_list(
        service: ImageService = Depends(get_service),
    ) -> str:
        """List all registered images with their IDs and resource URIs.

        Includes both completed images and in-progress (fire-and-forget)
        generations with their current status.

        Returns:
            JSON array of image records with resource URIs.
        """
        images = service.list_images()
        result: list[dict[str, object]] = [
            {
                "image_id": img.id,
                "status": "completed",
                "origin": img.origin,
                "origin_source": img.origin_source,
                "provider": img.provider,
                "content_type": img.content_type,
                "original_dimensions": list(img.original_dimensions),
                "original_uri": f"image://{img.id}/view",
                "metadata_uri": f"image://{img.id}/metadata",
                "resource_template": (
                    f"image://{img.id}/view{{?format,width,height,quality,crop_x,crop_y,crop_w,crop_h,rotate,flip}}"
                ),
                "prompt": img.prompt,
                "created_at": datetime.fromtimestamp(
                    img.created_at, tz=UTC
                ).isoformat(),
            }
            for img in images
        ]

        # Include in-progress and failed generations
        for pending in service.list_pending():
            result.append(
                {
                    "image_id": pending.id,
                    "status": pending.status,
                    "provider": pending.provider,
                    "prompt": pending.prompt,
                    "progress": pending.progress,
                    "progress_message": pending.progress_message,
                    "original_uri": f"image://{pending.id}/view",
                    "resource_template": (
                        f"image://{pending.id}/view{{?format,width,height,quality,crop_x,crop_y,crop_w,crop_h,rotate,flip}}"
                    ),
                    "created_at": datetime.fromtimestamp(
                        pending.created_at, tz=UTC
                    ).isoformat(),
                }
            )

        return json.dumps(result, indent=2)

    # -- Style library resources -----------------------------------------------

    @mcp.resource(
        "style://list",
        mime_type="application/json",
        description=(
            "List all available style presets with their names, tags, "
            "and default parameters. Use to browse styles before "
            "applying one via the apply_style prompt."
        ),
        icons=[Icon(src=_LUCIDE.format("palette"), mimeType="image/svg+xml")],
    )
    async def style_list(
        service: ImageService = Depends(get_service),
    ) -> str:
        """List all loaded style presets.

        Returns:
            JSON array of style summaries.
        """
        styles = service.list_styles()
        result = []
        for s in styles:
            desc = next(
                (line.strip() for line in s.body.splitlines() if line.strip()), ""
            )
            result.append(
                {
                    "name": s.name,
                    "tags": list(s.tags),
                    "description": desc,
                    "provider": s.provider,
                    "aspect_ratio": s.aspect_ratio,
                    "quality": s.quality,
                }
            )
        return json.dumps(result, indent=2)

    @mcp.resource(
        "style://{name}",
        mime_type="text/markdown",
        description=(
            "Read the full content of a style preset. Returns the "
            "complete markdown file including frontmatter defaults "
            "and creative brief body."
        ),
        icons=[Icon(src=_LUCIDE.format("palette"), mimeType="image/svg+xml")],
    )
    async def style_detail(
        name: str,
        service: ImageService = Depends(get_service),
    ) -> str:
        """Return the full markdown content of a style file.

        Args:
            name: Style identifier.

        Returns:
            The raw markdown content of the style file.

        Raises:
            ImageProviderError: If the style is not found.
        """
        entry = service.get_style(name)
        if entry is None:
            raise ImageProviderError(
                "server",
                f"Style not found: '{name}'. Use style://list to see available styles.",
            )
        try:
            return entry.file_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            raise ImageProviderError(
                "server",
                f"Style file missing on disk for '{name}'. "
                "The file may have been deleted externally.",
            ) from None

    # -- MCP Apps: image viewer -------------------------------------------------

    # Resolve the MCP Apps sandbox domain.  Priority:
    # 1. Explicit APP_DOMAIN env var (any host format)
    # 2. Auto-computed from BASE_URL for Claude (sha256 of MCP endpoint URL)
    # 3. None — host assigns its own sandbox origin (stdio / local setups)
    app_domain: str | None = (
        os.environ.get(f"{_ENV_PREFIX}_APP_DOMAIN", "").strip()
        or _compute_claude_app_domain()
    )

    @mcp.resource(
        _IMAGE_VIEWER_URI,
        description="Interactive image viewer for show_image results.",
        app=AppConfig(domain=app_domain),
    )
    def image_viewer() -> str:
        """HTML viewer that renders images from show_image tool results.

        Loaded by MCP Apps-capable clients (Claude Desktop, claude.ai) in a
        sandboxed iframe.  Listens for tool results via the ext-apps SDK and
        displays the image with metadata.
        """
        return _inject_sdk(_IMAGE_VIEWER_HTML)

    # -- MCP Apps: image gallery ------------------------------------------------

    @mcp.resource(
        _IMAGE_GALLERY_URI,
        description="Interactive gallery for browsing all generated images.",
        app=AppConfig(domain=app_domain),
    )
    def image_gallery() -> str:
        """HTML gallery that renders a browsable grid of generated images.

        Loaded by MCP Apps-capable clients (Claude Desktop, claude.ai) in a
        sandboxed iframe.  Receives the first page of thumbnail data from the
        ``browse_gallery`` tool result, then paginates via the ``gallery_page``
        app-only tool.
        """
        return _inject_sdk(_IMAGE_GALLERY_HTML)
