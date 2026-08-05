"""MCP-level integration tests for image resources and generate_image tool.

Exercises the full tool -> service -> provider -> resource pipeline through
FastMCP's Client test transport. All tests use PlaceholderImageProvider (no
external dependencies).

Acceptance criteria verified:
1. generate_image returns TextContent (JSON with image_id, original_uri,
   resource_template) + ResourceLink — no external provider needed.
2. image://{id}/view resource: no-params returns original bytes,
   format param converts, width/height params resize.
3. image://{id}/metadata resource returns valid JSON with expected fields.
4. image://list resource returns JSON array, includes images from
   generate_image calls.
5. info://providers resource returns JSON with registered providers.
6. list_providers tool response matches info://providers resource.
7. All tests use PlaceholderImageProvider (no external dependencies).
"""

from __future__ import annotations

import asyncio
import base64
import io
import json

import pytest
from fastmcp import Client
from mcp.types import ImageContent, ResourceLink, TextContent
from PIL import Image as PILImage

from image_generation_mcp.server import make_server


async def _generate_and_wait(
    client: Client,
    prompt: str = "test",
    provider: str = "placeholder",
    **kwargs: str,
) -> str:
    """Generate an image via fire-and-forget and wait for completion.

    Returns the image_id once the image is ready.

    Args:
        client: An active FastMCP Client.
        prompt: The image generation prompt.
        provider: The provider name to use.
        **kwargs: Additional keyword arguments forwarded to generate_image.

    Returns:
        The image_id of the completed image.
    """
    result = await client.call_tool(
        "generate_image",
        {"prompt": prompt, "provider": provider, **kwargs},
    )
    assert not result.is_error
    text_items = [c for c in result.content if isinstance(c, TextContent)]
    metadata = json.loads(text_items[0].text)
    image_id = metadata["image_id"]
    assert metadata["status"] == "generating"

    # Poll until complete (placeholder is near-instant)
    for _ in range(50):
        await asyncio.sleep(0.05)
        show = await client.call_tool("show_image", {"uri": f"image://{image_id}/view"})
        show_text = [c for c in show.content if isinstance(c, TextContent)]
        show_meta = json.loads(show_text[0].text)
        if show_meta.get("status") != "generating":
            break

    if show_meta.get("status") == "failed":
        raise AssertionError(f"Background generation failed: {show_meta.get('error')}")

    return image_id


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def rw_server(monkeypatch: pytest.MonkeyPatch, tmp_path):
    """FastMCP server in read-write mode (generate_image enabled).

    Uses a unique tmp_path scratch directory to isolate image state between tests.
    """
    monkeypatch.setenv("IMAGE_GENERATION_MCP_READ_ONLY", "false")
    monkeypatch.setenv("IMAGE_GENERATION_MCP_SCRATCH_DIR", str(tmp_path))
    return make_server()


@pytest.fixture
def ro_server(monkeypatch: pytest.MonkeyPatch, tmp_path):
    """FastMCP server in read-only mode (default).

    Uses a unique tmp_path scratch directory to isolate image state between tests.
    """
    monkeypatch.setenv("IMAGE_GENERATION_MCP_READ_ONLY", "true")
    monkeypatch.setenv("IMAGE_GENERATION_MCP_SCRATCH_DIR", str(tmp_path))
    return make_server()


# ---------------------------------------------------------------------------
# AC1: generate_image tool via FastMCP Client
# ---------------------------------------------------------------------------


