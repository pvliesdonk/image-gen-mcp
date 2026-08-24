"""Regression coverage for the generated MCPB install configuration."""

from __future__ import annotations

import json
from pathlib import Path


def test_mcpb_manifest_retains_project_install_fields() -> None:
    """Desktop installs retain image-generation configuration and secret handling."""
    manifest_path = Path(__file__).parents[1] / "packaging/mcpb/manifest.json.in"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    expected_env = {
        "IMAGE_GENERATION_MCP_SCRATCH_DIR": "${user_config.scratch_dir}",
        "IMAGE_GENERATION_MCP_STYLES_DIR": "${user_config.styles_dir}",
        "IMAGE_GENERATION_MCP_READ_ONLY": "${user_config.read_only}",
        "IMAGE_GENERATION_MCP_DEFAULT_PROVIDER": "${user_config.default_provider}",
        "IMAGE_GENERATION_MCP_PAID_PROVIDERS": "${user_config.paid_providers}",
        "IMAGE_GENERATION_MCP_OPENAI_API_KEY": "${user_config.openai_api_key}",
        "IMAGE_GENERATION_MCP_GOOGLE_API_KEY": "${user_config.google_api_key}",
        "IMAGE_GENERATION_MCP_SD_WEBUI_HOST": "${user_config.sd_webui_host}",
        "IMAGE_GENERATION_MCP_SD_WEBUI_MODEL": "${user_config.sd_webui_model}",
    }
    config = manifest["user_config"]
    env = manifest["server"]["mcp_config"]["env"]

    assert expected_env.items() <= env.items()
    assert config["scratch_dir"]["type"] == "directory"
    assert config["styles_dir"]["type"] == "directory"
    assert config["read_only"]["default"] is False
    assert config["default_provider"]["default"] == "auto"
    assert config["paid_providers"]["default"] == "openai"
    assert config["openai_api_key"]["sensitive"] is True
    assert config["google_api_key"]["sensitive"] is True
