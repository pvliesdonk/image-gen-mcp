"""Image generation provider protocol and types.

Defines the ImageProvider protocol for image generation backends,
the ImageResult value type, and the exception hierarchy.

Ported from questfoundry — PromptDistiller and ImageBrief are not
included; MCP clients write prompts directly.
"""

from __future__ import annotations

import base64
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

ProgressCallback = Callable[[float, str], None]
"""Signature for progress callbacks: ``(progress_fraction, message)``."""

if TYPE_CHECKING:
    from image_generation_mcp.providers.capabilities import ProviderCapabilities


@dataclass(frozen=True)
class ImageResult:
    """Result of an image generation call.

    Attributes:
        image_data: Raw image bytes.
        content_type: MIME type (e.g., ``image/png``).
        provider_metadata: Provider-specific metadata (model, seed, etc.).
    """

    image_data: bytes
    content_type: str = "image/png"
    provider_metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def size_bytes(self) -> int:
        """Size of image data in bytes."""
        return len(self.image_data)

    @classmethod
    def from_base64(
        cls,
        b64_data: str,
        content_type: str = "image/png",
        **metadata: Any,
    ) -> ImageResult:
        """Create from base64-encoded image data.

        Args:
            b64_data: Base64-encoded image string.
            content_type: MIME type of the image.
            **metadata: Additional provider metadata.

        Returns:
            ImageResult with decoded bytes.
        """
        return cls(
            image_data=base64.b64decode(b64_data),
            content_type=content_type,
            provider_metadata=metadata,
        )


@dataclass(frozen=True)
class InputImage:
    """A reference image supplied as input to a generation call.

    The input counterpart of :class:`ImageResult`.

    Attributes:
        data: Raw image bytes.
        content_type: MIME type (e.g., ``image/png``).
        source_id: Gallery image id when resolved from the store, else
            ``None`` (e.g. for local-file sources).
    """

    data: bytes
    content_type: str = "image/png"
    source_id: str | None = None

    @property
    def size_bytes(self) -> int:
        """Size of the image data in bytes."""
        return len(self.data)


@runtime_checkable
class ImageProvider(Protocol):
    """Protocol for image generation backends.

    All image providers must implement the ``generate`` method.
    The protocol is runtime-checkable for isinstance() validation.
    """

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
        progress_callback: ProgressCallback | None = None,
    ) -> ImageResult:
        """Generate an image from a text prompt.

        Args:
            prompt: Positive text prompt describing the desired image.
            negative_prompt: Things to avoid (provider support varies).
            aspect_ratio: Desired aspect ratio (e.g., ``16:9``, ``1:1``).
            quality: Quality level (``standard``, ``hd``).
            resolution: Output size tier -- ``"standard"``, ``"high"``, or
                ``"max"``. Independent of ``quality``. Like ``quality`` and
                ``background``, the tier is validated against the shared
                :data:`SUPPORTED_RESOLUTIONS` vocabulary once at the MCP
                tool boundary; providers receive it as valid-by-contract and
                never re-validate it themselves. A model that cannot honor
                the requested tier clamps to its best available tier (or
                no-ops for providers with no higher tier) rather than
                raising. See :attr:`ModelCapabilities.supported_resolutions`.
            background: Background transparency (``opaque``, ``transparent``).
                Only supported by some providers.
            model: Specific model to use (e.g., a checkpoint name for SD WebUI,
                or ``"dall-e-3"`` for OpenAI). Overrides the provider's
                configured default for this call.
            reference_images: Optional input images for image-to-image edits
                or composition. Providers that do not support image input
                raise :class:`ImageInputUnsupported` when this is non-empty.
            strength: Denoising strength (0.0-1.0) for image-to-image. Only
                SD WebUI uses it (as ``denoising_strength``); other providers
                ignore it. Has no effect without ``reference_images``.
            mask: Optional mask image for inpainting. Only OpenAI gpt-image
                models support it; other providers raise
                :class:`ImageProviderError`. Applies to the first reference
                image.
            progress_callback: Optional callback invoked with
                ``(fraction, message)`` during generation.  Only supported
                by SD WebUI; other providers ignore this parameter.

        Returns:
            ImageResult with generated image data.

        Raises:
            ImageProviderError: If generation fails.
        """
        ...

    async def discover_capabilities(self) -> ProviderCapabilities:
        """Discover this provider's capabilities at startup.

        Called once during server lifespan after provider construction.
        Results are cached for the server lifetime.

        Returns:
            ProviderCapabilities describing models and features.

        Raises:
            Exception: Any error during discovery (caller handles gracefully).
        """
        ...


SUPPORTED_ASPECT_RATIOS: tuple[str, ...] = ("1:1", "16:9", "9:16", "3:2", "2:3")
"""Aspect ratios supported across providers."""

SUPPORTED_QUALITY_LEVELS: tuple[str, ...] = ("standard", "hd")
"""Quality levels supported across providers."""

SUPPORTED_RESOLUTIONS: tuple[str, ...] = ("standard", "high", "max")
"""Resolution tiers accepted as input across providers. ``standard`` is each
provider's existing default size; ``high``/``max`` unlock higher tiers where a
model supports them (Gemini 2K/4K; OpenAI gpt-image-2's larger sizes) and are a
no-op elsewhere. This is the input-*validation* vocabulary; for which specific
models honor ``high``/``max`` see
:attr:`~image_generation_mcp.providers.capabilities.ModelCapabilities.supported_resolutions`."""

SUPPORTED_BACKGROUNDS: tuple[str, ...] = ("opaque", "transparent")
"""Background transparency modes supported across providers."""


class ImageProviderError(Exception):
    """Base exception for image provider errors."""

    def __init__(self, provider: str, message: str) -> None:
        self.provider = provider
        super().__init__(f"[{provider}] {message}")


class ImageContentPolicyError(ImageProviderError):
    """Raised when image generation is rejected by content policy."""


class ImageProviderConnectionError(ImageProviderError):
    """Raised when the image provider is unreachable."""


class ImageInputUnsupported(ImageProviderError):
    """Raised when a provider/model cannot accept reference images."""

    def __init__(self, provider: str, model: str | None = None) -> None:
        target = f" model {model!r}" if model else ""
        super().__init__(
            provider,
            f"does not support reference-image input{target}. "
            "Use a model that reports supports_image_input — see list_providers.",
        )


class TooManyInputImages(ImageProviderError):
    """Raised when more reference images are supplied than a model accepts."""

    def __init__(
        self, provider: str, model: str | None, max_input_images: int, given: int
    ) -> None:
        subject = f"Model {model!r}" if model else "This model"
        super().__init__(
            provider,
            f"{subject} accepts at most {max_input_images} reference image(s); "
            f"{given} were given.",
        )
