# OIDC Authentication

Optional token-based authentication for HTTP deployments. Two OIDC modes are available:

| Mode                       | Env var                | Use case                                               | Required vars                                                            |
| -------------------------- | ---------------------- | ------------------------------------------------------ | ------------------------------------------------------------------------ |
| **`remote`** (recommended) | `AUTH_MODE=remote`     | Local JWT validation (no upstream token re-validation) | `BASE_URL` + `OIDC_CONFIG_URL`                                           |
| **`oidc-proxy`**           | `AUTH_MODE=oidc-proxy` | DCR emulation for non-DCR IdPs                         | `BASE_URL` + `OIDC_CONFIG_URL` + `OIDC_CLIENT_ID` + `OIDC_CLIENT_SECRET` |

The mode is auto-detected when `AUTH_MODE` is not set: `oidc-proxy` when client credentials are present, `remote` otherwise. For an overview of all authentication modes (bearer token, OIDC, no auth), see the [Authentication guide](https://pvliesdonk.github.io/image-generation-mcp/unstable/guides/authentication/index.md).

Transport requirement

OIDC requires `--transport http` (or `sse`). It has no effect with `--transport stdio`.

Prefer remote mode

`remote` mode avoids the [OIDCProxy session lifetime issue](https://pvliesdonk.github.io/image-generation-mcp/unstable/guides/authentication/#known-limitations-oidc-session-lifetime) by validating tokens locally via JWKS without storing or re-validating upstream tokens. Use `oidc-proxy` only when your IdP does not support Dynamic Client Registration and you need DCR emulation.

## Remote Mode (recommended)

### Required Variables

| Variable                               | Description                                                                                   |
| -------------------------------------- | --------------------------------------------------------------------------------------------- |
| `IMAGE_GENERATION_MCP_BASE_URL`        | Public base URL of the server (such as `https://mcp.example.com`)                             |
| `IMAGE_GENERATION_MCP_OIDC_CONFIG_URL` | OIDC discovery endpoint (such as `https://auth.example.com/.well-known/openid-configuration`) |

### Optional Variables

| Variable                                    | Default | Description                                                                |
| ------------------------------------------- | ------- | -------------------------------------------------------------------------- |
| `IMAGE_GENERATION_MCP_OIDC_AUDIENCE`        | n/a     | Expected JWT audience claim; leave unset if your provider does not set one |
| `IMAGE_GENERATION_MCP_OIDC_REQUIRED_SCOPES` | n/a     | Comma-separated required scopes                                            |

### Example

```
IMAGE_GENERATION_MCP_BASE_URL=https://mcp.example.com
IMAGE_GENERATION_MCP_OIDC_CONFIG_URL=https://auth.example.com/.well-known/openid-configuration
# Optional:
# IMAGE_GENERATION_MCP_OIDC_AUDIENCE=image-generation-mcp
```

The server fetches the OIDC discovery document at startup to obtain `jwks_uri` and `issuer`, then validates incoming JWTs locally. No client credentials, JWT signing key, or upstream token storage needed.

## OIDCProxy Mode

### Required Variables

| Variable                                  | Description                                                                                                                                                        |
| ----------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `IMAGE_GENERATION_MCP_BASE_URL`           | Public base URL of the deployed server (`https://mcp.example.com`). Required for OIDC. Also the fallback source of the MCP Apps domain when `app_domain` is unset. |
| `IMAGE_GENERATION_MCP_OIDC_CONFIG_URL`    | OIDC discovery document URL (`https://auth.example.com/.well-known/openid-configuration`).                                                                         |
| `IMAGE_GENERATION_MCP_OIDC_CLIENT_ID`     | OIDC client identifier registered with the provider.                                                                                                               |
| `IMAGE_GENERATION_MCP_OIDC_CLIENT_SECRET` | OIDC client secret registered with the provider.                                                                                                                   |

### Optional Variables

| Variable                                        | Default   | Description                                                                                                                                                                                                                                                                                                                                                                   |
| ----------------------------------------------- | --------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `IMAGE_GENERATION_MCP_OIDC_AUDIENCE`            | (none)    | Expected `aud` claim; tokens issued for another audience are rejected.                                                                                                                                                                                                                                                                                                        |
| `IMAGE_GENERATION_MCP_OIDC_REQUIRED_SCOPES`     | `openid`  | Scopes a caller must present, space- or comma-separated. Defaults to `openid` in oidc-proxy mode.                                                                                                                                                                                                                                                                             |
| `IMAGE_GENERATION_MCP_OIDC_ADVERTISED_SCOPES`   | (none)    | Scopes advertised to MCP clients in protected-resource metadata, space- or comma-separated. Overrides the default `openid offline_access`; `oidc_required_scopes` is always added on top. Set this when the registered client is not permitted `offline_access`, or to have clients request extra claim scopes (such as `groups`) without also requiring them in every token. |
| `IMAGE_GENERATION_MCP_OIDC_JWT_SIGNING_KEY`     | `derived` | Signing key for issued JSON Web Tokens; used in oidc-proxy mode only. When unset, the key is derived deterministically from `oidc_client_secret`, so tokens survive a restart. Rotating that secret invalidates every issued token. Set this explicitly to decouple token validity from secret rotation. Generate with `openssl rand -hex 32`.                                |
| `IMAGE_GENERATION_MCP_OIDC_VERIFY_ACCESS_TOKEN` | `false`   | Validate the access token instead of the id token.                                                                                                                                                                                                                                                                                                                            |

## JWT Signing Key

When `IMAGE_GENERATION_MCP_OIDC_JWT_SIGNING_KEY` is unset, FastMCP derives the signing key from the OIDC client secret using deterministic key derivation, so the key stays the same across restarts and tokens keep validating.

The real reason to set an explicit key is secret rotation: because the default key is derived from the client secret, rotating that secret changes the derived key and invalidates every token issued under the old one. Setting an explicit signing key decouples token validity from client-secret rotation:

```
# Generate once, store in your .env file
openssl rand -hex 32
```

## Setup with Authelia

Note

Authelia does not support Dynamic Client Registration (RFC 7591). Clients must be registered manually in `configuration.yml`.

Opaque vs JWT access tokens

Authelia issues **opaque** (non-JWT) access tokens by default. This affects which OIDC mode you can use:

- **Remote mode** validates tokens locally via JWKS and **requires JWT access tokens**. Set `access_token_signed_response_alg: 'RS256'` on the client registration (see below).
- **OIDCProxy mode** verifies the `id_token` (always a standard JWT) instead of the access token, so opaque tokens work without extra configuration. However, oidc-proxy is subject to the [session lifetime limitation](https://pvliesdonk.github.io/image-generation-mcp/unstable/guides/authentication/#known-limitations-oidc-session-lifetime).

### Remote mode (recommended)

Remote mode requires only `BASE_URL` + `OIDC_CONFIG_URL` on the MCP server (no client credentials needed server-side). The client authenticates directly with Authelia; the server validates the resulting JWT access token via JWKS.

Client credentials are IdP-side only

In remote mode, `CLIENT_ID` and `CLIENT_SECRET` are configured in the **Authelia client registration** (so Authelia knows which client is connecting), but they are not set as MCP server environment variables. The MCP server only needs the OIDC discovery URL to fetch JWKS keys for token validation.

#### 1. Register the client in Authelia

```
identity_providers:
  oidc:
    clients:
      - client_id: image-generation-mcp
        client_secret: '$pbkdf2-sha512$...'   # authelia crypto hash generate
        redirect_uris:
          # In remote mode each MCP client handles its own OAuth flow.
          # List the callback URLs used by your client(s):
          - https://claude.ai/api/mcp/auth_callback  # Claude.ai web
        grant_types: [authorization_code]
        response_types: [code]
        pkce_challenge_method: S256
        scopes: [openid, profile, email]
        # Required for remote mode — enables JWT access tokens (RFC 9068)
        # Without this, Authelia issues opaque tokens that cannot be
        # validated locally via JWKS
        access_token_signed_response_alg: 'RS256'
        # Claude Code (and some other MCP clients) sends credentials via
        # POST body rather than HTTP Basic auth during token exchange
        token_endpoint_auth_method: 'client_secret_post'
```

Why `access_token_signed_response_alg`?

Remote mode's `JWTVerifier` decodes the access token as a JWT and validates its signature against the IdP's JWKS keys. Authelia's default opaque tokens are random strings with no JWT structure and cannot be validated locally. Setting `access_token_signed_response_alg: 'RS256'` tells Authelia to issue RFC 9068 JWT access tokens for this client.

Why `token_endpoint_auth_method`?

During the OAuth token exchange, the MCP client sends `client_id` and `client_secret` in the POST body (`client_secret_post`). Authelia defaults to `client_secret_basic` (HTTP Basic auth header). If these don't match, the token exchange fails with a `token_endpoint_auth_method` error. Setting `client_secret_post` explicitly ensures compatibility with Claude Code and other MCP clients.

#### 2. Set environment variables

```
IMAGE_GENERATION_MCP_BASE_URL=https://mcp.example.com
IMAGE_GENERATION_MCP_OIDC_CONFIG_URL=https://auth.example.com/.well-known/openid-configuration
```

No `CLIENT_ID`, `CLIENT_SECRET`, or `JWT_SIGNING_KEY` needed: the server validates tokens without participating in the OAuth handshake.

#### 3. Start with HTTP transport

```
image-generation-mcp serve --transport http --port 8000
```

### OIDCProxy mode (fallback)

Use oidc-proxy only when remote mode is not viable (such as when your IdP cannot issue JWT access tokens). Be aware of the [session lifetime limitation](https://pvliesdonk.github.io/image-generation-mcp/unstable/guides/authentication/#known-limitations-oidc-session-lifetime).

#### 1. Register the client in Authelia

```
identity_providers:
  oidc:
    clients:
      - client_id: image-generation-mcp
        client_secret: '$pbkdf2-sha512$...'   # authelia crypto hash generate
        redirect_uris:
          - https://mcp.example.com/auth/callback
        grant_types: [authorization_code]
        response_types: [code]
        pkce_challenge_method: S256
        scopes: [openid, profile, email]
        # Authelia defaults to client_secret_basic; Claude Code uses client_secret_post
        token_endpoint_auth_method: 'client_secret_post'
```

No `access_token_signed_response_alg` needed. OIDCProxy verifies the `id_token` (always a JWT) instead of the access token.

#### 2. Set environment variables

```
IMAGE_GENERATION_MCP_BASE_URL=https://mcp.example.com
IMAGE_GENERATION_MCP_OIDC_CONFIG_URL=https://auth.example.com/.well-known/openid-configuration
IMAGE_GENERATION_MCP_OIDC_CLIENT_ID=image-generation-mcp
IMAGE_GENERATION_MCP_OIDC_CLIENT_SECRET=your-client-secret
IMAGE_GENERATION_MCP_OIDC_JWT_SIGNING_KEY=$(openssl rand -hex 32)
```

#### 3. Start with HTTP transport

```
image-generation-mcp serve --transport http --port 8000
```

For subpath deployments (such as public URL `https://mcp.example.com/vault/mcp`), see [Subpath Deployments](#subpath-deployments) below.

See also `examples/oidc.env`.

## Architecture

### Remote mode

The server acts as a Resource Server (RFC 9728). The client authenticates directly with the IdP; the server validates tokens locally via JWKS.

```
Client → OIDC Provider (authenticate) → Client → image-generation-mcp (validate JWT)
```

1. Client authenticates with the OIDC provider independently
1. Client sends requests to the MCP server with the JWT token
1. Server validates the token locally using the IdP's JWKS keys
1. No upstream token storage or re-validation

### OIDCProxy mode

The server uses FastMCP's built-in `OIDCProxy` auth provider to act as an OAuth intermediary with DCR emulation.

```
Client → image-generation-mcp (with OIDCProxy) → OIDC Provider (Authelia/Keycloak)
```

1. Client connects to the MCP server
1. Server redirects to the OIDC provider for authentication
1. Provider authenticates the user and returns a code
1. Server exchanges the code for tokens and issues its own proxy JWT
1. Subsequent requests include the proxy JWT

Session lifetime

OIDCProxy re-validates upstream tokens on every request. When the upstream token expires (typically 1 h), sessions die even though the proxy JWT is still valid. See [Known Limitations](https://pvliesdonk.github.io/image-generation-mcp/unstable/guides/authentication/#known-limitations-oidc-session-lifetime).

## Docker Compose with OIDC

```
services:
  image-generation-mcp:
    image: ghcr.io/pvliesdonk/image-generation-mcp:latest
    env_file: .env
    volumes:
      - images-data:/data/service
      - state-data:/data/state
    environment:
      IMAGE_GENERATION_MCP_SCRATCH_DIR: /data/service
      FASTMCP_HOME: /data/state/fastmcp
    restart: unless-stopped
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.image-generation-mcp.rule=Host(`mcp.example.com`)"
      - "traefik.http.routers.image-generation-mcp.tls.certresolver=letsencrypt"
      - "traefik.http.services.image-generation-mcp.loadbalancer.server.port=8000"
    networks:
      - traefik

volumes:
  images-data:
  state-data:

networks:
  traefik:
    external: true
```

With the corresponding `.env`:

```
IMAGE_GENERATION_MCP_BASE_URL=https://mcp.example.com
IMAGE_GENERATION_MCP_OIDC_CONFIG_URL=https://auth.example.com/.well-known/openid-configuration
IMAGE_GENERATION_MCP_OIDC_CLIENT_ID=image-generation-mcp
IMAGE_GENERATION_MCP_OIDC_CLIENT_SECRET=your-client-secret
IMAGE_GENERATION_MCP_OIDC_JWT_SIGNING_KEY=your-stable-hex-key
```

For a prefixed deployment (such as `https://mcp.example.com/vault/mcp`), see [Subpath Deployments](#subpath-deployments) below.

## Subpath Deployments

When OIDC is enabled behind a reverse-proxy subpath, `BASE_URL` and `HTTP_PATH` serve different roles:

| Variable    | Purpose                                                    | Example                         |
| ----------- | ---------------------------------------------------------- | ------------------------------- |
| `BASE_URL`  | Public URL of the server, **including the subpath prefix** | `https://mcp.example.com/vault` |
| `HTTP_PATH` | Internal MCP endpoint mount point (**no subpath prefix**)  | `/mcp`                          |

The reverse proxy strips the subpath prefix before forwarding to the application. FastMCP concatenates `BASE_URL + HTTP_PATH` to build the public resource URL, so including the prefix in both produces broken URLs with duplicated path segments.

Do not duplicate the subpath

Setting `BASE_URL=https://mcp.example.com/vault` together with `HTTP_PATH=/vault/mcp` produces a duplicated resource URL: `https://mcp.example.com/vault/vault/mcp`. The subpath belongs in `BASE_URL` only.

### Configuration

Environment variables:

```
IMAGE_GENERATION_MCP_BASE_URL=https://mcp.example.com/vault
IMAGE_GENERATION_MCP_HTTP_PATH=/mcp
```

Register this callback URI in your OIDC provider:

```
https://mcp.example.com/vault/auth/callback
```

### Reverse proxy routing

The reverse proxy must:

1. **Strip the prefix** (`/vault`) from operational routes before forwarding to the app
1. **Forward OAuth discovery routes** to this service (without stripping prefixes):
   - `/.well-known/oauth-authorization-server` (authorization server metadata)
   - `/.well-known/oauth-protected-resource/vault/mcp` (protected resource metadata)

Example Traefik configuration:

```
labels:
  # Operational routes: strip /vault prefix before forwarding
  - "traefik.http.routers.vault-app.rule=Host(`mcp.example.com`) && PathPrefix(`/vault`)"
  - "traefik.http.middlewares.strip-vault.stripprefix.prefixes=/vault"
  - "traefik.http.routers.vault-app.middlewares=strip-vault"
  - "traefik.http.services.vault-app.loadbalancer.server.port=8000"
  # OAuth discovery routes: forward without stripping
  - "traefik.http.routers.vault-wellknown.rule=Host(`mcp.example.com`) && (PathPrefix(`/.well-known/oauth-authorization-server`) || PathPrefix(`/.well-known/oauth-protected-resource/vault/mcp`))"
  - "traefik.http.routers.vault-wellknown.service=vault-app"
```

Note

This configuration requires that no other OAuth service claims `/.well-known/oauth-authorization-server` on this hostname. See [Shared-hostname limitation](#shared-hostname-limitation) below.

### Shared-hostname limitation

Shared-hostname subpath with native OIDC is not supported

When multiple OAuth-capable services share a hostname (such as `mcp-auth-proxy` at the root and `image-generation-mcp` at `/vault`), native OIDC on a subpath does not work.

**Why:** FastMCP serves the OAuth authorization-server metadata at `/.well-known/oauth-authorization-server` (host root), regardless of the subpath in `BASE_URL`. The FastMCP codebase contains an RFC 8414 path-aware override (`OIDCProxy.get_well_known_routes()`) that would serve it at `/.well-known/oauth-authorization-server/vault`. However, this method is not wired into the route mounting flow and is effectively dead code.

The protected-resource metadata (`/.well-known/oauth-protected-resource/vault/mcp`) is correctly path-namespaced and does not collide. Only the authorization-server discovery route is the problem.

This works when `image-generation-mcp` is the **only** OAuth service on the hostname — the host-root `/.well-known/oauth-authorization-server` does not collide with anything. It breaks when another service already owns that route.

**Recommendations for shared-hostname scenarios:**

- **Dedicated hostname** (preferred): give `image-generation-mcp` its own hostname (such as `vault.example.com`) so discovery routes do not collide.
- **External auth gateway**: use `mcp-auth-proxy` as a sidecar instead of native OIDC. The MCP server runs unauthenticated behind the proxy, and the proxy handles OAuth discovery at its own routes.
