"""Tests for generate_image and show_image MCP tools.

Covers:
- generate_image returns TextContent + ResourceLink only (no ImageContent)
- generate_image has no AppConfig (viewer moved to show_image)
- show_image returns ImageContent + TextContent
- show_image with format conversion
- show_image with resize (width-only, height-only)
- show_image with crop (width+height)
- show_image metadata includes model field from provider_metadata
"""

from __future__ import annotations

import asyncio
import base64
import io
import json
import unittest.mock
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import pytest

if TYPE_CHECKING:
    from pathlib import Path
from fastmcp import FastMCP
from fastmcp.tools import ToolResult
from mcp.types import ImageContent, ResourceLink, TextContent
from PIL import Image

from image_generation_mcp.domain import ImageService
from image_generation_mcp.providers.capabilities import (
    ModelCapabilities,
    ProviderCapabilities,
)
from image_generation_mcp.providers.model_styles import MODEL_STYLES
from image_generation_mcp.providers.placeholder import PlaceholderImageProvider
from image_generation_mcp.providers.types import ImageResult
from image_generation_mcp.tools import register_tools
from tests._helpers import get_tool_including_app_only

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def service(tmp_path: Path) -> ImageService:
    """ImageService with a temp scratch directory, placeholder provider."""
    svc = ImageService(scratch_dir=tmp_path)
    svc.register_provider("placeholder", PlaceholderImageProvider())
    return svc


@pytest.fixture
def registered_image(service: ImageService) -> tuple[ImageService, str]:
    """Register a placeholder image and return (service, image_id)."""
    result = asyncio.run(
        PlaceholderImageProvider().generate("show test", aspect_ratio="1:1")
    )
    record = service.register_image(result, "placeholder", prompt="show test")
    return service, record.id


def _make_large_png(width: int = 1024, height: int = 768) -> bytes:
    """Create a synthetic PNG larger than 512px for thumbnail cap tests."""
    img = Image.new("RGB", (width, height), color=(100, 150, 200))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def large_registered_image(service: ImageService) -> tuple[ImageService, str]:
    """Register a 1024x768 synthetic image and return (service, image_id)."""
    png_data = _make_large_png(1024, 768)
    result = ImageResult(image_data=png_data, content_type="image/png")
    record = service.register_image(result, "test", prompt="large test")
    return service, record.id


# ---------------------------------------------------------------------------
# generate_image: return shape
# ---------------------------------------------------------------------------


class TestGenerateImageReturnShape:
    """generate_image must return TextContent + ResourceLink, no ImageContent."""

    async def _call_generate(self, service: ImageService) -> ToolResult:
        mcp = FastMCP("test")
        register_tools(mcp)
        tool = await mcp.get_tool("generate_image")
        assert tool is not None

        ctx = MagicMock()
        ctx.report_progress = AsyncMock()
        ctx.info = AsyncMock()
        cfg = MagicMock()
        cfg.paid_providers = frozenset()

        return await tool.fn(
            prompt="test image",
            provider="placeholder",
            service=service,
            config=cfg,
            ctx=ctx,
        )

    async def test_returns_text_content(self, service: ImageService) -> None:
        result = await self._call_generate(service)
        text_items = [c for c in result.content if isinstance(c, TextContent)]
        assert len(text_items) == 1
        metadata = json.loads(text_items[0].text)
        assert "image_id" in metadata
        assert "original_uri" in metadata
        assert metadata["status"] == "generating"
        assert "dimensions" not in metadata
        assert "original_size_bytes" not in metadata

    async def test_returns_resource_link(self, service: ImageService) -> None:
        result = await self._call_generate(service)
        link_items = [c for c in result.content if isinstance(c, ResourceLink)]
        assert len(link_items) == 1
        assert str(link_items[0].uri).startswith("image://")
        assert link_items[0].name == "Generated image (generating)"

    async def test_no_image_content_in_result(self, service: ImageService) -> None:
        result = await self._call_generate(service)
        image_items = [c for c in result.content if isinstance(c, ImageContent)]
        assert image_items == [], "generate_image must not return ImageContent"

    async def test_no_thumbnail_size_bytes_in_metadata(
        self, service: ImageService
    ) -> None:
        result = await self._call_generate(service)
        text_items = [c for c in result.content if isinstance(c, TextContent)]
        metadata = json.loads(text_items[0].text)
        assert "thumbnail_size_bytes" not in metadata

    async def test_resource_link_uri_matches_image_id(
        self, service: ImageService
    ) -> None:
        result = await self._call_generate(service)
        text_items = [c for c in result.content if isinstance(c, TextContent)]
        metadata = json.loads(text_items[0].text)
        image_id = metadata["image_id"]

        link_items = [c for c in result.content if isinstance(c, ResourceLink)]
        assert str(link_items[0].uri) == f"image://{image_id}/view"

    async def test_generate_image_background_completes(
        self, service: ImageService
    ) -> None:
        """Background task completes and persists an ImageRecord (covers _start_background_generation)."""
        result = await self._call_generate(service)
        text_items = [c for c in result.content if isinstance(c, TextContent)]
        image_id = json.loads(text_items[0].text)["image_id"]

        pending = None
        for _ in range(100):
            pending = service.get_pending(image_id)
            if pending and pending.status in ("completed", "failed"):
                break
            await asyncio.sleep(0.02)

        assert pending is not None and pending.status == "completed"
        assert service.get_image(image_id).id == image_id


# ---------------------------------------------------------------------------
# generate_image: tool registration properties
# ---------------------------------------------------------------------------


class TestGenerateImageRegistration:
    """generate_image tool registration properties."""

    async def test_no_app_config(self) -> None:
        """generate_image must not carry AppConfig — viewer is on show_image."""
        mcp = FastMCP("test")
        register_tools(mcp)

        tool = await mcp.get_tool("generate_image")
        assert tool is not None
        # meta is None or ui key is absent
        if tool.meta is not None:
            assert tool.meta.get("ui") is None

    async def test_tagged_write(self) -> None:
        mcp = FastMCP("test")
        register_tools(mcp)

        tool = await mcp.get_tool("generate_image")
        assert tool is not None
        assert "write" in tool.tags

    async def test_docstring_mentions_style_profile_and_warnings(self) -> None:
        """Docstring must point the LLM at style_profile fields and the warnings array."""
        mcp = FastMCP("test")
        register_tools(mcp)

        tool = await mcp.get_tool("generate_image")
        assert tool is not None
        doc = tool.description
        assert doc is not None
        assert "style_profile" in doc
        assert "warnings" in doc


class TestToolDescriptionIngestionHints:
    """Tool descriptions must point the LLM at the ingestion round-trip."""

    async def test_transform_image_description_names_ingestion_tools(self) -> None:
        mcp = FastMCP("test")
        register_tools(mcp)
        tool = await mcp.get_tool("transform_image")
        assert tool is not None
        doc = tool.description
        assert doc is not None
        # A reference image_id can be an externally-imported image; the hint
        # names all three ingestion tools, so pin all three against removal.
        assert "fetch_image" in doc
        assert "ingest_base64_image" in doc
        assert "create_upload_link" in doc

    async def test_fetch_image_description_names_transform_image(self) -> None:
        mcp = FastMCP("test")
        register_tools(mcp)
        tool = await mcp.get_tool("fetch_image")
        assert tool is not None
        doc = tool.description
        assert doc is not None
        assert "transform_image" in doc

    async def test_ingest_base64_image_description_names_transform_image(self) -> None:
        mcp = FastMCP("test")
        register_tools(mcp)
        tool = await mcp.get_tool("ingest_base64_image")
        assert tool is not None
        doc = tool.description
        assert doc is not None
        assert "transform_image" in doc


# ---------------------------------------------------------------------------
# show_image: tool registration properties
# ---------------------------------------------------------------------------


class TestShowImageRegistration:
    """show_image tool registration properties."""

    async def test_registered(self) -> None:
        mcp = FastMCP("test")
        register_tools(mcp)

        tool = await mcp.get_tool("show_image")
        assert tool is not None

    async def test_not_tagged_write(self) -> None:
        """show_image is a read operation — must not carry the 'write' tag."""
        mcp = FastMCP("test")
        register_tools(mcp)

        tool = await mcp.get_tool("show_image")
        assert tool is not None
        assert "write" not in tool.tags

    async def test_has_app_config(self) -> None:
        """show_image carries AppConfig pointing at the image viewer."""
        mcp = FastMCP("test")
        register_tools(mcp)

        tool = await mcp.get_tool("show_image")
        assert tool is not None
        assert tool.meta is not None
        app_data = tool.meta.get("ui")
        assert app_data is not None
        assert app_data["resourceUri"] == "ui://image-viewer/view.html"


# ---------------------------------------------------------------------------
# show_image: functional tests
# ---------------------------------------------------------------------------


class TestShowImageBasic:
    """show_image returns image bytes and metadata for a plain URI."""

    async def _call_show(
        self, service: ImageService, image_id: str, uri_suffix: str = ""
    ) -> ToolResult:
        mcp = FastMCP("test")
        register_tools(mcp)
        tool = await mcp.get_tool("show_image")
        assert tool is not None
        return await tool.fn(
            uri=f"image://{image_id}/view{uri_suffix}",
            service=service,
        )

    async def test_returns_image_content(
        self, registered_image: tuple[ImageService, str]
    ) -> None:
        service, image_id = registered_image
        result = await self._call_show(service, image_id)
        image_items = [c for c in result.content if isinstance(c, ImageContent)]
        assert len(image_items) == 1
        assert image_items[0].data  # non-empty base64
        # ImageContent is always a WebP thumbnail capped at 512px
        assert image_items[0].mimeType == "image/webp"
        raw = base64.b64decode(image_items[0].data)
        img = Image.open(io.BytesIO(raw))
        assert max(img.size) <= 512

    async def test_returns_text_metadata(
        self, registered_image: tuple[ImageService, str]
    ) -> None:
        service, image_id = registered_image
        result = await self._call_show(service, image_id)
        text_items = [c for c in result.content if isinstance(c, TextContent)]
        assert len(text_items) == 1
        meta = json.loads(text_items[0].text)
        assert meta["image_id"] == image_id
        assert "dimensions" in meta
        assert "thumbnail_dimensions" in meta
        assert "format" in meta
        assert "transforms_applied" in meta

    async def test_no_transforms_applied_for_plain_uri(
        self, registered_image: tuple[ImageService, str]
    ) -> None:
        service, image_id = registered_image
        result = await self._call_show(service, image_id)
        text_items = [c for c in result.content if isinstance(c, TextContent)]
        meta = json.loads(text_items[0].text)
        assert meta["transforms_applied"] == {}


