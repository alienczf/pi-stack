# Reach home-ws01 from a Cloud Agent

Cloud Agent VMs cannot use Tailscale's default TUN networking. `install.sh` puts the `tailscale` and `tailscaled` binaries on disk. `start.sh` runs `tailscaled` in userspace mode on every boot, with the HTTP proxy on `localhost:1054` and the SOCKS5 proxy on `localhost:1055`. SSH to `home-ws01` goes through that SOCKS proxy. Shell exports in `start` never reach the agent shell, so the SSH config holds the `ProxyCommand`. Later you can SSH in and run `pi-web-cli` or `pi-streams` on that host.

The target is `home-ws01.tail36bc2d.ts.net` port 22 as user `zhanfeng`. Use the FQDN. The short name `home-ws01` may not resolve. `HostKeyAlias home-ws01` keeps the known_hosts name stable.

## Add the two Cursor secrets

Add both secrets in the Cloud Agents dashboard guided environment setup, or in Settings > Secrets. Do not put them in the repo, in `environment.json`, or in chat.

- `TS_AUTHKEY`. A reusable, ephemeral, pre-approved auth key tagged `tag:cursor`.
- `HOME_WS01_SSH_KEY`. The private key for `zhanfeng` on `home-ws01`. `start.sh` writes it to `~/.ssh/home_ws01` with mode `600` and does not print it.

If a secret is missing, `start.sh` logs one line and continues. The agent still boots. `check.sh` fails the steps that need that secret.

## Restrict tag:cursor in the tailnet ACL

Default Tailscale ACLs allow `*:*`. A narrower rule does nothing until you remove that allow-all rule. Put `home-ws01`'s Tailscale IPv4 in `hosts` (run `tailscale ip -4` on the Pi). Then restrict `tag:cursor` to SSH on that host only:

```json
{
  "tagOwners": {
    "tag:cursor": ["autogroup:admin"]
  },
  "hosts": {
    "home-ws01": "100.x.y.z"
  },
  "acls": [
    {
      "action": "accept",
      "src": ["tag:cursor"],
      "dst": ["home-ws01:22"]
    }
  ]
}
```

Replace `100.x.y.z` with the Pi's Tailscale IPv4. Keep other rules you still need for humans. Do not advertise an exit node or subnet routes from the Cloud Agent.

## Rotate keys

Auth keys expire after at most 90 days. Mint a new tagged key before that and update `TS_AUTHKEY`.

For a key that does not expire on that schedule, create an OAuth client with the `auth_keys` scope and tag `tag:cursor`. Store the client secret as `TS_AUTHKEY`. `start.sh` detects a `tskey-client-` secret and passes `--advertise-tags=tag:cursor`. You can append `?ephemeral=true&preauthorized=true` to that secret value in Cursor Secrets. See [OAuth clients](https://tailscale.com/docs/features/oauth-clients).

Rotate `HOME_WS01_SSH_KEY` when you rotate `zhanfeng`'s authorized key on the Pi.

## Health check

```bash
ssh zhanfeng@home-ws01 'whoami; hostname'
```

From a Cloud Agent after `start.sh`, run `.cursor/cloud-env/check.sh`. It reports pass or fail for tailscaled, `tailscale status`, and the SSH command above.
