"""Project configuration for image-generation-mcp.

Composes ``fastmcp_pvl_core.ServerConfig`` for transport/auth/event-store
fields; adds image-generation domain fields below.

Add domain-specific fields between the CONFIG-FIELDS sentinels, populate
them in ``from_env`` between the CONFIG-FROM-ENV sentinels, and enforce
their invariants in ``__post_init__`` between the CONFIG-VALIDATE
sentinels; copier update preserves all three blocks across template
updates.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from fastmcp_pvl_core import (
    ServerConfig,
    TransferConfig,
    env,
    env_float,
    env_int,
    parse_bool,
    parse_list,
)

logger = logging.getLogger(__name__)

_ENV_PREFIX = "IMAGE_GENERATION_MCP"


# Unexpanded on purpose: these defaults are rendered verbatim into generated
# config artifacts, so they must stay machine-independent.  ``from_env``
# expands ``~`` when it resolves the effective paths.
_DEFAULT_SCRATCH_DIR = Path("~/.image-generation-mcp/images")
_DEFAULT_STYLES_DIR = Path("~/.image-generation-mcp/styles")


def _legacy_a1111(suffix: str, replacement: str) -> str | None:
    """Read a deprecated ``A1111_*`` alias env var, warning when it is set.

    Lives outside ``ProjectConfig.from_env`` so the config-surface AST scan
    does not report the aliases as domain fields; they are declared in
    ``config-presentation.domain.yml`` instead.

    Args:
        suffix: The deprecated env-var suffix (e.g. ``"A1111_HOST"``).
        replacement: The suffix operators should use instead.

    Returns:
        The alias value, or ``None`` when unset.
    """
    value = env(_ENV_PREFIX, suffix)
    if value:
        logger.warning(
            "%s_%s is deprecated — use %s_%s instead",
            _ENV_PREFIX,
            suffix,
            _ENV_PREFIX,
            replacement,
        )
    return value


@dataclass(frozen=True)
class ProjectConfig:
    """Image-generation-mcp configuration loaded from environment variables.

    The ``server`` field carries generic FastMCP server config (transport,
    auth, event store). Domain fields (provider keys, scratch dir, etc.)
    live directly on this dataclass.
    """

    # CONFIG-FIELDS-START — image-generation domain fields; kept across copier update
    server: ServerConfig = field(default_factory=ServerConfig)
    read_only: bool = field(
        default=True,
        metadata={
            "help": (
                "When true, write-tagged tools (image generation, transforms, "
                "uploads) are hidden from clients. Set false to enable them."
            ),
            "tags": ("mode",),
        },
    )
    scratch_dir: Path = field(
        default=_DEFAULT_SCRATCH_DIR,
        metadata={
            "help": (
                "Directory where generated images are saved. "
                "Created automatically on first use."
            ),
            "tags": ("storage",),
        },
    )
    openai_api_key: str | None = field(
        default=None,
        metadata={
            "help": (
                "OpenAI API key. Enables the OpenAI provider "
                "(gpt-image-2, gpt-image-1.5, dall-e-3) when set."
            ),
            "tags": ("providers",),
            "wizard": {"secret": True},
        },
    )
    google_api_key: str | None = field(
        default=None,
        metadata={
            "help": (
                "Google API key. Enables the Gemini provider "
                "(gemini-3.1-flash-image and others) when set. "
                "Get a key at https://aistudio.google.com/apikey."
            ),
            "tags": ("providers",),
            "wizard": {"secret": True},
        },
    )
    sd_webui_host: str | None = field(
        default=None,
        metadata={
            "help": (
                "SD WebUI base URL (such as http://localhost:7860). Enables "
                "the SD WebUI provider when set. Compatible with "
                "AUTOMATIC1111, Forge, reForge, and Forge-neo."
            ),
            "tags": ("providers",),
        },
    )
    sd_webui_model: str | None = field(
        default=None,
        metadata={
            "help": (
                "SD WebUI checkpoint name, used for model-aware preset "
                "detection (SD 1.5 / SDXL / Lightning) and checkpoint "
                "override. Unset uses the instance's current model."
            ),
            "tags": ("providers",),
        },
    )
    default_provider: str = field(
        default="auto",
        metadata={
            "help": (
                "Provider used when no keyword triggers auto-selection: "
                "auto, openai, gemini, sd_webui, or placeholder. "
                "auto picks the first configured provider."
            ),
            "tags": ("providers",),
        },
    )
    transform_cache_size: int = field(
        default=64,
        metadata={
            "help": (
                "Maximum number of transformed image results (resize, crop, "
                "convert) kept in memory. Set 0 to disable caching."
            ),
            "tags": ("tuning",),
        },
    )
    paid_providers: frozenset[str] = field(
        default=frozenset({"openai"}),
        metadata={
            "help": (
                "Comma-separated provider names that cost money; "
                "generate_image asks for confirmation (client elicitation) "
                "before using them. An empty value falls back to this "
                "default; to disable confirmation, set a value that names "
                "no provider (such as none)."
            ),
            "tags": ("providers",),
        },
    )
    styles_dir: Path = field(
        default=_DEFAULT_STYLES_DIR,
        metadata={
            "help": (
                "Directory for style preset files (Markdown with YAML "
                "front matter). Created automatically if it does not exist."
            ),
            "tags": ("storage",),
        },
    )
    allow_local_file_input: bool = field(
        default=False,
        metadata={
            "help": (
                "Allow reading input images from local filesystem paths. "
                "Off by default: only URLs and uploads are accepted."
            ),
            "tags": ("mode",),
        },
    )
    max_input_image_bytes: int = field(
        default=20 * 1024 * 1024,
        metadata={
            "help": "Maximum accepted input image size in bytes.",
            "tags": ("tuning",),
        },
    )
    # Composed core section, not flattened: since template v3.1.0 (core 4.6.0's
    # domain_env_surface) the generator resolves each TRANSFER_* var to the
    # matching TransferConfig field and documents it from core's own metadata,
    # so no per-var help belongs here — core owns that text and keeps it true.
    transfer: TransferConfig = field(
        default_factory=TransferConfig,
        metadata={"tags": ("transfer",)},
    )
    fetch_timeout_s: float = field(
        default=30.0,
        metadata={
            "help": (
                "HTTP timeout in seconds when fetching remote image URLs "
                "(fetch_image and URL inputs)."
            ),
            "tags": ("tuning",),
        },
    )
    # CONFIG-FIELDS-END

    def __post_init__(self) -> None:
        """Validate composed domain fields.  Raise ``ValueError`` when invalid.

        Runs on EVERY construction path — ``from_env`` and a direct
        ``ProjectConfig(field=...)`` alike.  That is what makes this the right
        home for a field invariant: ``env_float`` / ``env_int`` bounds check
        only the *env-sourced* value, never the default, so a direct
        construction slips past them.  They also cannot express an exclusive
        bound (their ``minimum`` / ``maximum`` are inclusive, so "must be > 0"
        lets ``0`` through) or a cross-field rule (A requires B,
        mutually-exclusive pairs).  All three belong here.

        The dataclass is ``frozen=True``: read fields freely, but plain
        assignment raises.  To *normalise* rather than merely check, use
        ``object.__setattr__(self, "name", value)``.
        """
        # CONFIG-VALIDATE-START — validate domain fields below; kept across copier update
        # The composed TransferConfig validates its own bounds (positive,
        # finite, ttl_default_s <= ttl_max_s) in its __post_init__, on both
        # the from_env and the direct-construction path.
        #
        # Normalise the deprecated provider alias here rather than in from_env
        # so a direct ProjectConfig(default_provider="a1111") is remapped too.
        if self.default_provider == "a1111":
            logger.warning(
                "DEFAULT_PROVIDER='a1111' is deprecated — use 'sd_webui' instead"
            )
            object.__setattr__(self, "default_provider", "sd_webui")
        # CONFIG-VALIDATE-END

    @classmethod
    def from_env(cls) -> ProjectConfig:
        """Load configuration from environment variables.

        Reads every ``IMAGE_GENERATION_MCP_*`` domain var documented by the
        field metadata above (rendered into ``.env.example`` and the README
        domain table by ``scripts/gen_config_surface.py``), plus the
        deprecated ``A1111_HOST`` / ``A1111_MODEL`` aliases declared in
        ``config-presentation.domain.yml``.

        Plus all generic ``ServerConfig`` env vars (BASE_URL, BEARER_TOKEN,
        OIDC_*, KV_STORE_URL, ...) — see
        ``fastmcp_pvl_core.ServerConfig.from_env``.

        Returns:
            A populated :class:`ProjectConfig` instance.
        """
        server = ServerConfig.from_env(_ENV_PREFIX)

        # CONFIG-FROM-ENV-START — image-generation domain reads; kept across copier update
        # Every read stays INLINE in its ``cls(...)`` keyword: the config-surface
        # generator (core's domain_env_surface) links a var to its dataclass
        # field — and so to that field's help/tags/wizard metadata — only when
        # the keyword's value expression contains exactly one literal env read.
        # Reading into a local first and passing it by name silently strips the
        # var's documentation from every generated artifact, so keep the reads
        # here rather than hoisting them.  Numeric parsing uses core's
        # env_int/env_float, which already warn and fall back on a malformed
        # value; the deprecated DEFAULT_PROVIDER='a1111' remap lives in
        # __post_init__ so it also covers direct construction.
        config = cls(
            server=server,
            read_only=parse_bool(env(_ENV_PREFIX, "READ_ONLY", "true")),
            scratch_dir=Path(
                env(_ENV_PREFIX, "SCRATCH_DIR") or _DEFAULT_SCRATCH_DIR
            ).expanduser(),
            openai_api_key=env(_ENV_PREFIX, "OPENAI_API_KEY"),
            google_api_key=env(_ENV_PREFIX, "GOOGLE_API_KEY"),
            sd_webui_host=env(_ENV_PREFIX, "SD_WEBUI_HOST")
            or _legacy_a1111("A1111_HOST", "SD_WEBUI_HOST"),
            sd_webui_model=env(_ENV_PREFIX, "SD_WEBUI_MODEL")
            or _legacy_a1111("A1111_MODEL", "SD_WEBUI_MODEL"),
            default_provider=env(_ENV_PREFIX, "DEFAULT_PROVIDER") or "auto",
            transform_cache_size=env_int(_ENV_PREFIX, "TRANSFORM_CACHE_SIZE", 64),
            # Unset or empty falls back to the default; a value naming no real
            # provider (e.g. "none") is how an operator disables the gate.
            paid_providers=frozenset(
                p.lower() for p in parse_list(env(_ENV_PREFIX, "PAID_PROVIDERS") or "")
            )
            or frozenset({"openai"}),
            styles_dir=Path(
                env(_ENV_PREFIX, "STYLES_DIR") or _DEFAULT_STYLES_DIR
            ).expanduser(),
            allow_local_file_input=parse_bool(
                env(_ENV_PREFIX, "ALLOW_LOCAL_FILE_INPUT", "false")
            ),
            max_input_image_bytes=env_int(
                _ENV_PREFIX, "MAX_INPUT_IMAGE_BYTES", 20 * 1024 * 1024
            ),
            transfer=TransferConfig.from_env(_ENV_PREFIX),
            fetch_timeout_s=env_float(_ENV_PREFIX, "FETCH_TIMEOUT_S", 30.0),
        )
        # CONFIG-FROM-ENV-END

        logger.debug("from_env: read_only=%s", config.read_only)
        return config
