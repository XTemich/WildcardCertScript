# Wildcard SSL Certificate Manager

[Русский](README.md) | **English**

A script for installing and managing SSL/TLS certificates (`*.example.com` + `example.com`) across three workflows: manual certificate placement, Let's Encrypt wildcard via Cloudflare DNS-only, and Let's Encrypt wildcard with Cloudflare proxy (`Full (strict)`).

---

## Modes

1. **Manual (`1`)** — Copies existing certificate and private key files into `/etc/ssl/custom/<domain>/` with safe permissions (`644` / `600`) and reloads Nginx if present.
2. **Cloudflare DNS-only (Grey Cloud) + Let's Encrypt Wildcard (`2`)** — Issues `*.example.com` and `example.com` via `certbot --dns-cloudflare`, sets up `/root/<domain>-ssl-renew.sh`, and schedules a cron job every 7 days at `04:05`.
3. **Cloudflare Proxied (Orange Cloud) + Let's Encrypt Wildcard + `Full (strict)` (`3`)** — Same wildcard issuance and auto-renewal as Mode 2, plus checks/switches the Cloudflare zone SSL/TLS mode to `Full (strict)` (`strict`) via the Cloudflare API.

---

## Requirements

- Python 3.8+ and Ubuntu / Debian (or any distribution using `apt` for Modes 2 & 3)
- Root access (`sudo`)
- For Modes 2 & 3: a domain hosted on Cloudflare and a Cloudflare API Token
- Nginx (optional) — validated (`nginx -t`) and reloaded (`systemctl reload nginx`) when available

---

## Quick Start

Interactive mode:

```bash
sudo python3 wildcard_ssl.py
```

Non-interactive CLI flags:

```bash
sudo python3 wildcard_ssl.py --mode 3 --domain example.com --token YOUR_CLOUDFLARE_API_TOKEN
```

---

## How to Create a Cloudflare API Token

1. Go to Cloudflare → **My Profile** → **API Tokens** → **Create Token**
2. For **Mode 2 (DNS-only)**: use the **Edit zone DNS** template (`Zone → DNS → Edit`)
3. For **Mode 3 (Proxied + `Full (strict)`)**: include both `Zone → DNS → Edit` and `Zone → SSL and Certificates → Edit` (plus `Zone → Zone → Read` if needed to look up the zone)
4. Scope **Zone Resources** → **Include** → **Specific zone** → your domain

---

## What the Script Does

- **Mode 1:** copies `fullchain.pem` and `privkey.pem` to `/etc/ssl/custom/<domain>/` and reloads Nginx
- **Modes 2 & 3:**
  - Installs `certbot` and `python3-certbot-dns-cloudflare`
  - Saves the API token to `/root/.secrets/certbot/cloudflare.ini` (`600`)
  - Issues a wildcard certificate for `<domain>` and `*.<domain>`
  - Creates `/root/<domain>-ssl-renew.sh` and adds a cron entry (`5 4 */7 * *`)
  - In **Mode 3**, checks the zone's SSL/TLS setting and switches it to `strict` (`Full (strict)`) if needed

---

## Certificate Locations & Nginx Example

- Let's Encrypt (Modes 2 & 3): `/etc/letsencrypt/live/<domain>/fullchain.pem` and `privkey.pem`
- Manual mode (Mode 1): `/etc/ssl/custom/<domain>/fullchain.pem` and `privkey.pem`

```nginx
ssl_certificate     /etc/letsencrypt/live/example.com/fullchain.pem;
ssl_certificate_key /etc/letsencrypt/live/example.com/privkey.pem;
```

---

## Testing Renewal

```bash
sudo certbot renew --dry-run
sudo /root/example.com-ssl-renew.sh
```

---

## Notes

- No email is required (`--register-unsafely-without-email`)
- Existing `crontab` entries are preserved; only the domain's renewal line is updated
- Running as `root` is required