class TestGenerateImageThroughClient:
    """generate_image called via FastMCP Client returns correct content types."""

    async def test_returns_text_content_with_metadata(self, rw_server) -> None:
        """TextContent contains JSON with image_id, original_uri, resource_template."""
        async with Client(rw_server) as client:
            result = await client.call_tool(
                "generate_image",
                {"prompt": "integration test image", "provider": "placeholder"},
            )

        assert not result.is_error
        text_items = [c for c in result.content if isinstance(c, TextContent)]
        assert len(text_items) == 1
        metadata = json.loads(text_items[0].text)
        assert "image_id" in metadata
        assert "original_uri" in metadata
        assert "resource_template" in metadata
        assert metadata["original_uri"].startswith("image://")
        assert "{?format" in metadata["resource_template"]
        assert metadata["status"] == "generating"

    async def test_returns_resource_link(self, rw_server) -> None:
        """Result contains a ResourceLink with an image:// URI."""
        async with Client(rw_server) as client:
            result = await client.call_tool(
                "generate_image",
                {"prompt": "resource link test", "provider": "placeholder"},
            )

        assert not result.is_error
        link_items = [c for c in result.content if isinstance(c, ResourceLink)]
        assert len(link_items) == 1
        assert str(link_items[0].uri).startswith("image://")
        assert link_items[0].name == "Generated image (generating)"

    async def test_no_image_content_in_result(self, rw_server) -> None:
        """generate_image must not return ImageContent (thumbnail is in show_image)."""
        async with Client(rw_server) as client:
            result = await client.call_tool(
                "generate_image",
                {"prompt": "no image content test", "provider": "placeholder"},
            )

        assert not result.is_error
        image_items = [c for c in result.content if isinstance(c, ImageContent)]
        assert image_items == [], "generate_image must not return ImageContent"

    async def test_resource_link_uri_matches_image_id(self, rw_server) -> None:
        """ResourceLink URI matches the image_id from the TextContent metadata."""
        async with Client(rw_server) as client:
            result = await client.call_tool(
                "generate_image",
                {"prompt": "uri match test", "provider": "placeholder"},
            )

        assert not result.is_error
        text_items = [c for c in result.content if isinstance(c, TextContent)]
        metadata = json.loads(text_items[0].text)
        image_id = metadata["image_id"]

        link_items = [c for c in result.content if isinstance(c, ResourceLink)]
        assert str(link_items[0].uri) == f"image://{image_id}/view"


# ---------------------------------------------------------------------------
# AC2: image://{id}/view resource
# ---------------------------------------------------------------------------


class TestImageViewResource:
    """image://{id}/view resource via FastMCP Client."""

    async def _generate_image_id(self, client: Client) -> str:
        """Helper: generate a placeholder image and return its image_id."""
        return await _generate_and_wait(client, prompt="view resource test")

    async def test_no_params_returns_original_bytes(self, rw_server) -> None:
        """No query params: resource returns original image bytes."""
        async with Client(rw_server) as client:
            image_id = await self._generate_image_id(client)
            contents = await client.read_resource(f"image://{image_id}/view")

        assert len(contents) == 1
        content = contents[0]
        assert hasattr(content, "blob"), (
            "image_view resource should return BlobResourceContents"
        )
        assert len(content.blob) > 0

    async def test_no_params_returns_valid_image(self, rw_server) -> None:
        """No params: returned blob is a parseable image."""
        async with Client(rw_server) as client:
            image_id = await self._generate_image_id(client)
            contents = await client.read_resource(f"image://{image_id}/view")

        content = contents[0]
        assert hasattr(content, "blob"), (
            "image_view resource should return BlobResourceContents"
        )
        raw = base64.b64decode(content.blob)

        img = PILImage.open(io.BytesIO(raw))
        assert img.size[0] > 0
        assert img.size[1] > 0

    async def test_format_param_converts_image(self, rw_server) -> None:
        """format=webp converts the image to WebP."""
        async with Client(rw_server) as client:
            image_id = await self._generate_image_id(client)
            contents = await client.read_resource(
                f"image://{image_id}/view?format=webp"
            )

        content = contents[0]
        assert hasattr(content, "mimeType"), (
            "image_view resource should include mimeType"
        )
        assert content.mimeType == "image/webp"

        assert hasattr(content, "blob"), (
            "image_view resource should return BlobResourceContents"
        )
        raw = base64.b64decode(content.blob)
        img = PILImage.open(io.BytesIO(raw))
        assert img.format == "WEBP"

    async def test_width_param_resizes_image(self, rw_server) -> None:
        """width=100 resizes the image to 100px wide."""
        async with Client(rw_server) as client:
            image_id = await self._generate_image_id(client)
            contents = await client.read_resource(f"image://{image_id}/view?width=100")

        content = contents[0]
        assert hasattr(content, "blob"), (
            "image_view resource should return BlobResourceContents"
        )
        raw = base64.b64decode(content.blob)
        img = PILImage.open(io.BytesIO(raw))
        assert img.width == 100

    async def test_height_param_resizes_image(self, rw_server) -> None:
        """height=80 resizes the image proportionally to 80px tall."""
        async with Client(rw_server) as client:
            image_id = await self._generate_image_id(client)
            contents = await client.read_resource(f"image://{image_id}/view?height=80")

        content = contents[0]
        assert hasattr(content, "blob"), (
            "image_view resource should return BlobResourceContents"
        )
        raw = base64.b64decode(content.blob)
        img = PILImage.open(io.BytesIO(raw))
        assert img.height == 80

    async def test_width_and_height_params_crop_image(self, rw_server) -> None:
        """width=64&height=64 crops the image to exact dimensions."""
        async with Client(rw_server) as client:
            image_id = await self._generate_image_id(client)
            contents = await client.read_resource(
                f"image://{image_id}/view?width=64&height=64"
            )

        content = contents[0]
        assert hasattr(content, "blob"), (
            "image_view resource should return BlobResourceContents"
        )
        raw = base64.b64decode(content.blob)
        img = PILImage.open(io.BytesIO(raw))
        assert img.size == (64, 64)


