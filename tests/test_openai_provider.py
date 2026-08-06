"""Tests for the OpenAI image provider."""

from __future__ import annotations

import base64
import logging
import math
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from image_generation_mcp.providers.openai import (
    _ARBITRARY_SIZE_MODELS,
    _DALLE3_SIZES,
    _GPT_IMAGE_SIZES,
    OpenAIImageProvider,
)
from image_generation_mcp.providers.types import (
    ImageContentPolicyError,
    ImageInputUnsupported,
    ImageProvider,
    ImageProviderConnectionError,
    ImageProviderError,
    InputImage,
)

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture
def _mock_openai():
    """Patch openai imports so tests don't need the real package."""
    with patch(
        "image_generation_mcp.providers.openai.OpenAIImageProvider._create_client"
    ):
        yield


def _openai_mock_response(b64: str = "aGk=") -> MagicMock:
    """Build a mock ``images.generate``/``images.edit`` response."""
    item = MagicMock()
    item.b64_json = b64
    item.revised_prompt = None
    resp = MagicMock()
    resp.data = [item]
    return resp


def _openai_provider_and_mock(
    model: str,
) -> Generator[tuple[OpenAIImageProvider, MagicMock], None, None]:
    """Yield a provider for ``model`` with mocked ``images.generate``/``.edit``."""
    mock_client = MagicMock()
    mock_client.images.generate = AsyncMock(return_value=_openai_mock_response())
    mock_client.images.edit = AsyncMock(return_value=_openai_mock_response())

    with patch(
        "image_generation_mcp.providers.openai.OpenAIImageProvider._create_client",
        return_value=mock_client,
    ):
        provider = OpenAIImageProvider(api_key="sk-test", model=model)

    yield provider, mock_client


@pytest.fixture
def openai_gpt2_provider_and_mock() -> Generator[
    tuple[OpenAIImageProvider, MagicMock], None, None
]:
    """Provider (model=gpt-image-2) with mocked ``images.generate``/``.edit``."""
    yield from _openai_provider_and_mock("gpt-image-2")


@pytest.fixture
def openai_gpt1_provider_and_mock() -> Generator[
    tuple[OpenAIImageProvider, MagicMock], None, None
]:
    """Provider (model=gpt-image-1) with mocked ``images.generate``/``.edit``."""
    yield from _openai_provider_and_mock("gpt-image-1")


@pytest.fixture
def openai_gpt2_dated_provider_and_mock() -> Generator[
    tuple[OpenAIImageProvider, MagicMock], None, None
]:
    """Provider (model=gpt-image-2-2026-04-21, the dated alias) with mocked
    ``images.generate``/``.edit``."""
    yield from _openai_provider_and_mock("gpt-image-2-2026-04-21")


@pytest.fixture
def openai_dalle3_provider_and_mock() -> Generator[
    tuple[OpenAIImageProvider, MagicMock], None, None
]:
    """Provider (model=dall-e-3) with mocked ``images.generate``/``.edit``."""
    yield from _openai_provider_and_mock("dall-e-3")


@pytest.fixture
def openai_discovery_mock() -> Generator[OpenAIImageProvider, None, None]:
    """Provider whose mocked ``models.list()`` reports every known image model."""
    mock_client = MagicMock()
    model_items = [
        MagicMock(id=model_id)
        for model_id in (
            "gpt-image-1",
            "gpt-image-1-mini",
            "gpt-image-1.5",
            "gpt-image-2",
            "chatgpt-image-latest",
            "dall-e-3",
            "dall-e-2",
        )
    ]
    mock_response = MagicMock()
    mock_response.data = model_items
    mock_client.models.list = AsyncMock(return_value=mock_response)

    with patch(
        "image_generation_mcp.providers.openai.OpenAIImageProvider._create_client",
        return_value=mock_client,
    ):
        provider = OpenAIImageProvider(api_key="sk-test")

    yield provider