class TestShowImageFormatConversion:
    """show_image with format query param converts the image."""

    async def _call_show(
        self, service: ImageService, image_id: str, query: str
    ) -> ToolResult:
        mcp = FastMCP("test")
        register_tools(mcp)
        tool = await mcp.get_tool("show_image")
        return await tool.fn(
            uri=f"image://{image_id}/view?{query}",
            service=service,
        )

    async def test_format_webp(
        self, registered_image: tuple[ImageService, str]
    ) -> None:
        service, image_id = registered_image
        result = await self._call_show(service, image_id, "format=webp")

        # ImageContent is always a WebP thumbnail (capped at 512px)
        image_items = [c for c in result.content if isinstance(c, ImageContent)]
        assert image_items[0].mimeType == "image/webp"
        raw = base64.b64decode(image_items[0].data)
        img = Image.open(io.BytesIO(raw))
        assert img.format == "WEBP"
        assert max(img.size) <= 512

        # Metadata records the requested transform
        text_items = [c for c in result.content if isinstance(c, TextContent)]
        meta = json.loads(text_items[0].text)
        assert meta["transforms_applied"]["format"] == "webp"
        assert "thumbnail_dimensions" in meta

    async def test_format_jpeg_metadata(
        self, registered_image: tuple[ImageService, str]
    ) -> None:
        """Format conversion is recorded in metadata; thumbnail is still WebP."""
        service, image_id = registered_image
        result = await self._call_show(service, image_id, "format=jpeg")

        # ImageContent is always WebP thumbnail regardless of requested format
        image_items = [c for c in result.content if isinstance(c, ImageContent)]
        assert image_items[0].mimeType == "image/webp"

        # Metadata records the requested jpeg conversion
        text_items = [c for c in result.content if isinstance(c, TextContent)]
        meta = json.loads(text_items[0].text)
        assert meta["transforms_applied"]["format"] == "jpeg"
        assert meta["format"] == "image/jpeg"


class TestShowImageResize:
    """show_image with width/height query params resizes the image."""

    async def _call_show(
        self, service: ImageService, image_id: str, query: str
    ) -> ToolResult:
        mcp = FastMCP("test")
        register_tools(mcp)
        tool = await mcp.get_tool("show_image")
        return await tool.fn(
            uri=f"image://{image_id}/view?{query}",
            service=service,
        )

    async def test_width_only_resize(
        self, registered_image: tuple[ImageService, str]
    ) -> None:
        service, image_id = registered_image
        result = await self._call_show(service, image_id, "width=100")

        # ImageContent is a WebP thumbnail; 100px < 512px cap so resize preserved
        image_items = [c for c in result.content if isinstance(c, ImageContent)]
        assert image_items[0].mimeType == "image/webp"
        raw = base64.b64decode(image_items[0].data)
        img = Image.open(io.BytesIO(raw))
        assert img.width == 100  # resize applied; still under 512px cap

        # Metadata records the requested width transform
        text_items = [c for c in result.content if isinstance(c, TextContent)]
        meta = json.loads(text_items[0].text)
        assert meta["transforms_applied"]["width"] == 100
        assert meta["dimensions"][0] == 100
        assert "thumbnail_dimensions" in meta

    async def test_height_only_resize(
        self, registered_image: tuple[ImageService, str]
    ) -> None:
        service, image_id = registered_image
        result = await self._call_show(service, image_id, "height=60")

        # ImageContent is a WebP thumbnail; 60px < 512px cap so resize preserved
        image_items = [c for c in result.content if isinstance(c, ImageContent)]
        assert image_items[0].mimeType == "image/webp"
        raw = base64.b64decode(image_items[0].data)
        img = Image.open(io.BytesIO(raw))
        assert img.height == 60  # resize applied; still under 512px cap

        # Metadata records the requested height transform
        text_items = [c for c in result.content if isinstance(c, TextContent)]
        meta = json.loads(text_items[0].text)
        assert meta["transforms_applied"]["height"] == 60
        assert meta["dimensions"][1] == 60
        assert "thumbnail_dimensions" in meta

    async def test_crop_width_and_height(
        self, registered_image: tuple[ImageService, str]
    ) -> None:
        service, image_id = registered_image
        result = await self._call_show(service, image_id, "width=80&height=80")

        # ImageContent is a WebP thumbnail; 80px < 512px cap so crop preserved
        image_items = [c for c in result.content if isinstance(c, ImageContent)]
        assert image_items[0].mimeType == "image/webp"
        raw = base64.b64decode(image_items[0].data)
        img = Image.open(io.BytesIO(raw))
        assert img.size == (80, 80)  # crop applied; still under 512px cap

        # Metadata records the requested crop
        text_items = [c for c in result.content if isinstance(c, TextContent)]
        meta = json.loads(text_items[0].text)
        assert meta["transforms_applied"]["width"] == 80
        assert meta["transforms_applied"]["height"] == 80
        assert meta["dimensions"] == [80, 80]


class TestShowImageThumbnailCap:
    """show_image caps ImageContent to a 512px WebP thumbnail for large images."""

    async def _call_show(
        self, service: ImageService, image_id: str, uri_suffix: str = ""
    ) -> ToolResult:
        mcp = FastMCP("test")
        register_tools(mcp)
        tool = await mcp.get_tool("show_image")
        return await tool.fn(
            uri=f"image://{image_id}/view{uri_suffix}",
            service=service,
        )

    async def test_large_image_downscaled_to_512(
        self, large_registered_image: tuple[ImageService, str]
    ) -> None:
        """A 1024x768 image is downscaled so longest edge is 512px."""
        service, image_id = large_registered_image
        result = await self._call_show(service, image_id)

        image_items = [c for c in result.content if isinstance(c, ImageContent)]
        assert image_items[0].mimeType == "image/webp"
        raw = base64.b64decode(image_items[0].data)
        img = Image.open(io.BytesIO(raw))
        # Longest edge must be exactly 512 (downscaled from 1024)
        assert max(img.size) == 512
        # Aspect ratio preserved: 1024:768 = 512:384
        assert img.size == (512, 384)

    async def test_large_image_metadata_reports_original_dimensions(
        self, large_registered_image: tuple[ImageService, str]
    ) -> None:
        """Metadata dimensions reflect original size, not thumbnail."""
        service, image_id = large_registered_image
        result = await self._call_show(service, image_id)

        text_items = [c for c in result.content if isinstance(c, TextContent)]
        meta = json.loads(text_items[0].text)
        # dimensions = original (no transforms requested)
        assert meta["dimensions"] == [1024, 768]
        # thumbnail_dimensions = downscaled
        assert meta["thumbnail_dimensions"] == [512, 384]

    async def test_large_image_under_1mb(
        self, large_registered_image: tuple[ImageService, str]
    ) -> None:
        """Thumbnail base64 stays well under the 1 MB client limit."""
        service, image_id = large_registered_image
        result = await self._call_show(service, image_id)

        image_items = [c for c in result.content if isinstance(c, ImageContent)]
        # base64 string length < 1 MB
        assert len(image_items[0].data) < 1_000_000

    async def test_large_image_with_resize_still_capped(
        self, large_registered_image: tuple[ImageService, str]
    ) -> None:
        """Resize to width=800 on a 1024x768 image: dimensions=800x600, thumbnail capped to 512."""
        service, image_id = large_registered_image
        result = await self._call_show(service, image_id, "?width=800")

        # Thumbnail is still capped at 512px
        image_items = [c for c in result.content if isinstance(c, ImageContent)]
        assert image_items[0].mimeType == "image/webp"
        raw = base64.b64decode(image_items[0].data)
        img = Image.open(io.BytesIO(raw))
        assert max(img.size) == 512

        # Metadata reports the transform result, not the thumbnail
        text_items = [c for c in result.content if isinstance(c, TextContent)]
        meta = json.loads(text_items[0].text)
        assert meta["dimensions"] == [800, 600]
        assert meta["thumbnail_dimensions"][0] <= 512
        assert meta["transforms_applied"]["width"] == 800


# generate_image — elicitation confirmation for paid providers
# ---------------------------------------------------------------------------


class TestElicitationPaidProviders:
    """generate_image asks for confirmation before using paid providers."""

    async def _call_generate(
        self,
        service: ImageService,
        *,
        provider: str = "placeholder",
        paid_providers: frozenset[str] = frozenset(),
        elicitation_supported: bool = False,
        elicitation_accepted: bool = True,
        elicit_response: object | None = None,
    ) -> ToolResult:
        mcp = FastMCP("test")
        register_tools(mcp)
        tool = await mcp.get_tool("generate_image")
        assert tool is not None

        ctx = MagicMock()
        ctx.report_progress = AsyncMock()
        ctx.info = AsyncMock()
        ctx.session.check_client_capability.return_value = elicitation_supported

        if elicitation_supported:
            from fastmcp.server.elicitation import AcceptedElicitation

            if elicitation_accepted:
                ctx.elicit = AsyncMock(return_value=AcceptedElicitation(data={}))
            elif elicit_response is not None:
                ctx.elicit = AsyncMock(return_value=elicit_response)
            else:
                from fastmcp.server.elicitation import CancelledElicitation

                ctx.elicit = AsyncMock(return_value=CancelledElicitation())

        cfg = MagicMock()
        cfg.paid_providers = paid_providers

        return await tool.fn(
            prompt="test image",
            provider=provider,
            service=service,
            config=cfg,
            ctx=ctx,
        )

    async def test_free_provider_no_elicitation(self, service: ImageService) -> None:
        """Free provider proceeds without elicitation regardless of support."""
        result = await self._call_generate(
            service,
            provider="placeholder",
            paid_providers=frozenset({"openai"}),
            elicitation_supported=True,
        )
        text_items = [c for c in result.content if isinstance(c, TextContent)]
        meta = json.loads(text_items[0].text)
        assert "image_id" in meta

    async def test_paid_provider_no_elicitation_support(
        self, service: ImageService
    ) -> None:
        """Paid provider proceeds silently when client lacks elicitation."""
        result = await self._call_generate(
            service,
            provider="placeholder",
            paid_providers=frozenset({"placeholder"}),
            elicitation_supported=False,
        )
        text_items = [c for c in result.content if isinstance(c, TextContent)]
        meta = json.loads(text_items[0].text)
        assert "image_id" in meta

    async def test_paid_provider_elicitation_accepted(
        self, service: ImageService
    ) -> None:
        """Paid provider proceeds after user accepts elicitation."""
        result = await self._call_generate(
            service,
            provider="placeholder",
            paid_providers=frozenset({"placeholder"}),
            elicitation_supported=True,
            elicitation_accepted=True,
        )
        text_items = [c for c in result.content if isinstance(c, TextContent)]
        meta = json.loads(text_items[0].text)
        assert "image_id" in meta

    async def test_paid_provider_elicitation_cancelled(
        self, service: ImageService
    ) -> None:
        """Paid provider returns cancellation when user cancels."""
        result = await self._call_generate(
            service,
            provider="placeholder",
            paid_providers=frozenset({"placeholder"}),
            elicitation_supported=True,
            elicitation_accepted=False,
        )
        text_items = [c for c in result.content if isinstance(c, TextContent)]
        assert len(text_items) == 1
        assert "cancelled" in text_items[0].text.lower()

    async def test_paid_provider_elicitation_declined(
        self, service: ImageService
    ) -> None:
        """Paid provider returns cancellation when user declines."""
        from fastmcp.server.elicitation import DeclinedElicitation

        result = await self._call_generate(
            service,
            provider="placeholder",
            paid_providers=frozenset({"placeholder"}),
            elicitation_supported=True,
            elicitation_accepted=False,
            elicit_response=DeclinedElicitation(),
        )
        text_items = [c for c in result.content if isinstance(c, TextContent)]
        assert len(text_items) == 1
        assert "cancelled" in text_items[0].text.lower()


