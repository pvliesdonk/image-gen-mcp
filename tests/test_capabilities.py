"""Tests for provider capability model — dataclasses, discovery, and service integration."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

import pytest

from image_generation_mcp.domain import ImageService
from image_generation_mcp.providers.capabilities import (
    ModelCapabilities,
    ProviderCapabilities,
    make_degraded,
)
from image_generation_mcp.providers.model_styles import StyleProfile
from image_generation_mcp.providers.placeholder import PlaceholderImageProvider

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def scratch_dir(tmp_path: Path) -> Path:
    return tmp_path / "scratch"


class TestModelCapabilities:
    """Tests for ModelCapabilities frozen dataclass."""

    def test_frozen(self) -> None:
        mc = ModelCapabilities(model_id="test", display_name="Test")
        with pytest.raises(AttributeError):
            mc.model_id = "other"  # type: ignore[misc]

    def test_defaults(self) -> None:
        mc = ModelCapabilities(model_id="m", display_name="M")
        assert mc.can_generate is True
        assert mc.can_edit is False
        assert mc.supports_mask is False
        assert mc.supported_aspect_ratios == ()
        assert mc.supported_qualities == ()
        assert mc.supported_formats == ()
        assert mc.supports_negative_prompt is False
        assert mc.supports_background is False
        assert mc.max_resolution is None
        assert mc.default_steps is None
        assert mc.default_cfg is None
        assert mc.prompt_style is None

    def test_to_dict(self) -> None:
        mc = ModelCapabilities(
            model_id="gpt-image-1",
            display_name="GPT Image 1",
            supported_aspect_ratios=("1:1", "16:9"),
            supported_formats=("png", "webp"),
            supports_background=True,
            max_resolution=1536,
        )
        d = mc.to_dict()
        assert d["model_id"] == "gpt-image-1"
        assert d["supported_aspect_ratios"] == ["1:1", "16:9"]
        assert d["supported_formats"] == ["png", "webp"]
        assert d["supports_background"] is True
        assert d["max_resolution"] == 1536
        assert "prompt_style" in d
        assert d["prompt_style"] is None

    def test_to_dict_returns_lists_not_tuples(self) -> None:
        mc = ModelCapabilities(
            model_id="m",
            display_name="M",
            supported_aspect_ratios=("1:1",),
        )
        d = mc.to_dict()
        assert isinstance(d["supported_aspect_ratios"], list)
        assert isinstance(d["supported_qualities"], list)
        assert isinstance(d["supported_formats"], list)


class TestProviderCapabilities:
    """Tests for ProviderCapabilities frozen dataclass."""

    def test_frozen(self) -> None:
        pc = ProviderCapabilities(provider_name="test")
        with pytest.raises(AttributeError):
            pc.provider_name = "other"  # type: ignore[misc]

    def test_defaults(self) -> None:
        pc = ProviderCapabilities(provider_name="test")
        assert pc.models == ()
        assert pc.supports_background is False
        assert pc.supports_negative_prompt is False
        assert pc.discovered_at == 0.0
        assert pc.degraded is False

    def test_to_dict_includes_models(self) -> None:
        model = ModelCapabilities(model_id="m1", display_name="Model 1")
        pc = ProviderCapabilities(
            provider_name="prov",
            models=(model,),
            discovered_at=1000.0,
        )
        d = pc.to_dict()
        assert d["provider_name"] == "prov"
        assert len(d["models"]) == 1
        assert d["models"][0]["model_id"] == "m1"
        assert d["discovered_at"] == 1000.0
        assert d["degraded"] is False


class TestMakeDegraded:
    """Tests for the make_degraded helper."""

    def test_creates_degraded_capabilities(self) -> None:
        caps = make_degraded("openai", 12345.0)
        assert caps.provider_name == "openai"
        assert caps.degraded is True
        assert caps.models == ()
        assert caps.discovered_at == 12345.0
        assert caps.supports_background is False
        assert caps.supports_negative_prompt is False


class TestPlaceholderDiscoverCapabilities:
    """Tests for PlaceholderImageProvider.discover_capabilities()."""

    async def test_returns_provider_capabilities(self) -> None:
        provider = PlaceholderImageProvider()
        caps = await provider.discover_capabilities()
        assert isinstance(caps, ProviderCapabilities)
        assert caps.provider_name == "placeholder"
        assert caps.degraded is False

    async def test_has_one_model(self) -> None:
        provider = PlaceholderImageProvider()
        caps = await provider.discover_capabilities()
        assert len(caps.models) == 1
        model = caps.models[0]
        assert model.model_id == "placeholder"
        assert model.can_generate is True
        assert model.can_edit is False
        assert model.supports_mask is False

    async def test_model_capabilities_match_provider(self) -> None:
        provider = PlaceholderImageProvider()
        caps = await provider.discover_capabilities()
        model = caps.models[0]
        assert model.supports_negative_prompt is False
        assert model.supports_background is True
        assert "1:1" in model.supported_aspect_ratios
        assert "16:9" in model.supported_aspect_ratios
        assert model.supported_qualities == ("standard",)
        assert model.supported_formats == ("png",)

    async def test_provider_level_flags(self) -> None:
        provider = PlaceholderImageProvider()
        caps = await provider.discover_capabilities()
        assert caps.supports_background is True
        assert caps.supports_negative_prompt is False

    async def test_discovered_at_is_set(self) -> None:
        provider = PlaceholderImageProvider()
        caps = await provider.discover_capabilities()
        assert caps.discovered_at > 0


class TestServiceDiscoverAll:
    """Tests for ImageService.discover_all_capabilities()."""

    async def test_populates_capabilities(self, scratch_dir: Path) -> None:
        svc = ImageService(scratch_dir=scratch_dir)
        svc.register_provider("placeholder", PlaceholderImageProvider())
        await svc.discover_all_capabilities()
        assert "placeholder" in svc.capabilities
        assert svc.capabilities["placeholder"].provider_name == "placeholder"

    async def test_multiple_providers(self, scratch_dir: Path) -> None:
        svc = ImageService(scratch_dir=scratch_dir)
        svc.register_provider("placeholder", PlaceholderImageProvider())
        svc.register_provider("placeholder2", PlaceholderImageProvider())
        await svc.discover_all_capabilities()
        assert len(svc.capabilities) == 2

    async def test_failure_marks_degraded(self, scratch_dir: Path) -> None:
        svc = ImageService(scratch_dir=scratch_dir)

        # Create a mock provider whose discover_capabilities() raises
        mock_provider = AsyncMock()
        mock_provider.discover_capabilities.side_effect = RuntimeError("API down")
        mock_provider.generate = AsyncMock()
        svc.register_provider("broken", mock_provider)

        await svc.discover_all_capabilities()
        assert "broken" in svc.capabilities
        assert svc.capabilities["broken"].degraded is True
        assert svc.capabilities["broken"].models == ()

    async def test_failure_does_not_block_other_providers(
        self, scratch_dir: Path
    ) -> None:
        svc = ImageService(scratch_dir=scratch_dir)

        mock_provider = AsyncMock()
        mock_provider.discover_capabilities.side_effect = RuntimeError("API down")
        mock_provider.generate = AsyncMock()
        svc.register_provider("broken", mock_provider)
        svc.register_provider("placeholder", PlaceholderImageProvider())

        await svc.discover_all_capabilities()
        assert svc.capabilities["broken"].degraded is True
        assert svc.capabilities["placeholder"].degraded is False


class TestListProvidersIncludesCapabilities:
    """Tests for enriched list_providers() response."""

    async def test_includes_capabilities_after_discovery(
        self, scratch_dir: Path
    ) -> None:
        svc = ImageService(scratch_dir=scratch_dir)
        svc.register_provider("placeholder", PlaceholderImageProvider())
        await svc.discover_all_capabilities()
        providers = svc.list_providers()
        entry = providers["placeholder"]
        assert "capabilities" in entry
        assert entry["capabilities"]["provider_name"] == "placeholder"
        assert len(entry["capabilities"]["models"]) == 1

    def test_no_capabilities_before_discovery(self, scratch_dir: Path) -> None:
        svc = ImageService(scratch_dir=scratch_dir)
        svc.register_provider("placeholder", PlaceholderImageProvider())
        providers = svc.list_providers()
        assert "capabilities" not in providers["placeholder"]

    def test_backward_compatible_fields(self, scratch_dir: Path) -> None:
        svc = ImageService(scratch_dir=scratch_dir)
        svc.register_provider("placeholder", PlaceholderImageProvider())
        providers = svc.list_providers()
        assert providers["placeholder"]["available"] is True
        assert "description" in providers["placeholder"]


def test_model_capabilities_to_dict_omits_style_profile_when_none():
    caps = ModelCapabilities(model_id="x", display_name="X")
    result = caps.to_dict()
    assert "style_profile" not in result


def test_model_capabilities_to_dict_includes_style_profile_when_set():
    profile = StyleProfile(
        label="L",
        style_hints="s",
        incompatible_styles="i",
        good_example="g",
        bad_example="b",
    )
    caps = ModelCapabilities(
        model_id="x",
        display_name="X",
        style_profile=profile,
    )
    result = caps.to_dict()
    assert result["style_profile"]["label"] == "L"
    assert result["style_profile"]["lifecycle"] == "current"


def test_model_capabilities_to_dict_omits_watermark_when_none():
    caps = ModelCapabilities(model_id="x", display_name="X")
    result = caps.to_dict()
    assert "watermark" not in result


def test_model_capabilities_to_dict_includes_watermark_when_set():
    caps = ModelCapabilities(model_id="x", display_name="X", watermark="synthid")
    result = caps.to_dict()
    assert result["watermark"] == "synthid"


def test_model_capabilities_watermark_none_string_is_preserved():
    """Explicit ``watermark='none'`` is preserved in the serialised output.

    Distinct from ``watermark=None`` (default — provider hasn't declared).
    The 'none' string asserts no watermark; the field is present in the
    dict (not omitted), so consumers can distinguish 'declared no
    watermark' from 'undeclared'.
    """
    caps = ModelCapabilities(model_id="x", display_name="X", watermark="none")
    result = caps.to_dict()
    assert result["watermark"] == "none"


def test_model_caps_image_input_defaults() -> None:
    from image_generation_mcp.providers.capabilities import ModelCapabilities

    cap = ModelCapabilities(model_id="m", display_name="M")
    assert cap.supports_image_input is False
    assert cap.max_input_images == 0


def test_model_caps_image_input_in_to_dict() -> None:
    from image_generation_mcp.providers.capabilities import ModelCapabilities

    cap = ModelCapabilities(
        model_id="m",
        display_name="M",
        supports_image_input=True,
        max_input_images=1,
    )
    d = cap.to_dict()
    assert d["supports_image_input"] is True
    assert d["max_input_images"] == 1


def test_model_capabilities_supported_resolutions_default():
    from image_generation_mcp.providers.capabilities import ModelCapabilities

    cap = ModelCapabilities(model_id="m", display_name="M")
    assert cap.supported_resolutions == ("standard",)
    assert cap.to_dict()["supported_resolutions"] == ["standard"]


def test_supported_resolutions_vocabulary():
    from image_generation_mcp.providers.types import SUPPORTED_RESOLUTIONS

    assert SUPPORTED_RESOLUTIONS == ("standard", "high", "max")