@pytest.mark.usefixtures("_mock_openai")
class TestOpenAIProvider:
    """Tests for OpenAIImageProvider."""

    def test_implements_protocol(self) -> None:
        provider = OpenAIImageProvider(api_key="sk-test")
        assert isinstance(provider, ImageProvider)

    def test_default_model_is_gpt_image(self) -> None:
        provider = OpenAIImageProvider(api_key="sk-test")
        assert provider._model == "gpt-image-2"
        assert provider._is_gpt_image is True

    def test_dalle3_model(self) -> None:
        provider = OpenAIImageProvider(api_key="sk-test", model="dall-e-3")
        assert provider._is_gpt_image is False

    def test_gpt_image_sizes(self) -> None:
        # Sizes are computed per-call; verify the module-level table is correct.
        assert _GPT_IMAGE_SIZES["1:1"] == "1024x1024"
        assert _GPT_IMAGE_SIZES["16:9"] == "1536x1024"

    def test_dalle3_sizes(self) -> None:
        # Sizes are computed per-call; verify the module-level table is correct.
        assert _DALLE3_SIZES["16:9"] == "1792x1024"

    def test_unsupported_format_raises(self) -> None:
        with pytest.raises(ImageProviderError, match="Unsupported output_format"):
            OpenAIImageProvider(api_key="sk-test", output_format="gif")

    def test_dalle3_rejects_webp_format(self) -> None:
        with pytest.raises(ImageProviderError, match="dall-e-3 does not support"):
            OpenAIImageProvider(
                api_key="sk-test", model="dall-e-3", output_format="webp"
            )

    def test_dalle3_rejects_jpeg_format(self) -> None:
        with pytest.raises(ImageProviderError, match="dall-e-3 does not support"):
            OpenAIImageProvider(
                api_key="sk-test", model="dall-e-3", output_format="jpeg"
            )

    async def test_dalle3_generate_sends_response_format(self) -> None:
        provider = OpenAIImageProvider(api_key="sk-test", model="dall-e-3")

        b64_image = base64.b64encode(b"data").decode()
        mock_item = MagicMock()
        mock_item.b64_json = b64_image
        mock_item.revised_prompt = None
        mock_response = MagicMock()
        mock_response.data = [mock_item]

        provider._client = MagicMock()
        provider._client.images = MagicMock()
        provider._client.images.generate = AsyncMock(return_value=mock_response)

        await provider.generate("a landscape")

        call_kwargs = provider._client.images.generate.call_args.kwargs
        assert call_kwargs["response_format"] == "b64_json"
        assert "output_format" not in call_kwargs

    async def test_unsupported_aspect_ratio_raises(self) -> None:
        provider = OpenAIImageProvider(api_key="sk-test")
        with pytest.raises(ImageProviderError, match="Unsupported aspect_ratio"):
            await provider.generate("test", aspect_ratio="7:3")

    async def test_generate_success(self) -> None:
        provider = OpenAIImageProvider(api_key="sk-test")

        b64_image = base64.b64encode(b"fake-png-data").decode()
        mock_item = MagicMock()
        mock_item.b64_json = b64_image
        mock_item.revised_prompt = "enhanced prompt"

        mock_response = MagicMock()
        mock_response.data = [mock_item]

        provider._client = MagicMock()
        provider._client.images = MagicMock()
        provider._client.images.generate = AsyncMock(return_value=mock_response)

        result = await provider.generate("a cat", aspect_ratio="1:1")

        assert result.image_data == b"fake-png-data"
        assert result.content_type == "image/png"
        assert result.provider_metadata["model"] == "gpt-image-2"
        assert result.provider_metadata["quality"] == "standard"
        assert result.provider_metadata["api_quality"] == "auto"
        assert result.provider_metadata["revised_prompt"] == "enhanced prompt"

    async def test_negative_prompt_appended(self) -> None:
        provider = OpenAIImageProvider(api_key="sk-test")

        b64_image = base64.b64encode(b"data").decode()
        mock_item = MagicMock()
        mock_item.b64_json = b64_image
        mock_item.revised_prompt = None

        mock_response = MagicMock()
        mock_response.data = [mock_item]

        provider._client = MagicMock()
        provider._client.images = MagicMock()
        provider._client.images.generate = AsyncMock(return_value=mock_response)

        await provider.generate("a cat", negative_prompt="dogs")

        call_kwargs = provider._client.images.generate.call_args.kwargs
        assert "Avoid: dogs" in call_kwargs["prompt"]

    async def test_empty_response_raises(self) -> None:
        provider = OpenAIImageProvider(api_key="sk-test")

        mock_response = MagicMock()
        mock_response.data = []

        provider._client = MagicMock()
        provider._client.images = MagicMock()
        provider._client.images.generate = AsyncMock(return_value=mock_response)

        with pytest.raises(ImageProviderError, match="Empty response"):
            await provider.generate("test")

    async def test_quality_mapping_standard_maps_to_auto(self) -> None:
        """gpt-image-1 standard quality maps to OpenAI's 'auto'."""
        provider = OpenAIImageProvider(api_key="sk-test")

        b64_image = base64.b64encode(b"data").decode()
        mock_item = MagicMock()
        mock_item.b64_json = b64_image
        mock_item.revised_prompt = None
        mock_response = MagicMock()
        mock_response.data = [mock_item]

        provider._client = MagicMock()
        provider._client.images = MagicMock()
        provider._client.images.generate = AsyncMock(return_value=mock_response)

        await provider.generate("test", quality="standard")

        call_kwargs = provider._client.images.generate.call_args.kwargs
        assert call_kwargs["quality"] == "auto"

    async def test_quality_mapping_hd_maps_to_high(self) -> None:
        """gpt-image-1 hd quality maps to OpenAI's 'high'."""
        provider = OpenAIImageProvider(api_key="sk-test")

        b64_image = base64.b64encode(b"data").decode()
        mock_item = MagicMock()
        mock_item.b64_json = b64_image
        mock_item.revised_prompt = None
        mock_response = MagicMock()
        mock_response.data = [mock_item]

        provider._client = MagicMock()
        provider._client.images = MagicMock()
        provider._client.images.generate = AsyncMock(return_value=mock_response)

        await provider.generate("test", quality="hd")

        call_kwargs = provider._client.images.generate.call_args.kwargs
        assert call_kwargs["quality"] == "high"

    @pytest.mark.parametrize("background", ["transparent", "opaque"])
    async def test_gpt_image_2_does_not_send_background(self, background: str) -> None:
        """gpt-image-2 dropped transparency support — must NOT pass background.

        Sending the background parameter to gpt-image-2 returns a 400 from
        OpenAI. The guard is unconditional — neither the explicit
        ``transparent`` request nor the implicit ``opaque`` default leaks
        through. Parametrised to document both paths.
        """
        provider = OpenAIImageProvider(api_key="sk-test")

        b64_image = base64.b64encode(b"data").decode()
        mock_item = MagicMock()
        mock_item.b64_json = b64_image
        mock_item.revised_prompt = None
        mock_response = MagicMock()
        mock_response.data = [mock_item]

        provider._client = MagicMock()
        provider._client.images = MagicMock()
        provider._client.images.generate = AsyncMock(return_value=mock_response)

        await provider.generate("test", model="gpt-image-2", background=background)

        call_kwargs = provider._client.images.generate.call_args.kwargs
        assert call_kwargs["model"] == "gpt-image-2"
        assert "background" not in call_kwargs

    @pytest.mark.parametrize("background", ["transparent", "opaque"])
    async def test_chatgpt_image_latest_does_not_send_background(
        self, background: str
    ) -> None:
        """chatgpt-image-latest is treated as no-background (resolves to gpt-image-2).

        It routes through the gpt-image path (not DALL-E) but must NOT pass the
        background parameter, since its current target dropped transparency.
        """
        provider = OpenAIImageProvider(api_key="sk-test")

        b64_image = base64.b64encode(b"data").decode()
        mock_item = MagicMock()
        mock_item.b64_json = b64_image
        mock_item.revised_prompt = None
        mock_response = MagicMock()
        mock_response.data = [mock_item]

        provider._client = MagicMock()
        provider._client.images = MagicMock()
        provider._client.images.generate = AsyncMock(return_value=mock_response)

        await provider.generate(
            "test", model="chatgpt-image-latest", background=background
        )

        call_kwargs = provider._client.images.generate.call_args.kwargs
        assert call_kwargs["model"] == "chatgpt-image-latest"
        assert "background" not in call_kwargs
        # Routed through the gpt-image path: native format kwargs present,
        # not the DALL-E fallback (which would force response_format/size).
        assert "output_format" in call_kwargs

    async def test_gpt_image_1_5_still_sends_background(self) -> None:
        """gpt-image-1.5 keeps transparency support — background passes through."""
        provider = OpenAIImageProvider(api_key="sk-test")

        b64_image = base64.b64encode(b"data").decode()
        mock_item = MagicMock()
        mock_item.b64_json = b64_image
        mock_item.revised_prompt = None
        mock_response = MagicMock()
        mock_response.data = [mock_item]

        provider._client = MagicMock()
        provider._client.images = MagicMock()
        provider._client.images.generate = AsyncMock(return_value=mock_response)

        await provider.generate("test", model="gpt-image-1.5", background="transparent")

        call_kwargs = provider._client.images.generate.call_args.kwargs
        assert call_kwargs["model"] == "gpt-image-1.5"
        assert call_kwargs["background"] == "transparent"

    async def test_per_call_model_overrides_constructor(self) -> None:
        """Per-call model= overrides the constructor model in the API call."""
        # Constructor uses the default (gpt-image-2), per-call uses dall-e-3
        provider = OpenAIImageProvider(api_key="sk-test")

        b64_image = base64.b64encode(b"data").decode()
        mock_item = MagicMock()
        mock_item.b64_json = b64_image
        mock_item.revised_prompt = None
        mock_response = MagicMock()
        mock_response.data = [mock_item]

        provider._client = MagicMock()
        provider._client.images = MagicMock()
        provider._client.images.generate = AsyncMock(return_value=mock_response)

        await provider.generate("test", model="dall-e-3")

        call_kwargs = provider._client.images.generate.call_args.kwargs
        assert call_kwargs["model"] == "dall-e-3"

    async def test_per_call_model_switches_size_table_to_dalle3(self) -> None:
        """Switching to dall-e-3 per-call uses the DALL-E 3 size table."""
        # Constructor is gpt-image-1 (1536x1024 for 16:9)
        # dall-e-3 uses 1792x1024 for 16:9
        provider = OpenAIImageProvider(api_key="sk-test")

        b64_image = base64.b64encode(b"data").decode()
        mock_item = MagicMock()
        mock_item.b64_json = b64_image
        mock_item.revised_prompt = None
        mock_response = MagicMock()
        mock_response.data = [mock_item]

        provider._client = MagicMock()
        provider._client.images = MagicMock()
        provider._client.images.generate = AsyncMock(return_value=mock_response)

        await provider.generate("test", aspect_ratio="16:9", model="dall-e-3")

        call_kwargs = provider._client.images.generate.call_args.kwargs
        assert call_kwargs["size"] == "1792x1024"

    async def test_per_call_model_switches_size_table_to_gpt_image(self) -> None:
        """Switching to gpt-image-1 per-call uses the GPT image size table."""
        # Constructor is dall-e-3 (1792x1024 for 16:9)
        # gpt-image-1 uses 1536x1024 for 16:9
        provider = OpenAIImageProvider(api_key="sk-test", model="dall-e-3")

        b64_image = base64.b64encode(b"data").decode()
        mock_item = MagicMock()
        mock_item.b64_json = b64_image
        mock_item.revised_prompt = None
        mock_response = MagicMock()
        mock_response.data = [mock_item]

        provider._client = MagicMock()
        provider._client.images = MagicMock()
        provider._client.images.generate = AsyncMock(return_value=mock_response)

        await provider.generate("test", aspect_ratio="16:9", model="gpt-image-1")

        call_kwargs = provider._client.images.generate.call_args.kwargs
        assert call_kwargs["size"] == "1536x1024"

    async def test_per_call_model_metadata_reflects_effective_model(self) -> None:
        """Result metadata shows the per-call model, not the constructor model."""
        provider = OpenAIImageProvider(api_key="sk-test")

        b64_image = base64.b64encode(b"data").decode()
        mock_item = MagicMock()
        mock_item.b64_json = b64_image
        mock_item.revised_prompt = None
        mock_response = MagicMock()
        mock_response.data = [mock_item]

        provider._client = MagicMock()
        provider._client.images = MagicMock()
        provider._client.images.generate = AsyncMock(return_value=mock_response)

        result = await provider.generate("test", model="dall-e-3")

        assert result.provider_metadata["model"] == "dall-e-3"

    async def test_per_call_dalle3_uses_response_format(self) -> None:
        """Switching to dall-e-3 per-call sets response_format, not output_format."""
        provider = OpenAIImageProvider(api_key="sk-test")  # default gpt-image-2

        b64_image = base64.b64encode(b"data").decode()
        mock_item = MagicMock()
        mock_item.b64_json = b64_image
        mock_item.revised_prompt = None
        mock_response = MagicMock()
        mock_response.data = [mock_item]

        provider._client = MagicMock()
        provider._client.images = MagicMock()
        provider._client.images.generate = AsyncMock(return_value=mock_response)

        result = await provider.generate("test", model="dall-e-3")

        call_kwargs = provider._client.images.generate.call_args.kwargs
        assert call_kwargs.get("response_format") == "b64_json"
        assert "output_format" not in call_kwargs
        assert result.content_type == "image/png"  # dall-e-3 always produces PNG