# ---------------------------------------------------------------------------
# show_image — model field in metadata
# ---------------------------------------------------------------------------


class TestShowImageModelField:
    """show_image metadata includes model from provider_metadata."""

    @pytest.fixture
    def image_with_model(self, service: ImageService) -> tuple[ImageService, str]:
        """Register an image whose provider_metadata includes a model."""
        result = asyncio.run(
            PlaceholderImageProvider().generate("model test", aspect_ratio="1:1")
        )
        # Inject a model key to simulate a real provider (e.g. OpenAI)
        result.provider_metadata["model"] = "dreamshaper_xl"
        record = service.register_image(result, "test-provider", prompt="model test")
        return service, record.id

    async def _call_show(self, service: ImageService, image_id: str) -> ToolResult:
        mcp = FastMCP("test")
        register_tools(mcp)
        tool = await mcp.get_tool("show_image")
        return await tool.fn(
            uri=f"image://{image_id}/view",
            service=service,
        )

    async def test_model_present_in_metadata(
        self, image_with_model: tuple[ImageService, str]
    ) -> None:
        service, image_id = image_with_model
        result = await self._call_show(service, image_id)
        text_items = [c for c in result.content if isinstance(c, TextContent)]
        meta = json.loads(text_items[0].text)
        assert meta["model"] == "dreamshaper_xl"

    async def test_model_none_when_absent(
        self, registered_image: tuple[ImageService, str]
    ) -> None:
        """Placeholder provider has no model key — field should be None."""
        service, image_id = registered_image
        result = await self._call_show(service, image_id)
        text_items = [c for c in result.content if isinstance(c, TextContent)]
        meta = json.loads(text_items[0].text)
        assert meta["model"] is None


# ---------------------------------------------------------------------------
# generate_image — parameter validation errors
# ---------------------------------------------------------------------------


class TestGenerateImageParameterValidation:
    """generate_image raises ValueError for invalid parameters."""

    async def _call_generate(
        self,
        service: ImageService,
        *,
        aspect_ratio: str = "1:1",
        quality: str = "standard",
        background: str = "opaque",
    ) -> ToolResult:
        mcp = FastMCP("test")
        register_tools(mcp)
        tool = await mcp.get_tool("generate_image")
        assert tool is not None

        ctx = MagicMock()
        ctx.report_progress = AsyncMock()
        cfg = MagicMock()
        cfg.paid_providers = frozenset()

        return await tool.fn(
            prompt="test image",
            provider="placeholder",
            aspect_ratio=aspect_ratio,
            quality=quality,
            background=background,
            service=service,
            config=cfg,
            ctx=ctx,
        )

    async def test_invalid_aspect_ratio_raises(self, service: ImageService) -> None:
        """Unsupported aspect_ratio raises ValueError."""
        with pytest.raises(ValueError, match="Unsupported aspect_ratio"):
            await self._call_generate(service, aspect_ratio="5:4")

    async def test_invalid_quality_raises(self, service: ImageService) -> None:
        """Unsupported quality level raises ValueError."""
        with pytest.raises(ValueError, match="Unsupported quality"):
            await self._call_generate(service, quality="ultra")

    async def test_invalid_background_raises(self, service: ImageService) -> None:
        """Unsupported background raises ValueError."""
        with pytest.raises(ValueError, match="Unsupported background"):
            await self._call_generate(service, background="blur")


# ---------------------------------------------------------------------------
# generate_image — resolution parameter
# ---------------------------------------------------------------------------


class TestGenerateImageResolutionParameter:
    """generate_image validates and threads the resolution parameter."""

    async def _call_generate(
        self, service: ImageService, *, resolution: str = "standard"
    ) -> ToolResult:
        mcp = FastMCP("test")
        register_tools(mcp)
        tool = await mcp.get_tool("generate_image")
        assert tool is not None

        ctx = MagicMock()
        ctx.report_progress = AsyncMock()
        cfg = MagicMock()
        cfg.paid_providers = frozenset()

        return await tool.fn(
            prompt="test image",
            provider="placeholder",
            resolution=resolution,
            service=service,
            config=cfg,
            ctx=ctx,
        )

    async def test_invalid_resolution_raises(self, service: ImageService) -> None:
        """Unsupported resolution tier raises ValueError."""
        with pytest.raises(ValueError, match="Unsupported resolution"):
            await self._call_generate(service, resolution="ultra")

    async def test_valid_resolution_threads_to_persisted_record(
        self, service: ImageService
    ) -> None:
        """resolution='high' reaches service.generate/register_image via
        _start_background_generation and completes successfully.

        The persisted record reflects the DELIVERED tier reported by the
        provider (via ``provider_metadata["resolution"]``), not necessarily
        the requested one. The placeholder provider has no higher tier than
        "standard", so it reports "standard" as delivered even though
        "high" was requested -- see providers/placeholder.py.
        """
        result = await self._call_generate(service, resolution="high")
        text_items = [c for c in result.content if isinstance(c, TextContent)]
        image_id = json.loads(text_items[0].text)["image_id"]

        pending = None
        for _ in range(100):
            pending = service.get_pending(image_id)
            if pending and pending.status in ("completed", "failed"):
                break
            await asyncio.sleep(0.02)

        assert pending is not None and pending.status == "completed"
        assert service.get_image(image_id).resolution == "standard"


# ---------------------------------------------------------------------------
# generate_image — error handling (content policy, connection)
# ---------------------------------------------------------------------------


class TestGenerateImageErrorHandling:
    """generate_image errors surface through show_image in fire-and-forget mode."""

    async def _call_generate_failing(
        self, service: ImageService, side_effect: Exception
    ) -> str:
        """Call generate_image with a provider that raises, wait for failure.

        Permanently replaces service.generate with a raising coroutine so the
        patch stays active when the background task runs.  Returns image_id.
        """

        async def _always_raise(*_args: object, **_kwargs: object) -> None:
            raise side_effect

        service.generate = _always_raise  # type: ignore[assignment]

        mcp = FastMCP("test")
        register_tools(mcp)
        tool = await mcp.get_tool("generate_image")
        assert tool is not None

        ctx = MagicMock()
        ctx.report_progress = AsyncMock()
        ctx.info = AsyncMock()
        ctx.session.check_client_capability.return_value = False
        cfg = MagicMock()
        cfg.paid_providers = frozenset()

        result = await tool.fn(
            prompt="test image",
            provider="placeholder",
            service=service,
            config=cfg,
            ctx=ctx,
        )

        text_items = [c for c in result.content if isinstance(c, TextContent)]
        return json.loads(text_items[0].text)["image_id"]

    async def test_content_policy_error_redirects_in_show_image(
        self, service: ImageService
    ) -> None:
        """ImageContentPolicyError: show_image redirects to check_generation_status."""
        from image_generation_mcp.providers.types import ImageContentPolicyError

        image_id = await self._call_generate_failing(
            service, ImageContentPolicyError("placeholder", "blocked")
        )

        # Let the background task run and fail
        await asyncio.sleep(0.1)

        mcp = FastMCP("test")
        register_tools(mcp)
        show_tool = await mcp.get_tool("show_image")
        assert show_tool is not None
        show_result = await show_tool.fn(
            uri=f"image://{image_id}/view",
            service=service,
        )
        show_text = [c for c in show_result.content if isinstance(c, TextContent)]
        meta = json.loads(show_text[0].text)
        assert meta["status"] == "failed"
        assert "check_generation_status" in meta["error"]

    async def test_connection_error_redirects_in_show_image(
        self, service: ImageService
    ) -> None:
        """ImageProviderConnectionError: show_image redirects to check_generation_status."""
        from image_generation_mcp.providers.types import ImageProviderConnectionError

        image_id = await self._call_generate_failing(
            service,
            ImageProviderConnectionError("placeholder", "connection refused"),
        )

        # Let the background task run and fail
        await asyncio.sleep(0.1)

        mcp = FastMCP("test")
        register_tools(mcp)
        show_tool = await mcp.get_tool("show_image")
        assert show_tool is not None
        show_result = await show_tool.fn(
            uri=f"image://{image_id}/view",
            service=service,
        )
        show_text = [c for c in show_result.content if isinstance(c, TextContent)]
        meta = json.loads(show_text[0].text)
        assert meta["status"] == "failed"
        assert "check_generation_status" in meta["error"]


# ---------------------------------------------------------------------------
# generate_image — elicitation: check_client_capability exception path
# ---------------------------------------------------------------------------


class TestElicitationCapabilityCheckFailure:
    """check_client_capability exception defaults to no elicitation support."""

    async def test_capability_check_exception_falls_back(
        self, service: ImageService
    ) -> None:
        """Exception in check_client_capability assumes no elicitation support."""
        mcp = FastMCP("test")
        register_tools(mcp)
        tool = await mcp.get_tool("generate_image")
        assert tool is not None

        ctx = MagicMock()
        ctx.report_progress = AsyncMock()
        ctx.info = AsyncMock()
        # check_client_capability raises an exception
        ctx.session.check_client_capability.side_effect = RuntimeError("no session")

        cfg = MagicMock()
        # placeholder is in paid_providers to trigger elicitation path
        cfg.paid_providers = frozenset({"placeholder"})

        result = await tool.fn(
            prompt="test image",
            provider="placeholder",
            service=service,
            config=cfg,
            ctx=ctx,
        )
        # Should proceed (no elicitation called) and return a valid image_id
        text_items = [c for c in result.content if isinstance(c, TextContent)]
        meta = json.loads(text_items[0].text)
        assert "image_id" in meta


