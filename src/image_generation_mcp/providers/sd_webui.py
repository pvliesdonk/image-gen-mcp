"""SD WebUI (Stable Diffusion WebUI) image provider.

Generates images via the SD WebUI REST API (``/sdapi/v1/txt2img``).
Compatible with A1111, Forge, reForge, and Forge-neo.
Model-aware presets auto-detect SD 1.5, SDXL, SDXL Lightning,
and Flux (dev/schnell) from the checkpoint name.

Ported from questfoundry — prompt distillation removed entirely.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, cast

import httpx

from image_generation_mcp.providers.capabilities import (
    ModelCapabilities,
    ProviderCapabilities,
    make_degraded,
)
from image_generation_mcp.providers.model_styles import resolve_style
from image_generation_mcp.providers.types import (
    ImageProviderConnectionError,
    ImageProviderError,
    ImageResult,
    InputImage,
    ProgressCallback,
    TooManyInputImages,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 180.0  # SDXL at high res can be slow on consumer GPUs
_PROGRESS_POLL_INTERVAL = 2.0  # seconds between /sdapi/v1/progress polls
_MAX_INPUT_IMAGES = 1
_DEFAULT_DENOISING_STRENGTH = 0.75


# -- Model-aware generation presets -------------------------------------------


@dataclass(frozen=True)
class _SdWebuiPreset:
    """Generation parameters tuned for a specific SD architecture.

    SD WebUI >=1.6 split the sampler and scheduler into separate API fields.
    Older versions used combined names like ``"DPM++ 2M Karras"``.
    """

    sizes: dict[str, tuple[int, int]] = field(repr=False)
    steps: int = 30
    sampler: str = "DPM++ 2M"
    scheduler: str = "Karras"
    cfg_scale: float = 7.0
    quality_tier: str = "medium"
    supports_negative_prompt: bool = True
    distilled_cfg_scale: float | None = None
    prompt_style: str = "clip"


_SD15_PRESET = _SdWebuiPreset(
    sizes={
        "1:1": (768, 768),
        "16:9": (912, 512),
        "9:16": (512, 912),
        "3:2": (768, 512),
        "2:3": (512, 768),
    },
)

_SDXL_SIZES: dict[str, tuple[int, int]] = {
    "1:1": (1024, 1024),
    "16:9": (1344, 768),
    "9:16": (768, 1344),
    "3:2": (1216, 832),
    "2:3": (832, 1216),
}

_SDXL_PRESET = _SdWebuiPreset(
    sizes=_SDXL_SIZES,
    steps=35,
    sampler="DPM++ 2M",
    scheduler="Karras",
    cfg_scale=7.5,
    quality_tier="high",
)

_SDXL_LIGHTNING_PRESET = _SdWebuiPreset(
    sizes=_SDXL_SIZES,
    steps=6,
    sampler="DPM++ SDE",
    scheduler="Karras",
    cfg_scale=2.0,
    quality_tier="high",
)

_FLUX_DEV_PRESET = _SdWebuiPreset(
    sizes=_SDXL_SIZES,
    steps=20,
    sampler="Euler",
    scheduler="Simple",
    cfg_scale=1.0,
    quality_tier="high",
    supports_negative_prompt=False,
    distilled_cfg_scale=3.5,
    prompt_style="natural_language",
)

_FLUX_SCHNELL_PRESET = _SdWebuiPreset(
    sizes=_SDXL_SIZES,
    steps=4,
    sampler="Euler",
    scheduler="Simple",
    cfg_scale=1.0,
    quality_tier="high",
    supports_negative_prompt=False,
    distilled_cfg_scale=3.5,
    prompt_style="natural_language",
)

_SD3_PRESET = _SdWebuiPreset(
    sizes=_SDXL_SIZES,
    steps=28,
    sampler="DPM++ 2M",
    scheduler="Karras",
    cfg_scale=4.5,
    quality_tier="high",
    supports_negative_prompt=True,
    prompt_style="natural_language",
)

# NOTE: keep these tag tuples in sync with CHECKPOINT_PATTERNS in
# providers/model_styles.py — both systems classify the same checkpoint
# names independently. _detect_architecture chooses the *generation
# preset* (resolution / steps / cfg / negative-prompt support);
# CHECKPOINT_PATTERNS chooses the *narrative style profile*. A new
# architecture needs an entry in BOTH places.
_SD3_TAGS = ("sd3", "sd_3", "stable_diffusion_3", "stable-diffusion-3")
_XL_TAGS = ("sdxl", "xl_", "_xl", "-xl")
_LIGHTNING_TAGS = ("lightning", "turbo")
_FLUX_TAGS = ("flux1", "flux2", "flux_", "_flux", "-flux")


def _detect_architecture(model_name: str) -> str:
    """Detect SD architecture from a checkpoint name.

    Detection order:
    1. SD 3 / 3.5 — returns ``"sd3"``
    2. Flux schnell — returns ``"flux_schnell"``
    3. Flux dev — returns ``"flux_dev"``
    4. Lightning/Turbo SDXL — returns ``"sdxl_lightning"``
    5. Standard SDXL — returns ``"sdxl"``
    6. SD 1.5 fallback — returns ``"sd15"``

    Args:
        model_name: Checkpoint name or title string (case-insensitive).

    Returns:
        One of ``"sd15"``, ``"sdxl"``, ``"sdxl_lightning"``, ``"flux_dev"``,
        ``"flux_schnell"``, or ``"sd3"``.
    """
    lower = model_name.lower()
    if any(tag in lower for tag in _SD3_TAGS):
        return "sd3"
    is_flux = any(tag in lower for tag in _FLUX_TAGS)
    if is_flux:
        if "schnell" in lower:
            return "flux_schnell"
        return "flux_dev"
    is_xl = any(tag in lower for tag in _XL_TAGS)
    is_lightning = any(tag in lower for tag in _LIGHTNING_TAGS)
    if is_xl and is_lightning:
        return "sdxl_lightning"
    if is_xl:
        return "sdxl"
    return "sd15"


_ARCH_PRESETS: dict[str, _SdWebuiPreset] = {
    "sd3": _SD3_PRESET,
    "flux_schnell": _FLUX_SCHNELL_PRESET,
    "flux_dev": _FLUX_DEV_PRESET,
    "sdxl_lightning": _SDXL_LIGHTNING_PRESET,
    "sdxl": _SDXL_PRESET,
}


def _resolve_preset(model: str | None) -> _SdWebuiPreset:
    """Choose generation preset based on checkpoint name."""
    if not model:
        return _SD15_PRESET
    arch = _detect_architecture(model)
    return _ARCH_PRESETS.get(arch, _SD15_PRESET)


class SdWebuiImageProvider:
    """Image provider using SD WebUI (A1111/Forge/reForge/Forge-neo).

    Args:
        host: WebUI base URL (e.g., ``http://localhost:7860``).
        model: Optional SD checkpoint name for preset detection and
            checkpoint override.
    """

    def __init__(
        self,
        host: str,
        model: str | None = None,
    ) -> None:
        self._host = host.rstrip("/")
        self._model = model
        self._preset = _resolve_preset(model)
        self._client = httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT)

    async def aclose(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    def _build_payload(
        self,
        *,
        prompt: str,
        negative_prompt: str | None,
        aspect_ratio: str,
        effective_model: str | None,
        preset: _SdWebuiPreset,
    ) -> tuple[dict[str, Any], int, int]:
        """Build the shared SD WebUI request payload.

        Args:
            prompt: Positive text prompt.
            negative_prompt: Negative prompt, or None.
            aspect_ratio: Desired aspect ratio string (e.g. ``"1:1"``).
            effective_model: Resolved checkpoint name, or None.
            preset: Architecture preset for this model.

        Returns:
            Tuple of ``(payload_dict, width, height)``.
        """
        default_size = preset.sizes["1:1"]
        width, height = preset.sizes.get(aspect_ratio, default_size)

        payload: dict[str, Any] = {
            "prompt": prompt,
            "width": width,
            "height": height,
            "steps": preset.steps,
            "cfg_scale": preset.cfg_scale,
            "sampler_name": preset.sampler,
            "scheduler": preset.scheduler,
        }

        # Flux models do not support negative prompts — omit entirely.
        # Other architectures always include the field (empty string if None).
        if preset.supports_negative_prompt:
            payload["negative_prompt"] = negative_prompt or ""
        elif negative_prompt:
            logger.debug("Model does not support negative prompts, ignoring")

        # distilled_cfg_scale is a Forge-specific parameter for Flux models
        if preset.distilled_cfg_scale is not None:
            payload["distilled_cfg_scale"] = preset.distilled_cfg_scale

        if effective_model:
            payload["override_settings"] = {"sd_model_checkpoint": effective_model}

        return payload, width, height

    async def generate(
        self,
        prompt: str,
        *,
        negative_prompt: str | None = None,
        aspect_ratio: str = "1:1",
        quality: str = "standard",  # noqa: ARG002
        resolution: str = "standard",
        background: str = "opaque",
        model: str | None = None,
        reference_images: Sequence[InputImage] | None = None,
        strength: float | None = None,
        mask: InputImage | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> ImageResult:
        """Generate or edit an image via the SD WebUI API.

        When ``reference_images`` is empty or None, calls ``/sdapi/v1/txt2img``
        (standard text-to-image).  When a single reference image is supplied,
        calls ``/sdapi/v1/img2img`` using that image as the init image.

        Args:
            prompt: Positive text prompt (SD tag format recommended).
            negative_prompt: Negative prompt (natively supported by SD).
            aspect_ratio: Desired aspect ratio.
            quality: Ignored — SD quality is controlled by steps/cfg.
            resolution: Ignored. This provider offers no higher-resolution
                tier; it always renders at the checkpoint/preset size for the
                requested aspect ratio and reports ``"resolution":
                "standard"`` in provider metadata regardless of the
                requested tier.
            background: Ignored — SD WebUI does not support background
                transparency control.
            model: Specific checkpoint name to use for this call. Overrides
                the constructor model for preset detection and
                ``override_settings``.
            reference_images: Optional single reference image used as the
                img2img init image.  Pass exactly one :class:`InputImage`;
                passing more than one raises :class:`TooManyInputImages`.
            strength: Denoising strength for img2img (0.0-1.0). Ignored for
                txt2img.  Defaults to 0.75 when reference_images is supplied
                and strength is None.
            mask: Not supported — SD WebUI inpainting is not wired to this
                parameter. Raises :class:`ImageProviderError` when supplied.
            progress_callback: Optional callback invoked with
                ``(fraction, message)`` during generation.  When provided,
                ``/sdapi/v1/progress`` is polled concurrently.

        Returns:
            ImageResult with PNG data and provider metadata.  Metadata
            includes ``edited=True`` when img2img was used.

        Raises:
            ImageProviderConnectionError: If SD WebUI is unreachable.
            ImageProviderError: On API errors.
            TooManyInputImages: When more than one reference image is supplied.
        """
        if mask is not None:
            raise ImageProviderError(
                "sd_webui", "mask is not supported by this provider"
            )

        effective_model = model or self._model
        effective_preset = _resolve_preset(effective_model)

        if background != "opaque":
            logger.debug(
                "SD WebUI does not support background transparency control, ignoring"
            )
        if resolution != "standard":
            logger.debug("resolution_ignored provider=sd_webui reason=unsupported")

        payload, width, height = self._build_payload(
            prompt=prompt,
            negative_prompt=negative_prompt,
            aspect_ratio=aspect_ratio,
            effective_model=effective_model,
            preset=effective_preset,
        )

        # Branch on ``reference_images`` directly (not a precomputed bool) so
        # mypy narrows ``Sequence | None`` to non-None inside the img2img block.
        if reference_images:
            if len(reference_images) > _MAX_INPUT_IMAGES:
                raise TooManyInputImages(
                    "sd_webui",
                    effective_model,
                    _MAX_INPUT_IMAGES,
                    len(reference_images),
                )
            payload["init_images"] = [
                base64.b64encode(reference_images[0].data).decode("ascii")
            ]
            payload["denoising_strength"] = (
                strength if strength is not None else _DEFAULT_DENOISING_STRENGTH
            )
            url = f"{self._host}/sdapi/v1/img2img"
        else:
            if strength is not None:
                logger.debug(
                    "strength_ignored provider=sd_webui "
                    "reason=no_reference_images endpoint=txt2img"
                )
            url = f"{self._host}/sdapi/v1/txt2img"
        is_img2img = bool(reference_images)

        logger.debug(
            "SD WebUI generate: host=%s model=%s size=%dx%d img2img=%s",
            self._host,
            effective_model,
            width,
            height,
            is_img2img,
        )

        # Run generation with concurrent progress polling when callback provided
        progress_task: asyncio.Task[None] | None = None
        if progress_callback is not None:
            progress_task = asyncio.create_task(
                self._poll_progress(effective_preset.steps, progress_callback)
            )

        try:
            response = await self._client.post(url, json=payload)
        except httpx.ConnectError as e:
            raise ImageProviderConnectionError(
                "sd_webui", f"Cannot connect to SD WebUI at {self._host}: {e}"
            ) from e
        except httpx.TimeoutException as e:
            raise ImageProviderConnectionError(
                "sd_webui",
                f"Request to SD WebUI timed out after {_DEFAULT_TIMEOUT}s: {e}",
            ) from e
        finally:
            if progress_task is not None:
                progress_task.cancel()
                await asyncio.gather(progress_task, return_exceptions=True)

        if response.status_code != 200:
            body_preview = response.text[:200]
            raise ImageProviderError(
                "sd_webui",
                f"SD WebUI returned HTTP {response.status_code}: {body_preview}",
            )

        data = response.json()
        images = data.get("images")
        if not images:
            raise ImageProviderError(
                "sd_webui",
                "SD WebUI response missing 'images' field or returned empty list",
            )

        # Extract seed and model name from response info
        seed = None
        active_model = effective_model
        info_str = data.get("info")
        if info_str:
            try:
                info = json.loads(info_str) if isinstance(info_str, str) else info_str
                seed = info.get("seed")
                if not effective_model:
                    active_model = info.get("sd_model_name")
            except (json.JSONDecodeError, TypeError, AttributeError) as e:
                logger.warning(
                    "SD WebUI info parse failed: %s (preview: %s)",
                    e,
                    str(info_str)[:100],
                )

        metadata: dict[str, Any] = {
            "quality": effective_preset.quality_tier,
            "model": active_model,
            "size": f"{width}x{height}",
            "steps": effective_preset.steps,
            "prompt_style": effective_preset.prompt_style,
            # Always-delivered tier: SD WebUI has no higher tier, so it
            # reports "standard" regardless of the requested resolution to
            # keep the delivered-tier contract truthful.
            "resolution": "standard",
        }
        if seed is not None:
            metadata["seed"] = seed
        if is_img2img:
            metadata["edited"] = True

        logger.info(
            "SD WebUI image generated: model=%s size=%dx%d seed=%s img2img=%s",
            active_model,
            width,
            height,
            seed,
            is_img2img,
        )

        return ImageResult.from_base64(
            images[0],
            content_type="image/png",
            **metadata,
        )

    async def discover_capabilities(self) -> ProviderCapabilities:
        """Discover SD WebUI checkpoint capabilities via sd-models API.

        Calls ``GET /sdapi/v1/sd-models`` to enumerate installed checkpoints
        and ``GET /sdapi/v1/options`` to identify the currently active model.
        Architecture (SD1.5, SDXL, Lightning) is auto-detected from each
        checkpoint name to populate correct resolution and step defaults.

        Returns:
            ProviderCapabilities with one ModelCapabilities entry per
            checkpoint.  Returns a degraded ProviderCapabilities (empty
            model list, ``degraded=True``) if SD WebUI is unreachable.
        """
        discovered_at = time.time()

        results = await asyncio.gather(
            self._client.get(f"{self._host}/sdapi/v1/sd-models"),
            self._client.get(f"{self._host}/sdapi/v1/options"),
            return_exceptions=True,
        )

        # Prioritize unexpected exceptions over connection/timeout errors
        connect_error = None
        for result in results:
            if isinstance(result, (httpx.ConnectError, httpx.TimeoutException)):
                if connect_error is None:
                    connect_error = result
            elif isinstance(result, BaseException):
                raise result

        if connect_error is not None:
            logger.warning(
                "SD WebUI unreachable during capability discovery at %s: %s",
                self._host,
                connect_error,
            )
            return make_degraded("sd_webui", discovered_at)

        models_response, options_response = cast(
            "tuple[httpx.Response, httpx.Response]",
            tuple(results),
        )

        # Log the active checkpoint from /options
        if options_response.status_code == 200:
            options_data = options_response.json()
            active_checkpoint = options_data.get("sd_model_checkpoint")
            if active_checkpoint:
                logger.info("SD WebUI active checkpoint: %s", active_checkpoint)

        if models_response.status_code != 200:
            logger.warning(
                "SD WebUI /sdapi/v1/sd-models returned HTTP %d — marking degraded",
                models_response.status_code,
            )
            return make_degraded("sd_webui", discovered_at)

        raw = models_response.json()
        if not isinstance(raw, list):
            logger.warning(
                "SD WebUI /sdapi/v1/sd-models returned unexpected type %s — marking degraded",
                type(raw).__name__,
            )
            return make_degraded("sd_webui", discovered_at)
        checkpoints: list[dict[str, Any]] = raw
        model_caps: list[ModelCapabilities] = []

        for checkpoint in checkpoints:
            title: str = checkpoint.get("title", "")
            if not title:
                logger.debug("Skipping checkpoint with empty title: %r", checkpoint)
                continue
            model_name: str = checkpoint.get("model_name", title)

            arch = _detect_architecture(title)
            preset = _resolve_preset(title)

            max_resolution = (
                1024
                if arch in ("sdxl", "sdxl_lightning", "flux_dev", "flux_schnell", "sd3")
                else 768
            )

            model_caps.append(
                ModelCapabilities(
                    model_id=title,
                    display_name=model_name,
                    can_generate=True,
                    can_edit=False,
                    supports_mask=False,
                    supported_aspect_ratios=tuple(preset.sizes.keys()),
                    supported_qualities=("standard",),
                    supported_formats=("png",),
                    supports_negative_prompt=preset.supports_negative_prompt,
                    supports_background=False,
                    supports_image_input=True,
                    max_input_images=_MAX_INPUT_IMAGES,
                    max_resolution=max_resolution,
                    default_steps=preset.steps,
                    default_cfg=preset.cfg_scale,
                    prompt_style=preset.prompt_style,
                    style_profile=resolve_style("sd_webui", title),
                )
            )

        logger.info(
            "SD WebUI capability discovery complete: %d checkpoints found at %s",
            len(model_caps),
            self._host,
        )

        return ProviderCapabilities(
            provider_name="sd_webui",
            models=tuple(model_caps),
            discovered_at=discovered_at,
        )

    async def _poll_progress(
        self,
        total_steps: int,
        callback: ProgressCallback,
    ) -> None:
        """Poll ``/sdapi/v1/progress`` and relay updates via *callback*.

        Runs as a concurrent task alongside ``/sdapi/v1/txt2img``.
        Cancellation-safe — the caller cancels this task when txt2img
        finishes.

        Args:
            total_steps: Expected step count (from the preset) for
                human-readable messages.
            callback: Called with ``(fraction, message)`` on each poll.
        """
        url = f"{self._host}/sdapi/v1/progress"
        while True:
            try:
                resp = await self._client.get(url, timeout=5.0)
                if resp.status_code != 200:
                    logger.debug(
                        "SD WebUI progress endpoint returned HTTP %d",
                        resp.status_code,
                    )
                else:
                    data = resp.json()
                    progress: float = data.get("progress", 0.0)
                    eta: float = data.get("eta_relative", 0.0)
                    current_step = round(progress * total_steps)
                    msg = f"Step {current_step}/{total_steps}"
                    if eta > 0:
                        msg += f" (ETA {eta:.0f}s)"
                    callback(progress, msg)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.debug(
                    "SD WebUI progress poll failed — continuing without update",
                    exc_info=True,
                )
            await asyncio.sleep(_PROGRESS_POLL_INTERVAL)