class TestErrorHandling:
    """Tests for OpenAI error conversion."""

    @pytest.mark.usefixtures("_mock_openai")
    async def test_connection_error(self) -> None:
        provider = OpenAIImageProvider(api_key="sk-test")

        from openai import APIConnectionError

        provider._client = MagicMock()
        provider._client.images = MagicMock()
        provider._client.images.generate = AsyncMock(
            side_effect=APIConnectionError(request=MagicMock())
        )

        with pytest.raises(ImageProviderConnectionError):
            await provider.generate("test")

    @pytest.mark.usefixtures("_mock_openai")
    async def test_content_policy_error(self) -> None:
        provider = OpenAIImageProvider(api_key="sk-test")

        from openai import APIStatusError

        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {"error": {"message": "content_policy"}}

        provider._client = MagicMock()
        provider._client.images = MagicMock()
        provider._client.images.generate = AsyncMock(
            side_effect=APIStatusError(
                message="content_policy violation",
                response=mock_response,
                body=None,
            )
        )

        with pytest.raises(ImageContentPolicyError):
            await provider.generate("test")

    @pytest.mark.usefixtures("_mock_openai")
    async def test_content_policy_error_structured_body(self) -> None:
        """Structured body[error][code] path triggers content policy error."""
        provider = OpenAIImageProvider(api_key="sk-test")

        from openai import APIStatusError

        mock_response = MagicMock()
        mock_response.status_code = 400

        provider._client = MagicMock()
        provider._client.images = MagicMock()
        provider._client.images.generate = AsyncMock(
            side_effect=APIStatusError(
                message="Your request was rejected",
                response=mock_response,
                body={
                    "error": {"code": "content_policy_violation", "message": "rejected"}
                },
            )
        )

        with pytest.raises(ImageContentPolicyError):
            await provider.generate("test")


