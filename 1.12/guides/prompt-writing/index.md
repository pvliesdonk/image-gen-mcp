# Prompt Writing Guide

Tips for writing effective image generation prompts, tailored to each provider.

For per-model strengths, weaknesses, and prompt examples, see the [Model Catalog](https://pvliesdonk.github.io/image-generation-mcp/1.12/providers/model-catalog/index.md).

## OpenAI (natural language)

OpenAI models work best with natural language descriptions. Be specific about what you want.

### General tips

- Describe the scene in complete sentences
- Include style, lighting, and composition details
- Specify camera angle or perspective when relevant
- Mention the medium (photograph, oil painting, digital art, etc.)

### Examples

**Product photography:**

```
A professional product photo of white sneakers on a clean white background,
studio lighting, sharp focus, commercial photography style, high resolution
```

**Logo design:**

```
A minimalist logo for "Acme Corp" with clean sans-serif typography,
blue and white color scheme, modern design, vector art style
```

**Illustration:**

```
A whimsical children's book illustration of a fox reading a book under
a large oak tree, watercolor style, warm autumn colors, soft lighting
```

### Negative prompts

When using OpenAI, negative prompts are appended as an "Avoid:" clause. Keep them concise:

```
Avoid: blurry, low quality, distorted text, watermark
```

______________________________________________________________________

## SD WebUI / Stable Diffusion (CLIP tag format)

Stable Diffusion models respond best to comma-separated tags ordered by importance.

### Tag structure

```
subject, medium, style, lighting, camera, quality tags
```

### Examples

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

**Anime:**

```
1boy, silver hair, red eyes, dark coat, standing on rooftop, city skyline,
night, wind, detailed, anime style, masterpiece
```

### Weighted tokens (emphasis)

Use parentheses to increase or decrease emphasis on specific tokens:

```
# Increase emphasis (1.1x per level of parentheses)
(detailed face)       # 1.1x emphasis
((detailed face))     # 1.21x emphasis
(detailed face:1.5)   # 1.5x emphasis (explicit weight)

# Decrease emphasis
[blurry background]   # 0.9x emphasis
(blurry background:0.5)  # 0.5x emphasis (explicit weight)
```

Weights are relative to the baseline of 1.0. Values above 1.0 strengthen a concept; values below 1.0 weaken it. Extreme weights (above 1.8 or below 0.3) often produce artifacts.

### Quality tags

Add these to improve output quality:

| Tags                           | Effect                           |
| ------------------------------ | -------------------------------- |
| `masterpiece, best quality`    | General quality boost            |
| `highly detailed, sharp focus` | Detail enhancement               |
| `8k, ultra high res`           | Resolution boost (use sparingly) |
| `professional, award winning`  | Style refinement                 |

### Negative prompts

Always include a negative prompt with SD WebUI to avoid common artifacts.

**General-purpose:**

```
lowres, bad anatomy, bad hands, text, error, missing fingers,
extra digit, fewer digits, cropped, worst quality, low quality,
normal quality, jpeg artifacts, signature, watermark, blurry
```

**Add for photorealism:**

```
cartoon, anime, illustration, painting, drawing, art, sketch
```

**Add for anime/illustration:**

```
photo, realistic, 3d render
```

### BREAK syntax

Use `BREAK` to separate concepts into different CLIP token chunks. This is useful when your prompt is long or has distinct elements:

```
1girl, detailed face, blue eyes BREAK
forest background, sunlight through trees BREAK
masterpiece, best quality, sharp focus
```

### CLIP token limits

- **SD 1.5:** 77 tokens per CLIP chunk
- **SDXL:** 77 tokens per chunk, but uses two CLIP encoders (ViT-L + ViT-bigG)

Front-load the most important tags. Tokens beyond the first 77-token chunk have diminishing influence.

______________________________________________________________________

## Provider-agnostic tips

### Aspect ratios

All providers support these aspect ratios:

| Ratio  | Best for                                |
| ------ | --------------------------------------- |
| `1:1`  | Avatars, icons, social media posts      |
| `16:9` | Landscapes, banners, desktop wallpapers |
| `9:16` | Phone wallpapers, stories, portraits    |
| `3:2`  | Photography standard, prints            |
| `2:3`  | Book covers, posters                    |

### Common use cases

| Use case                 | Recommended provider | Prompt approach                                |
| ------------------------ | -------------------- | ---------------------------------------------- |
| Logo with text           | OpenAI               | Natural language, specify text content exactly |
| Photo-realistic portrait | SD WebUI             | Tag format, include quality and lighting tags  |
| Anime character          | SD WebUI             | Tag format, include character details          |
| Quick placeholder        | Placeholder          | Any prompt (generates solid color)             |
| Product photo            | SD WebUI or OpenAI   | Describe studio setup and product details      |
| Landscape art            | SD WebUI or OpenAI   | Include composition, lighting, and style       |