# ---------------------------------------------------------------------------
# show_image — invalid scheme error
# ---------------------------------------------------------------------------


class TestShowImageInvalidScheme:
    """show_image raises ValueError for non-image:// URIs."""

    async def test_wrong_scheme_raises(self, service: ImageService) -> None:
        """Passing an https:// URI raises ValueError."""
        mcp = FastMCP("test")
        register_tools(mcp)
        tool = await mcp.get_tool("show_image")
        assert tool is not None

        with pytest.raises(ValueError, match="Expected an image://"):
            await tool.fn(
                uri="https://example.com/image.png",
                service=service,
            )


# ---------------------------------------------------------------------------
# show_image — quality in transform_params when non-default
# ---------------------------------------------------------------------------


class TestShowImageQualityTransform:
    """show_image includes quality in transforms_applied when non-default and format set."""

    async def test_quality_in_transform_params(
        self, registered_image: tuple[ImageService, str]
    ) -> None:
        """quality != 90 appears in transforms_applied when format is also set."""
        service, image_id = registered_image

        mcp = FastMCP("test")
        register_tools(mcp)
        tool = await mcp.get_tool("show_image")
        assert tool is not None

        result = await tool.fn(
            uri=f"image://{image_id}/view?format=jpeg&quality=75",
            service=service,
        )
        text_items = [c for c in result.content if isinstance(c, TextContent)]
        meta = json.loads(text_items[0].text)
        assert meta["transforms_applied"]["format"] == "jpeg"
        assert meta["transforms_applied"]["quality"] == 75


# ---------------------------------------------------------------------------
# list_providers tool — direct tool execution
# ---------------------------------------------------------------------------


class TestListProvidersTool:
    """list_providers tool returns JSON with provider info."""

    async def test_list_providers_returns_json(self, service: ImageService) -> None:
        """list_providers tool returns valid JSON with provider names."""
        mcp = FastMCP("test")
        register_tools(mcp)
        tool = await mcp.get_tool("list_providers")
        assert tool is not None

        result = await tool.fn(service=service)
        data = json.loads(result)
        assert "refreshed_at" in data
        assert "providers" in data
        assert "placeholder" in data["providers"]
        assert data["providers"]["placeholder"]["available"] is True

    async def test_list_providers_force_refresh_calls_discover(
        self, service: ImageService
    ) -> None:
        """force_refresh=True triggers capability re-discovery."""
        mcp = FastMCP("test")
        register_tools(mcp)
        tool = await mcp.get_tool("list_providers")

        with unittest.mock.patch.object(
            service,
            "discover_all_capabilities",
            new_callable=AsyncMock,
        ) as mock_discover:
            result = await tool.fn(force_refresh=True, service=service)
            mock_discover.assert_awaited_once()

        data = json.loads(result)
        assert "refreshed_at" in data

    async def test_list_providers_includes_warnings_array_always(
        self, service: ImageService
    ) -> None:
        """warnings is always present (empty when no deprecated models)."""
        mcp = FastMCP("test")
        register_tools(mcp)
        tool = await mcp.get_tool("list_providers")
        assert tool is not None

        result = await tool.fn(service=service)
        payload = json.loads(result)
        assert "warnings" in payload
        assert isinstance(payload["warnings"], list)
        # Placeholder provider has no style_profile → no warnings
        assert payload["warnings"] == []

    async def test_list_providers_warnings_lists_deprecated_dall_e_3(
        self, tmp_path: Path
    ) -> None:
        """warnings includes a sentence for each non-current configured model."""
        svc = ImageService(scratch_dir=tmp_path)
        svc.register_provider("openai", PlaceholderImageProvider())
        # Inject a discovered capabilities snapshot that includes dall-e-3
        # (deprecated lifecycle) directly into the service's _capabilities cache.
        dall_e_3_profile = MODEL_STYLES.get("openai:dall-e-3")
        assert dall_e_3_profile is not None, "dall-e-3 must be in MODEL_STYLES"
        model_caps = ModelCapabilities(
            model_id="dall-e-3",
            display_name="DALL-E 3",
            style_profile=dall_e_3_profile,
        )
        provider_caps = ProviderCapabilities(
            provider_name="openai",
            models=(model_caps,),
            discovered_at=0.0,
        )
        svc._capabilities["openai"] = provider_caps

        mcp = FastMCP("test")
        register_tools(mcp)
        tool = await mcp.get_tool("list_providers")
        assert tool is not None

        result = await tool.fn(service=svc)
        payload = json.loads(result)
        assert "warnings" in payload
        warnings = payload["warnings"]
        assert any("dall-e-3" in w and "2026-05-12" in w for w in warnings), (
            f"expected a deprecation warning mentioning dall-e-3 + 2026-05-12; "
            f"got {warnings!r}"
        )

    async def test_list_providers_warnings_lists_legacy_gpt_image_1(
        self, tmp_path: Path
    ) -> None:
        """warnings cover legacy-lifecycle models, not just deprecated ones.

        ``_build_lifecycle_warnings`` skips ``lifecycle == "current"`` and
        emits a warning for both ``"legacy"`` and ``"deprecated"``. Without
        this test the legacy branch was uncovered — an accidental narrowing
        to ``lifecycle == "deprecated"`` would slip through.
        """
        svc = ImageService(scratch_dir=tmp_path)
        svc.register_provider("openai", PlaceholderImageProvider())
        gpt_image_1_profile = MODEL_STYLES.get("openai:gpt-image-1")
        assert gpt_image_1_profile is not None
        assert gpt_image_1_profile.lifecycle == "legacy"
        model_caps = ModelCapabilities(
            model_id="gpt-image-1",
            display_name="GPT Image 1",
            style_profile=gpt_image_1_profile,
        )
        provider_caps = ProviderCapabilities(
            provider_name="openai",
            models=(model_caps,),
            discovered_at=0.0,
        )
        svc._capabilities["openai"] = provider_caps

        mcp = FastMCP("test")
        register_tools(mcp)
        tool = await mcp.get_tool("list_providers")
        assert tool is not None

        result = await tool.fn(service=svc)
        payload = json.loads(result)
        assert "warnings" in payload
        warnings = payload["warnings"]
        assert any("gpt-image-1" in w and "legacy" in w for w in warnings), (
            f"expected a legacy warning mentioning gpt-image-1; got {warnings!r}"
        )


# ---------------------------------------------------------------------------
# Tool annotations (readOnlyHint, destructiveHint, openWorldHint)
# ---------------------------------------------------------------------------


class TestToolAnnotations:
    """Verify all tools have correct MCP tool annotations for ChatGPT compat."""

    @pytest.mark.parametrize(
        "tool_name,expected",
        [
            (
                "generate_image",
                {
                    "readOnlyHint": False,
                    "destructiveHint": False,
                    "openWorldHint": True,
                },
            ),
            (
                "show_image",
                {
                    "readOnlyHint": True,
                    "destructiveHint": False,
                    "openWorldHint": False,
                },
            ),
            (
                "list_providers",
                {
                    "readOnlyHint": True,
                    "destructiveHint": False,
                    "openWorldHint": True,
                    "idempotentHint": False,
                },
            ),
            (
                "fetch_image",
                {
                    "readOnlyHint": False,
                    "destructiveHint": False,
                    "openWorldHint": True,
                },
            ),
            (
                "ingest_base64_image",
                {
                    "readOnlyHint": False,
                    "destructiveHint": False,
                    "openWorldHint": False,
                },
            ),
        ],
    )
    async def test_tool_annotations(
        self, tool_name: str, expected: dict[str, bool]
    ) -> None:
        """Each tool has the expected MCP annotations."""
        mcp = FastMCP("test")
        register_tools(mcp)
        tool = await mcp.get_tool(tool_name)
        assert tool is not None
        assert tool.annotations is not None
        for key, value in expected.items():
            assert getattr(tool.annotations, key) == value, (
                f"{tool_name}.annotations.{key}: "
                f"expected {value}, got {getattr(tool.annotations, key)}"
            )


# ---------------------------------------------------------------------------
# edit_image tool
# ---------------------------------------------------------------------------


class TestEditImageTool:
    """edit_image returns image + editable metadata; _save_edited_image persists."""

    async def _call_edit(self, service: ImageService, image_id: str) -> ToolResult:
        mcp = FastMCP("test")
        register_tools(mcp)
        tool = await mcp.get_tool("edit_image")
        assert tool is not None
        return await tool.fn(image_id=image_id, service=service)

    async def test_edit_image_returns_text_and_image_content(
        self, registered_image: tuple[ImageService, str]
    ) -> None:
        """edit_image returns TextContent + ImageContent with editable flag."""
        service, image_id = registered_image
        result = await self._call_edit(service, image_id)
        types = [c.type for c in result.content]
        assert "text" in types
        assert "image" in types

    async def test_edit_image_metadata_has_editable_flag(
        self, registered_image: tuple[ImageService, str]
    ) -> None:
        """Text content in edit_image result must set editable=true."""
        service, image_id = registered_image
        result = await self._call_edit(service, image_id)
        text_item = next(c for c in result.content if c.type == "text")
        meta = json.loads(text_item.text)
        assert meta["editable"] is True
        assert meta["image_id"] == image_id

    async def test_edit_image_returns_valid_base64(
        self, registered_image: tuple[ImageService, str]
    ) -> None:
        """ImageContent from edit_image must be valid base64-encoded image data."""
        service, image_id = registered_image
        result = await self._call_edit(service, image_id)
        img_item = next(c for c in result.content if c.type == "image")
        raw = base64.b64decode(img_item.data)
        img = Image.open(io.BytesIO(raw))
        assert img.width > 0

    async def test_edit_image_unknown_id_raises(self, service: ImageService) -> None:
        """edit_image raises for an unknown image_id."""
        from image_generation_mcp.providers.types import ImageProviderError

        mcp = FastMCP("test")
        register_tools(mcp)
        tool = await mcp.get_tool("edit_image")
        assert tool is not None

        with pytest.raises(ImageProviderError):
            await tool.fn(image_id="nonexistent", service=service)


# ---------------------------------------------------------------------------
# _save_edited_image tool
# ---------------------------------------------------------------------------


