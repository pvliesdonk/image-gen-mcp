"""Image generation service -- orchestrates providers and scratch storage.

The ``ImageService`` is the DI service object injected into MCP tools.
It holds registered providers, dispatches generation requests, manages
an in-memory image registry backed by sidecar JSON files, and saves
generated images to the scratch directory.
"""

from __future__ import annotations

import hashlib
import io
import json
import logging
import tempfile
import time
import uuid
from collections import OrderedDict
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, ClassVar, Literal, TypeAlias

from PIL import Image as PILImage

from image_generation_mcp._input_images import validate_image_bytes
from image_generation_mcp.processing import (
    convert_format,
    crop_region,
    crop_to_dimensions,
    flip_image,
    resize_image,
    rotate_image,
)
from image_generation_mcp.providers.capabilities import (
    ProviderCapabilities,
    make_degraded,
)
from image_generation_mcp.providers.types import (
    ImageProvider,
    ImageProviderError,
    ImageResult,
    InputImage,
    ProgressCallback,
)
from image_generation_mcp.styles import StyleEntry, scan_styles

logger = logging.getLogger(__name__)


ImageOrigin: TypeAlias = Literal["generated", "imported"]
"""How an image entered the gallery: produced by a provider, or imported.

Stored explicitly on :class:`ImageRecord` (not derived from ``origin_source``)
so the provenance discriminator is an explicit, serialized sidecar field and
stays stable if a future origin kind is added that is not source-derived.
"""


def _origin_pair(
    raw_origin: str | None, raw_source: str | None
) -> tuple[ImageOrigin, str | None]:
    """Canonical ``(origin, origin_source)`` pair — the single coupling rule.

    A record is ``"imported"`` only when it is **both** labeled
    ``origin="imported"`` **and** carries a truthy ``origin_source`` (its
    provenance); every other combination — including a stray source on a
    ``"generated"`` record — canonicalizes to ``("generated", None)``. Both
    conditions are load-bearing: dropping the ``raw_origin`` guard would flip a
    generated record that picked up a stray source to ``"imported"`` on reload.

    This is the one definition of the coupling, used both to validate at
    construction (:meth:`ImageRecord.__post_init__`) and to coerce persisted
    sidecar data on reload, so the two sites can never drift.
    """
    if raw_origin == "imported" and raw_source:
        return "imported", raw_source
    return "generated", None


@dataclass(frozen=True)
class ImageRecord:
    """Metadata for a registered image in the scratch directory.

    Invariant: ``origin`` and ``origin_source`` are a coupled pair —
    ``origin="imported"`` carries a (truthy) ``origin_source`` (its
    provenance), and ``origin="generated"`` carries ``origin_source=None``.
    See :func:`_origin_pair`.
    """

    id: str
    original_path: Path
    content_type: str
    provider: str
    prompt: str
    negative_prompt: str | None
    aspect_ratio: str
    quality: str
    resolution: str
    original_dimensions: tuple[int, int]
    provider_metadata: dict[
        str, Any
    ]  # treat as read-only; frozen prevents reassignment
    created_at: float
    source_image_ids: list[str] = field(default_factory=list)
    origin: ImageOrigin = "generated"
    origin_source: str | None = None

    def __post_init__(self) -> None:
        """Enforce the origin/origin_source pairing invariant.

        A record is consistent iff its pair equals its own canonical form
        (see :func:`_origin_pair`).
        """
        if (self.origin, self.origin_source) != _origin_pair(
            self.origin, self.origin_source
        ):
            raise ValueError(
                f"origin={self.origin!r} inconsistent with "
                f"origin_source={self.origin_source!r}"
            )


@dataclass(frozen=True)
class _PersistMeta:
    """Metadata bundle for :meth:`ImageService._persist_image`.

    Groups the domain fields shared by generated and imported images so the
    persist helper stays under the parameter ceiling.
    """

    content_type: str
    provider: str
    prompt: str
    negative_prompt: str | None
    aspect_ratio: str
    quality: str
    resolution: str
    background: str  # persisted to the sidecar only; not a field on ImageRecord
    provider_metadata: dict[str, Any]
    source_image_ids: list[str]
    origin: ImageOrigin
    origin_source: str | None


_PENDING_TTL_S = 600  # 10 minutes — clean up stale pending entries

