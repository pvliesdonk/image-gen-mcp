"""OpenAI image generation provider.

Supports the ``gpt-image-*`` family (``gpt-image-2`` current flagship,
``gpt-image-1.5`` previous-generation flagship — the right pick for
transparent backgrounds since gpt-image-2 dropped alpha support;
``gpt-image-1-mini`` cheaper current variant; ``gpt-image-1`` legacy;
``chatgpt-image-latest`` floating alias to the newest ChatGPT image model)
and ``dall-e-3`` (deprecated, API removal scheduled 2026-05-12) plus
``dall-e-2`` (legacy; this server does not route edits or masks to it).
Lifecycle metadata flows through ``providers.model_styles.MODEL_STYLES`` into
``list_providers``.
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
    ImageInputUnsupported,
    ImageProviderConnectionError,
    ImageProviderError,
    ImageResult,
    InputImage,
    ProgressCallback,
    TooManyInputImages,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

_GPT_IMAGE_SIZES: dict[str, str] = {
    "1:1": "1024x1024",
    "16:9": "1536x1024",
    "9:16": "1024x1536",
    "3:2": "1536x1024",
    "2:3": "1024x1536",
}

_DALLE3_SIZES: dict[str, str] = {
    "1:1": "1024x1024",
    "16:9": "1792x1024",
    "9:16": "1024x1792",
    "3:2": "1792x1024",
    "2:3": "1024x1792",
}

_FORMAT_TO_CONTENT_TYPE: dict[str, str] = {
    "png": "image/png",
    "jpeg": "image/jpeg",
    "webp": "image/webp",
}

_DALLE3_FORMATS: frozenset[str] = frozenset({"png"})

_KNOWN_IMAGE_MODELS: frozenset[str] = frozenset(
    {
        "gpt-image-2",
        "gpt-image-1.5",
        "gpt-image-1",
        "gpt-image-1-mini",
        "chatgpt-image-latest",
        "dall-e-3",
        "dall-e-2",
    }
)


def _is_gpt_image_model(model: str) -> bool:
    """Return True for gpt-image-* models (not dall-e).

    ``chatgpt-image-latest`` is a floating alias for the current ChatGPT image
    model, which is a member of the gpt-image family, so it routes through the
    gpt-image code path (sizes, formats, edit endpoint) rather than the DALL-E
    fallback.
    """
    return model.startswith("gpt-image") or model == "chatgpt-image-latest"


# Models in the gpt-image-* family that DON'T accept the ``background``
# API parameter. Most gpt-image-* models support transparency control;
# gpt-image-2 dropped it. ``chatgpt-image-latest`` is a floating alias whose
# target isn't guaranteed to support transparency (it currently resolves to
# gpt-image-2), so it is treated conservatively as no-background. Sending
# ``background`` to a model that doesn't accept it returns a 400. Keep in sync
# with ``supports_background`` in ``discover_capabilities()`` for the same
# model_ids.
_NO_BACKGROUND_GPT_IMAGE: frozenset[str] = frozenset(
    {"gpt-image-2", "chatgpt-image-latest"}
)

# OpenAI's images.edit endpoint accepts up to 16 reference images for the
# gpt-image family (multi-image composition). dall-e-3 has no edit endpoint;
# dall-e-2 edit is mask-only (out of scope here).
_MAX_INPUT_IMAGES: int = 16

_CONTENT_TYPE_TO_EXT: dict[str, str] = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
}


def _ext_for(content_type: str) -> str:
    """Return the filename extension for a supported input image content type.

    Raises:
        ImageProviderError: If the content type is not a supported input format.
    """
    ext = _CONTENT_TYPE_TO_EXT.get(content_type)
    if ext is None:
        supported = ", ".join(sorted(_CONTENT_TYPE_TO_EXT))
        raise ImageProviderError(
            "openai",
            f"Unsupported input image content type {content_type!r}. "
            f"Supported: {supported}",
        )
    return ext


class OpenAIImageProvider:
    """Image generation via OpenAI's Images API.

    Args:
        model: Model name (e.g. ``gpt-image-2``, ``gpt-image-1.5``, ``dall-e-3``).
        api_key: OpenAI API key.
        output_format: Image format (``png``, ``jpeg``, ``webp``).
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-image-2",
        output_format: str = "png",
    ) -> None:
        self._model = model
        self._output_format = output_format

        if output_format not in _FORMAT_TO_CONTENT_TYPE:
            supported = ", ".join(sorted(_FORMAT_TO_CONTENT_TYPE))
            raise ImageProviderError(
                "openai",
                f"Unsupported output_format '{output_format}'. Supported: {supported}",
            )

        self._is_gpt_image = _is_gpt_image_model(model)

        if not self._is_gpt_image and output_format not in _DALLE3_FORMATS:
            supported_dalle3 = ", ".join(sorted(_DALLE3_FORMATS))
            raise ImageProviderError(
                "openai",
                f"dall-e-3 does not support output_format '{output_format}'. "
                f"Supported: {supported_dalle3}",
            )

        self._client: AsyncOpenAI = self._create_client(api_key)

    def _create_client(self, api_key: str) -> AsyncOpenAI:
        """Create the AsyncOpenAI client (deferred import)."""
        try:
            from openai import AsyncOpenAI as _AsyncOpenAI
        except ImportError as e:
            raise ImageProviderError(
                "openai", "openai package not installed. Run: uv add openai"
            ) from e
        return _AsyncOpenAI(api_key=api_key)

    def _gpt_image_request(
        self,
        *,
        effective_model: str,
        prompt: str,
        negative_prompt: str | None,
        aspect_ratio: str,
        quality: str,
        background: str,
    ) -> tuple[dict[str, Any], str]:
        """Build the shared gpt-image request kwargs and resolved content type.

        Returns ``(kwargs, content_type)`` where ``kwargs`` carries prompt, n,
        size, quality, output_format and (when the model supports it)
        background — everything common to ``images.generate`` and
        ``images.edit`` for the gpt-image family. The caller adds ``model`` and,
        for edits, ``image``.

        Args:
            effective_model: The resolved model name (post-override).
            prompt: Positive text prompt.
            negative_prompt: Appended as ``"Avoid: ..."`` when non-None.
            aspect_ratio: Maps to OpenAI size parameter.
            quality: ``"standard"`` or ``"hd"``; mapped to API values.
            background: Background transparency (``opaque``, ``transparent``).

        Returns:
            Tuple of (kwargs dict, content_type string).

        Raises:
            ImageProviderError: When aspect_ratio is not supported.
        """
        size = _GPT_IMAGE_SIZES.get(aspect_ratio)
        if size is None:
            supported = ", ".join(sorted(_GPT_IMAGE_SIZES))
            raise ImageProviderError(
                "openai",
                f"Unsupported aspect_ratio '{aspect_ratio}'. Supported: {supported}",
            )
        effective_prompt = prompt
        if negative_prompt:
            effective_prompt = f"{prompt}\n\nAvoid: {negative_prompt}"
        api_quality = {"standard": "auto", "hd": "high"}.get(quality, quality)
        kwargs: dict[str, Any] = {
            "prompt": effective_prompt,
            "n": 1,
            "size": size,
            "quality": api_quality,
            "output_format": self._output_format,
        }
        if effective_model not in _NO_BACKGROUND_GPT_IMAGE:
            kwargs["background"] = background
        elif background == "transparent":
            logger.debug("background_param_skipped model=%s", effective_model)
        return kwargs, _FORMAT_TO_CONTENT_TYPE[self._output_format]

    async def generate(
        self,
        prompt: str,
        *,
        negative_prompt: str | None = None,
        aspect_ratio: str = "1:1",
        quality: str = "standard",
        resolution: str = "standard",  # noqa: ARG002
        background: str = "opaque",
        model: str | None = None,
        reference_images: Sequence[InputImage] | None = None,
        strength: float | None = None,
        mask: InputImage | None = None,
        progress_callback: ProgressCallback | None = None,  # noqa: ARG002
    ) -> ImageResult:
        """Generate an image via OpenAI Images API.

        Args:
            prompt: Positive text prompt.
            negative_prompt: Appended as ``"Avoid: ..."`` clause.
            aspect_ratio: Maps to OpenAI size parameter.
            quality: ``"standard"`` maps to ``"auto"`` for gpt-image-1
                (lets OpenAI choose). ``"hd"`` maps to ``"high"``.
            resolution: Accepted for protocol conformance; tier logic added
                in a later change.
            background: Background transparency (``opaque``, ``transparent``).
                Supported for gpt-image-1, gpt-image-1.5, and gpt-image-1-mini;
                not sent to gpt-image-2 or chatgpt-image-latest (no alpha
                support) or dall-e.
            model: Specific model to use for this call (e.g., ``"dall-e-3"``).
                Overrides the constructor model. Size table selection adjusts
                automatically.
            reference_images: For gpt-image models, triggers image-to-image
                editing / multi-image composition via ``images.edit``. Up to
                16 reference images are accepted. Raises
                :class:`ImageInputUnsupported` for non-gpt-image models
                (no edit endpoint). Raises :class:`TooManyInputImages`
                when more than 16 references are supplied.
            strength: Ignored — OpenAI does not support denoising strength.
            mask: Optional mask image for inpainting. Forwarded to
                ``images.edit`` when reference images are present. Must match
                the first reference image's size and format and carry an alpha
                channel; format/size mismatches return a 400 from OpenAI.

        Returns:
            ImageResult with generated image.

        Raises:
            ImageProviderError: On API errors.
            ImageContentPolicyError: On content policy rejection.
            ImageProviderConnectionError: On network errors.
            ImageInputUnsupported: When reference_images are supplied to a
                non-gpt-image model (dall-e or unknown).
            TooManyInputImages: When more than 16 reference_images are given.
        """
        if strength is not None:
            logger.debug("strength_ignored provider=openai reason=unsupported")

        if reference_images:
            return await self._edit(
                prompt,
                reference_images=reference_images,
                negative_prompt=negative_prompt,
                aspect_ratio=aspect_ratio,
                quality=quality,
                background=background,
                model=model,
                mask=mask,
            )
        if mask is not None:
            # A mask only applies to the img2img (edit) path; reject rather than
            # silently drop it on the text-to-image path.
            raise ImageProviderError("openai", "mask requires reference_images")
        effective_model = model or self._model
        # NOTE: any model not matching 'gpt-image*' (e.g. dall-e-2) falls back to
        # DALL-E 3 sizes/format. Unknown models will fail at the API level.
        is_gpt_image = _is_gpt_image_model(effective_model)

        if is_gpt_image:
            gpt_kwargs, content_type = self._gpt_image_request(
                effective_model=effective_model,
                prompt=prompt,
                negative_prompt=negative_prompt,
                aspect_ratio=aspect_ratio,
                quality=quality,
                background=background,
            )
            api_kwargs: dict[str, Any] = {"model": effective_model, **gpt_kwargs}
            size = gpt_kwargs["size"]
            api_quality = gpt_kwargs["quality"]
        else:
            # dall-e-3 only produces PNG; has its own size table
            sizes = _DALLE3_SIZES
            size = sizes.get(aspect_ratio)
            if size is None:
                supported = ", ".join(sorted(sizes))
                raise ImageProviderError(
                    "openai",
                    f"Unsupported aspect_ratio '{aspect_ratio}'. Supported: {supported}",
                )
            effective_prompt = prompt
            if negative_prompt:
                effective_prompt = f"{prompt}\n\nAvoid: {negative_prompt}"
            api_quality = quality
            content_type = _FORMAT_TO_CONTENT_TYPE["png"]
            api_kwargs = {
                "model": effective_model,
                "prompt": effective_prompt,
                "n": 1,
                "size": size,
                "quality": api_quality,
                "response_format": "b64_json",
            }
            logger.debug("dall-e-3 does not support background parameter, ignoring")

        logger.debug(
            "OpenAI image generation: model=%s size=%s quality=%s",
            effective_model,
            size,
            api_quality,
        )

        try:
            response = await self._client.images.generate(**api_kwargs)
        except ImageProviderError:
            raise
        except Exception as e:
            self._handle_error(e)

        if not response.data:
            raise ImageProviderError("openai", "Empty response from image API")

        image_item = response.data[0]
        b64_data = image_item.b64_json
        if not b64_data:
            raise ImageProviderError("openai", "No image data in response")

        metadata: dict[str, Any] = {
            "model": effective_model,
            "size": size,
            "quality": quality,
            "api_quality": api_quality,
        }
        revised_prompt = getattr(image_item, "revised_prompt", None)
        if revised_prompt:
            metadata["revised_prompt"] = revised_prompt

        logger.info("OpenAI image generated: model=%s size=%s", effective_model, size)

        return ImageResult.from_base64(
            b64_data,
            content_type=content_type,
            **metadata,
        )

    async def _edit(
        self,
        prompt: str,
        *,
        reference_images: Sequence[InputImage],
        negative_prompt: str | None,
        aspect_ratio: str,
        quality: str,
        background: str,
        model: str | None,
        mask: InputImage | None = None,
    ) -> ImageResult:
        """Edit/compose using OpenAI ``images.edit`` (gpt-image family only).

        Args:
            prompt: Edit description.
            reference_images: 1..16 input images (gpt-image composition).
            negative_prompt: Appended as ``"Avoid: ..."``.
            aspect_ratio: Maps to OpenAI size parameter.
            quality: ``"standard"`` or ``"hd"``; mapped to API values.
            background: Background transparency (``opaque``, ``transparent``).
            model: Override model; must be a gpt-image model.
            mask: Optional inpainting mask forwarded to ``images.edit`` as a
                file tuple. Must match the first reference image's size and
                format and carry an alpha channel; format/size mismatches are
                enforced by OpenAI and surface as 400 errors via
                :meth:`_handle_error`.

        Returns:
            ImageResult with edited image and ``edited=True`` in metadata.

        Raises:
            ImageInputUnsupported: model has no edit endpoint (dall-e-3).
            TooManyInputImages: more than 16 references supplied.
            ImageProviderError: On API errors.
            ImageContentPolicyError: On content policy rejection.
            ImageProviderConnectionError: On network errors.
        """
        effective_model = model or self._model
        if not _is_gpt_image_model(effective_model):
            raise ImageInputUnsupported("openai", effective_model)
        if len(reference_images) > _MAX_INPUT_IMAGES:
            raise TooManyInputImages(
                "openai", effective_model, _MAX_INPUT_IMAGES, len(reference_images)
            )

        kwargs, content_type = self._gpt_image_request(
            effective_model=effective_model,
            prompt=prompt,
            negative_prompt=negative_prompt,
            aspect_ratio=aspect_ratio,
            quality=quality,
            background=background,
        )
        kwargs["model"] = effective_model
        kwargs["image"] = [
            (f"reference_{i}{_ext_for(ref.content_type)}", ref.data, ref.content_type)
            for i, ref in enumerate(reference_images)
        ]
        if mask is not None:
            kwargs["mask"] = (
                f"mask{_ext_for(mask.content_type)}",
                mask.data,
                mask.content_type,
            )

        logger.debug(
            "OpenAI image edit: model=%s refs=%d mask=%s size=%s",
            effective_model,
            len(reference_images),
            mask is not None,
            kwargs["size"],
        )
        try:
            response = await self._client.images.edit(**kwargs)
        except ImageProviderError:
            raise
        except Exception as e:
            self._handle_error(e)

        if not response.data:
            raise ImageProviderError("openai", "Empty response from image edit API")
        b64_data = response.data[0].b64_json
        if not b64_data:
            raise ImageProviderError("openai", "No image data in edit response")
        logger.info(
            "OpenAI image edited: model=%s refs=%d",
            effective_model,
            len(reference_images),
        )
        return ImageResult.from_base64(
            b64_data,
            content_type=content_type,
            model=effective_model,
            size=kwargs["size"],
            quality=quality,
            api_quality=kwargs["quality"],
            edited=True,
        )

    def _handle_error(self, error: Exception) -> NoReturn:
        """Convert OpenAI exceptions to ImageProvider exceptions."""
        from openai import APIConnectionError, APIStatusError

        if isinstance(error, APIConnectionError):
            raise ImageProviderConnectionError(
                "openai", f"Connection error: {error}"
            ) from error

        if isinstance(error, APIStatusError):
            status = error.status_code
            body = getattr(error, "body", None) or {}
            code = (
                body.get("error", {}).get("code", "") if isinstance(body, dict) else ""
            )
            if status == 400 and (
                code == "content_policy_violation"
                or "content_policy" in str(error).lower()
            ):
                raise ImageContentPolicyError(
                    "openai", f"Content policy rejection: {error}"
                ) from error
            raise ImageProviderError(
                "openai", f"API error (HTTP {status}): {error}"
            ) from error

        raise ImageProviderError(
            "openai", f"Image generation failed: {error}"
        ) from error

    async def discover_capabilities(self) -> ProviderCapabilities:
        """Discover OpenAI image model capabilities via models.list().

        Calls the OpenAI models API to enumerate available models, then filters
        to known image models and maps them to :class:`ModelCapabilities` using
        hardcoded knowledge about each model's feature set.

        Returns:
            ProviderCapabilities with one entry per discovered image model.
            If the API call fails, returns a degraded ProviderCapabilities with
            an empty model list and ``degraded=True``.
        """
        discovered_at = time.time()

        try:
            response = await self._client.models.list()
            model_ids = {m.id for m in response.data if m.id in _KNOWN_IMAGE_MODELS}
        except Exception:
            logger.warning(
                "OpenAI models.list() failed; returning degraded capabilities",
                exc_info=True,
            )
            return make_degraded("openai", discovered_at)

        model_caps: list[ModelCapabilities] = []

        # OpenAI has no native negative_prompt API parameter; the provider
        # implements it by appending 'Avoid: ...' to the prompt text, so
        # supports_negative_prompt remains False at the capability level.
        if "gpt-image-1" in model_ids:
            model_caps.append(
                ModelCapabilities(
                    model_id="gpt-image-1",
                    display_name="GPT Image 1",
                    can_generate=True,
                    can_edit=True,
                    supports_mask=True,
                    supports_background=True,
                    supports_negative_prompt=False,
                    supports_image_input=True,
                    max_input_images=_MAX_INPUT_IMAGES,
                    supported_aspect_ratios=tuple(_GPT_IMAGE_SIZES),
                    supported_formats=("png", "jpeg", "webp"),
                    supported_qualities=("standard", "hd"),
                    max_resolution=1536,
                    style_profile=resolve_style("openai", "gpt-image-1"),
                )
            )

        # NOTE: capabilities for these models are assumed to match
        # gpt-image-1 — update once officially documented by OpenAI.
        for mini_model_id, mini_display in (
            ("gpt-image-1-mini", "GPT Image 1 Mini"),
            ("gpt-image-1.5", "GPT Image 1.5"),
        ):
            if mini_model_id in model_ids:
                model_caps.append(
                    ModelCapabilities(
                        model_id=mini_model_id,
                        display_name=mini_display,
                        can_generate=True,
                        can_edit=True,
                        supports_mask=True,
                        supports_background=True,
                        supports_negative_prompt=False,
                        supports_image_input=True,
                        max_input_images=_MAX_INPUT_IMAGES,
                        supported_aspect_ratios=tuple(_GPT_IMAGE_SIZES),
                        supported_formats=("png", "jpeg", "webp"),
                        supported_qualities=("standard", "hd"),
                        max_resolution=1536,
                        style_profile=resolve_style("openai", mini_model_id),
                    )
                )

        # gpt-image-2 — current OpenAI flagship (GA; the provider default) and
        # beyond gpt-image-1.5. It drops transparent-background support but
        # otherwise mirrors gpt-image-1.5's prompt grammar and supported aspect
        # ratios. We pin the conservative capability surface here; tighten
        # if/when OpenAI documents differences. Gated on `if "gpt-image-2" in
        # model_ids` like every other entry, so it only surfaces when the key's
        # models.list() returns it.
        if "gpt-image-2" in model_ids:
            model_caps.append(
                ModelCapabilities(
                    model_id="gpt-image-2",
                    display_name="GPT Image 2",
                    can_generate=True,
                    can_edit=True,
                    supports_mask=True,
                    supports_background=False,
                    supports_negative_prompt=False,
                    supports_image_input=True,
                    max_input_images=_MAX_INPUT_IMAGES,
                    supported_aspect_ratios=tuple(_GPT_IMAGE_SIZES),
                    supported_formats=("png", "jpeg", "webp"),
                    supported_qualities=("standard", "hd"),
                    max_resolution=1536,
                    style_profile=resolve_style("openai", "gpt-image-2"),
                )
            )

        # chatgpt-image-latest — floating alias for the current ChatGPT image
        # model (a gpt-image-family member). Capabilities mirror the gpt-image
        # surface, but transparency is not guaranteed (the alias currently
        # resolves to gpt-image-2, which dropped it), so supports_background is
        # False in lockstep with _NO_BACKGROUND_GPT_IMAGE.
        if "chatgpt-image-latest" in model_ids:
            model_caps.append(
                ModelCapabilities(
                    model_id="chatgpt-image-latest",
                    display_name="ChatGPT Image (latest)",
                    can_generate=True,
                    can_edit=True,
                    supports_mask=True,
                    supports_background=False,
                    supports_negative_prompt=False,
                    supports_image_input=True,
                    max_input_images=_MAX_INPUT_IMAGES,
                    supported_aspect_ratios=tuple(_GPT_IMAGE_SIZES),
                    supported_formats=("png", "jpeg", "webp"),
                    supported_qualities=("standard", "hd"),
                    max_resolution=1536,
                    style_profile=resolve_style("openai", "chatgpt-image-latest"),
                )
            )

        if "dall-e-3" in model_ids:
            model_caps.append(
                ModelCapabilities(
                    model_id="dall-e-3",
                    display_name="DALL-E 3",
                    can_generate=True,
                    can_edit=False,
                    supports_mask=False,
                    supports_background=False,
                    supports_negative_prompt=False,
                    supported_aspect_ratios=tuple(_DALLE3_SIZES),
                    supported_formats=("png",),
                    supported_qualities=("standard", "hd"),
                    max_resolution=1792,
                    style_profile=resolve_style("openai", "dall-e-3"),
                )
            )

        if "dall-e-2" in model_ids:
            model_caps.append(
                ModelCapabilities(
                    model_id="dall-e-2",
                    display_name="DALL-E 2",
                    can_generate=True,
                    can_edit=True,
                    # The server's edit/mask path is gpt-image-only, and
                    # supports_image_input defaults to False, so masks can never
                    # route here; advertise supports_mask=False to match.
                    supports_mask=False,
                    supports_background=False,
                    supports_negative_prompt=False,
                    supported_aspect_ratios=("1:1",),
                    supported_formats=("png",),
                    supported_qualities=("standard",),
                    max_resolution=1024,
                    style_profile=resolve_style("openai", "dall-e-2"),
                )
            )

        return ProviderCapabilities(
            provider_name="openai",
            models=tuple(model_caps),
            discovered_at=discovered_at,
        )