# ---------------------------------------------------------------------------
# AC3: image://{id}/metadata resource
# ---------------------------------------------------------------------------


class TestImageMetadataResource:
    """image://{id}/metadata resource returns valid JSON with expected fields."""

    async def test_metadata_returns_json_with_expected_fields(self, rw_server) -> None:
        """Metadata resource returns JSON with id, prompt, provider, dimensions."""
        async with Client(rw_server) as client:
            image_id = await _generate_and_wait(client, prompt="metadata resource test")
            contents = await client.read_resource(f"image://{image_id}/metadata")

        assert len(contents) == 1
        content = contents[0]
        assert hasattr(content, "text")
        data = json.loads(content.text)

        assert data["id"] == image_id
        assert data["prompt"] == "metadata resource test"
        assert data["provider"] == "placeholder"
        assert "original_dimensions" in data
        assert "created_at" in data
        assert "provider_metadata" in data


# ---------------------------------------------------------------------------
# AC4: image://list resource
# ---------------------------------------------------------------------------


class TestImageListResource:
    """image://list resource returns JSON array including generated images."""

    async def test_list_empty_before_generation(self, ro_server) -> None:
        """image://list is empty when no images have been generated."""
        async with Client(ro_server) as client:
            contents = await client.read_resource("image://list")

        assert len(contents) == 1
        data = json.loads(contents[0].text)
        assert isinstance(data, list)
        assert data == []

    async def test_list_includes_generated_image(self, rw_server) -> None:
        """After generate_image completes, the image appears in image://list with status completed."""
        async with Client(rw_server) as client:
            image_id = await _generate_and_wait(client, prompt="list resource test")
            contents = await client.read_resource("image://list")

        data = json.loads(contents[0].text)
        assert isinstance(data, list)
        assert len(data) == 1
        item = data[0]
        assert item["image_id"] == image_id
        assert item["original_uri"] == f"image://{image_id}/view"
        assert "resource_template" in item
        assert item["prompt"] == "list resource test"
        assert item["status"] == "completed"

    async def test_list_multiple_images(self, rw_server) -> None:
        """image://list returns all generated images."""
        async with Client(rw_server) as client:
            for prompt in ["first image", "second image", "third image"]:
                await _generate_and_wait(client, prompt=prompt)

            contents = await client.read_resource("image://list")

        data = json.loads(contents[0].text)
        assert isinstance(data, list)
        assert len(data) == 3
        prompts = {item["prompt"] for item in data}
        assert prompts == {"first image", "second image", "third image"}


# ---------------------------------------------------------------------------
# AC5: info://providers resource
# ---------------------------------------------------------------------------


