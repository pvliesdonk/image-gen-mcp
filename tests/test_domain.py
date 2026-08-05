"""Tests for the ImageService orchestrator."""

from __future__ import annotations

import io
from typing import TYPE_CHECKING

import pytest
from PIL import Image

if TYPE_CHECKING:
    from pathlib import Path

import json

from image_generation_mcp.domain import ImageService
from image_generation_mcp.providers.placeholder import PlaceholderImageProvider
from image_generation_mcp.providers.types import ImageProviderError, ImageResult


def _png_bytes(color: str = "red", size: tuple[int, int] = (4, 4)) -> bytes:
    """Return raw PNG bytes for a small solid-color image."""
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def scratch_dir(tmp_path: Path) -> Path:
    return tmp_path / "scratch"


@pytest.fixture
def service(scratch_dir: Path) -> ImageService:
    svc = ImageService(scratch_dir=scratch_dir)
    svc.register_provider("placeholder", PlaceholderImageProvider())
    return svc


class TestProviderRegistry:
    """Tests for provider registration and listing."""

    def test_register_and_list(self, service: ImageService) -> None:
        providers = service.list_providers()
        assert "placeholder" in providers
        assert providers["placeholder"]["available"] is True

    def test_empty_registry(self, scratch_dir: Path) -> None:
        svc = ImageService(scratch_dir=scratch_dir)
        assert svc.list_providers() == {}


class TestGenerate:
    """Tests for the generate method."""

    async def test_generate_with_explicit_provider(self, service: ImageService) -> None:
        name, result = await service.generate("a cat", provider="placeholder")
        assert name == "placeholder"
        assert result.image_data
        assert result.content_type == "image/png"

    async def test_generate_auto_with_only_placeholder(
        self, service: ImageService
    ) -> None:
        name, result = await service.generate("a cat")
        assert name == "placeholder"
        assert result.image_data

    async def test_generate_unknown_provider_raises(
        self, service: ImageService
    ) -> None:
        with pytest.raises(ImageProviderError, match="not available"):
            await service.generate("test", provider="nonexistent")

    async def test_generate_no_providers_raises(self, scratch_dir: Path) -> None:
        svc = ImageService(scratch_dir=scratch_dir)
        with pytest.raises(ImageProviderError, match="No providers are registered"):
            await svc.generate("test", provider="auto")

    async def test_generate_passes_params(self, service: ImageService) -> None:
        name, result = await service.generate(
            "test",
            provider="placeholder",
            negative_prompt="bad stuff",
            aspect_ratio="16:9",
            quality="hd",
        )
        assert name == "placeholder"
        assert result.provider_metadata["size"] == "640x360"

    async def test_generate_passes_model_to_provider(
        self, service: ImageService
    ) -> None:
        """Service passes model= through to the provider (placeholder ignores it)."""
        name, result = await service.generate(
            "test",
            provider="placeholder",
            model="some-checkpoint",
        )
        assert name == "placeholder"
        # Placeholder ignores model, result is still valid
        assert result.image_data

    async def test_generate_forwards_mask_to_provider(self, scratch_dir: Path) -> None:
        """ImageService.generate forwards mask= kwarg to the provider."""
        from unittest.mock import AsyncMock

        from image_generation_mcp.providers.types import ImageResult, InputImage

        svc = ImageService(scratch_dir=scratch_dir)

        fake_result = ImageResult(image_data=b"\x89PNG", content_type="image/png")
        fake_provider = AsyncMock()
        fake_provider.generate = AsyncMock(return_value=fake_result)
        svc.register_provider("fake", fake_provider)

        mask_image = InputImage(data=b"mask", content_type="image/png")
        await svc.generate("test", provider="fake", mask=mask_image)

        assert fake_provider.generate.await_count == 1
        call_kwargs = fake_provider.generate.call_args.kwargs
        assert call_kwargs["mask"] is mask_image


# ---------------------------------------------------------------------------
# ImageRecord.source_image_ids
# ---------------------------------------------------------------------------


async def test_source_image_ids_defaults_empty(tmp_path: Path) -> None:
    """ImageRecord.source_image_ids defaults to an empty list."""
    provider = PlaceholderImageProvider()
    result = await provider.generate("test", aspect_ratio="1:1")
    svc = ImageService(scratch_dir=tmp_path)
    record = svc.register_image(result, "placeholder", prompt="test")
    assert record.source_image_ids == []


async def test_source_image_ids_persisted_in_sidecar(tmp_path: Path) -> None:
    """source_image_ids is written to and read back from the sidecar JSON."""
    provider = PlaceholderImageProvider()
    result = await provider.generate("test", aspect_ratio="1:1")
    svc = ImageService(scratch_dir=tmp_path)
    record = svc.register_image(
        result, "placeholder", prompt="test", source_image_ids=["abc123"]
    )
    assert record.source_image_ids == ["abc123"]

    # Check sidecar
    sidecar = json.loads((tmp_path / f"{record.id}.json").read_text())
    assert sidecar["source_image_ids"] == ["abc123"]

    # Reload from disk
    svc2 = ImageService(scratch_dir=tmp_path)
    reloaded = svc2.get_image(record.id)
    assert reloaded.source_image_ids == ["abc123"]