class TestSaveEditedImageTool:
    """_save_edited_image persists transform results as a new ImageRecord."""

    async def _call_save(
        self,
        service: ImageService,
        source_image_id: str,
        **kwargs: object,
    ) -> ToolResult:
        mcp = FastMCP("test")
        register_tools(mcp)
        tool = await get_tool_including_app_only(mcp, "_save_edited_image")
        assert tool is not None
        return await tool.fn(source_image_id=source_image_id, service=service, **kwargs)

    async def test_save_no_transforms_creates_copy(
        self, registered_image: tuple[ImageService, str]
    ) -> None:
        """Saving with no transforms creates a new image record."""
        service, image_id = registered_image
        result = await self._call_save(service, image_id)
        text_item = next(c for c in result.content if c.type == "text")
        data = json.loads(text_item.text)
        assert "image_id" in data
        assert data["source_image_id"] == image_id
        # Result must be registered (retrievable from service)
        assert service.get_image(data["image_id"]) is not None

    async def test_save_with_crop_produces_cropped_image(
        self, registered_image: tuple[ImageService, str]
    ) -> None:
        """Crop transform produces image with correct dimensions."""
        service, image_id = registered_image
        result = await self._call_save(
            service, image_id, crop={"x": 0, "y": 0, "w": 50, "h": 50}
        )
        text_item = next(c for c in result.content if c.type == "text")
        new_id = json.loads(text_item.text)["image_id"]
        new_record = service.get_image(new_id)
        img = Image.open(io.BytesIO(new_record.original_path.read_bytes()))
        assert img.size == (50, 50)

    async def test_save_with_rotate_produces_rotated_image(
        self, registered_image: tuple[ImageService, str]
    ) -> None:
        """Rotate 90° transposes width and height."""
        service, image_id = registered_image
        original_record = service.get_image(image_id)
        orig_w, orig_h = original_record.original_dimensions

        result = await self._call_save(service, image_id, rotate=90)
        text_item = next(c for c in result.content if c.type == "text")
        new_id = json.loads(text_item.text)["image_id"]
        new_record = service.get_image(new_id)
        img = Image.open(io.BytesIO(new_record.original_path.read_bytes()))
        # 90° rotation swaps width ↔ height
        assert img.size == (orig_h, orig_w)

    async def test_save_with_flip_horizontal(
        self, registered_image: tuple[ImageService, str]
    ) -> None:
        """flip_horizontal produces a valid image of same dimensions."""
        service, image_id = registered_image
        original_record = service.get_image(image_id)

        result = await self._call_save(service, image_id, flip_horizontal=True)
        text_item = next(c for c in result.content if c.type == "text")
        new_id = json.loads(text_item.text)["image_id"]
        new_record = service.get_image(new_id)
        img = Image.open(io.BytesIO(new_record.original_path.read_bytes()))
        assert img.size == original_record.original_dimensions

    async def test_save_records_source_image_id(
        self, registered_image: tuple[ImageService, str]
    ) -> None:
        """New record has source_image_ids set to a list with the original image_id."""
        service, image_id = registered_image
        result = await self._call_save(service, image_id)
        text_item = next(c for c in result.content if c.type == "text")
        new_id = json.loads(text_item.text)["image_id"]
        new_record = service.get_image(new_id)
        assert new_record.source_image_ids == [image_id]

    async def test_save_invalid_crop_raises(
        self, registered_image: tuple[ImageService, str]
    ) -> None:
        """_save_edited_image raises for a malformed crop dict."""
        service, image_id = registered_image

        with pytest.raises(ValueError, match="crop must have"):
            await self._call_save(
                service,
                image_id,
                # missing required keys
                crop={"x": 0, "y": 0},
            )


# ---------------------------------------------------------------------------
# transform_image tool
# ---------------------------------------------------------------------------