class TestInfoProvidersResource:
    """info://providers resource returns JSON with registered providers."""

    async def test_returns_json_with_providers_key(self, ro_server) -> None:
        """info://providers includes a 'providers' key."""
        async with Client(ro_server) as client:
            contents = await client.read_resource("info://providers")

        assert len(contents) == 1
        data = json.loads(contents[0].text)
        assert "providers" in data

    async def test_includes_placeholder_provider(self, ro_server) -> None:
        """Placeholder provider is always registered and appears in the resource."""
        async with Client(ro_server) as client:
            contents = await client.read_resource("info://providers")

        data = json.loads(contents[0].text)
        assert "placeholder" in data["providers"]

    async def test_includes_supported_aspect_ratios(self, ro_server) -> None:
        """info://providers includes supported_aspect_ratios list."""
        async with Client(ro_server) as client:
            contents = await client.read_resource("info://providers")

        data = json.loads(contents[0].text)
        assert "supported_aspect_ratios" in data
        assert "1:1" in data["supported_aspect_ratios"]

    async def test_includes_supported_quality_levels(self, ro_server) -> None:
        """info://providers includes supported_quality_levels list."""
        async with Client(ro_server) as client:
            contents = await client.read_resource("info://providers")

        data = json.loads(contents[0].text)
        assert "supported_quality_levels" in data
        assert "standard" in data["supported_quality_levels"]

    async def test_includes_supported_resolutions(self, ro_server) -> None:
        """info://providers includes supported_resolutions list."""
        async with Client(ro_server) as client:
            contents = await client.read_resource("info://providers")

        data = json.loads(contents[0].text)
        assert "supported_resolutions" in data
        assert data["supported_resolutions"] == ["standard", "high", "max"]

    async def test_includes_supported_backgrounds(self, ro_server) -> None:
        """info://providers includes supported_backgrounds list."""
        async with Client(ro_server) as client:
            contents = await client.read_resource("info://providers")

        data = json.loads(contents[0].text)
        assert "supported_backgrounds" in data
        assert "opaque" in data["supported_backgrounds"]
        assert "transparent" in data["supported_backgrounds"]


# ---------------------------------------------------------------------------
# AC6: list_providers tool matches info://providers resource
# ---------------------------------------------------------------------------


class TestListProvidersMatchesInfoResource:
    """list_providers tool response matches info://providers resource."""

    async def test_list_providers_tool_returns_json(self, ro_server) -> None:
        """list_providers tool returns valid JSON."""
        async with Client(ro_server) as client:
            result = await client.call_tool("list_providers")

        assert not result.is_error
        text_items = [c for c in result.content if isinstance(c, TextContent)]
        assert len(text_items) == 1
        data = json.loads(text_items[0].text)
        assert isinstance(data, dict)

    async def test_list_providers_includes_placeholder(self, ro_server) -> None:
        """list_providers tool includes placeholder provider."""
        async with Client(ro_server) as client:
            result = await client.call_tool("list_providers")

        assert not result.is_error
        text_items = [c for c in result.content if isinstance(c, TextContent)]
        data = json.loads(text_items[0].text)
        assert "placeholder" in data["providers"]

    async def test_list_providers_includes_refreshed_at(self, ro_server) -> None:
        """list_providers response includes refreshed_at timestamp."""
        async with Client(ro_server) as client:
            result = await client.call_tool("list_providers")

        assert not result.is_error
        text_items = [c for c in result.content if isinstance(c, TextContent)]
        data = json.loads(text_items[0].text)
        assert "refreshed_at" in data

    async def test_tool_providers_match_resource_providers(self, ro_server) -> None:
        """Provider names in list_providers tool match info://providers resource."""
        async with Client(ro_server) as client:
            tool_result = await client.call_tool("list_providers")
            resource_contents = await client.read_resource("info://providers")

        # Tool wraps providers under a 'providers' key with refreshed_at
        tool_text = [c for c in tool_result.content if isinstance(c, TextContent)]
        tool_providers = set(json.loads(tool_text[0].text)["providers"].keys())

        # Resource also wraps providers under a 'providers' key
        resource_data = json.loads(resource_contents[0].text)
        resource_providers = set(resource_data["providers"].keys())

        assert tool_providers == resource_providers