@pytest.mark.usefixtures("_mock_openai")
async def test_openai_rejects_reference_images_for_non_edit_model() -> None:
    """dall-e-3 has no edit endpoint -> reference_images raises ImageInputUnsupported."""
    provider = OpenAIImageProvider(api_key="sk-test", model="dall-e-3")

    with pytest.raises(ImageInputUnsupported):
        await provider.generate(
            "a cat",
            reference_images=[InputImage(data=b"x", content_type="image/png")],
        )


@pytest.mark.usefixtures("_mock_openai")
class TestOpenAIEdit:
    """Tests for the OpenAI images.edit (image-to-image / composition) path."""

    def _mk_provider(self, model: str = "gpt-image-1") -> OpenAIImageProvider:
        return OpenAIImageProvider(api_key="sk-test", model=model)

    def _mk_response(self, b64: str = "aGk=") -> MagicMock:
        item = MagicMock()
        item.b64_json = b64
        resp = MagicMock()
        resp.data = [item]
        return resp

    async def test_edit_with_single_reference_calls_images_edit(self) -> None:
        provider = self._mk_provider()
        provider._client = MagicMock()
        provider._client.images = MagicMock()
        provider._client.images.edit = AsyncMock(return_value=self._mk_response())

        ref = InputImage(data=b"png-bytes", content_type="image/png", source_id="a")
        result = await provider.generate("make it blue", reference_images=[ref])

        provider._client.images.edit.assert_awaited_once()
        kwargs = provider._client.images.edit.call_args.kwargs
        assert kwargs["model"] == "gpt-image-1"
        assert isinstance(kwargs["image"], list) and len(kwargs["image"]) == 1
        # file tuple: (filename, data, content_type)
        _fname, data, ctype = kwargs["image"][0]
        assert data == b"png-bytes"
        assert ctype == "image/png"
        assert result.provider_metadata.get("edited") is True

    async def test_edit_with_multiple_references(self) -> None:
        provider = self._mk_provider()
        provider._client = MagicMock()
        provider._client.images = MagicMock()
        provider._client.images.edit = AsyncMock(return_value=self._mk_response())
        refs = [
            InputImage(data=b"a", content_type="image/png"),
            InputImage(data=b"b", content_type="image/jpeg"),
        ]
        await provider.generate("compose", reference_images=refs)
        image_arg = provider._client.images.edit.call_args.kwargs["image"]
        assert len(image_arg) == 2
        # filenames carry the content-type's extension
        assert image_arg[0][0].endswith(".png")
        assert image_arg[1][0].endswith(".jpg")

    async def test_edit_too_many_references_raises(self) -> None:
        from image_generation_mcp.providers.types import TooManyInputImages

        provider = self._mk_provider()
        provider._client = MagicMock()
        refs = [InputImage(data=b"x", content_type="image/png") for _ in range(17)]
        with pytest.raises(TooManyInputImages):
            await provider.generate("x", reference_images=refs)

    async def test_edit_negative_prompt_appended(self) -> None:
        provider = self._mk_provider()
        provider._client = MagicMock()
        provider._client.images = MagicMock()
        provider._client.images.edit = AsyncMock(return_value=self._mk_response())
        await provider.generate(
            "x",
            negative_prompt="dogs",
            reference_images=[InputImage(data=b"a", content_type="image/png")],
        )
        assert "Avoid: dogs" in provider._client.images.edit.call_args.kwargs["prompt"]

    async def test_edit_empty_response_raises(self) -> None:
        provider = self._mk_provider()
        provider._client = MagicMock()
        provider._client.images = MagicMock()
        empty = MagicMock()
        empty.data = []
        provider._client.images.edit = AsyncMock(return_value=empty)
        with pytest.raises(ImageProviderError, match="Empty response"):
            await provider.generate(
                "x", reference_images=[InputImage(data=b"a", content_type="image/png")]
            )

    async def test_edit_missing_b64_raises(self) -> None:
        provider = self._mk_provider()
        provider._client = MagicMock()
        provider._client.images = MagicMock()
        provider._client.images.edit = AsyncMock(return_value=self._mk_response(b64=""))
        with pytest.raises(ImageProviderError, match="No image data"):
            await provider.generate(
                "x", reference_images=[InputImage(data=b"a", content_type="image/png")]
            )

    async def test_edit_api_error_is_funneled(self) -> None:
        from openai import APIConnectionError

        provider = self._mk_provider()
        provider._client = MagicMock()
        provider._client.images = MagicMock()
        provider._client.images.edit = AsyncMock(
            side_effect=APIConnectionError(request=MagicMock())
        )
        with pytest.raises(ImageProviderConnectionError):
            await provider.generate(
                "x", reference_images=[InputImage(data=b"a", content_type="image/png")]
            )

    async def test_edit_per_call_dalle_override_rejected(self) -> None:
        provider = self._mk_provider("gpt-image-1")
        with pytest.raises(ImageInputUnsupported):
            await provider.generate(
                "x",
                model="dall-e-3",
                reference_images=[InputImage(data=b"a", content_type="image/png")],
            )

    async def test_edit_unsupported_content_type_raises(self) -> None:
        provider = self._mk_provider()
        with pytest.raises(
            ImageProviderError, match="Unsupported input image content type"
        ):
            await provider.generate(
                "x",
                reference_images=[InputImage(data=b"a", content_type="image/gif")],
            )

    async def test_edit_exactly_16_references_accepted(self) -> None:
        provider = self._mk_provider()
        provider._client = MagicMock()
        provider._client.images = MagicMock()
        provider._client.images.edit = AsyncMock(return_value=self._mk_response())
        refs = [InputImage(data=b"x", content_type="image/png") for _ in range(16)]
        await provider.generate("x", reference_images=refs)
        provider._client.images.edit.assert_awaited_once()
        assert len(provider._client.images.edit.call_args.kwargs["image"]) == 16

    async def test_edit_gpt_image_2_omits_background(self) -> None:
        provider = self._mk_provider("gpt-image-2")
        provider._client = MagicMock()
        provider._client.images = MagicMock()
        provider._client.images.edit = AsyncMock(return_value=self._mk_response())
        await provider.generate(
            "x",
            background="transparent",
            reference_images=[InputImage(data=b"a", content_type="image/png")],
        )
        # gpt-image-2 does not accept background; it is omitted from the request.
        assert "background" not in provider._client.images.edit.call_args.kwargs

    async def test_generate_ignores_strength(self) -> None:
        """Passing strength=0.5 is accepted and not forwarded to images.generate kwargs."""
        provider = self._mk_provider()
        provider._client = MagicMock()
        provider._client.images = MagicMock()
        provider._client.images.generate = AsyncMock(return_value=self._mk_response())

        result = await provider.generate("a cat", aspect_ratio="1:1", strength=0.5)

        assert result.image_data == b"hi"  # _mk_response uses b64="aGk=" → b"hi"
        # strength must NOT be forwarded to the OpenAI SDK call
        call_kwargs = provider._client.images.generate.call_args.kwargs
        assert "strength" not in call_kwargs

    async def test_edit_with_mask_sends_mask_file(self) -> None:
        """When a mask is provided, images.edit receives a mask kwarg as a file tuple."""
        provider = self._mk_provider()
        provider._client = MagicMock()
        provider._client.images = MagicMock()
        provider._client.images.edit = AsyncMock(return_value=self._mk_response())

        ref = InputImage(data=b"img", content_type="image/png")
        msk = InputImage(data=b"msk", content_type="image/png")
        await provider.generate(
            "inpaint",
            reference_images=[ref],
            mask=msk,
        )

        provider._client.images.edit.assert_awaited_once()
        kwargs = provider._client.images.edit.call_args.kwargs
        assert "mask" in kwargs
        _fname, data, ctype = kwargs["mask"]
        assert data == b"msk"
        assert ctype == "image/png"
        assert _fname.endswith(".png")
        # image list is still the references
        assert isinstance(kwargs["image"], list) and len(kwargs["image"]) == 1

    async def test_edit_without_mask_omits_mask_kwarg(self) -> None:
        """When no mask is provided, images.edit is called without a mask kwarg."""
        provider = self._mk_provider()
        provider._client = MagicMock()
        provider._client.images = MagicMock()
        provider._client.images.edit = AsyncMock(return_value=self._mk_response())

        await provider.generate(
            "edit",
            reference_images=[InputImage(data=b"img", content_type="image/png")],
        )

        provider._client.images.edit.assert_awaited_once()
        kwargs = provider._client.images.edit.call_args.kwargs
        assert "mask" not in kwargs

    async def test_generate_mask_without_reference_images_raises(self) -> None:
        """A mask on the text-to-image path (no reference_images) is rejected."""
        provider = self._mk_provider()
        with pytest.raises(ImageProviderError, match="mask requires reference_images"):
            await provider.generate(
                "txt2img with a stray mask",
                mask=InputImage(data=b"msk", content_type="image/png"),
            )


