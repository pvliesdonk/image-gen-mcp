"""Tests for OpenAIImageProvider.discover_capabilities()."""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from image_generation_mcp.providers.capabilities import (
    ModelCapabilities,
    ProviderCapabilities,
)
from image_generation_mcp.providers.openai import OpenAIImageProvider


@pytest.fixture
def provider() -> OpenAIImageProvider:
    """OpenAIImageProvider with _create_client patched out."""
    with patch(
        "image_generation_mcp.providers.openai.OpenAIImageProvider._create_client"
    ):
        p = OpenAIImageProvider(api_key="sk-test")
    # Replace _client with a plain MagicMock so we can configure models.list
    p._client = MagicMock()
    return p


def _make_model(*model_ids: str) -> MagicMock:
    """Build a mock models.list() response with the given model IDs."""
    models = []
    for mid in model_ids:
        m = MagicMock()
        m.id = mid
        models.append(m)
    response = MagicMock()
    response.data = models
    return response


class TestDiscoverCapabilitiesSuccess:
    """Happy-path tests for discover_capabilities()."""

    async def test_openai_discover_capabilities_success(
        self, provider: OpenAIImageProvider
    ) -> None:
        """Returns 2 ModelCapabilities when gpt-image-1 and dall-e-3 are present."""
        provider._client.models = MagicMock()
        provider._client.models.list = AsyncMock(
            return_value=_make_model("gpt-image-1", "dall-e-3")
        )

        caps = await provider.discover_capabilities()

        assert isinstance(caps, ProviderCapabilities)
        assert caps.provider_name == "openai"
        assert caps.degraded is False
        assert len(caps.models) == 2
        model_ids = {m.model_id for m in caps.models}
        assert model_ids == {"gpt-image-1", "dall-e-3"}

    async def test_openai_discover_capabilities_filters_non_image(
        self, provider: OpenAIImageProvider
    ) -> None:
        """Non-image models (gpt-4o, text-embedding-3-small) are excluded."""
        provider._client.models = MagicMock()
        provider._client.models.list = AsyncMock(
            return_value=_make_model("gpt-4o", "text-embedding-3-small", "gpt-image-1")
        )

        caps = await provider.discover_capabilities()

        assert len(caps.models) == 1
        assert caps.models[0].model_id == "gpt-image-1"

    async def test_openai_discover_capabilities_no_image_models(
        self, provider: OpenAIImageProvider
    ) -> None:
        """Empty model list when no image models are in the response — not degraded."""
        provider._client.models = MagicMock()
        provider._client.models.list = AsyncMock(
            return_value=_make_model("gpt-4o", "text-embedding-3-small")
        )

        caps = await provider.discover_capabilities()

        assert caps.degraded is False
        assert caps.models == ()
        assert caps.supports_background is False
        assert caps.supports_negative_prompt is False

    async def test_openai_discover_capabilities_api_failure(
        self, provider: OpenAIImageProvider, caplog: pytest.LogCaptureFixture
    ) -> None:
        """API error returns degraded=True, empty models, and logs a warning."""
        provider._client.models = MagicMock()
        provider._client.models.list = AsyncMock(
            side_effect=RuntimeError("network timeout")
        )

        with caplog.at_level(logging.WARNING):
            caps = await provider.discover_capabilities()

        assert caps.degraded is True
        assert caps.models == ()
        assert caps.provider_name == "openai"
        assert any(
            "degraded" in record.message.lower() or "failed" in record.message.lower()
            for record in caplog.records
        )


class TestDiscoverGptImage1Fields:
    """Verify specific fields for the gpt-image-1 model entry."""

    async def test_openai_discover_gpt_image_1_fields(
        self, provider: OpenAIImageProvider
    ) -> None:
        """gpt-image-1 has the expected capability fields."""
        provider._client.models = MagicMock()
        provider._client.models.list = AsyncMock(
            return_value=_make_model("gpt-image-1")
        )

        caps = await provider.discover_capabilities()

        assert len(caps.models) == 1
        m = caps.models[0]
        assert isinstance(m, ModelCapabilities)
        assert m.model_id == "gpt-image-1"
        assert m.display_name == "GPT Image 1"
        assert m.can_generate is True
        assert m.can_edit is True
        assert m.supports_mask is True
        assert m.supports_background is True
        assert m.supports_negative_prompt is False
        assert "1:1" in m.supported_aspect_ratios
        assert "16:9" in m.supported_aspect_ratios
        assert "png" in m.supported_formats
        assert "jpeg" in m.supported_formats
        assert "webp" in m.supported_formats
        assert "standard" in m.supported_qualities
        assert "hd" in m.supported_qualities
        assert m.max_resolution == 1536


