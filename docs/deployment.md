# Deployment Guide

## Local / Direct

```bash
pip install git+https://github.com/bry5an/tver-dl.git

# or from source with UV
uv sync
uv run tver-dl --config config.yaml
```

Connect to a Japanese VPN before running.

---

## Docker

The Docker setup bundles three services: a config fetcher, a VPN tunnel, and the downloader.

### Services

```mermaid
flowchart LR
    config["config\n(curl)"]
    gluetun["gluetun\n(NordVPN/OpenVPN)"]
    tver["tver-dl"]

    config -->|"writes config.yaml\nto shared volume"| tver
    gluetun -->|"network_mode:\nservice:gluetun"| tver
```

| Service | Image | Role |
|---------|-------|------|
| `config` | `curlimages/curl` | One-shot: fetches `config.yaml` from a URL into a shared volume |
| `gluetun` | `qmcgaw/gluetun` | VPN container; tver-dl routes all traffic through it |
| `tver-dl` | local build | Downloader; waits for `config` to complete before starting |

### Setup

1. **Create `.env`** in the project root:

   ```env
   VPN_SERVICE_PROVIDER=nordvpn
   OPENVPN_USER=your_vpn_username
   OPENVPN_PASSWORD=your_vpn_password
   SERVER_COUNTRIES=Japan
   POSTGRESQL_CONNECTION=postgresql://user:pass@host:5432/db
   CONFIG_URL=https://your-host/config.yaml
   ```

2. **Build and run**:

   ```bash
   docker compose up --build
   ```

3. **Schedule** with cron or a systemd timer to run periodically:

   ```cron
   0 6 * * * cd /path/to/tver-dl && docker compose up --build
   ```

### Notes

- `SETUPTOOLS_SCM_PRETEND_VERSION` must be set in the Dockerfile because the Docker build context has no git history. The version is hardcoded there.
- Secrets (`VPN credentials`, `POSTGRESQL_CONNECTION`) are injected via `.env` — never hardcoded in the image.

---

## Ansible

An Ansible playbook is included in `ansible/` to sync downloaded files from a remote server.

See [ansible/README.md](../ansible/README.md) for setup and usage.

---

## VPN Requirements

TVer requires a Japanese IP address. The VPN check runs three parallel geolocation lookups (ipapi.co, ip.seeip.org, api.myip.com) and prompts before continuing if the detected country is not Japan.

Skip the check with `--skip-vpn-check` (e.g. if your geolocation services are unreliable or you know your VPN is connected).
