# BookBridge staging deployment

These are deployment templates, not evidence that anything is deployed. With no key configured, the preview provides only the clearly labeled **invented sample**. Live mode may be enabled after both Qloo endpoints have been validated with an issued key; the sample never becomes live evidence merely because live mode is available.

This plan adds only an isolated `bookbridge` system user/service, nginx site, DNS record, and positive-TTL staging port lease. Preserve all foreign services, nginx defaults/includes (including any common Cloudflare real-IP policy), certificates, DNS records, leases, and files. Do not add a cron job. Never publish this private competitions repository or its history; if a public repository is required, export a separately audited clean-room tree with new history.

## Stage

1. Through the runtime registry, allocate an unused host-local TCP port to BookBridge with a positive 14-day staging TTL. Record the renewal owner, actual port, lease ID, allocation time, and expiry in the registry/handoff, and renew it before expiry. Keep the lease token only in the registry-generated mode-0600 environment file inside its owner's mode-0700 state directory. Never print it or pass it to the application, public source, or `service.env`.
2. Create the dedicated identity if absent; do not reuse another service account:

   ```bash
   sudo groupadd --system bookbridge
   sudo useradd --system --gid bookbridge --home-dir /nonexistent --shell /usr/sbin/nologin bookbridge
   ```

   Check `getent group bookbridge` and `getent passwd bookbridge` first so existing correct entries are preserved.
3. Stage a reviewed BookBridge release under `/opt/bookbridge/releases/<release-id>`, excluding `.git`, `.env*`, caches, tests, private evidence, and credentials. Create a new Python 3.12 environment at that release's `venv` and install its `requirements.txt`; never update an active release or share its environment with another release. Verify import of `bookbridge.app` using this Python from the release directory before switching. Keep the release and `/opt/bookbridge/current` symlink root-owned and not writable by `bookbridge`. Point `/opt/bookbridge/current` atomically to the reviewed release only after its dependencies and import checks pass. The service resolves its executable through `current/venv`, so a source rollback also restores the matching dependencies.
4. Create `/etc/bookbridge/service.env` using a root-only editor, without printing its contents:

   ```text
   TCP_PORT=<actual registry-leased port>
   ```

   Leave `QLOO_API_KEY` absent for the invented-sample preview. For the authorized live deployment after validating an issued key, add `QLOO_API_KEY=...` only with a root-only editor. Set the directory root-owned mode `0755` and the file root-owned mode `0600`; never use `cat`, shell tracing, `systemctl show Environment`, or logs to expose the key.

## Install and verify

1. Copy `bookbridge.service` to `/etc/systemd/system/bookbridge.service`. Replace `@@DOMAIN@@`, `@@PORT@@`, `@@CERT@@`, and `@@KEY@@` in a copied nginx site file such as `/etc/nginx/sites-available/bookbridge.conf`. `@@PORT@@` must equal `TCP_PORT`; certificate placeholders must reference the existing valid wildcard Cloudflare origin certificate and key. Do not alter shared TLS/Cloudflare-real-IP includes or existing default servers. Enable only this new site. The template deliberately has no `default_server`: only its exact `server_name` belongs to BookBridge, while existing default servers continue to reject or handle unrecognized Host values.
2. Before starting anything, verify ownership/modes, the release symlink, venv executable, and that no `@@...@@` placeholders remain. Then run:

   ```bash
   sudo systemd-analyze verify /etc/systemd/system/bookbridge.service
   sudo nginx -t
   sudo systemctl daemon-reload
   sudo systemctl enable --now bookbridge.service
   ```

   Reload nginx only after `nginx -t` succeeds. A failure must leave the currently loaded nginx configuration untouched.
3. Test the origin without changing Host routing, then test the proxied public TLS name after the isolated DNS record is active. Confirm HTTP redirects to the fixed HTTPS domain, TLS works through Cloudflare, `/`, `/app.js`, `/styles.css`, and `/api/status` respond, and status reports sample available but live unavailable while no key exists. Exercise one sample request and confirm the UI still labels it invented/synthetic; do not call or claim live Qloo results.
4. Read `systemctl status bookbridge.service` and bounded journal output for startup errors, but do not print environment values. Record the DNS record, service/site filenames, release ID, origin/proxied checks, lease expiry, and the renewal owner in the handoff.

Uvicorn deliberately binds only `127.0.0.1`, uses one worker, emits no access log, and does not trust proxy headers. Consequently all nginx callers intentionally share the app's loopback client bucket of 30 API requests per minute. The prototype also permits only 400 actual upstream attempts per rolling 24 hours in process memory; restarting the service resets that counter, cache, and rolling budget. The 90-second nginx timeout accommodates the roughly 32-second four-call recommendation path, but this remains a low-volume staging demo.

## Roll back or clean up

For an application rollback, atomically repoint `/opt/bookbridge/current` to the previously recorded release, restart only `bookbridge.service`, and repeat the origin and proxied checks.

For full cleanup, disable and stop only `bookbridge.service`; remove only the BookBridge unit and enabled/site files; run `nginx -t` before reloading nginx; remove only the BookBridge DNS record; and release only BookBridge's runtime-registry lease. Remove BookBridge releases, venv, environment file, and dedicated user/group only after confirming no retained rollback needs or ownership references. Do not delete shared certificates, common nginx configuration/default servers, foreign releases, users, DNS, leases, or runtime-registry state.
