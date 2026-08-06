"""Placeholder image provider for testing.

Generates minimal solid-color PNG images with no external dependencies.
Zero cost, instant generation — ideal for development and CI.

Ported from questfoundry.
"""

from __future__ import annotations

import hashlib
import logging
import struct
import time
import zlib
from typing import TYPE_CHECKING

from image_generation_mcp.providers.capabilities import (
    ModelCapabilities,
    ProviderCapabilities,
)
from image_generation_mcp.providers.model_styles import resolve_style
from image_generation_mcp.providers.types import (
    ImageInputUnsupported,
    ImageProviderError,
    ImageResult,
    InputImage,
    ProgressCallback,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

logger = logging.getLogger(__name__)

_ASPECT_RATIO_TO_SIZE: dict[str, tuple[int, int]] = {
    "1:1": (256, 256),
    "16:9": (640, 360),
    "9:16": (360, 640),
    "3:2": (480, 320),
    "2:3": (320, 480),
}

_PALETTE: list[tuple[int, int, int]] = [
    (88, 101, 130),  # slate blue
    (130, 88, 101),  # dusty rose
    (101, 130, 88),  # sage green
    (130, 118, 88),  # warm sand
    (88, 130, 125),  # teal
    (118, 88, 130),  # muted purple
]


def _make_png(
    width: int, height: int, r: int, g: int, b: int, *, alpha: int = 255
) -> bytes:
    """Generate a minimal solid-color PNG in pure Python.

    Args:
        width: Image width in pixels.
        height: Image height in pixels.
        r: Red channel (0-255).
        g: Green channel (0-255).
        b: Blue channel (0-255).
        alpha: Alpha channel (0-255). Values below 255 use RGBA color type 6.

    Returns:
        Raw PNG bytes.
    """

    def _chunk(chunk_type: bytes, data: bytes) -> bytes:
        payload = chunk_type + data
        crc = struct.pack(">I", zlib.crc32(payload) & 0xFFFFFFFF)
        return struct.pack(">I", len(data)) + payload + crc

    sig = b"\x89PNG\r\n\x1a\n"

    if alpha < 255:
        # Color type 6 = RGBA (4 bytes per pixel)
        ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
        ihdr = _chunk(b"IHDR", ihdr_data)
        row = bytes([0]) + bytes([r, g, b, alpha]) * width
    else:
        # Color type 2 = RGB (3 bytes per pixel)
        ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
        ihdr = _chunk(b"IHDR", ihdr_data)
        row = bytes([0]) + bytes([r, g, b]) * width

    raw_data = row * height
    compressed = zlib.compress(raw_data)
    idat = _chunk(b"IDAT", compressed)

    iend = _chunk(b"IEND", b"")
    return sig + ihdr + idat + iend


class PlaceholderImageProvider:
    """Zero-cost image provider that generates solid-color PNGs.

    Each call produces a minimal PNG with a color selected from a
    rotating palette (based on prompt hash).
    """

    async def generate(
        self,
        prompt: str,
        *,
        negative_prompt: str | None = None,  # noqa: ARG002
        aspect_ratio: str = "1:1",
        quality: str = "standard",  # noqa: ARG002
        resolution: str = "standard",
        background: str = "opaque",
        model: str | None = None,
        reference_images: Sequence[InputImage] | None = None,
        strength: float | None = None,
        mask: InputImage | None = None,
        progress_callback: ProgressCallback | None = None,  # noqa: ARG002
    ) -> ImageResult:
        """Generate a placeholder PNG.

        Args:
            prompt: Text prompt (used only for color selection).
            negative_prompt: Ignored.
            aspect_ratio: Determines image dimensions.
            quality: Ignored.
            resolution: Ignored. This provider offers no higher-resolution
                tier; it always renders at its normal aspect-ratio-determined
                size and reports ``"resolution": "standard"`` in provider
                metadata regardless of the requested tier.
            background: When ``"transparent"``, generates an RGBA PNG with
                alpha=0. When ``"opaque"`` (default), generates an RGB PNG.
            model: Ignored by the placeholder provider.
            reference_images: Not supported by this provider. Raises
                :class:`ImageInputUnsupported` when non-empty.
            strength: Ignored by the placeholder provider.
            mask: Not supported by this provider. Raises
                :class:`ImageProviderError` when supplied.

        Returns:
            ImageResult with a solid-color PNG.

        Raises:
            ImageInputUnsupported: When reference_images are supplied.
            ImageProviderError: When mask is supplied.
        """
        if mask is not None:
            raise ImageProviderError(
                "placeholder", "mask is not supported by this provider"
            )
        if reference_images:
            raise ImageInputUnsupported("placeholder", model)
        if strength is not None:
            logger.debug("strength_ignored provider=placeholder reason=unsupported")
        if resolution != "standard":
            # Intentionally DEBUG, not the real providers' WARNING
            # resolution_clamped: placeholder is a zero-cost test provider, so
            # an ignored tier is an internal detail, not an operator-facing
            # degradation.
            logger.debug("resolution_ignored provider=placeholder reason=unsupported")
        if model is not None:
            logger.debug("Placeholder provider ignores model parameter: %r", model)
        if aspect_ratio not in _ASPECT_RATIO_TO_SIZE:
            logger.warning("Unknown aspect_ratio %r, falling back to 1:1", aspect_ratio)
        width, height = _ASPECT_RATIO_TO_SIZE.get(
            aspect_ratio, _ASPECT_RATIO_TO_SIZE["1:1"]
        )

        idx = int(hashlib.sha256(prompt.encode()).hexdigest(), 16) % len(_PALETTE)
        r, g, b = _PALETTE[idx]

        alpha = 0 if background == "transparent" else 255
        image_data = _make_png(width, height, r, g, b, alpha=alpha)

        return ImageResult(
            image_data=image_data,
            content_type="image/png",
            provider_metadata={
                "quality": "placeholder",
                "size": f"{width}x{height}",
                "color": f"#{r:02x}{g:02x}{b:02x}",
                # Always-delivered tier: the placeholder has no higher tier,
                # so it reports "standard" regardless of the requested
                # resolution to keep the delivered-tier contract truthful.
                "resolution": "standard",
            },
        )

    async def discover_capabilities(self) -> ProviderCapabilities:
        """Return static capabilities for the placeholder provider.

        Returns:
            ProviderCapabilities with one model and fixed feature set.
        """
        model = ModelCapabilities(
            model_id="placeholder",
            display_name="Placeholder (solid-color PNG)",
            can_generate=True,
            can_edit=False,
            supports_mask=False,
            supported_aspect_ratios=tuple(_ASPECT_RATIO_TO_SIZE),
            supported_qualities=("standard",),
            supported_formats=("png",),
            supports_negative_prompt=False,
            supports_background=True,
            max_resolution=640,
            style_profile=resolve_style("placeholder", "placeholder"),
        )
        return ProviderCapabilities(
            provider_name="placeholder",
            models=(model,),
            discovered_at=time.time(),
        )