def test_register_image_records_source_ids(tmp_path: Path) -> None:
    """register_image stores multiple source_image_ids on the record."""
    import io

    from PIL import Image

    from image_generation_mcp.providers.types import ImageResult

    buf = io.BytesIO()
    Image.new("RGB", (4, 4), "red").save(buf, format="PNG")
    service = ImageService(scratch_dir=tmp_path)
    record = service.register_image(
        ImageResult(image_data=buf.getvalue(), content_type="image/png"),
        "gemini",
        prompt="p",
        source_image_ids=["abc", "def"],
    )
    assert record.source_image_ids == ["abc", "def"]


def test_load_registry_reads_legacy_source_image_id(tmp_path: Path) -> None:
    """_load_registry falls back to legacy scalar source_image_id in sidecar."""
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (4, 4), "red").save(buf, format="PNG")
    (tmp_path / "aaaaaaaaaaaa-original.png").write_bytes(buf.getvalue())
    (tmp_path / "aaaaaaaaaaaa.json").write_text(
        json.dumps(
            {
                "id": "aaaaaaaaaaaa",
                "prompt": "p",
                "negative_prompt": None,
                "provider": "gemini",
                "aspect_ratio": "1:1",
                "quality": "standard",
                "content_type": "image/png",
                "original_filename": "aaaaaaaaaaaa-original.png",
                "original_dimensions": [4, 4],
                "provider_metadata": {},
                "created_at": "2026-01-01T00:00:00+00:00",
                "source_image_id": "legacy123456",
            }
        )
    )
    service = ImageService(scratch_dir=tmp_path)
    assert service.get_image("aaaaaaaaaaaa").source_image_ids == ["legacy123456"]


async def test_generate_passes_reference_images_to_provider(tmp_path: Path) -> None:
    """generate() forwards reference_images to the resolved provider."""
    from unittest.mock import AsyncMock

    from image_generation_mcp.providers.types import ImageResult, InputImage

    service = ImageService(scratch_dir=tmp_path, default_provider="fake")
    fake = AsyncMock()
    fake.generate = AsyncMock(
        return_value=ImageResult(image_data=b"x", content_type="image/png")
    )
    service.register_provider("fake", fake)

    refs = [InputImage(data=b"in", content_type="image/png", source_id="abc")]
    await service.generate("p", provider="fake", reference_images=refs)

    assert fake.generate.call_args.kwargs["reference_images"] == refs


async def test_generate_forwards_strength_to_provider(tmp_path: Path) -> None:
    """generate() forwards strength to the resolved provider."""
    from unittest.mock import AsyncMock

    from image_generation_mcp.providers.types import ImageResult

    service = ImageService(scratch_dir=tmp_path, default_provider="fake")
    fake = AsyncMock()
    fake.generate = AsyncMock(
        return_value=ImageResult(image_data=b"x", content_type="image/png")
    )
    service.register_provider("fake", fake)

    await service.generate("p", provider="fake", strength=0.5)

    assert fake.generate.call_args.kwargs["strength"] == 0.5


async def test_generate_forwards_resolution_to_provider(tmp_path: Path) -> None:
    """generate() forwards resolution to the resolved provider."""
    from unittest.mock import AsyncMock

    from image_generation_mcp.providers.types import ImageResult

    service = ImageService(scratch_dir=tmp_path, default_provider="fake")
    fake = AsyncMock()
    fake.generate = AsyncMock(
        return_value=ImageResult(image_data=b"x", content_type="image/png")
    )
    service.register_provider("fake", fake)

    await service.generate("p", provider="fake", resolution="high")

    assert fake.generate.call_args.kwargs["resolution"] == "high"


# ---------------------------------------------------------------------------
# Delivered resolution persistence
# ---------------------------------------------------------------------------


def test_register_image_persists_delivered_resolution(service: ImageService) -> None:
    """register_image persists the delivered tier, not the requested one."""
    result = ImageResult(
        image_data=_png_bytes(),
        content_type="image/png",
        provider_metadata={"resolution": "standard"},  # clamped from "max"
    )
    record = service.register_image(result, "gemini", prompt="x", resolution="max")
    assert record.resolution == "standard"  # delivered, not requested


def test_register_image_falls_back_to_requested_resolution(
    service: ImageService,
) -> None:
    """When a provider does not report a delivered tier, the requested one persists."""
    result = ImageResult(image_data=_png_bytes(), content_type="image/png")
    record = service.register_image(result, "sd_webui", prompt="x", resolution="high")
    assert record.resolution == "high"


def test_resolution_round_trips_through_sidecar(
    service: ImageService, scratch_dir: Path
) -> None:
    """The delivered resolution survives a sidecar write + registry reload."""
    result = ImageResult(
        image_data=_png_bytes(),
        content_type="image/png",
        provider_metadata={"resolution": "max"},
    )
    record = service.register_image(result, "openai", prompt="x", resolution="max")

    reloaded_service = ImageService(scratch_dir=scratch_dir)
    reloaded = reloaded_service.get_image(record.id)
    assert reloaded.resolution == "max"


def test_register_pending_carries_resolution(service: ImageService) -> None:
    """register_pending threads the requested resolution onto PendingGeneration."""
    pending = service.register_pending(
        service.allocate_image_id(), "x", "gemini", resolution="high"
    )
    assert pending.resolution == "high"