def _parse(size: str) -> tuple[int, int]:
    w, h = size.split("x")
    return int(w), int(h)


@pytest.mark.parametrize(
    "table",
    [
        "high",
        "max",
    ],
)
def test_gpt_image_2_tables_satisfy_constraints(table: str) -> None:
    from image_generation_mcp.providers.openai import (
        _GPT_IMAGE_2_HIGH_SIZES,
        _GPT_IMAGE_2_MAX_SIZES,
    )

    sizes = _GPT_IMAGE_2_HIGH_SIZES if table == "high" else _GPT_IMAGE_2_MAX_SIZES
    exact = {"1:1": 1.0, "16:9": 16 / 9, "9:16": 9 / 16, "3:2": 3 / 2, "2:3": 2 / 3}
    for ratio, size in sizes.items():
        w, h = _parse(size)
        assert w % 16 == 0 and h % 16 == 0, f"{ratio} not /16"
        assert max(w, h) <= 3840, f"{ratio} edge >3840"
        assert 655_360 <= w * h <= 8_294_400, f"{ratio} px out of range"
        assert max(w, h) / min(w, h) <= 3.0 + 1e-9, f"{ratio} ratio >3:1"
        assert math.isclose(w / h, exact[ratio], rel_tol=1e-9), f"{ratio} not exact"


