#!/usr/bin/env bash
set -euo pipefail

log() { printf 'cloud-env: %s\n' "$*"; }

mask_kernel_mode_tailscaled() {
  if systemctl list-unit-files tailscaled.service >/dev/null 2>&1; then
    sudo systemctl disable --now tailscaled.service >/dev/null 2>&1 || true
    sudo systemctl mask tailscaled.service >/dev/null 2>&1 || true
  fi
}

sudo apt-get update -qq
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
  ca-certificates curl python3 netcat-openbsd openssh-client

mask_kernel_mode_tailscaled

install_tailscale_binaries() {
  local arch tarball tmp dir
  case "$(uname -m)" in
    x86_64) arch=amd64 ;;
    aarch64|arm64) arch=arm64 ;;
    *)
      log "unsupported architecture $(uname -m)"
      exit 1
      ;;
  esac

  tarball=$(python3 -c "import json,urllib.request,sys; print(json.load(urllib.request.urlopen('https://pkgs.tailscale.com/stable/?mode=json'))['Tarballs']['${arch}'])")
  tmp=$(mktemp -d)
  trap 'rm -rf "$tmp"' RETURN
  curl -fsSL "https://pkgs.tailscale.com/stable/${tarball}" | tar -xz -C "$tmp"
  dir=$(find "$tmp" -mindepth 1 -maxdepth 1 -type d -name 'tailscale_*' -print -quit)
  if [[ -z "$dir" || ! -x "$dir/tailscale" || ! -x "$dir/tailscaled" ]]; then
    log "Tailscale tarball did not contain tailscale and tailscaled"
    exit 1
  fi
  sudo install -m 755 "$dir/tailscale" /usr/local/bin/tailscale
  sudo install -m 755 "$dir/tailscaled" /usr/local/bin/tailscaled
}

if ! command -v tailscale >/dev/null || ! command -v tailscaled >/dev/null; then
  install_tailscale_binaries
else
  log "tailscale already on PATH ($(command -v tailscale))"
fi

if ! nc -h 2>&1 | grep -q -- '-X'; then
  log "netcat-openbsd is required (nc -X 5 for SOCKS). Installed nc does not support -X."
  exit 1
fi

ver=$(tailscale version 2>/dev/null || true)
log "install complete (${ver%%$'\n'*})"
