"""Gemini image generation provider.

Uses the Gemini native generateContent API with responseModalities=["IMAGE"].
Requires the google-genai package (optional dependency).
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any, NoReturn

from image_generation_mcp.providers.capabilities import (
    ModelCapabilities,
    ProviderCapabilities,
    make_degraded,
)
from image_generation_mcp.providers.model_styles import resolve_style
from image_generation_mcp.providers.types import (
    ImageContentPolicyError,
    ImageProviderConnectionError,
    ImageProviderError,
    ImageResult,
    InputImage,
    ProgressCallback,
    TooManyInputImages,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from google import genai as genai_type

logger = logging.getLogger(__name__)

# All Gemini-supported aspect ratios — direct pass-through identity mapping.
# Kept consistent with other providers that may need to remap ratios.
_ASPECT_RATIOS: dict[str, str] = {
    "1:1": "1:1",
    "16:9": "16:9",
    "9:16": "9:16",
    "3:2": "3:2",
    "2:3": "2:3",
    "3:4": "3:4",
    "4:3": "4:3",
    "4:5": "4:5",
    "5:4": "5:4",
    "4:1": "4:1",
    "1:4": "1:4",
    "8:1": "8:1",
    "1:8": "1:8",
    "21:9": "21:9",
}

# Models that support thinking_config (reasoning before image generation).
# gemini-2.5-flash-image does NOT support thinking.
_THINKING_MODELS: frozenset[str] = frozenset(
    {
        "gemini-3.1-flash-image",
        "gemini-3-pro-image",
        "gemini-3.1-flash-lite-image",
    }
)

# Known Gemini image-capable models in preference order (first entry is the
# default). Discovery returns this static list — models.list() does not reliably
# filter image-generation models, so we maintain the known set here. The GA ids
# (no ``-preview`` suffix) are pinned; the older ``-preview`` aliases are dropped
# now that the GA ids are generally available.
# When adding a model, also add its reference-image cap to
# _MAX_INPUT_IMAGES_BY_MODEL below; otherwise the conservative default applies.
_KNOWN_IMAGE_MODELS: list[tuple[str, str]] = [
    ("gemini-3.1-flash-image", "Gemini 3.1 Flash Image"),
    ("gemini-3-pro-image", "Gemini 3 Pro Image"),
    ("gemini-3.1-flash-lite-image", "Gemini 3.1 Flash Lite Image"),
    ("gemini-2.5-flash-image", "Gemini 2.5 Flash Image"),
]

# NOTE: insertion order encodes tier rank, lowest to highest (standard <
# high < max). Do not reorder -- the clamp's best-available-tier selection
# (``max(model_resolutions, key=list(_RESOLUTION_TO_IMAGE_SIZE).index)``)
# relies on this dict's iteration order to find the highest tier a model
# supports.
_RESOLUTION_TO_IMAGE_SIZE: dict[str, str] = {
    "standard": "1K",
    "high": "2K",
    "max": "4K",
}

_SUPPORTED_ASPECT_RATIOS: tuple[str, ...] = tuple(_ASPECT_RATIOS)
_SUPPORTED_QUALITIES: tuple[str, ...] = ("standard", "hd")

# Maximum reference images per generate() call, by model. Gemini 3 image
# models accept up to 14 reference images for multi-image composition (per the
# ai.google.dev image-generation docs). The older gemini-2.5-flash-image has no
# documented multi-image limit, so a conservative cap is applied. Unknown
# models fall back to the conservative default.
_MAX_INPUT_IMAGES_BY_MODEL: dict[str, int] = {
    "gemini-2.5-flash-image": 3,
    "gemini-3.1-flash-image": 14,
    "gemini-3-pro-image": 14,
    # [unverified] lite cap not separately documented; assume the Gemini 3.1
    # image-family limit of 14 rather than the conservative default.
    "gemini-3.1-flash-lite-image": 14,
}
_DEFAULT_MAX_INPUT_IMAGES = 3


def _max_input_images(model: str) -> int:
    """Return the reference-image cap for a Gemini model."""
    return _MAX_INPUT_IMAGES_BY_MODEL.get(model, _DEFAULT_MAX_INPUT_IMAGES)


class GeminiImageProvider:
    """Image generation provider backed by the Gemini generateContent API.

    Uses the google-genai SDK with native image generation via
    ``responseModalities=["IMAGE"]``. Registered when
    ``IMAGE_GENERATION_MCP_GOOGLE_API_KEY`` is set.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-3.1-flash-image",
    ) -> None:
        """Initialise the Gemini provider.

        Args:
            api_key: Google API key with Gemini access.
            model: Default model ID for image generation.
        """
        self._model = model
        self._client = self._create_client(api_key)

    def _create_client(self, api_key: str) -> genai_type.Client:
        """Create the google-genai client.

        Separated from ``__init__`` so tests can patch it without needing
        the real ``google-genai`` package installed.

        Args:
            api_key: Google API key.

        Returns:
            Initialised ``genai.Client``.
        """
        from google import genai  # pragma: no cover

        return genai.Client(api_key=api_key)  # pragma: no cover

    async def generate(
        self,
        prompt: str,
        *,
        negative_prompt: str | None = None,
        aspect_ratio: str = "1:1",
        quality: str = "standard",
        resolution: str = "standard",
        background: str = "opaque",
        model: str | None = None,
        reference_images: Sequence[InputImage] | None = None,
        strength: float | None = None,
        mask: InputImage | None = None,
        progress_callback: ProgressCallback | None = None,  # noqa: ARG002
    ) -> ImageResult:
        """Generate an image using the Gemini generateContent API.

        Args:
            prompt: Positive text prompt.
            negative_prompt: Appended as ``"\\n\\nAvoid: {negative_prompt}"``
                (Gemini has no native negative prompt support).
            aspect_ratio: One of the supported ratios (14 total).
            quality: ``"standard"`` uses minimal settings (no thinking).
                ``"hd"`` on thinking-capable models enables
                thinking_level=High and text+image response modalities
                for improved composition. Independent of ``resolution`` --
                quality no longer controls output size.
            resolution: One of ``"standard"``/``"high"``/``"max"``, mapped to
                the Gemini ``image_size`` values 1K/2K/4K. Independent of
                ``quality``. Validated against the shared vocabulary at the
                MCP tool boundary (see :class:`ImageProvider`); this provider
                treats it as valid-by-contract and clamps to the model's best
                available tier when the requested tier exceeds what the
                model supports (logged as ``resolution_clamped``). The
                delivered tier is reported back in
                ``provider_metadata["resolution"]``.
            background: Ignored — Gemini does not support transparent backgrounds.
            model: Override the default model for this call.
            reference_images: Optional list of reference images for
                image-to-image editing and multi-image composition. The
                per-model cap is reported as ``max_input_images`` in
                ``list_providers``; passing more raises ``TooManyInputImages``.
                When provided, the image bytes are sent as inline image parts
                alongside the prompt for guided generation.
            strength: Ignored — Gemini does not support denoising strength.
            mask: Not supported — Gemini does not support inpainting masks.
                Raises :class:`ImageProviderError` when supplied.
            progress_callback: Ignored — Gemini does not report progress.

        Returns:
            ImageResult with PNG image data.

        Raises:
            ImageProviderError: If generation fails or returns no image.
            ImageContentPolicyError: If the prompt violates content policy.
            ImageProviderConnectionError: If the Gemini API is unreachable.
            TooManyInputImages: If more reference images than the model's cap
                are supplied.
        """
        # Reject unsupported masks before importing the SDK, so the guard is
        # reachable even if google-genai is missing.
        if mask is not None:
            raise ImageProviderError("gemini", "mask is not supported by this provider")

        from google.genai import types

        if strength is not None:
            logger.debug("strength_ignored provider=gemini reason=unsupported")

        if aspect_ratio not in _ASPECT_RATIOS:
            raise ImageProviderError(
                "gemini",
                f"Unsupported aspect_ratio: {aspect_ratio!r}. "
                f"Supported: {sorted(_ASPECT_RATIOS)}",
            )

        effective_model = model or self._model

        model_resolutions, _ = _resolution_capabilities(effective_model)
        effective_resolution = resolution
        if resolution not in model_resolutions:
            # Clamp to the model's best available tier rather than rejecting,
            # matching the "all providers, graceful no-op elsewhere" decision.
            effective_resolution = max(
                model_resolutions, key=list(_RESOLUTION_TO_IMAGE_SIZE).index
            )
            logger.warning(
                "resolution_clamped provider=%s model=%s requested=%s effective=%s",
                "gemini",
                effective_model,
                resolution,
                effective_resolution,
            )

        max_refs = _max_input_images(effective_model)
        if reference_images and len(reference_images) > max_refs:
            raise TooManyInputImages(
                "gemini", effective_model, max_refs, len(reference_images)
            )

        full_prompt = prompt
        if negative_prompt:
            full_prompt = f"{prompt}\n\nAvoid: {negative_prompt}"

        if background == "transparent":
            logger.debug(
                "Gemini does not support transparent backgrounds; "
                "background parameter ignored"
            )

        is_hd = quality == "hd"
        use_thinking = is_hd and effective_model in _THINKING_MODELS

        thinking_config = (
            types.ThinkingConfig(thinking_level=types.ThinkingLevel.HIGH)
            if use_thinking
            else None
        )

        config = types.GenerateContentConfig(
            response_modalities=["TEXT", "IMAGE"] if use_thinking else ["IMAGE"],
            image_config=types.ImageConfig(
                aspect_ratio=_ASPECT_RATIOS[aspect_ratio],
                image_size=_RESOLUTION_TO_IMAGE_SIZE[effective_resolution],
            ),
            thinking_config=thinking_config,
        )

        # google-genai normalizes a single-element [str] identically to a bare
        # str, so always using a list (even with no reference images) keeps one
        # code path without changing text-to-image behavior.
        contents: list[Any] = [full_prompt]
        for ref in reference_images or []:
            contents.append(
                types.Part.from_bytes(data=ref.data, mime_type=ref.content_type)
            )

        try:
            response = await self._client.aio.models.generate_content(
                model=effective_model,
                contents=contents,
                config=config,
            )
        except Exception as exc:
            self._handle_error(exc)

        for part in response.parts or []:
            if part.inline_data is not None:
                data = part.inline_data.data
                if isinstance(data, bytes):
                    return ImageResult(
                        image_data=data,
                        content_type=part.inline_data.mime_type or "image/png",
                        provider_metadata={
                            "model": effective_model,
                            "quality": quality,
                            "aspect_ratio": aspect_ratio,
                            "resolution": effective_resolution,
                        },
                    )

        raise ImageProviderError("gemini", "No image in response")

    async def discover_capabilities(self) -> ProviderCapabilities:
        """Return capabilities for known Gemini image-generation models.

        Uses a static known model list rather than calling models.list(),
        which does not reliably filter image-capable models.

        Returns:
            ProviderCapabilities with the known Gemini image models.
        """
        discovered_at = time.time()
        try:
            models = tuple(
                self._build_model_capabilities(model_id, display_name)
                for model_id, display_name in _KNOWN_IMAGE_MODELS
            )
            return ProviderCapabilities(
                provider_name="gemini",
                models=models,
                discovered_at=discovered_at,
                degraded=False,
            )
        except Exception:
            logger.exception("Gemini capability discovery failed")
            return make_degraded("gemini", discovered_at)

    def _build_model_capabilities(
        self, model_id: str, display_name: str
    ) -> ModelCapabilities:
        """Build the :class:`ModelCapabilities` entry for one known model.

        Args:
            model_id: Model identifier (e.g. ``"gemini-3-pro-image"``).
            display_name: Human-readable display name.

        Returns:
            ModelCapabilities describing this model's supported ratios,
            qualities, resolution tiers, and other generation limits.
        """
        supported_resolutions, max_resolution = _resolution_capabilities(model_id)
        return ModelCapabilities(
            model_id=model_id,
            display_name=display_name,
            can_generate=True,
            can_edit=False,
            supported_aspect_ratios=_SUPPORTED_ASPECT_RATIOS,
            supported_qualities=_SUPPORTED_QUALITIES,
            supported_resolutions=supported_resolutions,
            supported_formats=("image/png",),
            supports_negative_prompt=False,
            supports_background=False,
            supports_image_input=True,
            max_input_images=_max_input_images(model_id),
            max_resolution=max_resolution,
            prompt_style="natural_language",
            style_profile=resolve_style("gemini", model_id),
            # SynthID watermark: see docs/providers/gemini.md.
            watermark="synthid",
        )

    def _handle_error(self, exc: Exception) -> NoReturn:
        """Convert exceptions to ImageProviderError subtypes.

        Args:
            exc: Exception raised by the Gemini API client.

        Raises:
            ImageContentPolicyError: For content policy / safety violations.
            ImageProviderConnectionError: For network / timeout errors.
            ImageProviderError: For all other failures.
        """
        import httpx

        exc_str = str(exc).lower()
        if any(kw in exc_str for kw in ("safety", "policy", "blocked", "harm")):
            raise ImageContentPolicyError("gemini", str(exc)) from exc
        # httpx is a direct dependency — check concrete types first.
        # Then fall back to a name-based check to catch google-genai transport
        # errors (e.g. google.api_core.exceptions.ServiceUnavailable) without
        # importing google packages at the top level.
        if isinstance(exc, (httpx.ConnectError, httpx.TimeoutException)):
            raise ImageProviderConnectionError("gemini", str(exc)) from exc
        exc_type = type(exc).__name__.lower()
        if "connection" in exc_type or "timeout" in exc_type:
            raise ImageProviderConnectionError("gemini", str(exc)) from exc

        raise ImageProviderError("gemini", str(exc)) from exc