async def test_gpt_image_2_max_selects_max_table(
    openai_gpt2_provider_and_mock: tuple[OpenAIImageProvider, MagicMock],
) -> None:
    provider, mock = openai_gpt2_provider_and_mock
    result = await provider.generate("x", aspect_ratio="16:9", resolution="max")
    assert mock.images.generate.call_args.kwargs["size"] == "3840x2160"
    assert result.provider_metadata["resolution"] == "max"


async def test_gpt_image_2_high_selects_high_table(
    openai_gpt2_provider_and_mock: tuple[OpenAIImageProvider, MagicMock],
) -> None:
    provider, mock = openai_gpt2_provider_and_mock
    await provider.generate("x", aspect_ratio="1:1", resolution="high")
    assert mock.images.generate.call_args.kwargs["size"] == "1920x1920"


async def test_non_gpt_image_2_ignores_resolution(
    openai_gpt1_provider_and_mock: tuple[OpenAIImageProvider, MagicMock],
) -> None:
    provider, mock = openai_gpt1_provider_and_mock  # model gpt-image-1
    result = await provider.generate("x", aspect_ratio="1:1", resolution="max")
    assert mock.images.generate.call_args.kwargs["size"] == "1024x1024"
    assert result.provider_metadata["resolution"] == "standard"