class TestTransformImageTool:
    """transform_image tool: registration, validation, and provenance."""

    async def _make_ctx(self) -> MagicMock:
        ctx = MagicMock()
        ctx.report_progress = AsyncMock()
        ctx.info = AsyncMock()
        ctx.session.check_client_capability.return_value = False
        return ctx

    async def _make_cfg(self) -> MagicMock:
        cfg = MagicMock()
        cfg.allow_local_file_input = False
        cfg.max_input_image_bytes = 20 * 1024 * 1024
        cfg.paid_providers = frozenset()
        return cfg

    async def test_transform_image_registered(self) -> None:
        """transform_image is registered and tagged 'write'."""
        mcp = FastMCP("test")
        register_tools(mcp)
        tool = await mcp.get_tool("transform_image")
        assert tool is not None
        assert "write" in tool.tags

    async def test_transform_image_errors_without_image_input(
        self, service: ImageService
    ) -> None:
        """With no image-input-capable provider, transform_image raises ValueError."""
        # The default 'service' fixture uses PlaceholderImageProvider which has
        # supports_image_input=False by default (no capabilities injected).
        mcp = FastMCP("test")
        register_tools(mcp)
        tool = await mcp.get_tool("transform_image")
        assert tool is not None

        ctx = await self._make_ctx()
        cfg = await self._make_cfg()

        with pytest.raises(ValueError, match=r"image.input"):
            await tool.fn(
                prompt="make it blue",
                reference_images=["0123456789ab"],
                service=service,
                config=cfg,
                ctx=ctx,
            )

    async def test_transform_image_rejects_unknown_reference(
        self, tmp_path: Path
    ) -> None:
        """Unknown reference image raises ValueError containing 'not found'."""
        svc = ImageService(scratch_dir=tmp_path)
        svc.register_provider("placeholder", PlaceholderImageProvider())
        # Inject image-input-capable capabilities for the placeholder provider
        svc._capabilities["placeholder"] = ProviderCapabilities(
            provider_name="placeholder",
            models=(
                ModelCapabilities(
                    model_id="placeholder",
                    display_name="Placeholder",
                    supports_image_input=True,
                    max_input_images=1,
                ),
            ),
            discovered_at=1000.0,
        )

        mcp = FastMCP("test")
        register_tools(mcp)
        tool = await mcp.get_tool("transform_image")
        assert tool is not None

        ctx = await self._make_ctx()
        cfg = await self._make_cfg()

        with pytest.raises(ValueError, match="not found"):
            await tool.fn(
                prompt="make it blue",
                reference_images=["deadbeef0000"],
                service=svc,
                config=cfg,
                ctx=ctx,
            )

    async def test_transform_image_completes_with_provenance(
        self, tmp_path: Path
    ) -> None:
        """transform_image spawns a background task and records source_image_ids."""
        svc = ImageService(scratch_dir=tmp_path)
        provider = PlaceholderImageProvider()
        svc.register_provider("placeholder", provider)

        # Inject image-input-capable capabilities
        svc._capabilities["placeholder"] = ProviderCapabilities(
            provider_name="placeholder",
            models=(
                ModelCapabilities(
                    model_id="placeholder",
                    display_name="Placeholder",
                    supports_image_input=True,
                    max_input_images=4,
                ),
            ),
            discovered_at=1000.0,
        )

        # Register a real source image in the gallery
        src_result = await provider.generate("source image", aspect_ratio="1:1")
        src_record = svc.register_image(
            src_result, "placeholder", prompt="source image"
        )
        source_image_id = src_record.id

        # Stub service.generate to return a real image without hitting
        # PlaceholderImageProvider's image-input guard (it raises
        # ImageInputUnsupported for reference_images).
        stub_result = await provider.generate("make it blue", aspect_ratio="1:1")

        # Capture reference_images kwarg with AsyncMock
        async def _fake_generate(
            *_args: object, **_kwargs: object
        ) -> tuple[str, ImageResult]:
            return "placeholder", stub_result

        mock_generate = AsyncMock(side_effect=_fake_generate)
        svc.generate = mock_generate  # type: ignore[assignment]

        mcp = FastMCP("test")
        register_tools(mcp)
        tool = await mcp.get_tool("transform_image")
        assert tool is not None

        ctx = await self._make_ctx()
        cfg = await self._make_cfg()

        result = await tool.fn(
            prompt="make it blue",
            reference_images=[source_image_id],
            provider="placeholder",
            service=svc,
            config=cfg,
            ctx=ctx,
        )

        # Result must be a ToolResult with TextContent + ResourceLink
        text_items = [c for c in result.content if isinstance(c, TextContent)]
        link_items = [c for c in result.content if isinstance(c, ResourceLink)]
        assert len(text_items) == 1
        assert len(link_items) == 1

        metadata = json.loads(text_items[0].text)
        assert metadata["status"] == "generating"
        assert "image_id" in metadata
        image_id = metadata["image_id"]

        # source_image_ids propagated into response
        assert source_image_id in metadata["source_image_ids"]

        # ResourceLink URI matches image_id
        assert str(link_items[0].uri) == f"image://{image_id}/view"
        assert "Transformed" in link_items[0].name

        # Poll until background task completes
        pending = None
        for _ in range(100):
            pending = svc.get_pending(image_id)
            if pending and pending.status in ("completed", "failed"):
                break
            await asyncio.sleep(0.02)

        assert pending is not None and pending.status == "completed"
        completed_record = svc.get_image(image_id)
        assert completed_record.id == image_id
        assert completed_record.source_image_ids == [source_image_id]

        # Verify generate was called with reference_images kwarg
        assert mock_generate.await_count >= 1
        call_kwargs = mock_generate.call_args.kwargs
        assert "reference_images" in call_kwargs
        reference_images = call_kwargs["reference_images"]
        assert isinstance(reference_images, list)
        assert len(reference_images) == 1
        # reference_images[0] is an InputImage; verify its source_id matches
        assert reference_images[0].source_id == source_image_id

    async def test_transform_image_threads_resolution_to_generate(
        self, tmp_path: Path
    ) -> None:
        """resolution parameter reaches service.generate with the requested tier."""
        svc = ImageService(scratch_dir=tmp_path)
        provider = PlaceholderImageProvider()
        svc.register_provider("placeholder", provider)

        svc._capabilities["placeholder"] = ProviderCapabilities(
            provider_name="placeholder",
            models=(
                ModelCapabilities(
                    model_id="placeholder",
                    display_name="Placeholder",
                    supports_image_input=True,
                    max_input_images=4,
                ),
            ),
            discovered_at=1000.0,
        )

        src_result = await provider.generate("source image", aspect_ratio="1:1")
        src_record = svc.register_image(
            src_result, "placeholder", prompt="source image"
        )
        source_image_id = src_record.id

        stub_result = await provider.generate("make it blue", aspect_ratio="1:1")

        async def _fake_generate(
            *_args: object, **_kwargs: object
        ) -> tuple[str, ImageResult]:
            return "placeholder", stub_result

        mock_generate = AsyncMock(side_effect=_fake_generate)
        svc.generate = mock_generate  # type: ignore[assignment]

        mcp = FastMCP("test")
        register_tools(mcp)
        tool = await mcp.get_tool("transform_image")
        assert tool is not None

        ctx = await self._make_ctx()
        cfg = await self._make_cfg()

        result = await tool.fn(
            prompt="make it blue",
            reference_images=[source_image_id],
            provider="placeholder",
            resolution="high",
            service=svc,
            config=cfg,
            ctx=ctx,
        )
        text_items = [c for c in result.content if isinstance(c, TextContent)]
        image_id = json.loads(text_items[0].text)["image_id"]

        pending = None
        for _ in range(100):
            pending = svc.get_pending(image_id)
            if pending and pending.status in ("completed", "failed"):
                break
            await asyncio.sleep(0.02)

        assert pending is not None and pending.status == "completed"
        assert mock_generate.await_count >= 1
        assert mock_generate.call_args.kwargs["resolution"] == "high"

    async def test_transform_image_auto_routes_to_capable_provider(
        self, tmp_path: Path
    ) -> None:
        """With provider='auto', transform_image routes to an image-input-capable provider.

        The default PlaceholderImageProvider has supports_image_input=False.
        A second "fakegen" provider has supports_image_input=True.
        With provider='auto', the tool must select "fakegen" instead of raising.
        """
        svc = ImageService(scratch_dir=tmp_path)

        # Register the default placeholder (NOT image-capable)
        svc.register_provider("placeholder", PlaceholderImageProvider())
        # No capabilities injected for placeholder → supports_image_input=False by default

        # Register a fake image-capable provider (PlaceholderImageProvider instance
        # is fine — we stub svc.generate so the guard never hits the real impl)
        fake_provider = PlaceholderImageProvider()
        svc.register_provider("fakegen", fake_provider)

        # Inject image-input-capable capabilities ONLY for fakegen
        svc._capabilities["fakegen"] = ProviderCapabilities(
            provider_name="fakegen",
            models=(
                ModelCapabilities(
                    model_id="fakegen",
                    display_name="FakeGen",
                    supports_image_input=True,
                    max_input_images=1,
                ),
            ),
            discovered_at=1000.0,
        )

        # Register a real gallery source image via the placeholder provider
        src_result = await PlaceholderImageProvider().generate(
            "source image", aspect_ratio="1:1"
        )
        src_record = svc.register_image(
            src_result, "placeholder", prompt="source image"
        )
        source_image_id = src_record.id

        # Stub svc.generate to capture which provider is chosen
        stub_result = await PlaceholderImageProvider().generate(
            "auto route test", aspect_ratio="1:1"
        )
        chosen_provider_name: list[str] = []

        async def _fake_generate(
            *_args: object, **_kwargs: object
        ) -> tuple[str, ImageResult]:
            chosen_provider_name.append("fakegen")
            return "fakegen", stub_result

        mock_generate = AsyncMock(side_effect=_fake_generate)
        svc.generate = mock_generate  # type: ignore[assignment]

        mcp = FastMCP("test")
        register_tools(mcp)
        tool = await mcp.get_tool("transform_image")
        assert tool is not None

        ctx = await self._make_ctx()
        cfg = await self._make_cfg()

        # Call with provider="auto" (the default) — should NOT raise
        result = await tool.fn(
            prompt="auto route test",
            reference_images=[source_image_id],
            provider="auto",
            service=svc,
            config=cfg,
            ctx=ctx,
        )

        text_items = [c for c in result.content if isinstance(c, TextContent)]
        assert len(text_items) == 1
        metadata = json.loads(text_items[0].text)
        assert metadata["status"] == "generating"
        image_id = metadata["image_id"]

        # Poll until background task completes
        pending = None
        for _ in range(100):
            pending = svc.get_pending(image_id)
            if pending and pending.status in ("completed", "failed"):
                break
            await asyncio.sleep(0.02)

        assert pending is not None and pending.status == "completed"

        # The capable provider ("fakegen") must have been selected
        assert chosen_provider_name == ["fakegen"], (
            f"Expected auto-routing to select 'fakegen'; got {chosen_provider_name}"
        )

    async def test_transform_image_auto_routes_multi_image_to_higher_cap_provider(
        self, tmp_path: Path
    ) -> None:
        """auto-routing must honor max_input_images for the request's ref count.

        Gemini caps at 1 reference; OpenAI accepts 16. A 2-image auto request
        must route to OpenAI, not Gemini (which would then reject the count).
        """
        svc = ImageService(scratch_dir=tmp_path)
        svc.register_provider("placeholder", PlaceholderImageProvider())
        svc.register_provider("gemini", PlaceholderImageProvider())
        svc.register_provider("openai", PlaceholderImageProvider())
        svc._capabilities["gemini"] = ProviderCapabilities(
            provider_name="gemini",
            models=(
                ModelCapabilities(
                    model_id="gemini-flash",
                    display_name="Gemini",
                    supports_image_input=True,
                    max_input_images=1,
                ),
            ),
            discovered_at=1000.0,
        )
        svc._capabilities["openai"] = ProviderCapabilities(
            provider_name="openai",
            models=(
                ModelCapabilities(
                    model_id="gpt-image-1",
                    display_name="GPT Image 1",
                    supports_image_input=True,
                    max_input_images=16,
                ),
            ),
            discovered_at=1000.0,
        )

        # Two real gallery source images
        ids: list[str] = []
        for i in range(2):
            res = await PlaceholderImageProvider().generate(
                f"src {i}", aspect_ratio="1:1"
            )
            ids.append(svc.register_image(res, "placeholder", prompt=f"src {i}").id)

        stub_result = await PlaceholderImageProvider().generate("x", aspect_ratio="1:1")
        chosen: list[str] = []

        async def _fake_generate(
            *_args: object, **kwargs: object
        ) -> tuple[str, ImageResult]:
            chosen.append(str(kwargs.get("provider")))
            return "openai", stub_result

        svc.generate = AsyncMock(side_effect=_fake_generate)  # type: ignore[assignment]

        mcp = FastMCP("test")
        register_tools(mcp)
        tool = await mcp.get_tool("transform_image")
        assert tool is not None
        ctx = await self._make_ctx()
        cfg = await self._make_cfg()

        result = await tool.fn(
            prompt="compose two",
            reference_images=ids,
            provider="auto",
            service=svc,
            config=cfg,
            ctx=ctx,
        )
        metadata = json.loads(
            next(c for c in result.content if isinstance(c, TextContent)).text
        )
        image_id = metadata["image_id"]
        pending = None
        for _ in range(100):
            pending = svc.get_pending(image_id)
            if pending and pending.status in ("completed", "failed"):
                break
            await asyncio.sleep(0.02)
        assert pending is not None and pending.status == "completed"
        assert chosen == ["openai"], (
            f"2-image auto request must route to openai (cap 16), got {chosen}"
        )

    async def test_transform_image_auto_no_provider_for_count_raises(
        self, tmp_path: Path
    ) -> None:
        """auto-routing raises when no provider accepts the requested ref count."""
        svc = ImageService(scratch_dir=tmp_path)
        svc.register_provider("gemini", PlaceholderImageProvider())
        svc._capabilities["gemini"] = ProviderCapabilities(
            provider_name="gemini",
            models=(
                ModelCapabilities(
                    model_id="gemini-flash",
                    display_name="Gemini",
                    supports_image_input=True,
                    max_input_images=1,
                ),
            ),
            discovered_at=1000.0,
        )
        ids: list[str] = []
        for i in range(2):
            res = await PlaceholderImageProvider().generate(
                f"src {i}", aspect_ratio="1:1"
            )
            ids.append(svc.register_image(res, "gemini", prompt=f"src {i}").id)

        mcp = FastMCP("test")
        register_tools(mcp)
        tool = await mcp.get_tool("transform_image")
        assert tool is not None
        with pytest.raises(ValueError, match="No configured provider accepts"):
            await tool.fn(
                prompt="two refs",
                reference_images=ids,
                provider="auto",
                service=svc,
                config=await self._make_cfg(),
                ctx=await self._make_ctx(),
            )

    # F1: missing backing file raises ValueError (not raw OSError)
    async def test_transform_image_missing_backing_file_raises_value_error(
        self, tmp_path: Path
    ) -> None:
        """Gallery record exists but backing file deleted → ValueError 'not found'.

        If the file read is outside the try block, OSError leaks past the
        resolver's KeyError→ImageReferenceNotFound mapping and surfaces as a
        raw OSError instead of a clean ValueError.
        """
        svc = ImageService(scratch_dir=tmp_path)
        provider = PlaceholderImageProvider()
        svc.register_provider("placeholder", provider)

        # Inject image-input-capable capabilities for the placeholder provider
        svc._capabilities["placeholder"] = ProviderCapabilities(
            provider_name="placeholder",
            models=(
                ModelCapabilities(
                    model_id="placeholder",
                    display_name="Placeholder",
                    supports_image_input=True,
                    max_input_images=4,
                ),
            ),
            discovered_at=1000.0,
        )

        # Register a real gallery image so a record exists in the in-memory registry
        src_result = await provider.generate("source image", aspect_ratio="1:1")
        src_record = svc.register_image(
            src_result, "placeholder", prompt="source image"
        )
        source_image_id = src_record.id

        # Delete the backing file from disk — record stays in memory registry
        backing_path = svc.get_image(source_image_id).original_path
        backing_path.unlink()

        mcp = FastMCP("test")
        register_tools(mcp)
        tool = await mcp.get_tool("transform_image")
        assert tool is not None

        ctx = await self._make_ctx()
        cfg = await self._make_cfg()

        with pytest.raises(ValueError, match="not found"):
            await tool.fn(
                prompt="make it blue",
                reference_images=[source_image_id],
                provider="placeholder",
                service=svc,
                config=cfg,
                ctx=ctx,
            )

    # F10: capability-filter rejection when too many images for the model
    async def test_transform_image_too_many_images_for_model_raises_value_error(
        self, tmp_path: Path
    ) -> None:
        """Provider has max_input_images=1 but two references passed → ValueError.

        This exercises the ``m.max_input_images >= len(resolved)`` branch in
        the capability-filter that rejects the request synchronously before
        spawning any background task.
        """
        svc = ImageService(scratch_dir=tmp_path)
        provider = PlaceholderImageProvider()
        svc.register_provider("placeholder", provider)

        # Inject image-input-capable capabilities with max_input_images=1
        svc._capabilities["placeholder"] = ProviderCapabilities(
            provider_name="placeholder",
            models=(
                ModelCapabilities(
                    model_id="placeholder",
                    display_name="Placeholder",
                    supports_image_input=True,
                    max_input_images=1,
                ),
            ),
            discovered_at=1000.0,
        )

        # Register two real gallery images
        src1 = await provider.generate("source image 1", aspect_ratio="1:1")
        rec1 = svc.register_image(src1, "placeholder", prompt="source image 1")
        src2 = await provider.generate("source image 2", aspect_ratio="1:1")
        rec2 = svc.register_image(src2, "placeholder", prompt="source image 2")

        mcp = FastMCP("test")
        register_tools(mcp)
        tool = await mcp.get_tool("transform_image")
        assert tool is not None

        ctx = await self._make_ctx()
        cfg = await self._make_cfg()

        with pytest.raises(ValueError, match="no model accepting"):
            await tool.fn(
                prompt="combine them",
                reference_images=[rec1.id, rec2.id],
                provider="placeholder",
                service=svc,
                config=cfg,
                ctx=ctx,
            )

    # F11: parameter-validation guards for transform_image
    @pytest.mark.parametrize(
        "param,value,match",
        [
            ("aspect_ratio", "5:4", "Unsupported aspect_ratio"),
            ("quality", "ultra", "Unsupported quality"),
            ("resolution", "ultra", "Unsupported resolution"),
            ("background", "blurred", "Unsupported background"),
        ],
    )
    async def test_transform_image_invalid_enum_params_raise(
        self,
        tmp_path: Path,
        param: str,
        value: str,
        match: str,
    ) -> None:
        """Invalid aspect_ratio / quality / background raise ValueError before resolution.

        reference_images is non-empty so the empty-list guard does not fire
        first; the enum guard is what raises.
        """
        svc = ImageService(scratch_dir=tmp_path)
        svc.register_provider("placeholder", PlaceholderImageProvider())
        svc._capabilities["placeholder"] = ProviderCapabilities(
            provider_name="placeholder",
            models=(
                ModelCapabilities(
                    model_id="placeholder",
                    display_name="Placeholder",
                    supports_image_input=True,
                    max_input_images=1,
                ),
            ),
            discovered_at=1000.0,
        )

        mcp = FastMCP("test")
        register_tools(mcp)
        tool = await mcp.get_tool("transform_image")
        assert tool is not None

        ctx = await self._make_ctx()
        cfg = await self._make_cfg()

        kwargs: dict[str, object] = {
            "prompt": "test",
            "reference_images": ["0123456789ab"],
            "service": svc,
            "config": cfg,
            "ctx": ctx,
            param: value,
        }
        with pytest.raises(ValueError, match=match):
            await tool.fn(**kwargs)

    async def test_transform_image_empty_reference_images_raises(
        self, service: ImageService
    ) -> None:
        """transform_image raises ValueError when reference_images is empty."""
        mcp = FastMCP("test")
        register_tools(mcp)
        tool = await mcp.get_tool("transform_image")
        assert tool is not None

        ctx = await self._make_ctx()
        cfg = await self._make_cfg()

        with pytest.raises(ValueError, match="reference_images must not be empty"):
            await tool.fn(
                prompt="test",
                reference_images=[],
                service=service,
                config=cfg,
                ctx=ctx,
            )

    async def test_transform_image_metadata_includes_prompt_style_and_resource_template(
        self, tmp_path: Path
    ) -> None:
        """transform_image response metadata includes prompt_style and resource_template keys.

        These fields must be present to match the symmetry with generate_image response.
        """
        svc = ImageService(scratch_dir=tmp_path)
        provider = PlaceholderImageProvider()
        svc.register_provider("placeholder", provider)

        svc._capabilities["placeholder"] = ProviderCapabilities(
            provider_name="placeholder",
            models=(
                ModelCapabilities(
                    model_id="placeholder",
                    display_name="Placeholder",
                    supports_image_input=True,
                    max_input_images=4,
                ),
            ),
            discovered_at=1000.0,
        )

        src_result = await provider.generate("source image", aspect_ratio="1:1")
        src_record = svc.register_image(
            src_result, "placeholder", prompt="source image"
        )
        source_image_id = src_record.id

        stub_result = await provider.generate("transform test", aspect_ratio="1:1")

        async def _fake_generate(
            *_args: object, **_kwargs: object
        ) -> tuple[str, ImageResult]:
            return "placeholder", stub_result

        svc.generate = AsyncMock(side_effect=_fake_generate)  # type: ignore[assignment]

        mcp = FastMCP("test")
        register_tools(mcp)
        tool = await mcp.get_tool("transform_image")
        assert tool is not None

        ctx = await self._make_ctx()
        cfg = await self._make_cfg()

        result = await tool.fn(
            prompt="make it blue",
            reference_images=[source_image_id],
            provider="placeholder",
            service=svc,
            config=cfg,
            ctx=ctx,
        )

        text_items = [c for c in result.content if isinstance(c, TextContent)]
        assert len(text_items) == 1
        metadata = json.loads(text_items[0].text)

        assert "prompt_style" in metadata, (
            "transform_image must include 'prompt_style' in metadata"
        )
        assert "resource_template" in metadata, (
            "transform_image must include 'resource_template' in metadata"
        )
        image_id = metadata["image_id"]
        assert metadata["resource_template"] == (
            f"image://{image_id}/view"
            "{?format,width,height,quality,crop_x,crop_y,crop_w,crop_h,rotate,flip}"
        )

    # F13: mask parameter — requires supports_mask model
    async def test_transform_image_mask_requires_supports_mask(
        self, tmp_path: Path
    ) -> None:
        """transform_image raises ValueError matching 'mask' when the chosen model
        supports image input but not masks (supports_mask=False)."""
        svc = ImageService(scratch_dir=tmp_path)
        provider = PlaceholderImageProvider()
        svc.register_provider("placeholder", provider)

        # Inject capabilities: image-input capable but supports_mask=False
        svc._capabilities["placeholder"] = ProviderCapabilities(
            provider_name="placeholder",
            models=(
                ModelCapabilities(
                    model_id="placeholder",
                    display_name="Placeholder",
                    supports_image_input=True,
                    max_input_images=4,
                    supports_mask=False,
                ),
            ),
            discovered_at=1000.0,
        )

        # Register two gallery images (base + mask)
        base_result = await provider.generate("base image", aspect_ratio="1:1")
        base_record = svc.register_image(
            base_result, "placeholder", prompt="base image"
        )
        mask_result = await provider.generate("mask image", aspect_ratio="1:1")
        mask_record = svc.register_image(
            mask_result, "placeholder", prompt="mask image"
        )

        mcp = FastMCP("test")
        register_tools(mcp)
        tool = await mcp.get_tool("transform_image")
        assert tool is not None

        ctx = await self._make_ctx()
        cfg = await self._make_cfg()

        with pytest.raises(ValueError, match=r"reference image\(s\) with a mask"):
            await tool.fn(
                prompt="inpaint this",
                reference_images=[base_record.id],
                mask=mask_record.id,
                provider="placeholder",
                service=svc,
                config=cfg,
                ctx=ctx,
            )

    async def test_transform_image_mask_auto_no_mask_capable_provider(
        self, tmp_path: Path
    ) -> None:
        """provider='auto' with a mask but no mask-capable provider → ValueError.

        Exercises the auto `eligible` filter's supports_mask clause (the
        explicit-provider test above covers the `capable` filter).
        """
        svc = ImageService(scratch_dir=tmp_path)
        provider = PlaceholderImageProvider()
        svc.register_provider("placeholder", provider)
        # image-input capable but supports_mask=False — not eligible for a mask
        svc._capabilities["placeholder"] = ProviderCapabilities(
            provider_name="placeholder",
            models=(
                ModelCapabilities(
                    model_id="placeholder",
                    display_name="Placeholder",
                    supports_image_input=True,
                    max_input_images=4,
                    supports_mask=False,
                ),
            ),
            discovered_at=1000.0,
        )
        base = svc.register_image(
            await provider.generate("base", aspect_ratio="1:1"),
            "placeholder",
            prompt="base",
        )
        msk = svc.register_image(
            await provider.generate("mask", aspect_ratio="1:1"),
            "placeholder",
            prompt="mask",
        )
        mcp = FastMCP("test")
        register_tools(mcp)
        tool = await mcp.get_tool("transform_image")
        assert tool is not None
        with pytest.raises(ValueError, match=r"reference image\(s\) with a mask"):
            await tool.fn(
                prompt="inpaint",
                reference_images=[base.id],
                mask=msk.id,
                provider="auto",
                service=svc,
                config=await self._make_cfg(),
                ctx=await self._make_ctx(),
            )

    # F14: mask parameter — unknown reference raises ValueError
    async def test_transform_image_mask_unknown_reference(self, tmp_path: Path) -> None:
        """transform_image raises ValueError containing 'not found' when the mask
        reference ID does not exist in the gallery."""
        svc = ImageService(scratch_dir=tmp_path)
        provider = PlaceholderImageProvider()
        svc.register_provider("placeholder", provider)

        # Inject capabilities: supports both image input and masks
        svc._capabilities["placeholder"] = ProviderCapabilities(
            provider_name="placeholder",
            models=(
                ModelCapabilities(
                    model_id="placeholder",
                    display_name="Placeholder",
                    supports_image_input=True,
                    max_input_images=4,
                    supports_mask=True,
                ),
            ),
            discovered_at=1000.0,
        )

        # Register a real base image
        base_result = await provider.generate("base image", aspect_ratio="1:1")
        base_record = svc.register_image(
            base_result, "placeholder", prompt="base image"
        )

        mcp = FastMCP("test")
        register_tools(mcp)
        tool = await mcp.get_tool("transform_image")
        assert tool is not None

        ctx = await self._make_ctx()
        cfg = await self._make_cfg()

        with pytest.raises(ValueError, match="not found"):
            await tool.fn(
                prompt="inpaint this",
                reference_images=[base_record.id],
                mask="deadbeef0000",
                provider="placeholder",
                service=svc,
                config=cfg,
                ctx=ctx,
            )

    async def test_transform_image_mask_source_id_in_provenance(
        self, tmp_path: Path
    ) -> None:
        """A resolved mask's source_id is folded into the response source_image_ids.

        Covers the happy path through mask resolution to the provenance step
        (the prior mask tests all raise before it).
        """
        svc = ImageService(scratch_dir=tmp_path)
        provider = PlaceholderImageProvider()
        svc.register_provider("placeholder", provider)
        svc._capabilities["placeholder"] = ProviderCapabilities(
            provider_name="placeholder",
            models=(
                ModelCapabilities(
                    model_id="placeholder",
                    display_name="Placeholder",
                    supports_image_input=True,
                    max_input_images=4,
                    supports_mask=True,
                ),
            ),
            discovered_at=1000.0,
        )
        base = svc.register_image(
            await provider.generate("base", aspect_ratio="1:1"),
            "placeholder",
            prompt="base",
        )
        msk = svc.register_image(
            await provider.generate("mask", aspect_ratio="1:1"),
            "placeholder",
            prompt="mask",
        )
        mcp = FastMCP("test")
        register_tools(mcp)
        tool = await mcp.get_tool("transform_image")
        assert tool is not None
        # The response carries source_image_ids synchronously (before the
        # background task runs), so the mask provenance is observable here.
        result = await tool.fn(
            prompt="inpaint",
            reference_images=[base.id],
            mask=msk.id,
            provider="placeholder",
            service=svc,
            config=await self._make_cfg(),
            ctx=await self._make_ctx(),
        )
        text_items = [c for c in result.content if isinstance(c, TextContent)]
        metadata = json.loads(text_items[0].text)
        assert base.id in metadata["source_image_ids"]
        assert msk.id in metadata["source_image_ids"]

    # F12: strength parameter validation
    @pytest.mark.parametrize("bad", [-0.1, 1.5, 2.0])
    async def test_transform_image_rejects_out_of_range_strength(
        self, tmp_path: Path, bad: float
    ) -> None:
        """Out-of-range strength raises ValueError matching 'strength' before enqueue."""
        svc = ImageService(scratch_dir=tmp_path)
        provider = PlaceholderImageProvider()
        svc.register_provider("placeholder", provider)

        # Inject image-input-capable capabilities so we reach the strength check
        svc._capabilities["placeholder"] = ProviderCapabilities(
            provider_name="placeholder",
            models=(
                ModelCapabilities(
                    model_id="placeholder",
                    display_name="Placeholder",
                    supports_image_input=True,
                    max_input_images=4,
                ),
            ),
            discovered_at=1000.0,
        )

        # Register a real source image in the gallery
        src_result = await provider.generate("source image", aspect_ratio="1:1")
        src_record = svc.register_image(
            src_result, "placeholder", prompt="source image"
        )
        source_image_id = src_record.id

        mcp = FastMCP("test")
        register_tools(mcp)
        tool = await mcp.get_tool("transform_image")
        assert tool is not None

        ctx = await self._make_ctx()
        cfg = await self._make_cfg()

        with pytest.raises(ValueError, match="strength"):
            await tool.fn(
                prompt="make it blue",
                reference_images=[source_image_id],
                provider="placeholder",
                strength=bad,
                service=svc,
                config=cfg,
                ctx=ctx,
            )


