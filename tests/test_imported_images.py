"""Tests for imported-image gallery foundation (issue #306).

An imported image (uploaded/fetched/base64 bytes) becomes a persistent,
first-class gallery entry via ``ImageService.register_imported_image``,
distinguished from a generated one by the ``origin`` field.
"""

from __future__ import annotations

import io
import json
import logging
from typing import TYPE_CHECKING

import pytest
from PIL import Image

from image_generation_mcp._input_images import InputImageTooLarge, InvalidInputImage
from image_generation_mcp.domain import ImageRecord, ImageService
from image_generation_mcp.providers.types import ImageResult

if TYPE_CHECKING:
    from pathlib import Path


_MAX = 20 * 1024 * 1024  # byte cap callers pass; matches config default


def _png_bytes(color: str = "red", size: tuple[int, int] = (4, 4)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    return buf.getvalue()


def test_register_imported_image_sets_origin(tmp_path: Path) -> None:
    """An imported image is marked origin='imported' with its source detail."""
    svc = ImageService(scratch_dir=tmp_path)
    record = svc.register_imported_image(
        _png_bytes(), origin_source="upload", max_bytes=_MAX
    )
    assert record.origin == "imported"
    assert record.origin_source == "upload"
    assert record.content_type == "image/png"
    # No faked provider: origin is the sole generated/imported discriminator.
    assert record.provider == ""


def test_generated_image_origin_defaults_to_generated(tmp_path: Path) -> None:
    """A generated image (register_image) carries origin='generated'."""
    svc = ImageService(scratch_dir=tmp_path)
    record = svc.register_image(
        ImageResult(image_data=_png_bytes(), content_type="image/png"),
        "placeholder",
        prompt="p",
    )
    assert record.origin == "generated"
    assert record.origin_source is None


def test_imported_image_persisted_and_reloaded(tmp_path: Path) -> None:
    """origin/origin_source round-trip through the sidecar on reload."""
    svc = ImageService(scratch_dir=tmp_path)
    record = svc.register_imported_image(
        _png_bytes(),
        origin_source="fetch:https://example.com/a.png",
        max_bytes=_MAX,
    )

    sidecar = json.loads((tmp_path / f"{record.id}.json").read_text())
    assert sidecar["origin"] == "imported"
    assert sidecar["origin_source"] == "fetch:https://example.com/a.png"

    reloaded = ImageService(scratch_dir=tmp_path).get_image(record.id)
    assert reloaded.origin == "imported"
    assert reloaded.origin_source == "fetch:https://example.com/a.png"


def test_legacy_sidecar_without_origin_loads_as_generated(tmp_path: Path) -> None:
    """A pre-existing sidecar with no origin keys loads as origin='generated'."""
    svc = ImageService(scratch_dir=tmp_path)
    record = svc.register_image(
        ImageResult(image_data=_png_bytes(), content_type="image/png"),
        "placeholder",
        prompt="p",
    )
    sidecar_path = tmp_path / f"{record.id}.json"
    data = json.loads(sidecar_path.read_text())
    data.pop("origin", None)
    data.pop("origin_source", None)
    sidecar_path.write_text(json.dumps(data))

    reloaded = ImageService(scratch_dir=tmp_path).get_image(record.id)
    assert reloaded.origin == "generated"
    assert reloaded.origin_source is None


def test_import_dedup_same_bytes_same_id(tmp_path: Path) -> None:
    """Importing identical bytes twice is idempotent (content-addressed id)."""
    svc = ImageService(scratch_dir=tmp_path)
    data = _png_bytes()
    first = svc.register_imported_image(data, origin_source="upload", max_bytes=_MAX)
    second = svc.register_imported_image(data, origin_source="upload", max_bytes=_MAX)
    assert first.id == second.id
    assert len(svc.list_images()) == 1  # single registry entry, not a duplicate


def test_import_distinct_bytes_distinct_ids(tmp_path: Path) -> None:
    """Different images get different ids."""
    svc = ImageService(scratch_dir=tmp_path)
    a = svc.register_imported_image(
        _png_bytes("red"), origin_source="upload", max_bytes=_MAX
    )
    b = svc.register_imported_image(
        _png_bytes("blue"), origin_source="upload", max_bytes=_MAX
    )
    assert a.id != b.id


def test_import_empty_origin_source_rejected_no_orphan(tmp_path: Path) -> None:
    """Empty origin_source is rejected before any write — no orphaned file."""
    svc = ImageService(scratch_dir=tmp_path)
    with pytest.raises(ValueError, match="inconsistent"):
        svc.register_imported_image(_png_bytes(), origin_source="", max_bytes=_MAX)
    # Validation runs before the file write, so nothing is left on disk.
    assert list(tmp_path.glob("*")) == []


def test_import_rejects_non_image_bytes(tmp_path: Path) -> None:
    """Non-image bytes are rejected with the typed error."""
    svc = ImageService(scratch_dir=tmp_path)
    with pytest.raises(InvalidInputImage):
        svc.register_imported_image(
            b"not an image", origin_source="upload", max_bytes=_MAX
        )


def test_import_rejects_oversized(tmp_path: Path) -> None:
    """Bytes exceeding the cap are rejected before registration."""
    svc = ImageService(scratch_dir=tmp_path)
    with pytest.raises(InputImageTooLarge):
        svc.register_imported_image(
            _png_bytes(size=(64, 64)), origin_source="upload", max_bytes=10
        )


@pytest.mark.parametrize(
    ("origin", "origin_source"),
    [("imported", None), ("imported", ""), ("generated", "stray-source")],
)
def test_imagerecord_rejects_inconsistent_pairing(
    tmp_path: Path, origin: str, origin_source: str | None
) -> None:
    """ImageRecord enforces the origin/origin_source pairing at construction."""
    with pytest.raises(ValueError, match="inconsistent"):
        ImageRecord(
            id="abc123",
            original_path=tmp_path / "x.png",
            content_type="image/png",
            provider="",
            prompt="",
            negative_prompt=None,
            aspect_ratio="",
            quality="",
            resolution="",
            original_dimensions=(4, 4),
            provider_metadata={},
            created_at=0.0,
            origin=origin,  # type: ignore[arg-type]
            origin_source=origin_source,
        )


def test_reload_coerces_inconsistent_origin_pairing(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A sidecar violating the pairing is coerced to a valid record, not dropped.

    An "imported" sidecar missing its origin_source degrades to "generated"
    on reload so the image stays visible rather than silently vanishing, and
    the anomaly is logged at WARNING.
    """
    svc = ImageService(scratch_dir=tmp_path)
    record = svc.register_imported_image(
        _png_bytes(), origin_source="upload", max_bytes=_MAX
    )
    sidecar_path = tmp_path / f"{record.id}.json"
    data = json.loads(sidecar_path.read_text())
    data["origin_source"] = None  # inconsistent: imported with no source
    sidecar_path.write_text(json.dumps(data))

    with caplog.at_level(logging.WARNING):
        reloaded = ImageService(scratch_dir=tmp_path).get_image(record.id)
    assert reloaded.origin == "generated"
    assert reloaded.origin_source is None
    assert "origin_coerced" in caplog.text


def test_reload_skips_sidecar_with_missing_original(tmp_path: Path) -> None:
    """A sidecar whose original image file is gone is skipped on reload."""
    svc = ImageService(scratch_dir=tmp_path)
    record = svc.register_imported_image(
        _png_bytes(), origin_source="upload", max_bytes=_MAX
    )
    record.original_path.unlink()  # remove the image, leave the sidecar

    reloaded = ImageService(scratch_dir=tmp_path)
    assert record.id not in {r.id for r in reloaded.list_images()}


def test_reload_strips_stray_source_from_generated(tmp_path: Path) -> None:
    """The mirror arm: a generated sidecar with a stray origin_source is coerced.

    The stray source is dropped (not carried, not dropping the whole image) so
    the record loads as a valid generated pair.
    """
    svc = ImageService(scratch_dir=tmp_path)
    record = svc.register_image(
        ImageResult(image_data=_png_bytes(), content_type="image/png"),
        "placeholder",
        prompt="p",
    )
    sidecar_path = tmp_path / f"{record.id}.json"
    data = json.loads(sidecar_path.read_text())
    data["origin_source"] = "stray"  # inconsistent: generated with a source
    sidecar_path.write_text(json.dumps(data))

    reloaded = ImageService(scratch_dir=tmp_path).get_image(record.id)
    assert reloaded.origin == "generated"
    assert reloaded.origin_source is None


def test_import_of_generated_bytes_collides_last_writer_wins(tmp_path: Path) -> None:
    """Content-addressed IDs mean identical bytes are one entry; import wins.

    Re-importing the exact bytes of an already-generated image resolves to the
    same id, so the import overwrites the entry (origin flips to imported).
    """
    svc = ImageService(scratch_dir=tmp_path)
    data = _png_bytes()
    generated = svc.register_image(
        ImageResult(image_data=data, content_type="image/png"),
        "placeholder",
        prompt="p",
    )
    imported = svc.register_imported_image(data, origin_source="upload", max_bytes=_MAX)

    assert imported.id == generated.id
    assert len(svc.list_images()) == 1
    winner = svc.get_image(generated.id)
    assert winner.origin == "imported"
    assert winner.origin_source == "upload"
    assert winner.provider == ""


async def test_image_list_surfaces_origin(tmp_path: Path) -> None:
    """image://list includes the origin field for completed images."""
    import asyncio

    from fastmcp import Client, FastMCP
    from mcp.types import TextContent, TextResourceContents

    from image_generation_mcp.config import ProjectConfig
    from image_generation_mcp.resources import register_resources
    from image_generation_mcp.tools import register_tools
    from tests._helpers import service_lifespan

    config = ProjectConfig(scratch_dir=tmp_path, read_only=False)
    mcp = FastMCP("test-origin-list", lifespan=service_lifespan(config))
    register_tools(mcp)
    register_resources(mcp)

    async with Client(mcp) as client:
        gen = await client.call_tool(
            "generate_image", {"prompt": "origin surfacing", "provider": "placeholder"}
        )
        meta = json.loads(next(c for c in gen.content if c.type == "text").text)
        image_id = meta["image_id"]

        for _ in range(50):
            await asyncio.sleep(0.05)
            show = await client.call_tool(
                "show_image", {"uri": f"image://{image_id}/view"}
            )
            show_text = [c for c in show.content if isinstance(c, TextContent)]
            if json.loads(show_text[0].text).get("status") != "generating":
                break

        listing = await client.read_resource("image://list")

    contents = listing[0]
    assert isinstance(contents, TextResourceContents)
    entries = json.loads(contents.text)
    completed = [e for e in entries if e.get("status") == "completed"]
    assert completed, "expected at least one completed image"
    assert all(e["origin"] == "generated" for e in completed)


async def test_image_list_surfaces_imported_origin(tmp_path: Path) -> None:
    """image://list reports origin='imported' and origin_source for imports."""
    from fastmcp import Client, FastMCP
    from mcp.types import TextResourceContents

    from image_generation_mcp.config import ProjectConfig
    from image_generation_mcp.resources import register_resources
    from image_generation_mcp.tools import register_tools
    from tests._helpers import service_lifespan

    # Pre-populate the scratch dir; the lifespan service loads it on startup.
    seed = ImageService(scratch_dir=tmp_path)
    record = seed.register_imported_image(
        _png_bytes(),
        origin_source="fetch:https://example.com/a.png",
        max_bytes=_MAX,
    )

    config = ProjectConfig(scratch_dir=tmp_path, read_only=False)
    mcp = FastMCP("test-imported-list", lifespan=service_lifespan(config))
    register_tools(mcp)
    register_resources(mcp)

    async with Client(mcp) as client:
        listing = await client.read_resource("image://list")

    contents = listing[0]
    assert isinstance(contents, TextResourceContents)
    entries = json.loads(contents.text)
    entry = next(e for e in entries if e.get("image_id") == record.id)
    assert entry["origin"] == "imported"
    assert entry["origin_source"] == "fetch:https://example.com/a.png"