async def test_non_gpt_image_2_logs_resolution_clamped_at_warning(
    openai_gpt1_provider_and_mock: tuple[OpenAIImageProvider, MagicMock],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A dropped tier request on a non-arbitrary-size model logs at WARNING.

    WARNING mirrors Gemini's resolution_clamped log (both are paid,
    tier-capable providers where a silent downgrade is worth flagging).
    """
    provider, _mock = openai_gpt1_provider_and_mock  # model gpt-image-1
    with caplog.at_level(logging.WARNING):
        await provider.generate("x", aspect_ratio="1:1", resolution="max")
    assert (
        "resolution_clamped provider=openai model=gpt-image-1 "
        "requested=max effective=standard" in caplog.text
    )


async def test_gpt_image_2_does_not_log_resolution_clamped(
    openai_gpt2_provider_and_mock: tuple[OpenAIImageProvider, MagicMock],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """gpt-image-2 honors high/max natively, so no downgrade is logged."""
    provider, _mock = openai_gpt2_provider_and_mock
    with caplog.at_level(logging.WARNING):
        await provider.generate("x", aspect_ratio="1:1", resolution="max")
    assert "resolution_clamped" not in caplog.text


async def test_non_gpt_image_2_does_not_log_for_standard_resolution(
    openai_gpt1_provider_and_mock: tuple[OpenAIImageProvider, MagicMock],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """No downgrade log fires when the requested tier is already 'standard'."""
    provider, _mock = openai_gpt1_provider_and_mock
    with caplog.at_level(logging.WARNING):
        await provider.generate("x", aspect_ratio="1:1", resolution="standard")
    assert "resolution_clamped" not in caplog.text


async def test_dalle3_logs_resolution_clamped_at_warning(
    openai_dalle3_provider_and_mock: tuple[OpenAIImageProvider, MagicMock],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """dall-e-3 has no tier table either -- the else branch must log too.

    Pairs with test_non_gpt_image_2_logs_resolution_clamped_at_warning:
    that test covers the gpt-image (non-arbitrary-size) branch of
    _gpt_image_request; this one covers the sibling dall-e (else) branch
    in generate() itself, which has its own size table and previously had
    no log at all.
    """
    provider, _mock = openai_dalle3_provider_and_mock
    with caplog.at_level(logging.WARNING):
        result = await provider.generate("x", aspect_ratio="1:1", resolution="max")
    assert (
        "resolution_clamped provider=openai model=dall-e-3 "
        "requested=max effective=standard" in caplog.text
    )
    assert result.provider_metadata["resolution"] == "standard"


async def test_dalle3_does_not_log_for_standard_resolution(
    openai_dalle3_provider_and_mock: tuple[OpenAIImageProvider, MagicMock],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """No downgrade log fires on dall-e-3 when the requested tier is 'standard'."""
    provider, _mock = openai_dalle3_provider_and_mock
    with caplog.at_level(logging.WARNING):
        await provider.generate("x", aspect_ratio="1:1", resolution="standard")
    assert "resolution_clamped" not in caplog.text


async def test_gpt_image_2_dated_alias_selects_max_table(
    openai_gpt2_dated_provider_and_mock: tuple[OpenAIImageProvider, MagicMock],
) -> None:
    """The dated gpt-image-2-2026-04-21 alias honors high/max like gpt-image-2.

    Guards the "gpt-image-2-2026-04-21 is gpt-image-2's dated snapshot, same
    sizing behavior" claim in _ARBITRARY_SIZE_MODELS' comment against a
    future refactor that matches on the bare model name only.
    """
    provider, mock = openai_gpt2_dated_provider_and_mock
    result = await provider.generate("x", aspect_ratio="16:9", resolution="max")
    assert mock.images.generate.call_args.kwargs["size"] == "3840x2160"
    assert result.provider_metadata["resolution"] == "max"


async def test_gpt_image_2_edit_threads_resolution(
    openai_gpt2_provider_and_mock: tuple[OpenAIImageProvider, MagicMock],
) -> None:
    provider, mock = openai_gpt2_provider_and_mock

    ref = InputImage(data=b"\x89PNG", content_type="image/png")
    result = await provider.generate(
        "x", aspect_ratio="16:9", resolution="max", reference_images=[ref]
    )
    assert mock.images.edit.call_args.kwargs["size"] == "3840x2160"
    assert result.provider_metadata["resolution"] == "max"


async def test_gpt_image_2_capability_reports_resolutions(
    openai_discovery_mock: OpenAIImageProvider,
) -> None:
    provider = openai_discovery_mock  # discovery returns gpt-image-2 in model list
    caps = await provider.discover_capabilities()
    gpt2 = next(m for m in caps.models if m.model_id == "gpt-image-2")
    assert gpt2.supported_resolutions == ("standard", "high", "max")
    assert gpt2.max_resolution == 3840


async def test_advertised_high_max_implies_arbitrary_size_membership(
    openai_discovery_mock: OpenAIImageProvider,
) -> None:
    """Single-source-of-truth guard: advertised implies deliverable.

    Any discovered model whose supported_resolutions includes "high" or
    "max" must be in _ARBITRARY_SIZE_MODELS -- the same membership check
    that governs actual size-table selection at generate time (see
    _effective_resolution / _gpt_image_request). Prevents
    discover_capabilities from silently drifting out of sync with the
    runtime by re-introducing a hand-written high/max literal.

    Deliberately NOT bidirectional: gpt-image-2-2026-04-21 is in
    _ARBITRARY_SIZE_MODELS by design but has no discovered capability
    entry of its own (issue #338, out of scope here) -- asserting the
    reverse direction would wrongly fail on that gap.
    """
    provider = openai_discovery_mock
    caps = await provider.discover_capabilities()
    for model in caps.models:
        if (
            "high" in model.supported_resolutions
            or "max" in model.supported_resolutions
        ):
            assert model.model_id in _ARBITRARY_SIZE_MODELS, (
                f"{model.model_id} advertises high/max but is not in "
                "_ARBITRARY_SIZE_MODELS, so generate() cannot deliver it"
            )