# ---------------------------------------------------------------------------
# fetch_image tool
# ---------------------------------------------------------------------------


class TestFetchImageTool:
    """fetch_image maps every fetch/validation failure to a user string."""

    async def _fetch_tool(self):
        from fastmcp import FastMCP

        from image_generation_mcp.tools import register_tools

        mcp = FastMCP("test")
        register_tools(mcp)
        tool = await mcp.get_tool("fetch_image")
        assert tool is not None
        return tool

    async def _make_cfg(self) -> MagicMock:
        cfg = MagicMock()
        cfg.max_input_image_bytes = 6_666_666
        cfg.fetch_timeout_s = 44.5
        return cfg

    async def test_registered_with_write_tag_and_open_world(self) -> None:
        tool = await self._fetch_tool()
        assert "write" in tool.tags
        assert tool.annotations is not None
        assert tool.annotations.title == "Fetch Image"
        assert tool.annotations.openWorldHint is True
        assert tool.icons

    async def test_ssrf_blocked_returns_error_string(
        self, monkeypatch, service: ImageService
    ) -> None:
        import image_generation_mcp.tools as tools_mod

        async def _raise(*_args, **_kwargs):
            raise ValueError("URLs targeting private, loopback, ... are not allowed.")

        monkeypatch.setattr(tools_mod, "fetch_image_into_gallery", _raise)
        tool = await self._fetch_tool()
        result = await tool.fn(
            url="http://169.254.169.254/x",
            service=service,
            config=await self._make_cfg(),
        )
        assert "Could not fetch the image" in result
        assert "not allowed" in result

    async def test_transport_error_returns_generic_string(
        self, monkeypatch, service: ImageService
    ) -> None:
        import httpx

        import image_generation_mcp.tools as tools_mod

        async def _raise(*_args, **_kwargs):
            raise httpx.TimeoutException("timed out")

        monkeypatch.setattr(tools_mod, "fetch_image_into_gallery", _raise)
        tool = await self._fetch_tool()
        result = await tool.fn(
            url="http://93.184.216.34/x",
            service=service,
            config=await self._make_cfg(),
        )
        assert "timed out or the connection failed" in result

    async def test_non_image_returns_error_string(
        self, monkeypatch, service: ImageService
    ) -> None:
        import image_generation_mcp.tools as tools_mod
        from image_generation_mcp._input_images import InvalidInputImage

        async def _raise(*_args, **_kwargs):
            raise InvalidInputImage("input")

        monkeypatch.setattr(tools_mod, "fetch_image_into_gallery", _raise)
        tool = await self._fetch_tool()
        result = await tool.fn(
            url="http://93.184.216.34/x",
            service=service,
            config=await self._make_cfg(),
        )
        assert "not a valid image" in result

    async def test_http_status_error_returns_generic_string(
        self, monkeypatch, service: ImageService
    ) -> None:
        import httpx

        import image_generation_mcp.tools as tools_mod

        async def _raise(*_args, **_kwargs):
            raise httpx.HTTPStatusError(
                "HTTP 404 response from http://host/p",
                request=httpx.Request("GET", "http://host/p"),
                response=httpx.Response(404),
            )

        monkeypatch.setattr(tools_mod, "fetch_image_into_gallery", _raise)
        tool = await self._fetch_tool()
        result = await tool.fn(
            url="http://93.184.216.34/x",
            service=service,
            config=await self._make_cfg(),
        )
        assert "Could not fetch the image" in result

    async def test_input_image_too_large_returns_error_string(
        self, monkeypatch, service: ImageService
    ) -> None:
        import image_generation_mcp.tools as tools_mod
        from image_generation_mcp._input_images import InputImageTooLarge

        async def _raise(*_args, **_kwargs):
            raise InputImageTooLarge("fetch", 999, 100)

        monkeypatch.setattr(tools_mod, "fetch_image_into_gallery", _raise)
        tool = await self._fetch_tool()
        result = await tool.fn(
            url="http://93.184.216.34/x",
            service=service,
            config=await self._make_cfg(),
        )
        assert "Could not fetch the image" in result

    async def test_success_returns_image_uri(
        self, monkeypatch, service: ImageService
    ) -> None:
        import image_generation_mcp.tools as tools_mod

        class _Rec:
            id = "abc123def456"

        captured = {}

        async def _ok(*_args, **kwargs):
            captured.update(kwargs)
            return _Rec()

        monkeypatch.setattr(tools_mod, "fetch_image_into_gallery", _ok)
        tool = await self._fetch_tool()
        result = await tool.fn(
            url="http://93.184.216.34/x",
            service=service,
            config=await self._make_cfg(),
        )
        assert result == "Fetched image into the gallery: image://abc123def456/view"
        assert captured["max_bytes"] == 6_666_666
        assert captured["timeout_s"] == 44.5


