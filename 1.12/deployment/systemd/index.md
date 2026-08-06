# Systemd Deployment

Run image-generation-mcp as a native Linux service using the `.deb` or `.rpm` package.

## Installation

Note

Packages are built for x86_64/amd64 (pure Python, but packaged per-architecture). The package installs [uv](https://docs.astral.sh/uv/) automatically if not already present.

### Debian / Ubuntu

```
# Download the .deb from the latest release
curl -LO https://github.com/pvliesdonk/image-generation-mcp/releases/latest/download/image-generation-mcp_latest.deb
sudo apt install ./image-generation-mcp_latest.deb
```

### RHEL / Fedora

```
curl -LO https://github.com/pvliesdonk/image-generation-mcp/releases/latest/download/image-generation-mcp_latest.rpm
sudo dnf install image-generation-mcp_latest.rpm
```

The package creates:

| Path                                                   | Purpose                                                                 |
| ------------------------------------------------------ | ----------------------------------------------------------------------- |
| `/usr/lib/systemd/system/image-generation-mcp.service` | Systemd unit file                                                       |
| `/etc/image-generation-mcp/env`                        | Environment configuration                                               |
| `/var/lib/image-generation-mcp/`                       | Data directory (writable state; images saved to `images/` subdirectory) |

A dedicated `image-generation-mcp` system user and group are created automatically.

## Configuration

Edit `/etc/image-generation-mcp/env` to configure the server. All variables use the `IMAGE_GENERATION_MCP_` prefix. See [Configuration](https://pvliesdonk.github.io/image-generation-mcp/1.12/configuration/index.md) for the full reference.

### OpenAI provider

```
IMAGE_GENERATION_MCP_READ_ONLY=false
IMAGE_GENERATION_MCP_OPENAI_API_KEY=sk-...
IMAGE_GENERATION_MCP_SCRATCH_DIR=/var/lib/image-generation-mcp/images
```

### SD WebUI (Stable Diffusion WebUI)

```
IMAGE_GENERATION_MCP_READ_ONLY=false
IMAGE_GENERATION_MCP_SD_WEBUI_HOST=http://localhost:7860
IMAGE_GENERATION_MCP_SCRATCH_DIR=/var/lib/image-generation-mcp/images
```

### Placeholder (testing)

```
IMAGE_GENERATION_MCP_READ_ONLY=false
IMAGE_GENERATION_MCP_SCRATCH_DIR=/var/lib/image-generation-mcp/images
```

### With authentication

```
IMAGE_GENERATION_MCP_READ_ONLY=false
IMAGE_GENERATION_MCP_OPENAI_API_KEY=sk-...
IMAGE_GENERATION_MCP_BASE_URL=https://mcp.example.com
IMAGE_GENERATION_MCP_OIDC_CONFIG_URL=https://auth.example.com/.well-known/openid-configuration
IMAGE_GENERATION_MCP_OIDC_CLIENT_ID=image-generation-mcp
IMAGE_GENERATION_MCP_OIDC_CLIENT_SECRET=your-client-secret
# Generate a stable signing key: openssl rand -hex 32
IMAGE_GENERATION_MCP_OIDC_JWT_SIGNING_KEY=paste-generated-key-here
```

Warning

The env file contains secrets (API keys, OIDC credentials). The package sets permissions to `0640 root:image-generation-mcp`. Do not loosen these.

Note

systemd `EnvironmentFile` does not perform shell substitution. Generate values like the JWT signing key separately (`openssl rand -hex 32`) and paste the result into the env file.

## Service management

```
# Enable and start
sudo systemctl enable --now image-generation-mcp

# Check status
sudo systemctl status image-generation-mcp

# View logs (follow mode)
sudo journalctl -u image-generation-mcp -f

# Restart after config change
sudo systemctl restart image-generation-mcp

# Stop
sudo systemctl stop image-generation-mcp
```

## Security hardening

The systemd unit includes these security directives:

| Directive                                      | Effect                                            |
| ---------------------------------------------- | ------------------------------------------------- |
| `ProtectSystem=strict`                         | Mounts `/usr`, `/boot`, `/efi` read-only          |
| `ProtectHome=yes`                              | Hides `/home`, `/root`, `/run/user`               |
| `NoNewPrivileges=yes`                          | Prevents privilege escalation via setuid binaries |
| `PrivateTmp=yes`                               | Isolates `/tmp` and `/var/tmp`                    |
| `PrivateDevices=yes`                           | Hides physical devices                            |
| `ProtectKernelTunables=yes`                    | Blocks writes to `/proc` and `/sys`               |
| `ProtectKernelModules=yes`                     | Prevents loading kernel modules                   |
| `ProtectControlGroups=yes`                     | Mounts cgroup filesystem read-only                |
| `RestrictSUIDSGID=yes`                         | Blocks creating setuid/setgid files               |
| `RestrictRealtime=yes`                         | Denies realtime scheduling                        |
| `SystemCallArchitectures=native`               | Blocks non-native syscalls                        |
| `ReadWritePaths=/var/lib/image-generation-mcp` | Only writable path                                |

The service runs as the unprivileged `image-generation-mcp` user. It can only write to `/var/lib/image-generation-mcp/`.

## Manual setup (without package)

If you prefer not to use the `.deb`/`.rpm` package:

```
# 1. Install uv
curl -LsSf https://astral.sh/uv/install.sh | sudo env UV_INSTALL_DIR=/usr/local/bin sh

# 2. Create system group and user
sudo groupadd --system image-generation-mcp
sudo useradd --system --gid image-generation-mcp \
    --shell /usr/sbin/nologin \
    --home-dir /var/lib/image-generation-mcp \
    --no-create-home \
    image-generation-mcp

# 3. Create directories
sudo install -d -o image-generation-mcp -g image-generation-mcp -m 0750 \
    /var/lib/image-generation-mcp
sudo install -d -m 0750 /etc/image-generation-mcp

# 4. Download service file and env template
sudo curl -o /usr/lib/systemd/system/image-generation-mcp.service \
    https://raw.githubusercontent.com/pvliesdonk/image-generation-mcp/main/packaging/image-generation-mcp.service
sudo curl -o /etc/image-generation-mcp/env \
    https://raw.githubusercontent.com/pvliesdonk/image-generation-mcp/main/packaging/env.example
sudo chmod 0640 /etc/image-generation-mcp/env
sudo chown root:image-generation-mcp /etc/image-generation-mcp/env

# 5. Edit configuration
sudo editor /etc/image-generation-mcp/env

# 6. Enable and start
sudo systemctl daemon-reload
sudo systemctl enable --now image-generation-mcp
```

## Troubleshooting

### Service fails to start

Check logs for the specific error:

```
sudo journalctl -u image-generation-mcp --no-pager -n 50
```

Common causes:

- **Missing uv**: The service requires `uvx` at `/usr/local/bin/uvx`. Install with `curl -LsSf https://astral.sh/uv/install.sh | sudo env UV_INSTALL_DIR=/usr/local/bin sh`
- **Missing API key**: OpenAI provider requires `IMAGE_GENERATION_MCP_OPENAI_API_KEY`
- **SD WebUI not reachable**: Verify `IMAGE_GENERATION_MCP_SD_WEBUI_HOST` is accessible from the service user
- **Port conflict**: Default HTTP port is 8000. Check with `ss -tlnp | grep 8000`

### Permission denied on images directory

```
# Verify ownership
ls -la /var/lib/image-generation-mcp/

# Fix if needed
sudo chown -R image-generation-mcp:image-generation-mcp /var/lib/image-generation-mcp
```

### Uninstalling

```
# Debian / Ubuntu
sudo apt remove image-generation-mcp

# RHEL / Fedora
sudo dnf remove image-generation-mcp
```

The package stops and disables the service automatically. It does not remove the system user or data directory. Delete those manually if desired:

```
sudo rm -rf /var/lib/image-generation-mcp /etc/image-generation-mcp
sudo userdel image-generation-mcp
sudo groupdel image-generation-mcp
```
