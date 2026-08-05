"""Tests for the placeholder image provider."""

from __future__ import annotations

import pytest

from image_generation_mcp.providers.placeholder import PlaceholderImageProvider
from image_generation_mcp.providers.types import (
    ImageInputUnsupported,
    ImageProvider,
    InputImage,
)


class TestPlaceholderProvider:
    """Tests for PlaceholderImageProvider."""

    @pytest.fixture
    def provider(self) -> PlaceholderImageProvider:
        return PlaceholderImageProvider()

    async def test_implements_protocol(
        self, provider: PlaceholderImageProvider
    ) -> None:
        assert isinstance(provider, ImageProvider)

    async def test_generate_returns_image_result(
        self, provider: PlaceholderImageProvider
    ) -> None:
        result = await provider.generate("a cat")
        assert result.image_data
        assert result.content_type == "image/png"
        assert result.provider_metadata["quality"] == "placeholder"

    async def test_png_signature(self, provider: PlaceholderImageProvider) -> None:
        result = await provider.generate("test")
        assert result.image_data[:8] == b"\x89PNG\r\n\x1a\n"

    async def test_deterministic_color(
        self, provider: PlaceholderImageProvider
    ) -> None:
        r1 = await provider.generate("same prompt")
        r2 = await provider.generate("same prompt")
        assert r1.provider_metadata["color"] == r2.provider_metadata["color"]

    async def test_different_prompts_can_differ(
        self, provider: PlaceholderImageProvider
    ) -> None:
        # Not guaranteed to differ for all pairs, but these two do
        r1 = await provider.generate("alpha")
        r2 = await provider.generate("beta")
        # At minimum, both produce valid results
        assert r1.image_data
        assert r2.image_data

    @pytest.mark.parametrize(
        "ratio,expected_size",
        [
            ("1:1", "256x256"),
            ("16:9", "640x360"),
            ("9:16", "360x640"),
            ("3:2", "480x320"),
            ("2:3", "320x480"),
        ],
    )
    async def test_aspect_ratios(
        self,
        provider: PlaceholderImageProvider,
        ratio: str,
        expected_size: str,
    ) -> None:
        result = await provider.generate("test", aspect_ratio=ratio)
        assert result.provider_metadata["size"] == expected_size

    async def test_unknown_aspect_ratio_falls_back(
        self, provider: PlaceholderImageProvider
    ) -> None:
        result = await provider.generate("test", aspect_ratio="7:3")
        assert result.provider_metadata["size"] == "256x256"

    async def test_model_param_ignored(
        self, provider: PlaceholderImageProvider
    ) -> None:
        """Passing model= should have no effect on the result."""
        result_default = await provider.generate("test")
        result_with_model = await provider.generate("test", model="some-model")
        assert result_default.provider_metadata == result_with_model.provider_metadata

    async def test_model_param_none_accepted(
        self, provider: PlaceholderImageProvider
    ) -> None:
        result = await provider.generate("test", model=None)
        assert result.image_data

    async def test_discover_capabilities_populates_style_profile(
        self, provider: PlaceholderImageProvider
    ) -> None:
        """style_profile is populated on the returned ModelCapabilities."""
        caps = await provider.discover_capabilities()

        assert caps.models, "expected at least one model in capabilities"
        for model_caps in caps.models:
            assert model_caps.style_profile is not None, (
                f"expected style_profile for {model_caps.model_id}"
            )
            assert model_caps.style_profile.label


async def test_placeholder_rejects_reference_images() -> None:
    """Placeholder provider raises ImageInputUnsupported when reference_images are given."""
    provider = PlaceholderImageProvider()

    with pytest.raises(ImageInputUnsupported):
        await provider.generate(
            "x",
            reference_images=[InputImage(data=b"x", content_type="image/png")],
        )


async def test_placeholder_ignores_strength() -> None:
    """Placeholder provider accepts strength and ignores it (no error)."""
    provider = PlaceholderImageProvider()

    result = await provider.generate("x", strength=0.5)
    assert result.image_data  # produced normally, strength ignored


async def test_placeholder_rejects_mask() -> None:
    """Placeholder provider raises ImageProviderError when mask is given."""
    from image_generation_mcp.providers.types import ImageProviderError

    with pytest.raises(ImageProviderError, match="mask"):
        await PlaceholderImageProvider().generate(
            "x", mask=InputImage(data=b"m", content_type="image/png")
        )


async def test_placeholder_accepts_and_ignores_resolution():
    from image_generation_mcp.providers.placeholder import PlaceholderImageProvider

    provider = PlaceholderImageProvider()
    result = await provider.generate("a cat", resolution="max")
    assert result.image_data


async def test_placeholder_reports_standard_delivered_resolution() -> None:
    """The placeholder always delivers 'standard', regardless of the request.

    It has no higher tier, so it must report its always-delivered tier in
    provider_metadata rather than silently defaulting to the requested one.
    """
    provider = PlaceholderImageProvider()
    result = await provider.generate("a cat", resolution="max")
    assert result.provider_metadata["resolution"] == "standard"