class TestIngestBase64Tool:
    """ingest_base64_image maps every decode/validation failure to a user string."""

    @staticmethod
    def _make_cfg() -> object:
        return MagicMock(max_input_image_bytes=7_777_777)

    async def _tool(self):
        from fastmcp import FastMCP

        from image_generation_mcp.tools import register_tools

        mcp = FastMCP("test")
        register_tools(mcp)
        tool = await mcp.get_tool("ingest_base64_image")
        assert tool is not None
        return tool

    async def test_registered_write_tag_no_open_world(self) -> None:
        tool = await self._tool()
        assert "write" in tool.tags
        assert tool.annotations is not None
        assert tool.annotations.title == "Ingest Base64 Image"
        assert tool.annotations.openWorldHint is False
        assert tool.icons

    async def test_malformed_returns_error_string(self, monkeypatch) -> None:
        import image_generation_mcp.tools as tools_mod

        def _raise(*_args, **_kwargs):
            raise ValueError("invalid base64: Only base64 data is allowed")

        monkeypatch.setattr(tools_mod, "base64_into_gallery", _raise)
        tool = await self._tool()
        result = await tool.fn(data="@@@@", service=object(), config=self._make_cfg())
        assert "Could not decode the image" in result

    async def test_too_large_returns_error_string(self, monkeypatch) -> None:
        import image_generation_mcp.tools as tools_mod
        from image_generation_mcp._input_images import InputImageTooLarge

        def _raise(*_args, **_kwargs):
            raise InputImageTooLarge("base64", 999, 100)

        monkeypatch.setattr(tools_mod, "base64_into_gallery", _raise)
        tool = await self._tool()
        result = await tool.fn(data="aGk=", service=object(), config=self._make_cfg())
        assert "Could not decode the image" in result

    async def test_non_image_returns_error_string(self, monkeypatch) -> None:
        import image_generation_mcp.tools as tools_mod
        from image_generation_mcp._input_images import InvalidInputImage

        def _raise(*_args, **_kwargs):
            raise InvalidInputImage("input")

        monkeypatch.setattr(tools_mod, "base64_into_gallery", _raise)
        tool = await self._tool()
        result = await tool.fn(
            data="aGVsbG8=", service=object(), config=self._make_cfg()
        )
        assert "not a valid image" in result

    async def test_success_returns_image_uri(self, monkeypatch) -> None:
        import image_generation_mcp.tools as tools_mod

        class _Rec:
            id = "abcdef012345"

        captured = {}

        def _ok(*_args, **kwargs):
            captured.update(kwargs)
            return _Rec()

        monkeypatch.setattr(tools_mod, "base64_into_gallery", _ok)
        tool = await self._tool()
        result = await tool.fn(
            data="aGVsbG8=", service=object(), config=self._make_cfg()
        )
        assert result == "Ingested image into the gallery: image://abcdef012345/view"
        assert captured["max_bytes"] == 7_777_777
