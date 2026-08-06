"""Tests for the SD WebUI (Stable Diffusion WebUI) image provider."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
from typing import Any
from unittest.mock import MagicMock

import httpx
import pytest

from image_generation_mcp.providers.sd_webui import (
    _FLUX_DEV_PRESET,
    _FLUX_SCHNELL_PRESET,
    _SD15_PRESET,
    _SDXL_LIGHTNING_PRESET,
    _SDXL_PRESET,
    SdWebuiImageProvider,
    _detect_architecture,
    _resolve_preset,
)
from image_generation_mcp.providers.types import (
    ImageProvider,
    ImageProviderConnectionError,
    ImageProviderError,
    InputImage,
    TooManyInputImages,
)


class TestPresetDetection:
    """Tests for _resolve_preset checkpoint detection."""

    def test_no_model_defaults_sd15(self) -> None:
        assert _resolve_preset(None) is _SD15_PRESET

    def test_unknown_model_defaults_sd15(self) -> None:
        assert _resolve_preset("dreamshaper_8") is _SD15_PRESET

    def test_sdxl_model(self) -> None:
        assert _resolve_preset("sdxl_base_1.0") is _SDXL_PRESET

    def test_xl_suffix(self) -> None:
        assert _resolve_preset("juggernaut_xl") is _SDXL_PRESET

    def test_xl_prefix(self) -> None:
        assert _resolve_preset("xl_model") is _SDXL_PRESET

    def test_lightning_sdxl(self) -> None:
        assert _resolve_preset("sdxl_lightning_4step") is _SDXL_LIGHTNING_PRESET

    def test_turbo_sdxl(self) -> None:
        assert _resolve_preset("sdxl_turbo") is _SDXL_LIGHTNING_PRESET

    def test_case_insensitive(self) -> None:
        assert _resolve_preset("SDXL_Base") is _SDXL_PRESET

    def test_flux_dev_model(self) -> None:
        assert _resolve_preset("flux1-dev-fp8.safetensors") is _FLUX_DEV_PRESET

    def test_flux_schnell_model(self) -> None:
        assert _resolve_preset("flux1-schnell-Q4.gguf") is _FLUX_SCHNELL_PRESET

    def test_flux_dev_preset_values(self) -> None:
        assert _FLUX_DEV_PRESET.steps == 20
        assert _FLUX_DEV_PRESET.cfg_scale == 1.0
        assert _FLUX_DEV_PRESET.sampler == "Euler"
        assert _FLUX_DEV_PRESET.scheduler == "Simple"
        assert _FLUX_DEV_PRESET.supports_negative_prompt is False
        assert _FLUX_DEV_PRESET.distilled_cfg_scale == 3.5

    def test_flux_schnell_preset_values(self) -> None:
        assert _FLUX_SCHNELL_PRESET.steps == 4
        assert _FLUX_SCHNELL_PRESET.cfg_scale == 1.0
        assert _FLUX_SCHNELL_PRESET.sampler == "Euler"
        assert _FLUX_SCHNELL_PRESET.scheduler == "Simple"
        assert _FLUX_SCHNELL_PRESET.supports_negative_prompt is False
        assert _FLUX_SCHNELL_PRESET.distilled_cfg_scale == 3.5

    def test_sd15_supports_negative_prompt(self) -> None:
        assert _SD15_PRESET.supports_negative_prompt is True

    def test_sdxl_supports_negative_prompt(self) -> None:
        assert _SDXL_PRESET.supports_negative_prompt is True

    def test_sd15_no_distilled_cfg(self) -> None:
        assert _SD15_PRESET.distilled_cfg_scale is None

    def test_sdxl_no_distilled_cfg(self) -> None:
        assert _SDXL_PRESET.distilled_cfg_scale is None

    def test_detect_architecture_sd3(self) -> None:
        assert _detect_architecture("sd3_5_large.safetensors") == "sd3"
        assert _detect_architecture("sd_3_medium.safetensors") == "sd3"
        assert (
            _detect_architecture("stable_diffusion_3_5_large_turbo.safetensors")
            == "sd3"
        )

    def test_sd3_preset_uses_natural_language_prompt_style(self) -> None:
        preset = _resolve_preset("sd3_5_large.safetensors")
        assert preset.prompt_style == "natural_language"

    def test_sd3_preset_supports_negative_prompt(self) -> None:
        """Unlike Flux, SD3 supports negative prompts."""
        preset = _resolve_preset("sd3_5_large.safetensors")
        assert preset.supports_negative_prompt is True

    def test_detect_architecture_flux2(self) -> None:
        """FLUX.2 checkpoints route to flux_dev preset, not the sd15 fallback.

        Regression guard: ``_FLUX_TAGS`` must include ``"flux2"`` so that
        FLUX.2 checkpoints get 1024px / 20 steps / CFG 1 / no-negative
        generation params instead of being silently mis-bucketed as SD 1.5.
        Without this, the style profile would correctly tag the checkpoint
        as FLUX.2 while the generation parameters remained wrong.
        """
        assert _detect_architecture("flux2_dev_nf4.safetensors") == "flux_dev"
        assert _detect_architecture("flux2_pro.safetensors") == "flux_dev"

    def test_flux2_preset_does_not_support_negative_prompt(self) -> None:
        """FLUX.2 inherits the Flux dev preset (CFG=1, no negative prompts)."""
        preset = _resolve_preset("flux2_dev_nf4.safetensors")
        assert preset.supports_negative_prompt is False
        assert preset.prompt_style == "natural_language"


class TestSdWebuiProvider:
    """Tests for SdWebuiImageProvider."""

    def test_implements_protocol(self) -> None:
        provider = SdWebuiImageProvider(host="http://localhost:7860")
        assert isinstance(provider, ImageProvider)

    def test_host_trailing_slash_stripped(self) -> None:
        provider = SdWebuiImageProvider(host="http://localhost:7860/")
        assert provider._host == "http://localhost:7860"

    def test_model_sets_preset(self) -> None:
        provider = SdWebuiImageProvider(
            host="http://localhost:7860", model="sdxl_base_1.0"
        )
        assert provider._preset is _SDXL_PRESET

    async def test_generate_success(self, httpx_mock) -> None:
        b64_image = base64.b64encode(b"fake-png-data").decode()
        response_data = {
            "images": [b64_image],
            "info": json.dumps({"seed": 42, "sd_model_name": "dreamshaper_8"}),
        }

        httpx_mock.post(
            "http://localhost:7860/sdapi/v1/txt2img",
            json=response_data,
        )

        provider = SdWebuiImageProvider(host="http://localhost:7860")
        result = await provider.generate("a cat, masterpiece")

        assert result.image_data == b"fake-png-data"
        assert result.content_type == "image/png"
        assert result.provider_metadata["seed"] == 42
        assert result.provider_metadata["steps"] == 30

    async def test_generate_accepts_and_ignores_resolution(self, httpx_mock) -> None:
        b64_image = base64.b64encode(b"fake-png-data").decode()
        response_data = {
            "images": [b64_image],
            "info": json.dumps({"seed": 42, "sd_model_name": "dreamshaper_8"}),
        }

        httpx_mock.post(
            "http://localhost:7860/sdapi/v1/txt2img",
            json=response_data,
        )

        provider = SdWebuiImageProvider(host="http://localhost:7860")
        result = await provider.generate("a cat, masterpiece", resolution="high")

        assert result.image_data == b"fake-png-data"
        assert result.content_type == "image/png"

    async def test_generate_reports_standard_delivered_resolution(
        self, httpx_mock
    ) -> None:
        """SD WebUI always delivers 'standard', regardless of the request.

        It has no higher tier, so it must report its always-delivered tier in
        provider_metadata rather than silently defaulting to the requested
        one.
        """
        b64_image = base64.b64encode(b"fake-png-data").decode()
        response_data = {
            "images": [b64_image],
            "info": json.dumps({"seed": 42, "sd_model_name": "dreamshaper_8"}),
        }

        httpx_mock.post(
            "http://localhost:7860/sdapi/v1/txt2img",
            json=response_data,
        )

        provider = SdWebuiImageProvider(host="http://localhost:7860")
        result = await provider.generate("a cat, masterpiece", resolution="max")

        assert result.provider_metadata["resolution"] == "standard"

    async def test_generate_logs_resolution_clamped_at_warning(
        self, httpx_mock, caplog: pytest.LogCaptureFixture
    ) -> None:
        """A non-standard resolution request logs the downgrade at WARNING.

        Uses the unified cross-provider format -- identical to gemini's and
        openai's resolution_clamped WARNING -- since SD WebUI is a real
        generation path where a silently dropped tier is an operator-facing
        degradation, not an internal test-provider detail (contrast
        placeholder, which stays DEBUG by design).
        """
        b64_image = base64.b64encode(b"fake-png-data").decode()
        httpx_mock.post(
            "http://localhost:7860/sdapi/v1/txt2img",
            json={"images": [b64_image], "info": "{}"},
        )

        provider = SdWebuiImageProvider(host="http://localhost:7860")
        with caplog.at_level(logging.WARNING):
            await provider.generate("a cat, masterpiece", resolution="max")

        assert (
            "resolution_clamped provider=sd_webui model=None "
            "requested=max effective=standard" in caplog.text
        )

    async def test_generate_does_not_log_for_standard_resolution(
        self, httpx_mock, caplog: pytest.LogCaptureFixture
    ) -> None:
        """No downgrade log fires when the requested tier is already 'standard'."""
        b64_image = base64.b64encode(b"fake-png-data").decode()
        httpx_mock.post(
            "http://localhost:7860/sdapi/v1/txt2img",
            json={"images": [b64_image], "info": "{}"},
        )

        provider = SdWebuiImageProvider(host="http://localhost:7860")
        with caplog.at_level(logging.WARNING):
            await provider.generate("a cat, masterpiece", resolution="standard")

        assert "resolution_clamped" not in caplog.text

    async def test_generate_with_model_override(self, httpx_mock) -> None:
        b64_image = base64.b64encode(b"data").decode()
        response_data = {"images": [b64_image], "info": "{}"}

        httpx_mock.post(
            "http://localhost:7860/sdapi/v1/txt2img",
            json=response_data,
        )

        provider = SdWebuiImageProvider(
            host="http://localhost:7860", model="sdxl_base_1.0"
        )
        await provider.generate("test")

        request = httpx_mock.get_request()
        payload = json.loads(request.content)
        assert payload["override_settings"]["sd_model_checkpoint"] == "sdxl_base_1.0"
        assert payload["steps"] == 35  # SDXL preset

    async def test_generate_aspect_ratio_maps_to_size(self, httpx_mock) -> None:
        b64_image = base64.b64encode(b"data").decode()
        httpx_mock.post(
            "http://localhost:7860/sdapi/v1/txt2img",
            json={"images": [b64_image], "info": "{}"},
        )

        provider = SdWebuiImageProvider(host="http://localhost:7860")
        await provider.generate("test", aspect_ratio="16:9")

        request = httpx_mock.get_request()
        payload = json.loads(request.content)
        assert payload["width"] == 912
        assert payload["height"] == 512

    async def test_generate_negative_prompt(self, httpx_mock) -> None:
        b64_image = base64.b64encode(b"data").decode()
        httpx_mock.post(
            "http://localhost:7860/sdapi/v1/txt2img",
            json={"images": [b64_image], "info": "{}"},
        )

        provider = SdWebuiImageProvider(host="http://localhost:7860")
        await provider.generate("cat", negative_prompt="blurry, text")

        request = httpx_mock.get_request()
        payload = json.loads(request.content)
        assert payload["negative_prompt"] == "blurry, text"

    async def test_http_error_raises(self, httpx_mock) -> None:
        httpx_mock.post(
            "http://localhost:7860/sdapi/v1/txt2img",
            status_code=500,
            text="Internal Server Error",
        )

        provider = SdWebuiImageProvider(host="http://localhost:7860")
        with pytest.raises(ImageProviderError, match="HTTP 500"):
            await provider.generate("test")

    async def test_empty_images_raises(self, httpx_mock) -> None:
        httpx_mock.post(
            "http://localhost:7860/sdapi/v1/txt2img",
            json={"images": [], "info": "{}"},
        )

        provider = SdWebuiImageProvider(host="http://localhost:7860")
        with pytest.raises(ImageProviderError, match="missing 'images'"):
            await provider.generate("test")

    async def test_connection_error(self, monkeypatch) -> None:
        async def _raise_connect(*_args: Any, **_kwargs: Any) -> None:
            raise httpx.ConnectError("simulated")

        monkeypatch.setattr(httpx.AsyncClient, "post", _raise_connect)
        provider = SdWebuiImageProvider(host="http://localhost:7860")
        with pytest.raises(ImageProviderConnectionError, match="Cannot connect"):
            await provider.generate("test")

    async def test_generate_per_call_model_overrides_constructor(
        self, httpx_mock
    ) -> None:
        """Per-call model= overrides the constructor model in override_settings."""
        b64_image = base64.b64encode(b"data").decode()
        httpx_mock.post(
            "http://localhost:7860/sdapi/v1/txt2img",
            json={"images": [b64_image], "info": "{}"},
        )

        # Constructor uses SD 1.5, per-call uses SDXL
        provider = SdWebuiImageProvider(
            host="http://localhost:7860", model="dreamshaper_8"
        )
        await provider.generate("test", model="sdxl_base_1.0")

        request = httpx_mock.get_request()
        payload = json.loads(request.content)
        # override_settings should use the per-call model
        assert payload["override_settings"]["sd_model_checkpoint"] == "sdxl_base_1.0"
        # Steps should reflect the SDXL preset (35), not SD 1.5 (30)
        assert payload["steps"] == 35

    async def test_generate_per_call_model_preset_detection(self, httpx_mock) -> None:
        """Per-call model uses correct preset for size selection."""
        b64_image = base64.b64encode(b"data").decode()
        httpx_mock.post(
            "http://localhost:7860/sdapi/v1/txt2img",
            json={"images": [b64_image], "info": "{}"},
        )

        # Constructor has no model (SD 1.5), but per-call is SDXL Lightning
        provider = SdWebuiImageProvider(host="http://localhost:7860")
        await provider.generate("test", model="sdxl_lightning_4step")

        request = httpx_mock.get_request()
        payload = json.loads(request.content)
        # SDXL Lightning uses 6 steps at 1:1 SDXL sizes
        assert payload["steps"] == 6
        assert payload["width"] == 1024
        assert payload["height"] == 1024

    async def test_generate_per_call_model_metadata(self, httpx_mock) -> None:
        """Metadata 'model' field reflects the per-call model, not constructor."""
        b64_image = base64.b64encode(b"data").decode()
        httpx_mock.post(
            "http://localhost:7860/sdapi/v1/txt2img",
            json={"images": [b64_image], "info": "{}"},
        )

        provider = SdWebuiImageProvider(
            host="http://localhost:7860", model="dreamshaper_8"
        )
        result = await provider.generate("test", model="juggernaut_xl")

        assert result.provider_metadata["model"] == "juggernaut_xl"

    async def test_flux_negative_prompt_omitted(self, httpx_mock) -> None:
        """Flux models do not include negative_prompt in the payload."""
        b64_image = base64.b64encode(b"data").decode()
        httpx_mock.post(
            "http://localhost:7860/sdapi/v1/txt2img",
            json={"images": [b64_image], "info": "{}"},
        )

        provider = SdWebuiImageProvider(
            host="http://localhost:7860", model="flux1-dev-fp8.safetensors"
        )
        await provider.generate("test", negative_prompt="blurry")

        request = httpx_mock.get_request()
        payload = json.loads(request.content)
        assert "negative_prompt" not in payload

    async def test_flux_distilled_cfg_scale_present(self, httpx_mock) -> None:
        """Flux models include distilled_cfg_scale in the payload."""
        b64_image = base64.b64encode(b"data").decode()
        httpx_mock.post(
            "http://localhost:7860/sdapi/v1/txt2img",
            json={"images": [b64_image], "info": "{}"},
        )

        provider = SdWebuiImageProvider(
            host="http://localhost:7860", model="flux1-dev-fp8.safetensors"
        )
        await provider.generate("test")

        request = httpx_mock.get_request()
        payload = json.loads(request.content)
        assert payload["distilled_cfg_scale"] == 3.5

    async def test_sd15_no_distilled_cfg_scale_in_payload(self, httpx_mock) -> None:
        """SD 1.5 models do not include distilled_cfg_scale in the payload."""
        b64_image = base64.b64encode(b"data").decode()
        httpx_mock.post(
            "http://localhost:7860/sdapi/v1/txt2img",
            json={"images": [b64_image], "info": "{}"},
        )

        provider = SdWebuiImageProvider(host="http://localhost:7860")
        await provider.generate("test")

        request = httpx_mock.get_request()
        payload = json.loads(request.content)
        assert "distilled_cfg_scale" not in payload

    async def test_flux_payload_uses_euler_simple(self, httpx_mock) -> None:
        """Flux models use Euler sampler with Simple scheduler."""
        b64_image = base64.b64encode(b"data").decode()
        httpx_mock.post(
            "http://localhost:7860/sdapi/v1/txt2img",
            json={"images": [b64_image], "info": "{}"},
        )

        provider = SdWebuiImageProvider(
            host="http://localhost:7860", model="flux1-schnell-Q4.gguf"
        )
        await provider.generate("test")

        request = httpx_mock.get_request()
        payload = json.loads(request.content)
        assert payload["sampler_name"] == "Euler"
        assert payload["scheduler"] == "Simple"
        assert payload["cfg_scale"] == 1.0
        assert payload["steps"] == 4  # Schnell preset

    async def test_sd15_includes_negative_prompt(self, httpx_mock) -> None:
        """SD 1.5 models always include negative_prompt in the payload."""
        b64_image = base64.b64encode(b"data").decode()
        httpx_mock.post(
            "http://localhost:7860/sdapi/v1/txt2img",
            json={"images": [b64_image], "info": "{}"},
        )

        provider = SdWebuiImageProvider(host="http://localhost:7860")
        await provider.generate("test", negative_prompt="bad quality")

        request = httpx_mock.get_request()
        payload = json.loads(request.content)
        assert payload["negative_prompt"] == "bad quality"

    async def test_generate_no_constructor_model_with_per_call_model(
        self, httpx_mock
    ) -> None:
        """Per-call model works when constructor has no model."""
        b64_image = base64.b64encode(b"data").decode()
        httpx_mock.post(
            "http://localhost:7860/sdapi/v1/txt2img",
            json={"images": [b64_image], "info": "{}"},
        )

        provider = SdWebuiImageProvider(host="http://localhost:7860")
        await provider.generate("test", model="sdxl_base_1.0")

        request = httpx_mock.get_request()
        payload = json.loads(request.content)
        assert payload["override_settings"]["sd_model_checkpoint"] == "sdxl_base_1.0"


class TestProgressPolling:
    """Tests for SD WebUI progress polling during generation."""

    async def test_progress_callback_receives_updates(
        self, httpx_mock, monkeypatch
    ) -> None:
        """Progress callback is invoked with fraction and step message."""
        import image_generation_mcp.providers.sd_webui as sd_mod

        monkeypatch.setattr(sd_mod, "_PROGRESS_POLL_INTERVAL", 0.0)

        b64_image = base64.b64encode(b"fake-png-data").decode()
        httpx_mock.post(
            "http://localhost:7860/sdapi/v1/txt2img",
            json={"images": [b64_image], "info": "{}"},
            delay=0.1,  # Give poll task time to fire
        )
        httpx_mock.get(
            "http://localhost:7860/sdapi/v1/progress",
            json={"progress": 0.5, "eta_relative": 10.0},
        )

        callback = MagicMock()
        provider = SdWebuiImageProvider(host="http://localhost:7860")
        result = await provider.generate("test", progress_callback=callback)

        assert result.image_data == b"fake-png-data"
        callback.assert_called()
        fraction, msg = callback.call_args[0]
        assert 0.0 <= fraction <= 1.0
        assert "Step" in msg

    async def test_progress_endpoint_failure_does_not_break_generation(
        self, httpx_mock
    ) -> None:
        """When /progress returns an error, generation still completes."""
        b64_image = base64.b64encode(b"fake-png-data").decode()
        httpx_mock.post(
            "http://localhost:7860/sdapi/v1/txt2img",
            json={"images": [b64_image], "info": "{}"},
        )
        httpx_mock.get(
            "http://localhost:7860/sdapi/v1/progress",
            status_code=500,
            text="Internal Server Error",
        )

        callback = MagicMock()
        provider = SdWebuiImageProvider(host="http://localhost:7860")
        result = await provider.generate("test", progress_callback=callback)

        # Generation succeeds despite progress endpoint failure
        assert result.image_data == b"fake-png-data"

    async def test_no_callback_skips_polling(self, httpx_mock) -> None:
        """Without progress_callback, no /progress polling occurs."""
        b64_image = base64.b64encode(b"fake-png-data").decode()
        httpx_mock.post(
            "http://localhost:7860/sdapi/v1/txt2img",
            json={"images": [b64_image], "info": "{}"},
        )

        provider = SdWebuiImageProvider(host="http://localhost:7860")
        result = await provider.generate("test", progress_callback=None)

        assert result.image_data == b"fake-png-data"
        # No GET requests should have been made
        assert len(httpx_mock.get_requests()) == 0

    async def test_progress_message_includes_eta(self, httpx_mock, monkeypatch) -> None:
        """Progress message includes ETA when available."""
        import image_generation_mcp.providers.sd_webui as sd_mod

        monkeypatch.setattr(sd_mod, "_PROGRESS_POLL_INTERVAL", 0.0)

        b64_image = base64.b64encode(b"fake-png-data").decode()
        httpx_mock.post(
            "http://localhost:7860/sdapi/v1/txt2img",
            json={"images": [b64_image], "info": "{}"},
            delay=0.1,  # Give poll task time to fire
        )
        httpx_mock.get(
            "http://localhost:7860/sdapi/v1/progress",
            json={"progress": 0.5, "eta_relative": 12.0},
        )

        calls: list[tuple[float, str]] = []

        def _capture(fraction: float, msg: str) -> None:
            calls.append((fraction, msg))

        provider = SdWebuiImageProvider(host="http://localhost:7860")
        await provider.generate("test", progress_callback=_capture)

        assert len(calls) > 0, "Expected at least one progress callback"
        for fraction, msg in calls:
            assert "ETA" in msg
            assert fraction == 0.5

    async def test_poll_progress_cancellation(self) -> None:
        """_poll_progress respects cancellation."""
        callback = MagicMock()
        provider = SdWebuiImageProvider(host="http://localhost:7860")
        task = asyncio.create_task(provider._poll_progress(30, callback))
        # Let the loop start then cancel
        await asyncio.sleep(0.05)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task


# -- httpx mock fixture -------------------------------------------------------


@pytest.fixture
def httpx_mock(monkeypatch):
    """Simple httpx mock that captures requests and returns canned responses."""
    return _HttpxMock(monkeypatch)


class _HttpxMock:
    """Minimal httpx mock for SD WebUI tests."""

    def __init__(self, monkeypatch) -> None:
        self._monkeypatch = monkeypatch
        self._post_routes: list[dict[str, Any]] = []
        self._get_routes: list[dict[str, Any]] = []
        self._requests: list[httpx.Request] = []
        self._get_request_list: list[httpx.Request] = []

    def post(
        self,
        url: str,
        *,
        json: dict | None = None,
        status_code: int = 200,
        text: str | None = None,
        delay: float = 0.0,
    ) -> None:
        route = {
            "url": url,
            "json": json,
            "status_code": status_code,
            "text": text,
            "delay": delay,
        }
        self._post_routes.append(route)
        self._patch()

    def get(
        self,
        url: str,
        *,
        json: dict | None = None,
        status_code: int = 200,
        text: str | None = None,
    ) -> None:
        route = {
            "url": url,
            "json": json,
            "status_code": status_code,
            "text": text,
        }
        self._get_routes.append(route)
        self._patch()

    def get_request(self) -> httpx.Request:
        assert self._requests, "No POST requests captured"
        return self._requests[-1]

    def get_requests(self) -> list[httpx.Request]:
        """Return all captured GET requests."""
        return list(self._get_request_list)

    def _patch(self) -> None:
        mock = self

        async def _mock_post(
            client_self: Any,  # noqa: ARG001
            url: str,
            **kwargs: Any,
        ) -> httpx.Response:
            # httpx passes json= which gets serialized to content
            json_body = kwargs.get("json")
            content = (
                json.dumps(json_body).encode()
                if json_body is not None
                else kwargs.get("content", b"")
            )
            request = httpx.Request("POST", url, content=content)
            mock._requests.append(request)

            for route in mock._post_routes:
                if str(url) == route["url"]:
                    if route.get("delay", 0) > 0:
                        await asyncio.sleep(route["delay"])
                    if route["text"] is not None:
                        return httpx.Response(
                            status_code=route["status_code"],
                            text=route["text"],
                            request=request,
                        )
                    return httpx.Response(
                        status_code=route["status_code"],
                        json=route["json"],
                        request=request,
                    )

            return httpx.Response(status_code=404, text="Not Found", request=request)

        async def _mock_get(
            client_self: Any,  # noqa: ARG001
            url: str,
            **kwargs: Any,  # noqa: ARG001
        ) -> httpx.Response:
            request = httpx.Request("GET", url)
            mock._get_request_list.append(request)

            for route in mock._get_routes:
                if str(url) == route["url"]:
                    if route["text"] is not None:
                        return httpx.Response(
                            status_code=route["status_code"],
                            text=route["text"],
                            request=request,
                        )
                    return httpx.Response(
                        status_code=route["status_code"],
                        json=route["json"],
                        request=request,
                    )

            return httpx.Response(status_code=404, text="Not Found", request=request)

        self._monkeypatch.setattr(httpx.AsyncClient, "post", _mock_post)
        self._monkeypatch.setattr(httpx.AsyncClient, "get", _mock_get)


# -- img2img tests -------------------------------------------------------


class TestImg2Img:
    """Tests for SD WebUI img2img (reference-image) dispatch."""

    async def test_img2img_with_reference_posts_to_img2img(self, httpx_mock) -> None:
        """When reference_images is given, POST goes to /sdapi/v1/img2img."""
        raw_bytes = b"fake-raw-png"
        b64_image = base64.b64encode(b"output-png").decode()
        httpx_mock.post(
            "http://localhost:7860/sdapi/v1/img2img",
            json={"images": [b64_image], "info": "{}"},
        )

        provider = SdWebuiImageProvider(host="http://localhost:7860")
        result = await provider.generate(
            "edit this",
            reference_images=[InputImage(data=raw_bytes, content_type="image/png")],
            strength=0.4,
        )

        request = httpx_mock.get_request()
        assert "/sdapi/v1/img2img" in str(request.url)
        payload = json.loads(request.content)
        assert payload["init_images"] == [base64.b64encode(raw_bytes).decode("ascii")]
        assert payload["denoising_strength"] == 0.4
        assert result.provider_metadata["edited"] is True

    async def test_img2img_default_denoising_when_strength_none(
        self, httpx_mock
    ) -> None:
        """When strength is None, denoising_strength defaults to 0.75."""
        b64_image = base64.b64encode(b"output-png").decode()
        httpx_mock.post(
            "http://localhost:7860/sdapi/v1/img2img",
            json={"images": [b64_image], "info": "{}"},
        )

        provider = SdWebuiImageProvider(host="http://localhost:7860")
        await provider.generate(
            "edit this",
            reference_images=[InputImage(data=b"raw", content_type="image/png")],
            strength=None,
        )

        request = httpx_mock.get_request()
        payload = json.loads(request.content)
        assert payload["denoising_strength"] == 0.75

    async def test_img2img_explicit_zero_strength_preserved(self, httpx_mock) -> None:
        """strength=0.0 is forwarded as denoising_strength=0.0, not defaulted."""
        b64_image = base64.b64encode(b"output-png").decode()
        httpx_mock.post(
            "http://localhost:7860/sdapi/v1/img2img",
            json={"images": [b64_image], "info": "{}"},
        )

        provider = SdWebuiImageProvider(host="http://localhost:7860")
        await provider.generate(
            "edit this",
            reference_images=[InputImage(data=b"raw", content_type="image/png")],
            strength=0.0,
        )

        payload = json.loads(httpx_mock.get_request().content)
        assert payload["denoising_strength"] == 0.0

    async def test_img2img_too_many_references_raises(self) -> None:
        """Two reference images raises TooManyInputImages before any HTTP call."""
        provider = SdWebuiImageProvider(host="http://localhost:7860")

        with pytest.raises(TooManyInputImages):
            await provider.generate(
                "edit this",
                reference_images=[
                    InputImage(data=b"img1", content_type="image/png"),
                    InputImage(data=b"img2", content_type="image/png"),
                ],
            )

    async def test_txt2img_unaffected_when_no_references(self, httpx_mock) -> None:
        """With no reference_images, POSTs to /txt2img and has no img2img fields."""
        b64_image = base64.b64encode(b"output-png").decode()
        httpx_mock.post(
            "http://localhost:7860/sdapi/v1/txt2img",
            json={"images": [b64_image], "info": "{}"},
        )

        provider = SdWebuiImageProvider(host="http://localhost:7860")
        await provider.generate("a cat", strength=0.3)

        request = httpx_mock.get_request()
        assert "/sdapi/v1/txt2img" in str(request.url)
        payload = json.loads(request.content)
        assert "init_images" not in payload
        assert "denoising_strength" not in payload


async def test_sd_webui_rejects_mask() -> None:
    """SD WebUI provider raises ImageProviderError when mask is given."""
    from image_generation_mcp.providers.types import ImageProviderError, InputImage

    provider = SdWebuiImageProvider(host="http://localhost:7860")

    with pytest.raises(ImageProviderError, match="mask"):
        await provider.generate(
            "x", mask=InputImage(data=b"m", content_type="image/png")
        )
