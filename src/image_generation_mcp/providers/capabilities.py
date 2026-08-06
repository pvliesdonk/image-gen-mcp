"""Provider capability model — frozen dataclasses for runtime discovery.

Defines :class:`ModelCapabilities` and :class:`ProviderCapabilities` which
represent what each provider and model can do.  Populated at startup via
each provider's ``discover_capabilities()`` method.

See ADR-0007 for the design rationale.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from image_generation_mcp.providers.model_styles import StyleProfile

WatermarkKind = Literal["none", "synthid"]


@dataclass(frozen=True)
class ModelCapabilities:
    """Capabilities of a single model within a provider.

    Attributes:
        model_id: Model identifier (e.g., ``"gpt-image-1"``).
        display_name: Human-readable display name.
        can_generate: Supports text-to-image generation.
        can_edit: Supports image editing (image-to-image).
        supports_mask: Supports inpainting masks (an alpha-channel mask image).
        supported_aspect_ratios: Aspect ratio strings this model accepts.
        supported_qualities: Quality level strings this model accepts.
        supported_resolutions: Resolution tiers this model actually honors
            beyond ``"standard"``. Most models are ``("standard",)`` --
            ``"high"``/``"max"`` are silent no-ops. Independent of
            ``max_resolution``: do not derive one from the other.
        supported_formats: Output format strings (e.g., ``"png"``, ``"webp"``).
        supports_negative_prompt: Accepts negative prompt parameter.
        supports_background: Supports background transparency control.
        supports_image_input: Supports reference image input for generation.
        max_input_images: Maximum number of reference images this model accepts.
        max_resolution: Maximum dimension in pixels, or ``None`` if unlimited.
        default_steps: Default inference steps (SD WebUI-specific), or ``None``.
        default_cfg: Default CFG scale (SD WebUI-specific), or ``None``.
        prompt_style: Recommended prompt format — ``"clip"`` for CLIP-tag
            models (SD 1.5, SDXL), ``"natural_language"`` for T5-based
            models (Flux), or ``None`` for providers without guidance.
        style_profile: Optional narrative metadata (label, hints,
            incompatibility notes, examples, lifecycle) read by LLMs when
            selecting a model. ``None`` when no profile is registered for
            this model.
        watermark: Identifier for any persistent watermark embedded in the
            model's output. ``"synthid"`` for Google SynthID (Gemini Image
            family — Flash and Pro tiers); ``"none"`` to explicitly assert
            no watermark;
            ``None`` (default) when the provider has not declared a value.
            LLMs and downstream tools should warn users when bit-perfect
            originals are required and ``watermark`` is not ``None`` and
            not ``"none"`` (i.e. a specific watermark scheme is declared).
    """

    model_id: str
    display_name: str
    can_generate: bool = True
    can_edit: bool = False
    supports_mask: bool = False
    supported_aspect_ratios: tuple[str, ...] = ()
    supported_qualities: tuple[str, ...] = ()
    supported_resolutions: tuple[str, ...] = ("standard",)
    supported_formats: tuple[str, ...] = ()
    supports_negative_prompt: bool = False
    supports_background: bool = False
    supports_image_input: bool = False
    max_input_images: int = 0
    max_resolution: int | None = None
    default_steps: int | None = None
    default_cfg: float | None = None
    prompt_style: str | None = None
    style_profile: StyleProfile | None = None
    watermark: WatermarkKind | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dictionary.

        The ``style_profile`` and ``watermark`` keys are omitted entirely
        when their underlying field is ``None``. All other ``None``-valued
        fields are included explicitly as ``null``.
        """
        result: dict[str, Any] = {
            "model_id": self.model_id,
            "display_name": self.display_name,
            "can_generate": self.can_generate,
            "can_edit": self.can_edit,
            "supports_mask": self.supports_mask,
            "supported_aspect_ratios": list(self.supported_aspect_ratios),
            "supported_qualities": list(self.supported_qualities),
            "supported_resolutions": list(self.supported_resolutions),
            "supported_formats": list(self.supported_formats),
            "supports_negative_prompt": self.supports_negative_prompt,
            "supports_background": self.supports_background,
            "supports_image_input": self.supports_image_input,
            "max_input_images": self.max_input_images,
            "max_resolution": self.max_resolution,
            "default_steps": self.default_steps,
            "default_cfg": self.default_cfg,
            "prompt_style": self.prompt_style,
        }
        if self.style_profile is not None:
            result["style_profile"] = self.style_profile.to_dict()
        if self.watermark is not None:
            result["watermark"] = self.watermark
        return result


@dataclass(frozen=True)
class ProviderCapabilities:
    """Aggregate capabilities for a provider (one or more models).

    Attributes:
        provider_name: Registry key (e.g., ``"openai"``).
        models: Per-model capability details.
        discovered_at: Unix timestamp when discovery completed.
        degraded: ``True`` if discovery failed (empty model list).
        supports_background: ``True`` if any model supports background control
            (derived from ``models``).
        supports_negative_prompt: ``True`` if any model supports negative prompts
            (derived from ``models``).
    """

    provider_name: str
    models: tuple[ModelCapabilities, ...] = ()
    discovered_at: float = 0.0
    degraded: bool = False

    @property
    def supports_background(self) -> bool:
        """Return True if any model in this provider supports background control."""
        return any(m.supports_background for m in self.models)

    @property
    def supports_negative_prompt(self) -> bool:
        """Return True if any model in this provider supports negative prompts."""
        return any(m.supports_negative_prompt for m in self.models)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dictionary."""
        result: dict[str, Any] = {
            "provider_name": self.provider_name,
            "models": [m.to_dict() for m in self.models],
            "supports_background": self.supports_background,
            "supports_negative_prompt": self.supports_negative_prompt,
            "discovered_at": self.discovered_at,
            "degraded": self.degraded,
        }
        return result


def make_degraded(provider_name: str, discovered_at: float) -> ProviderCapabilities:
    """Create a degraded capabilities entry for a provider that failed discovery.

    Args:
        provider_name: Provider registry key.
        discovered_at: Unix timestamp of the failed discovery attempt.

    Returns:
        A ``ProviderCapabilities`` with ``degraded=True`` and empty model list.
    """
    return ProviderCapabilities(
        provider_name=provider_name,
        degraded=True,
        discovered_at=discovered_at,
    )