# Cache key: (image_id, format, width, height, quality, crop_x, crop_y, crop_w, crop_h, rotate, flip)
_TransformCacheKey: TypeAlias = tuple[
    str, str, int, int, int, int, int, int, int, int, str
]


@dataclass
class PendingGeneration:
    """Tracks an in-progress or recently completed background generation.

    Mutable: ``status``, ``error``, ``completed_at``, ``progress``, and
    ``progress_message`` are updated as the background task progresses.
    """

    id: str
    prompt: str
    provider: str
    negative_prompt: str | None = None
    aspect_ratio: str = "1:1"
    quality: str = "standard"
    resolution: str = "standard"
    background: str = "opaque"
    model: str | None = None
    status: str = "generating"  # "generating", "completed", "failed"
    error: str | None = None
    created_at: float = field(default_factory=time.time)
    completed_at: float | None = None
    progress: float = 0.0
    progress_message: str = ""


class ImageService:
    """Central orchestrator for image generation.

    Args:
        scratch_dir: Directory for saving generated images.
        default_provider: Provider name to use when none specified.
        transform_cache_size: Maximum number of transform results to keep
            in the in-memory LRU cache. Set to 0 to disable caching.
    """

    def __init__(
        self,
        scratch_dir: Path,
        default_provider: str = "auto",
        transform_cache_size: int = 64,
    ) -> None:
        self._providers: dict[str, ImageProvider] = {}
        self._capabilities: dict[str, ProviderCapabilities] = {}
        self._scratch_dir = scratch_dir
        self._default_provider = default_provider
        # NOTE: register_image is called via asyncio.to_thread (cross-thread
        # mutation). Safe under CPython GIL; revisit if moving to free-threading.
        self._images: dict[str, ImageRecord] = {}
        # NOTE: OrderedDict is not thread-safe in general, but CPython's GIL
        # serialises individual dict operations. Methods that touch this cache
        # (get_transformed_image, delete_image) are called via asyncio.to_thread,
        # so concurrent mutations are possible, but each individual op is atomic
        # under the GIL. Safe under CPython; revisit if moving to free-threading.
        self._transform_cache: OrderedDict[_TransformCacheKey, tuple[bytes, str]] = (
            OrderedDict()
        )
        self._transform_cache_size = transform_cache_size
        self._pending: dict[str, PendingGeneration] = {}
        self._styles: dict[str, StyleEntry] = {}

        # Rebuild registry from existing sidecar files
        self._load_registry()

    @property
    def scratch_dir(self) -> Path:
        """The scratch directory for saved images."""
        return self._scratch_dir

    @property
    def providers(self) -> dict[str, ImageProvider]:
        """Registered providers (read-only view)."""
        return self._providers

    # --- Style library ---------------------------------------------------

    def load_styles(self, styles_dir: Path) -> None:
        """Scan a directory for style files and populate the in-memory dict.

        Args:
            styles_dir: Path to the styles directory.
        """
        self._styles = scan_styles(styles_dir)

    def get_style(self, name: str) -> StyleEntry | None:
        """Return a style by name, or ``None`` if not found.

        Args:
            name: Style identifier.
        """
        return self._styles.get(name)

    def list_styles(self) -> list[StyleEntry]:
        """Return all styles sorted by name.

        Returns:
            List of :class:`StyleEntry` instances, sorted alphabetically.
        """
        return sorted(self._styles.values(), key=lambda s: s.name)

    def save_style(
        self,
        name: str,
        body: str,
        styles_dir: Path,
        *,
        tags: list[str] | None = None,
        provider: str | None = None,
        aspect_ratio: str | None = None,
        quality: str | None = None,
    ) -> StyleEntry:
        """Write a style file to disk and update the in-memory dict.

        Uses an atomic write pattern: write to a temp file then rename.

        Args:
            name: Style identifier (used as filename ``{name}.md``).
            body: Markdown prose — the creative brief.
            styles_dir: Directory to write the style file into.
            tags: Optional categorization tags.
            provider: Optional suggested provider.
            aspect_ratio: Optional default aspect ratio.
            quality: Optional default quality level.

        Returns:
            The newly created :class:`StyleEntry`.
        """
        styles_dir.mkdir(parents=True, exist_ok=True)
        file_path = styles_dir / f"{name}.md"

        # Build YAML frontmatter
        lines = ["---"]
        lines.append(f"name: {name}")
        if tags:
            tag_items = ", ".join(f'"{t}"' for t in tags)
            lines.append(f"tags: [{tag_items}]")
        if provider:
            lines.append(f"provider: {provider}")
        if aspect_ratio:
            lines.append(f'aspect_ratio: "{aspect_ratio}"')
        if quality:
            lines.append(f"quality: {quality}")
        lines.append("---")
        lines.append("")
        lines.append(body)

        content = "\n".join(lines) + "\n"

        # Atomic write: temp file in same dir, then rename
        fd, tmp_path = tempfile.mkstemp(
            dir=styles_dir, suffix=".tmp", prefix=f".{name}_"
        )
        try:
            with open(fd, "w", encoding="utf-8") as f:  # noqa: PTH123 — fd not a path
                f.write(content)
            Path(tmp_path).replace(file_path)
        except BaseException:
            Path(tmp_path).unlink(missing_ok=True)
            raise

        entry = StyleEntry(
            name=name,
            tags=tuple(tags) if tags else (),
            provider=provider,
            aspect_ratio=aspect_ratio,
            quality=quality,
            body=body.strip(),
            file_path=file_path.resolve(),
        )
        self._styles[name] = entry
        logger.info("Saved style '%s' to %s", name, file_path)
        return entry

    def delete_style(self, name: str) -> None:
        """Delete a style file from disk and remove from in-memory dict.

        Args:
            name: Style identifier.

        Raises:
            KeyError: If the style is not found.
        """
        entry = self._styles.get(name)
        if entry is None:
            msg = f"Style not found: {name!r}"
            raise KeyError(msg)

        entry.file_path.unlink(missing_ok=True)
        del self._styles[name]
        logger.info("Deleted style '%s'", name)

    async def aclose(self) -> None:
        """Close all providers that support async cleanup."""
        for provider in self._providers.values():
            if hasattr(provider, "aclose"):
                await provider.aclose()
        self._transform_cache.clear()

    @property
    def capabilities(self) -> dict[str, ProviderCapabilities]:
        """Discovered provider capabilities."""
        return self._capabilities

    def register_provider(self, name: str, provider: ImageProvider) -> None:
        """Register an image provider.

        Args:
            name: Provider name (e.g., ``"openai"``, ``"placeholder"``).
            provider: Provider instance implementing ``ImageProvider``.
        """
        self._providers[name] = provider
        logger.info("Registered image provider: %s", name)

    async def discover_all_capabilities(self) -> None:
        """Discover capabilities for all registered providers.

        Calls ``discover_capabilities()`` on each provider. If a provider
        raises an exception, it is registered with ``degraded=True`` and
        an empty model list — server startup is not blocked.
        """
        for name, provider in self._providers.items():
            try:
                caps = await provider.discover_capabilities()
                self._capabilities[name] = caps
                model_count = len(caps.models)
                logger.info(
                    "Discovered capabilities for %s: %d model(s)%s",
                    name,
                    model_count,
                    " (degraded)" if caps.degraded else "",
                )
            except Exception:
                logger.warning(
                    "Capability discovery failed for %s — marking degraded",
                    name,
                    exc_info=True,
                )
                self._capabilities[name] = make_degraded(name, time.time())

    _PROVIDER_DESCRIPTIONS: ClassVar[dict[str, str]] = {
        "openai": (
            "OpenAI (gpt-image-2 / dall-e-3) — best for text, logos, "
            "and general-purpose generation"
        ),
        "sd_webui": (
            "Stable Diffusion via SD WebUI (A1111/Forge) — best for "
            "photorealism, portraits, and artistic styles"
        ),
        "placeholder": (
            "Zero-cost solid-color PNG — instant, no API key, for testing and drafts"
        ),
    }

    def list_providers(self) -> dict[str, dict[str, Any]]:
        """List registered providers with availability and capability info.

        Returns:
            Dict of provider name -> ``{available, description, capabilities}``.
            The ``capabilities`` key is present only after discovery has run.
        """
        result: dict[str, dict[str, Any]] = {}
        for name in self._providers:
            entry: dict[str, Any] = {
                "available": True,
                "description": self._PROVIDER_DESCRIPTIONS.get(name, name),
            }
            if name in self._capabilities:
                entry["capabilities"] = self._capabilities[name].to_dict()
            result[name] = entry
        return result

    def resolve_provider_name(
        self,
        provider: str,
        prompt: str,
        *,
        background: str = "opaque",
    ) -> str:
        """Resolve a provider name without instantiating the provider.

        Useful for pre-generation checks (e.g., cost confirmation) that
        need to know which provider will be used before calling
        :meth:`generate`.

        Args:
            provider: Provider name or ``"auto"``.
            prompt: The generation prompt (used for auto-selection).
            background: Requested background mode (used for capability filtering).

        Returns:
            The resolved provider name string.

        Raises:
            ImageProviderError: If no matching provider is available.
        """
        name, _ = self._resolve_provider(
            provider or self._default_provider, prompt, background=background
        )
        return name

    def _resolve_provider(
        self,
        provider: str,
        prompt: str,
        *,
        background: str = "opaque",
    ) -> tuple[str, ImageProvider]:
        """Resolve a provider name to an instance.

        Args:
            provider: Provider name or ``"auto"``.
            prompt: The generation prompt (used for auto-selection).
            background: Requested background mode (used for capability filtering).

        Returns:
            Tuple of (resolved_name, provider_instance).

        Raises:
            ImageProviderError: If no matching provider is available.
        """
        if not self._providers:
            raise ImageProviderError(
                provider,
                "No providers are registered. Configure at least one: "
                "set IMAGE_GENERATION_MCP_OPENAI_API_KEY for OpenAI, "
                "IMAGE_GENERATION_MCP_SD_WEBUI_HOST for Stable Diffusion, "
                "or the placeholder provider is always available.",
            )

        if provider == "auto":
            from image_generation_mcp.providers.selector import select_provider

            selected = select_provider(
                prompt,
                set(self._providers),
                capabilities=self._capabilities or None,
                background=background,
            )
            return selected, self._providers[selected]

        if provider not in self._providers:
            available = ", ".join(self._providers)
            raise ImageProviderError(
                provider,
                f"Provider '{provider}' not available. Available: {available}",
            )
        return provider, self._providers[provider]

    async def generate(
        self,
        prompt: str,
        *,
        provider: str | None = None,
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
    ) -> tuple[str, ImageResult]:
        """Generate an image using a provider.

        Args:
            prompt: Text prompt for image generation.
            provider: Provider name, or ``None`` to use the configured default.
            negative_prompt: Things to avoid in the image.
            aspect_ratio: Desired aspect ratio.
            quality: Quality level.
            resolution: Requested resolution tier. Passed through to the
                provider, which may clamp it to a lower delivered tier.
            background: Background transparency (``opaque``, ``transparent``).
                Provider support varies.
            model: Specific model to use (e.g., a checkpoint name for SD WebUI,
                or ``"dall-e-3"`` for OpenAI). Passed through to the provider.
            reference_images: Optional list of input images for image-to-image
                generation. Passed through to the provider unchanged.
            strength: Denoising strength (0.0-1.0) for image-to-image. Only
                SD WebUI uses it; other providers ignore it. Has no effect
                without ``reference_images``.
            mask: Optional mask image for inpainting. Only OpenAI gpt-image
                models support it; other providers raise
                :class:`ImageProviderError`. Applies to the first reference
                image.
            progress_callback: Optional callback invoked with
                ``(fraction, message)`` during generation.  Only SD WebUI
                uses this; other providers ignore it.

        Returns:
            Tuple of (provider_name, ImageResult).

        Raises:
            ImageProviderError: If generation fails.
        """
        resolved_name, resolved_provider = self._resolve_provider(
            provider or self._default_provider,
            prompt,
            background=background,
        )

        # Warn if the resolved provider has degraded capabilities
        caps = self._capabilities.get(resolved_name)
        if caps and caps.degraded:
            logger.warning(
                "Generating with degraded provider %s — capability "
                "discovery failed at startup",
                resolved_name,
            )

        logger.info(
            "Generating image with provider=%s, aspect_ratio=%s",
            resolved_name,
            aspect_ratio,
        )

        result = await resolved_provider.generate(
            prompt,
            negative_prompt=negative_prompt,
            aspect_ratio=aspect_ratio,
            quality=quality,
            resolution=resolution,
            background=background,
            model=model,
            reference_images=reference_images,
            strength=strength,
            mask=mask,
            progress_callback=progress_callback,
        )

        return resolved_name, result

    # ------------------------------------------------------------------
    # Pending generation tracking (fire-and-forget)
    # ------------------------------------------------------------------

    def allocate_image_id(self) -> str:
        """Pre-allocate a unique image ID for fire-and-forget generation.

        Returns:
            A 12-character hex string suitable for use as an image ID.
        """
        return uuid.uuid4().hex[:12]

    def register_pending(
        self,
        image_id: str,
        prompt: str,
        provider: str,
        *,
        negative_prompt: str | None = None,
        aspect_ratio: str = "1:1",
        quality: str = "standard",
        resolution: str = "standard",
        background: str = "opaque",
        model: str | None = None,
    ) -> PendingGeneration:
        """Register a pending generation for background processing.

        Args:
            image_id: Pre-allocated image ID from :meth:`allocate_image_id`.
            prompt: The generation prompt.
            provider: Resolved provider name.
            negative_prompt: Negative prompt (if any).
            aspect_ratio: Requested aspect ratio.
            quality: Requested quality level.
            resolution: Requested resolution tier.
            background: Requested background mode.
            model: Specific model to use.

        Returns:
            The created PendingGeneration.
        """
        pending = PendingGeneration(
            id=image_id,
            prompt=prompt,
            provider=provider,
            negative_prompt=negative_prompt,
            aspect_ratio=aspect_ratio,
            quality=quality,
            resolution=resolution,
            background=background,
            model=model,
        )
        self._pending[image_id] = pending
        logger.info(
            "Registered pending generation: %s (provider=%s)", image_id, provider
        )
        return pending

    def get_pending(self, image_id: str) -> PendingGeneration | None:
        """Look up a pending generation by ID.

        Returns:
            The PendingGeneration, or ``None`` if not found.
        """
        self._cleanup_stale_pending()
        return self._pending.get(image_id)

    def complete_pending(self, image_id: str) -> None:
        """Mark a pending generation as completed.

        Called after the image has been registered in the image registry.
        The pending entry is kept briefly so ``show_image`` can detect the
        transition, then cleaned up on next access.
        """
        pending = self._pending.get(image_id)
        if pending is not None:
            pending.status = "completed"
            pending.completed_at = time.time()
            pending.progress = 1.0

    def fail_pending(self, image_id: str, error: str) -> None:
        """Mark a pending generation as failed.

        Args:
            image_id: The pending generation ID.
            error: Human-readable error message.
        """
        pending = self._pending.get(image_id)
        if pending is not None:
            pending.status = "failed"
            pending.error = error
            pending.completed_at = time.time()

    def cleanup_pending(self, image_id: str) -> None:
        """Remove a pending generation entry after it has been read."""
        self._pending.pop(image_id, None)

    def list_pending(self) -> list[PendingGeneration]:
        """Return all pending generations (generating or recently failed).

        Returns:
            List of PendingGeneration instances.
        """
        self._cleanup_stale_pending()
        return [p for p in self._pending.values() if p.status != "completed"]

    def _cleanup_stale_pending(self) -> None:
        """Remove pending entries that have exceeded the TTL."""
        now = time.time()
        stale = [
            pid
            for pid, p in self._pending.items()
            if (p.completed_at is not None and (now - p.completed_at) > _PENDING_TTL_S)
            or (now - p.created_at) > _PENDING_TTL_S
        ]
        for pid in stale:
            self._pending.pop(pid, None)

    # ------------------------------------------------------------------
    # Image registry
    # ------------------------------------------------------------------

    def register_image(
        self,
        result: ImageResult,
        provider_name: str,
        *,
        prompt: str,
        negative_prompt: str | None = None,
        aspect_ratio: str = "1:1",
        quality: str = "standard",
        resolution: str = "standard",
        background: str = "opaque",
        image_id: str | None = None,
        source_image_ids: list[str] | None = None,
    ) -> ImageRecord:
        """Register a generated image in the scratch directory.

        Saves the original image, writes a sidecar JSON metadata file,
        and stores the record in the in-memory registry.

        Args:
            result: The image result to register.
            provider_name: Name of the provider that generated the image.
            prompt: The generation prompt.
            negative_prompt: Things to avoid (if any).
            aspect_ratio: Requested aspect ratio.
            quality: Requested quality level.
            resolution: Requested resolution tier. The persisted record
                reflects the *delivered* tier reported by the provider in
                ``result.provider_metadata["resolution"]`` when present,
                falling back to this requested value otherwise.
            background: Requested background transparency.
            image_id: Pre-allocated image ID (from :meth:`allocate_image_id`).
                If ``None``, a content-addressed ID is derived from the
                image data.
            source_image_ids: IDs of source images this was derived from.

        Returns:
            The created ImageRecord.
        """
        # Use pre-allocated ID or derive from content
        if image_id is None:
            image_id = hashlib.sha256(result.image_data).hexdigest()[:12]
        effective_resolution = str(
            result.provider_metadata.get("resolution", resolution)
        )
        return self._persist_image(
            image_id=image_id,
            data=result.image_data,
            meta=_PersistMeta(
                content_type=result.content_type,
                provider=provider_name,
                prompt=prompt,
                negative_prompt=negative_prompt,
                aspect_ratio=aspect_ratio,
                quality=quality,
                resolution=effective_resolution,
                background=background,
                provider_metadata=result.provider_metadata,
                source_image_ids=list(source_image_ids or []),
                origin="generated",
                origin_source=None,
            ),
        )

    def register_imported_image(
        self,
        data: bytes,
        *,
        origin_source: str,
        max_bytes: int,
    ) -> ImageRecord:
        """Register externally-sourced bytes as a first-class gallery entry.

        The image gets a content-addressed ID (so re-importing identical
        bytes is idempotent) and is marked ``origin="imported"`` — it has an
        empty provider and prompt, so ``origin`` is the sole generated/imported
        discriminator. Every existing tool, resource, and ``transform_image``
        reference then works on it unchanged.

        Args:
            data: Raw image bytes (from an upload, URL fetch, or base64 body).
            origin_source: Provenance detail (e.g. ``"upload"``,
                ``"fetch:<url>"``, or an original filename).
            max_bytes: Maximum allowed byte size. Callers pass the configured
                ``max_input_image_bytes`` so the cap stays uniform across every
                input surface (no separate default here to drift from it).

        Returns:
            The created ImageRecord.

        Raises:
            InputImageTooLarge: When ``len(data) > max_bytes``.
            InvalidInputImage: When the bytes are not a decodable image, or the
                format is not one of PNG/JPEG/WEBP.
            ValueError: When ``origin_source`` is empty/falsy — an imported
                image must carry a provenance (enforced by ImageRecord's
                origin pairing invariant).
        """
        content_type = validate_image_bytes(data, max_bytes=max_bytes)
        return self._persist_image(
            image_id=hashlib.sha256(data).hexdigest()[:12],
            data=data,
            meta=_PersistMeta(
                content_type=content_type,
                provider="",
                prompt="",
                negative_prompt=None,
                aspect_ratio="",
                quality="",
                resolution="",
                background="opaque",
                provider_metadata={},
                source_image_ids=[],
                origin="imported",
                origin_source=origin_source,
            ),
        )

    def _persist_image(
        self,
        *,
        image_id: str,
        data: bytes,
        meta: _PersistMeta,
    ) -> ImageRecord:
        """Persist image bytes + sidecar + registry entry; return the record.

        Shared by :meth:`register_image` (generated) and
        :meth:`register_imported_image` (imported).
        """
        self._scratch_dir.mkdir(parents=True, exist_ok=True)

        original_dimensions = PILImage.open(io.BytesIO(data)).size  # (w, h)

        ext = _mime_to_ext(meta.content_type)
        original_filename = f"{image_id}-original{ext}"
        original_path = self._scratch_dir / original_filename

        # Build (and thereby validate, via __post_init__) the record BEFORE
        # writing the image file or sidecar, so an inconsistent origin pair
        # raises without leaving an orphaned image file behind.
        record = ImageRecord(
            id=image_id,
            original_path=original_path,
            content_type=meta.content_type,
            provider=meta.provider,
            prompt=meta.prompt,
            negative_prompt=meta.negative_prompt,
            aspect_ratio=meta.aspect_ratio,
            quality=meta.quality,
            resolution=meta.resolution,
            original_dimensions=original_dimensions,
            provider_metadata=meta.provider_metadata,
            created_at=time.time(),
            source_image_ids=meta.source_image_ids,
            origin=meta.origin,
            origin_source=meta.origin_source,
        )
        original_path.write_bytes(data)

        sidecar_path = self._scratch_dir / f"{image_id}.json"
        sidecar_data = {
            "id": record.id,
            "prompt": record.prompt,
            "negative_prompt": record.negative_prompt,
            "provider": record.provider,
            "aspect_ratio": record.aspect_ratio,
            "quality": record.quality,
            "resolution": record.resolution,
            "background": meta.background,
            "content_type": record.content_type,
            "original_filename": original_filename,
            "original_size_bytes": len(data),
            "original_dimensions": list(record.original_dimensions),
            "provider_metadata": record.provider_metadata,
            "created_at": datetime.fromtimestamp(record.created_at, tz=UTC).isoformat(),
            "source_image_ids": record.source_image_ids,
            "origin": record.origin,
            "origin_source": record.origin_source,
        }
        sidecar_path.write_text(json.dumps(sidecar_data, indent=2))

        self._images[image_id] = record

        logger.info(
            "registered_image image_id=%s origin=%s provider=%s bytes=%d",
            image_id,
            meta.origin,
            meta.provider,
            len(data),
        )
        return record

    def get_image(self, image_id: str) -> ImageRecord:
        """Look up a registered image by ID.

        Args:
            image_id: The content-addressed image ID.

        Returns:
            The ImageRecord for the image.

        Raises:
            ImageProviderError: If the image ID is not found.
        """
        if image_id not in self._images:
            raise ImageProviderError(
                "server",
                f"Image '{image_id}' not found. "
                "Read image://list to see available IDs.",
            )
        return self._images[image_id]

    def delete_image(self, image_id: str) -> ImageRecord:
        """Delete a registered image from the scratch directory.

        Removes the image file and its sidecar JSON, evicts all transform
        cache entries for this image, and removes it from the in-memory
        registry.

        Args:
            image_id: The content-addressed image ID.

        Returns:
            The ``ImageRecord`` that was deleted (for confirmation logging).

        Raises:
            ImageProviderError: If *image_id* is not registered.
        """
        record = self.get_image(image_id)  # raises if not found

        # Delete original image file
        try:
            record.original_path.unlink(missing_ok=True)
        except OSError as exc:
            logger.warning(
                "Could not delete image file %s: %s", record.original_path, exc
            )

        # Delete sidecar JSON
        sidecar_path = self._scratch_dir / f"{image_id}.json"
        try:
            sidecar_path.unlink(missing_ok=True)
        except OSError as exc:
            logger.warning("Could not delete sidecar %s: %s", sidecar_path, exc)

        # Evict all transform cache entries for this image
        stale_keys = [k for k in self._transform_cache if k[0] == image_id]
        for key in stale_keys:
            self._transform_cache.pop(key, None)

        # Remove from registry
        del self._images[image_id]

        logger.info("Deleted image %s (provider=%s)", image_id, record.provider)
        return record

    def get_transformed_image(
        self,
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
    ) -> tuple[bytes, str]:
        """Return image bytes with optional transforms, using an LRU cache.

        Requests with no transform parameters bypass the cache entirely and
        return the original file bytes directly.

        Transforms are applied in this order: crop-region → rotate → flip →
        resize/crop → format conversion.

        Args:
            image_id: Image registry ID.
            format: Target format (``"png"``, ``"webp"``, ``"jpeg"``), or
                empty string to keep the original format.
            width: Target width in pixels, or ``0`` for original.
            height: Target height in pixels, or ``0`` for original.
            quality: Compression quality for lossy formats (1-100).
            crop_x: Left edge of crop box in pixels (requires crop_w/crop_h).
            crop_y: Top edge of crop box in pixels (requires crop_w/crop_h).
            crop_w: Width of crop box in pixels (0 = no region crop).
            crop_h: Height of crop box in pixels (0 = no region crop).
            rotate: Rotation in degrees — 90, 180, or 270 (0 = no rotation).
            flip: Flip axis — ``"horizontal"`` or ``"vertical"`` (empty = no flip).

        Returns:
            Tuple of ``(image_bytes, content_type)``.

        Raises:
            ImageProviderError: If *image_id* is not registered.
        """
        record = self.get_image(image_id)

        # No-transform bypass: skip cache for plain original reads
        if (
            not format
            and width == 0
            and height == 0
            and not (crop_w > 0 and crop_h > 0)
            and not rotate
            and not flip
        ):
            return record.original_path.read_bytes(), record.content_type

        # Normalize all crop params to 0 when the effective crop is skipped
        # (crop_w=0 or crop_h=0) so that nonsensical half-zero combinations
        # share the same cache entry as a genuine no-crop request.
        _crop_active = crop_w > 0 and crop_h > 0
        norm_crop_x = crop_x if _crop_active else 0
        norm_crop_y = crop_y if _crop_active else 0
        norm_crop_w = crop_w if _crop_active else 0
        norm_crop_h = crop_h if _crop_active else 0

        key = (
            image_id,
            format,
            width,
            height,
            quality,
            norm_crop_x,
            norm_crop_y,
            norm_crop_w,
            norm_crop_h,
            rotate,
            flip,
        )

        # Cache hit: move to end (most-recently-used) and return
        if key in self._transform_cache:
            self._transform_cache.move_to_end(key)
            return self._transform_cache[key]

        # Cache miss: compute transform
        data = record.original_path.read_bytes()
        content_type = record.content_type

        # 1. Crop region (arbitrary box, always from original)
        if crop_w > 0 and crop_h > 0:
            data = crop_region(data, crop_x, crop_y, crop_w, crop_h)

        # 2. Rotate (lossless 90° increments)
        if rotate:
            data = rotate_image(data, rotate)

        # 3. Flip (lossless)
        if flip:
            data = flip_image(data, flip)

        # 4. Resize/center-crop (existing behavior preserved)
        if width > 0 and height > 0:
            data = crop_to_dimensions(data, width, height)
        elif width > 0:
            orig_w, orig_h = record.original_dimensions
            ratio = width / orig_w
            new_height = round(orig_h * ratio)
            data = resize_image(data, width, new_height)
        elif height > 0:
            orig_w, orig_h = record.original_dimensions
            ratio = height / orig_h
            new_width = round(orig_w * ratio)
            data = resize_image(data, new_width, height)

        # 5. Format conversion last
        if format:
            data, content_type = convert_format(data, format, quality=quality)

        # Store in cache, evict oldest if over size limit
        if self._transform_cache_size > 0:
            self._transform_cache[key] = (data, content_type)
            if len(self._transform_cache) > self._transform_cache_size:
                self._transform_cache.popitem(last=False)

        return data, content_type

    def list_images(self) -> list[ImageRecord]:
        """Return all registered images.

        Returns:
            List of ImageRecord instances.
        """
        return list(self._images.values())

    def _load_registry(self) -> None:
        """Rebuild the in-memory registry from sidecar JSON files."""
        if not self._scratch_dir.exists():
            return

        count = 0
        for sidecar_path in sorted(self._scratch_dir.glob("*.json")):
            try:
                data = json.loads(sidecar_path.read_text())
                image_id = data["id"]
                original_path = self._scratch_dir / data["original_filename"]
                if not original_path.exists():
                    logger.warning(
                        "Skipping sidecar %s: original file missing (%s)",
                        sidecar_path,
                        original_path,
                    )
                    continue

                # Parse ISO timestamp back to epoch
                created_at = datetime.fromisoformat(data["created_at"]).timestamp()

                source_ids = data.get("source_image_ids")
                if source_ids is None:
                    legacy = data.get("source_image_id")
                    source_ids = [legacy] if legacy else []
                # Normalize the origin pair as a unit so a corrupted sidecar
                # can never trip ImageRecord's pairing invariant on reload: an
                # "imported" record without a source degrades to "generated"
                # rather than dropping the whole image.
                origin, origin_source = _origin_pair(
                    data.get("origin"), data.get("origin_source")
                )
                if data.get("origin") == "imported" and origin == "generated":
                    logger.warning(
                        "origin_coerced image_id=%s reason=imported_without_source",
                        image_id,
                    )
                record = ImageRecord(
                    id=image_id,
                    original_path=original_path,
                    content_type=data["content_type"],
                    provider=data["provider"],
                    prompt=data["prompt"],
                    negative_prompt=data.get("negative_prompt"),
                    aspect_ratio=data.get("aspect_ratio", "1:1"),
                    quality=data.get("quality", "standard"),
                    resolution=data.get("resolution", "standard"),
                    original_dimensions=tuple(data["original_dimensions"]),
                    provider_metadata=data.get("provider_metadata", {}),
                    created_at=created_at,
                    source_image_ids=source_ids,
                    origin=origin,
                    origin_source=origin_source,
                )
                self._images[image_id] = record
                count += 1
            except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                logger.warning("Skipping corrupt sidecar file: %s", sidecar_path)

        if count:
            logger.info("Loaded %d images from scratch directory", count)


_MIME_TO_EXT: dict[str, str] = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
}


def _mime_to_ext(content_type: str) -> str:
    """Map MIME type to file extension."""
    return _MIME_TO_EXT.get(content_type, ".png")