class TestDiscoverGptImage2Fields:
    """Verify specific fields for the gpt-image-2 model entry.

    gpt-image-2 mirrors gpt-image-1.5's surface except it drops transparent-
    background support per OpenAI's documented difference. The branch is
    gated on models.list() returning the id, so the entry is dormant until
    OpenAI ships it publicly.
    """

    async def test_openai_discover_gpt_image_2_fields(
        self, provider: OpenAIImageProvider
    ) -> None:
        """gpt-image-2 has the expected capability fields, no transparency."""
        provider._client.models = MagicMock()
        provider._client.models.list = AsyncMock(
            return_value=_make_model("gpt-image-2")
        )

        caps = await provider.discover_capabilities()

        assert len(caps.models) == 1
        m = caps.models[0]
        assert isinstance(m, ModelCapabilities)
        assert m.model_id == "gpt-image-2"
        assert m.display_name == "GPT Image 2"
        assert m.can_generate is True
        assert m.can_edit is True
        assert m.supports_mask is True
        # Documented difference vs gpt-image-1.5: no transparency support.
        assert m.supports_background is False
        assert m.supports_negative_prompt is False
        assert "1:1" in m.supported_aspect_ratios
        assert "16:9" in m.supported_aspect_ratios
        assert "png" in m.supported_formats
        assert "jpeg" in m.supported_formats
        assert "webp" in m.supported_formats
        assert "standard" in m.supported_qualities
        assert "hd" in m.supported_qualities
        assert m.max_resolution == 3840
        assert m.supported_resolutions == ("standard", "high", "max")
        assert m.style_profile is not None
        assert "OpenAI GPT Image 2" in m.style_profile.label


class TestDiscoverDalle3Fields:
    """Verify specific fields for the dall-e-3 model entry."""

    async def test_openai_discover_dalle3_fields(
        self, provider: OpenAIImageProvider
    ) -> None:
        """dall-e-3 has the expected capability fields."""
        provider._client.models = MagicMock()
        provider._client.models.list = AsyncMock(return_value=_make_model("dall-e-3"))

        caps = await provider.discover_capabilities()

        assert len(caps.models) == 1
        m = caps.models[0]
        assert isinstance(m, ModelCapabilities)
        assert m.model_id == "dall-e-3"
        assert m.display_name == "DALL-E 3"
        assert m.can_generate is True
        assert m.can_edit is False
        assert m.supports_mask is False
        assert m.supports_background is False
        assert m.supports_negative_prompt is False
        assert "1:1" in m.supported_aspect_ratios
        assert "16:9" in m.supported_aspect_ratios
        assert m.supported_formats == ("png",)
        assert "standard" in m.supported_qualities
        assert "hd" in m.supported_qualities
        assert m.max_resolution == 1792


class TestDiscoverProviderLevelFlags:
    """Verify provider-level aggregate flags."""

    async def test_openai_discover_provider_level_flags(
        self, provider: OpenAIImageProvider
    ) -> None:
        """supports_background is True (gpt-image-1); supports_negative_prompt is False."""
        provider._client.models = MagicMock()
        provider._client.models.list = AsyncMock(
            return_value=_make_model("gpt-image-1", "dall-e-3")
        )

        caps = await provider.discover_capabilities()

        assert caps.supports_background is True
        assert caps.supports_negative_prompt is False

    async def test_supports_background_false_when_only_dalle3(
        self, provider: OpenAIImageProvider
    ) -> None:
        """supports_background is False when only dall-e-3 is present."""
        provider._client.models = MagicMock()
        provider._client.models.list = AsyncMock(return_value=_make_model("dall-e-3"))

        caps = await provider.discover_capabilities()

        assert caps.supports_background is False
        assert caps.supports_negative_prompt is False

    async def test_discovered_at_is_set(self, provider: OpenAIImageProvider) -> None:
        """discovered_at is a positive unix timestamp."""
        provider._client.models = MagicMock()
        provider._client.models.list = AsyncMock(
            return_value=_make_model("gpt-image-1")
        )

        caps = await provider.discover_capabilities()

        assert caps.discovered_at > 0

    async def test_discovered_at_set_on_degraded(
        self, provider: OpenAIImageProvider
    ) -> None:
        """discovered_at is still set when discovery fails (degraded path)."""
        provider._client.models = MagicMock()
        provider._client.models.list = AsyncMock(side_effect=RuntimeError("auth error"))

        caps = await provider.discover_capabilities()

        assert caps.degraded is True
        assert caps.discovered_at > 0


class TestDiscoverDalle2Fields:
    """Verify specific fields for the dall-e-2 model entry."""

    async def test_dalle2_fields(self, provider: OpenAIImageProvider) -> None:
        """dall-e-2 has the expected capability fields."""
        provider._client.models = MagicMock()
        provider._client.models.list = AsyncMock(return_value=_make_model("dall-e-2"))

        caps = await provider.discover_capabilities()

        assert len(caps.models) == 1
        m = caps.models[0]
        assert m.model_id == "dall-e-2"
        assert m.display_name == "DALL-E 2"
        assert m.can_generate is True
        assert m.can_edit is True
        # The server's edit/mask path is gpt-image-only and dall-e-2 has no
        # image-input support, so masks can never route here.
        assert m.supports_mask is False
        assert m.supports_background is False
        assert m.supported_aspect_ratios == ("1:1",)
        assert m.supported_formats == ("png",)
        assert m.supported_qualities == ("standard",)
        assert m.max_resolution == 1024


