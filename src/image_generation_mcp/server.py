"""Image Generation MCP — FastMCP server entry point.

Composes the primitives from ``fastmcp-pvl-core`` into IG's
``make_server()``.  See https://gofastmcp.com/servers for the FastMCP
server surface and the fastmcp-pvl-core README for the helpers used here.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version
from typing import TYPE_CHECKING, Any

from fastmcp import FastMCP
from fastmcp.server.transforms import ResourcesAsTools
from fastmcp_pvl_core import (
    ServerConfig,
    apply_tool_visibility,
    build_auth,
    build_instructions,
    build_kv_store,  # noqa: F401  — re-exported for downstream projects' convenience
    configure_logging_from_env,
    configure_task_backend,
    env,
    register_server_info_tool,
    resolve_auth_mode,
    wire_middleware_stack,
)
from mcp.types import Icon, ToolAnnotations

from image_generation_mcp._server_deps import _service_context
from image_generation_mcp.config import _ENV_PREFIX, ProjectConfig
from image_generation_mcp.prompts import register_prompts
from image_generation_mcp.resources import register_resources
from image_generation_mcp.tools import register_tools

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = logging.getLogger(__name__)

_LUCIDE = "https://unpkg.com/lucide-static/icons/{}.svg"
_DEFAULT_SERVER_NAME = "image-generation-mcp"


def _load_server_config() -> ServerConfig:
    """Load only the generic ``ServerConfig`` slice from IG env vars.

    Compat helper used by ``_resolve_auth_mode`` / ``_build_remote_auth``
    wrappers that preserve their historical zero-arg call shape.
    """
    return ServerConfig.from_env(env_prefix=_ENV_PREFIX)


def _resolve_auth_mode() -> str | None:
    """Resolve the configured auth mode from IG env vars.

    Backward-compat wrapper around :func:`fastmcp_pvl_core.resolve_auth_mode`
    that still returns ``None`` (not ``"none"``) when no auth is configured,
    matching the pre-retrofit contract expected by tests.
    """
    mode = resolve_auth_mode(_load_server_config())
    return None if mode == "none" else mode


def _build_remote_auth() -> object | None:
    """Build a ``RemoteAuthProvider`` from IG env vars, or ``None``.

    Backward-compat wrapper around
    :func:`fastmcp_pvl_core.build_remote_auth`.
    """
    from fastmcp_pvl_core import build_remote_auth

    return build_remote_auth(_load_server_config())


def _build_bearer_auth() -> object | None:
    """Build a ``StaticTokenVerifier`` from IG env vars, or ``None``.

    Backward-compat wrapper around
    :func:`fastmcp_pvl_core.build_bearer_auth`.
    """
    from fastmcp_pvl_core import build_bearer_auth

    return build_bearer_auth(_load_server_config())


def _build_oidc_auth() -> object | None:
    """Build an ``OIDCProxy`` from IG env vars, or ``None``.

    Backward-compat wrapper around
    :func:`fastmcp_pvl_core.build_oidc_proxy_auth`.
    """
    from fastmcp_pvl_core import build_oidc_proxy_auth

    return build_oidc_proxy_auth(_load_server_config())


# pvl-core registers the transfer tools bare (no title / hints / icon / tags).
# Per the Tool Registration Checklist, attach the missing metadata here, and
# tag create_upload_link ``write`` so the read-only ``mcp.disable(tags={"write"})``
# hides it (it mutates the gallery via register_imported_image).
_TRANSFER_TOOL_META: dict[str, tuple[ToolAnnotations, str, str | None]] = {
    "create_download_link": (
        ToolAnnotations(
            title="Create Download Link",
            readOnlyHint=True,
            destructiveHint=False,
            openWorldHint=False,
        ),
        "download",
        None,
    ),
    "create_upload_link": (
        ToolAnnotations(
            title="Create Upload Link",
            readOnlyHint=False,
            destructiveHint=False,
            openWorldHint=False,
        ),
        "upload",
        "write",
    ),
}


class _TitledResourcesAsTools(ResourcesAsTools):
    """``ResourcesAsTools`` whose two bridge tools carry ``annotations.title``.

    fastmcp's transform constructs ``list_resources`` / ``read_resource``
    with title-less annotations; the Tool Registration Checklist requires a
    non-empty title on every registered tool (enforced by
    ``tests/test_tools.py``). Overrides the parent's private factory methods —
    if a fastmcp upgrade renames them, the enforcement test fails loudly
    rather than shipping untitled bridge tools.
    """

    @staticmethod
    def _with_title(tool: Any, title: str) -> Any:
        """Return *tool* with a per-tool copy of its annotations carrying *title*.

        MUST copy, never mutate in place: upstream passes one module-level
        ``_DEFAULT_ANNOTATIONS`` singleton to both bridge tools, so an
        in-place write makes the second tool's title win for both (and
        pollutes fastmcp's shared default for the process lifetime).
        """
        base = tool.annotations or ToolAnnotations()
        tool.annotations = base.model_copy(update={"title": title})
        return tool

    def _make_list_resources_tool(self) -> Any:
        return self._with_title(super()._make_list_resources_tool(), "List Resources")

    def _make_read_resource_tool(self) -> Any:
        return self._with_title(super()._make_read_resource_tool(), "Read Resource")


def _finalize_transfer_tool_metadata(mcp: FastMCP) -> None:
    """Attach title/hints/icon (and the ``write`` tag) to the transfer tools.

    pvl-core's ``register_transfer_routes`` registers ``create_download_link`` /
    ``create_upload_link`` without annotations or tags; this fills that gap
    post-registration (FastMCP tools are mutable). Accesses the tool store the
    same way ``fastmcp_pvl_core.register_tool_icons`` does — FastMCP exposes no
    public sync tools accessor.
    """
    from fastmcp.tools.tool import Tool

    by_name: dict[str, list[Tool]] = {}
    for comp in mcp.local_provider._components.values():
        if isinstance(comp, Tool):
            by_name.setdefault(comp.name, []).append(comp)

    for name, (annotation, icon, tag) in _TRANSFER_TOOL_META.items():
        for tool in by_name.get(name, []):
            tool.annotations = annotation
            tool.icons = [Icon(src=_LUCIDE.format(icon), mimeType="image/svg+xml")]
            if tag:
                tool.tags = tool.tags | {tag}


def make_server(
    *,
    transport: str = "stdio",
    config: ProjectConfig | None = None,
) -> FastMCP:
    """Construct the Image Generation MCP FastMCP server.

    Args:
        transport: ``"stdio"`` / ``"http"`` / ``"sse"``.  HTTP-only
            features (capability-link transfer routes) are wired only when
            transport != ``"stdio"`` and ``base_url`` is set.
        config: Optional pre-loaded config; defaults to env-based load.

    Returns:
        A configured :class:`fastmcp.FastMCP` instance.
    """
    if config is None:
        config = ProjectConfig.from_env()
    configure_logging_from_env()

    # Background-task backend (SEP-1686 / Docket).  Unconditional and
    # template-owned: pydocket ships in fastmcp-pvl-core's base dependencies,
    # so the backend is always configurable, and whether this server actually
    # uses tasks is decided by registering ``task=True`` tools — not by
    # packaging or by an opt-in switch here.  It mutates fastmcp's
    # process-global settings, which fastmcp reads lazily at root-lifespan
    # entry, so doing it inside ``make_server`` covers both CLI paths (
    # ``server.run(...)`` and the uvicorn ``http_app()`` one).
    # ``IMAGE_GENERATION_MCP_TASKS_URL`` selects the backend; unset, a
    # ``redis://`` ``IMAGE_GENERATION_MCP_KV_STORE_URL`` is reused so one URL
    # configures every stateful subsystem, and otherwise fastmcp's
    # ``memory://`` default applies.  The queue name is derived from the env
    # prefix, so two servers sharing one Redis do not share a queue.
    configure_task_backend(_ENV_PREFIX, config.server)

    # Operator overrides: SERVER_NAME renames this instance; INSTRUCTIONS
    # replaces the default instructions text (the latter is the override that
    # build_instructions' hint advertises). Both fall back when unset/empty.
    server_name = env(_ENV_PREFIX, "SERVER_NAME", "image-generation-mcp")
    instructions = env(_ENV_PREFIX, "INSTRUCTIONS") or build_instructions(
        env_prefix=_ENV_PREFIX,
        domain_line=(
            "AI image generation server supporting multiple providers "
            "(OpenAI gpt-image-2/dall-e-3, Google Gemini image, "
            "Stable Diffusion via SD WebUI, and a zero-cost placeholder). "
            "Start by calling list_providers to see configured providers."
        ),
    )

    auth = build_auth(config.server)
    auth_mode = resolve_auth_mode(config.server) if auth is not None else "none"
    if auth_mode == "none":
        logger.warning(
            "No auth configured — server accepts unauthenticated connections"
        )
    else:
        logger.info("Auth enabled: mode=%s", auth_mode)

    try:
        pkg_ver = _pkg_version("image-generation-mcp")
    except PackageNotFoundError:
        pkg_ver = "unknown"

    logger.info(
        "Server config: name=%s version=%s auth=%s mode=%s",
        server_name,
        pkg_ver,
        auth_mode,
        "read-only" if config.read_only else "read-write",
    )

    @asynccontextmanager
    async def _lifespan(_mcp: object) -> AsyncIterator[dict[str, Any]]:
        """Bind the config ``make_server`` resolved to the service lifespan.

        ``server_lifespan`` is the env-loading standalone entry; here we reuse
        the already-resolved ``config`` so a caller-injected config governs the
        service and config is not loaded a second time at startup.
        """
        async with _service_context(config) as state:
            yield state

    mcp = FastMCP(
        name=server_name,
        instructions=instructions,
        icons=[Icon(src=_LUCIDE.format("palette"), mimeType="image/svg+xml")],
        lifespan=_lifespan,
        auth=auth,
    )

    wire_middleware_stack(mcp)

    register_tools(mcp)
    register_resources(mcp)
    register_prompts(mcp)

    register_server_info_tool(
        mcp,
        server_name=server_name,
        server_version=pkg_ver,
        # DOMAIN-UPSTREAM-START — wire upstream version reporting for servers
        # that talk to a remote service (paperless-mcp, etc.). The provider is
        # a zero-arg callable; the simplest pattern is a module-level upstream
        # client (typically constructed from env vars at import time) whose
        # version method is referenced here. ``CurrentContext()`` is a FastMCP
        # DI marker — it only resolves to a live context when used as a
        # parameter default in a tool/resource handler, so it cannot be called
        # directly from a zero-arg provider.
        # Uncomment the kwargs below as additional arguments to this call:
        # upstream_version=lambda: _upstream_client.remote_version(),
        # upstream_label="paperless",
        # DOMAIN-UPSTREAM-END
    )

    # DOMAIN-WIRING-START — project-specific wiring (custom HTTP routes,
    # transforms, mode toggles, alternative middleware, additional registrations);
    # kept across copier update. Leave empty for projects that don't customise
    # make_server() beyond the standard scaffold.
    # Capability-link transfer (upload + download) via pvl-core's shared
    # framework. Registered only on an HTTP transport with base_url set: the
    # /transfer/{token} route needs an HTTP server, and register_transfer_routes
    # raises ConfigurationError without base_url.
    if transport != "stdio" and config.server.base_url:
        from dataclasses import replace

        from fastmcp_pvl_core import register_transfer_routes

        from image_generation_mcp._transfer_sink import GalleryTransferSink

        _transfer_sink = GalleryTransferSink(config)
        # Cap uploads at the tighter of the transfer and domain image limits so
        # an oversized image is rejected with a clean 413 at the route boundary,
        # not accepted and then 500'd inside sink.write (register_imported_image
        # raises InputImageTooLarge, which pvl-core re-raises as a generic 500).
        # This is the "effective cap is the smaller of the two" contract the docs
        # state (see pvliesdonk/fastmcp-pvl-core#233 for the sink-error status gap).
        _transfer_config = replace(
            config.transfer,
            max_upload_bytes=min(
                config.transfer.max_upload_bytes, config.max_input_image_bytes
            ),
        )
        register_transfer_routes(
            mcp,
            config.server,
            _transfer_config,
            sink=_transfer_sink,
            validate=_transfer_sink.validate,
        )
        _finalize_transfer_tool_metadata(mcp)

    # IG-specific: expose resources as tools for clients without resource support.
    # Apply AFTER all registrations so the transform sees every resource.
    mcp.add_transform(_TitledResourcesAsTools(mcp))

    if config.read_only:
        mcp.disable(tags={"write"})
    # DOMAIN-WIRING-END

    # Operator tool visibility (IMAGE_GENERATION_MCP_TOOLS_ALLOW /
    # IMAGE_GENERATION_MCP_TOOLS_DENY) applies last: fastmcp resolves visibility
    # transforms in call order, so the operator's lists win over any
    # visibility calls in the wiring above, and pvl-core's zero-tools-exposed
    # diagnostic judges the full registered tool set.
    apply_tool_visibility(mcp, config.server)

    return mcp
