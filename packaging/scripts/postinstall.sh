#!/bin/bash
# Post-install script: create venv and install image-generation-mcp from PyPI.
set -eu

INSTALL_DIR="/opt/image-generation-mcp"
VENV_DIR="${INSTALL_DIR}/venv"
SERVICE_USER="image-generation-mcp"

# Determine package version — set by nfpm via VERSION env var, or read
# from the installed package metadata as fallback.
PKG_VERSION="${VERSION:-}"

# Create install directory
mkdir -p "$INSTALL_DIR"

# Create or update the virtual environment
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
fi

# Upgrade pip and install the package
"${VENV_DIR}/bin/pip" install --quiet --upgrade pip

if [ -n "$PKG_VERSION" ]; then
    case "$PKG_VERSION" in
        *-rc.*)
            # Pre-releases never reach PyPI; install the wheel attached to
            # this version's own GitHub release. The wheel filename carries
            # the PEP 440 canonical spelling (-rc.N -> rcN).
            canonical="$(printf '%s' "$PKG_VERSION" | sed 's/-rc\./rc/')"
            "${VENV_DIR}/bin/pip" install --quiet \
                "image-generation-mcp @ https://github.com/pvliesdonk/image-generation-mcp/releases/download/v${PKG_VERSION}/image_generation_mcp-${canonical}-py3-none-any.whl"
            ;;
        *)
            "${VENV_DIR}/bin/pip" install --quiet "image-generation-mcp==${PKG_VERSION}"
            ;;
    esac
else
    "${VENV_DIR}/bin/pip" install --quiet "image-generation-mcp"
fi

# Ensure config directory exists
mkdir -p /etc/image-generation-mcp

# Copy example env if no config exists yet
if [ ! -f /etc/image-generation-mcp/env ]; then
    if [ -f /etc/image-generation-mcp/env.example ]; then
        cp /etc/image-generation-mcp/env.example /etc/image-generation-mcp/env
    fi
fi

# Restrict env file permissions — it may contain secrets (tokens, API keys).
if [ -f /etc/image-generation-mcp/env ]; then
    chmod 600 /etc/image-generation-mcp/env
fi

# Reload systemd to pick up the unit file.
# Note: the service is intentionally NOT enabled here — start-on-boot requires
# explicit opt-in by the administrator via: systemctl enable image-generation-mcp
systemctl daemon-reload 2>/dev/null || true

# On upgrade, restart the service if it's already running so the new version is loaded.
if systemctl is-active --quiet image-generation-mcp 2>/dev/null; then
    systemctl restart image-generation-mcp
fi