class TestDiscoverStyleProfile:
    """Verify style_profile is populated on discover_capabilities() results."""

    async def test_discover_capabilities_populates_style_profile(
        self, provider: OpenAIImageProvider
    ) -> None:
        """style_profile is populated on returned ModelCapabilities entries."""
        provider._client.models = MagicMock()
        provider._client.models.list = AsyncMock(
            return_value=_make_model(
                "gpt-image-1",
                "gpt-image-1-mini",
                "gpt-image-1.5",
                "chatgpt-image-latest",
                "dall-e-3",
                "dall-e-2",
            )
        )

        caps = await provider.discover_capabilities()

        assert caps.models, "expected at least one model in capabilities"
        for model_caps in caps.models:
            assert model_caps.style_profile is not None, (
                f"expected style_profile for {model_caps.model_id}"
            )
            assert model_caps.style_profile.label


class TestDiscoverNewGptImageModels:
    """Verify discovery of gpt-image-1-mini and gpt-image-1.5."""

    async def test_gpt_image_1_mini_discovered(
        self, provider: OpenAIImageProvider
    ) -> None:
        """gpt-image-1-mini is discovered with correct fields."""
        provider._client.models = MagicMock()
        provider._client.models.list = AsyncMock(
            return_value=_make_model("gpt-image-1-mini")
        )

        caps = await provider.discover_capabilities()

        assert len(caps.models) == 1
        m = caps.models[0]
        assert m.model_id == "gpt-image-1-mini"
        assert m.display_name == "GPT Image 1 Mini"
        assert m.can_generate is True
        assert m.can_edit is True
        assert m.supports_background is True
        assert "png" in m.supported_formats
        assert "jpeg" in m.supported_formats
        assert "webp" in m.supported_formats

    async def test_gpt_image_1_5_discovered(
        self, provider: OpenAIImageProvider
    ) -> None:
        """gpt-image-1.5 is discovered with correct fields."""
        provider._client.models = MagicMock()
        provider._client.models.list = AsyncMock(
            return_value=_make_model("gpt-image-1.5")
        )

        caps = await provider.discover_capabilities()

        assert len(caps.models) == 1
        m = caps.models[0]
        assert m.model_id == "gpt-image-1.5"
        assert m.display_name == "GPT Image 1.5"
        assert m.can_generate is True

    async def test_chatgpt_image_latest_discovered(
        self, provider: OpenAIImageProvider
    ) -> None:
        """chatgpt-image-latest (floating alias) is discovered with gpt-image caps."""
        provider._client.models = MagicMock()
        provider._client.models.list = AsyncMock(
            return_value=_make_model("chatgpt-image-latest")
        )

        caps = await provider.discover_capabilities()

        assert len(caps.models) == 1
        m = caps.models[0]
        assert m.model_id == "chatgpt-image-latest"
        assert m.display_name == "ChatGPT Image (latest)"
        assert m.can_generate is True
        assert m.can_edit is True
        assert m.supports_image_input is True
        assert m.max_input_images == 16
        # Floating alias currently resolves to gpt-image-2, which drops
        # transparency; advertise no-background conservatively.
        assert m.supports_background is False
        # Reference-image edits route through the gpt-image edit path, so the
        # alias must be recognised as a gpt-image-family model.
        from image_generation_mcp.providers.openai import _is_gpt_image_model

        assert _is_gpt_image_model("chatgpt-image-latest") is True

    async def test_all_five_models_discovered(
        self, provider: OpenAIImageProvider
    ) -> None:
        """All five known models are discovered when present."""
        provider._client.models = MagicMock()
        provider._client.models.list = AsyncMock(
            return_value=_make_model(
                "gpt-image-1",
                "gpt-image-1-mini",
                "gpt-image-1.5",
                "dall-e-3",
                "dall-e-2",
            )
        )

        caps = await provider.discover_capabilities()

        model_ids = {m.model_id for m in caps.models}
        assert model_ids == {
            "gpt-image-1",
            "gpt-image-1-mini",
            "gpt-image-1.5",
            "dall-e-3",
            "dall-e-2",
        }


class TestDiscoverImageInputCapability:
    """Verify image-input capability fields on gpt-image models."""

    async def test_gpt_image_models_advertise_image_input(
        self, provider: OpenAIImageProvider
    ) -> None:
        """gpt-image models advertise image-input support; dall-e-3 does not."""
        provider._client.models = MagicMock()
        provider._client.models.list = AsyncMock(
            return_value=_make_model(
                "gpt-image-2",
                "gpt-image-1.5",
                "gpt-image-1",
                "gpt-image-1-mini",
                "dall-e-3",
            )
        )

        caps = await provider.discover_capabilities()

        by_id = {m.model_id: m for m in caps.models}
        for mid in ("gpt-image-2", "gpt-image-1.5", "gpt-image-1", "gpt-image-1-mini"):
            assert by_id[mid].supports_image_input is True
            assert by_id[mid].max_input_images == 16
        # dall-e-3 has no edit support
        assert by_id["dall-e-3"].supports_image_input is False
        assert by_id["dall-e-3"].max_input_images == 0
