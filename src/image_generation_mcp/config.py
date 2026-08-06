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

# Core's own defaults for the transfer knobs, kept in sync by construction.
_TRANSFER_DEFAULTS = TransferConfig()


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
    transfer_ttl_default_s: float = field(
        default=_TRANSFER_DEFAULTS.ttl_default_s,
        metadata={
            "help": (
                "Default lifetime in seconds of a create_download_link / "
                "create_upload_link URL when the caller omits one. "
                "HTTP transports only."
            ),
            "tags": ("transfer",),
        },
    )
    transfer_ttl_max_s: float = field(
        default=_TRANSFER_DEFAULTS.ttl_max_s,
        metadata={
            "help": (
                "Ceiling in seconds a caller-requested transfer-link "
                "lifetime is clamped to."
            ),
            "tags": ("transfer",),
        },
    )
    transfer_grace_ttl_s: float = field(
        default=_TRANSFER_DEFAULTS.grace_ttl_s,
        metadata={
            "help": (
                "Post-success grace window in seconds a one-time transfer "
                "link stays reclaimable, so a stalled download can retry."
            ),
            "tags": ("transfer",),
        },
    )
    transfer_lease_s: float = field(
        default=_TRANSFER_DEFAULTS.lease_s,
        metadata={
            "help": (
                "Reclaim window in seconds for an in-flight transfer whose "
                "handler crashed."
            ),
            "tags": ("transfer",),
        },
    )
    transfer_max_upload_bytes: int = field(
        default=_TRANSFER_DEFAULTS.max_upload_bytes,
        metadata={
            "help": "Per-upload size cap in bytes for create_upload_link bodies.",
            "tags": ("transfer",),
        },
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

    @property
    def transfer(self) -> TransferConfig:
        """The core transfer config assembled from the flat ``transfer_*`` fields.

        A property rather than a composed ``TransferConfig`` field so the
        config-surface generator documents the flat fields' metadata instead
        of discovering core's metadata-less dataclass. Construction runs
        ``TransferConfig.__post_init__`` validation.

        Returns:
            A validated :class:`fastmcp_pvl_core.TransferConfig`.
        """
        return TransferConfig(
            ttl_default_s=self.transfer_ttl_default_s,
            ttl_max_s=self.transfer_ttl_max_s,
            grace_ttl_s=self.transfer_grace_ttl_s,
            lease_s=self.transfer_lease_s,
            max_upload_bytes=self.transfer_max_upload_bytes,
        )

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
        # Constructing the composed TransferConfig runs its bounds validation
        # (positive, finite, ttl_default_s <= ttl_max_s) on every path.
        _ = self.transfer
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
        read_only = parse_bool(env(_ENV_PREFIX, "READ_ONLY", "true"))

        scratch_dir = Path(
            env(_ENV_PREFIX, "SCRATCH_DIR") or _DEFAULT_SCRATCH_DIR
        ).expanduser()

        openai_api_key = env(_ENV_PREFIX, "OPENAI_API_KEY")
        google_api_key = env(_ENV_PREFIX, "GOOGLE_API_KEY")

        sd_webui_host = env(_ENV_PREFIX, "SD_WEBUI_HOST") or _legacy_a1111(
            "A1111_HOST", "SD_WEBUI_HOST"
        )
        sd_webui_model = env(_ENV_PREFIX, "SD_WEBUI_MODEL") or _legacy_a1111(
            "A1111_MODEL", "SD_WEBUI_MODEL"
        )

        default_provider = env(_ENV_PREFIX, "DEFAULT_PROVIDER") or "auto"
        if default_provider == "a1111":
            logger.warning(
                "DEFAULT_PROVIDER='a1111' is deprecated — use 'sd_webui' instead"
            )
            default_provider = "sd_webui"

        raw_cache = env(_ENV_PREFIX, "TRANSFORM_CACHE_SIZE")
        transform_cache_size = 64
        if raw_cache:
            try:
                transform_cache_size = int(raw_cache)
            except ValueError:
                logger.warning(
                    "Invalid TRANSFORM_CACHE_SIZE=%r — using default 64", raw_cache
                )

        raw_paid = env(_ENV_PREFIX, "PAID_PROVIDERS")
        paid_providers = (
            frozenset(p.lower() for p in parse_list(raw_paid))
            if raw_paid is not None
            else frozenset({"openai"})
        )

        styles_dir = Path(
            env(_ENV_PREFIX, "STYLES_DIR") or _DEFAULT_STYLES_DIR
        ).expanduser()

        allow_local_file_input = parse_bool(
            env(_ENV_PREFIX, "ALLOW_LOCAL_FILE_INPUT", "false")
        )

        raw_max_input = env(_ENV_PREFIX, "MAX_INPUT_IMAGE_BYTES")
        max_input_image_bytes = 20 * 1024 * 1024
        if raw_max_input:
            try:
                max_input_image_bytes = int(raw_max_input)
            except ValueError:
                logger.warning(
                    "Invalid MAX_INPUT_IMAGE_BYTES=%r — using default %d",
                    raw_max_input,
                    max_input_image_bytes,
                )

        raw_fetch_timeout = env(_ENV_PREFIX, "FETCH_TIMEOUT_S")
        fetch_timeout_s = 30.0
        if raw_fetch_timeout:
            try:
                fetch_timeout_s = float(raw_fetch_timeout)
            except ValueError:
                logger.warning(
                    "Invalid FETCH_TIMEOUT_S=%r — using default %s",
                    raw_fetch_timeout,
                    fetch_timeout_s,
                )

        config = cls(
            server=server,
            read_only=read_only,
            scratch_dir=scratch_dir,
            openai_api_key=openai_api_key,
            google_api_key=google_api_key,
            sd_webui_host=sd_webui_host,
            sd_webui_model=sd_webui_model,
            default_provider=default_provider,
            transform_cache_size=transform_cache_size,
            paid_providers=paid_providers,
            styles_dir=styles_dir,
            allow_local_file_input=allow_local_file_input,
            max_input_image_bytes=max_input_image_bytes,
            transfer_ttl_default_s=env_float(
                _ENV_PREFIX,
                "TRANSFER_TTL_DEFAULT_S",
                _TRANSFER_DEFAULTS.ttl_default_s,
                strict=True,
            ),
            transfer_ttl_max_s=env_float(
                _ENV_PREFIX,
                "TRANSFER_TTL_MAX_S",
                _TRANSFER_DEFAULTS.ttl_max_s,
                strict=True,
            ),
            transfer_grace_ttl_s=env_float(
                _ENV_PREFIX,
                "TRANSFER_GRACE_TTL_S",
                _TRANSFER_DEFAULTS.grace_ttl_s,
                strict=True,
            ),
            transfer_lease_s=env_float(
                _ENV_PREFIX,
                "TRANSFER_LEASE_S",
                _TRANSFER_DEFAULTS.lease_s,
                strict=True,
            ),
            transfer_max_upload_bytes=env_int(
                _ENV_PREFIX,
                "TRANSFER_MAX_UPLOAD_BYTES",
                _TRANSFER_DEFAULTS.max_upload_bytes,
                strict=True,
            ),
            fetch_timeout_s=fetch_timeout_s,
        )
        # CONFIG-FROM-ENV-END

        logger.debug("from_env: read_only=%s", config.read_only)
        return config