# Per-model resolution ceiling. Only Gemini 3 Pro Image and Gemini 3.1 Flash
# Image support the full 1K/2K/4K range (ai.google.dev/gemini-api/docs/
# image-generation attributes multi-resolution output to the Gemini 3 image
# family). gemini-3.1-flash-lite-image and gemini-2.5-flash-image are 1K-only.
# Unknown/future models fall back to standard-only (fail closed), matching this
# file's conservative _DEFAULT_MAX_INPUT_IMAGES stance for undocumented models;
# a new 4K-capable model is added here explicitly when it ships.
# [unverified] 1024/3840 are the conventional 1K/4K long-edge pixel figures;
# ai.google.dev names the tiers without publishing per-tier pixel dimensions.
_FULL_RANGE_RESOLUTIONS: tuple[str, ...] = ("standard", "high", "max")
_RESOLUTION_CAPS_BY_MODEL: dict[str, tuple[tuple[str, ...], int]] = {
    "gemini-3.1-flash-image": (_FULL_RANGE_RESOLUTIONS, 3840),
    "gemini-3-pro-image": (_FULL_RANGE_RESOLUTIONS, 3840),
}
_DEFAULT_RESOLUTION_CAPS: tuple[tuple[str, ...], int] = (("standard",), 1024)


def _resolution_capabilities(model: str) -> tuple[tuple[str, ...], int]:
    """Return ``(supported_resolutions, max_resolution)`` for a Gemini model.

    Unknown models fail closed to standard-only.
    """
    return _RESOLUTION_CAPS_BY_MODEL.get(model, _DEFAULT_RESOLUTION_CAPS)
