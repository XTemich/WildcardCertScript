# Wildcard SSL Certificate Manager

**English** | [Русский](README.md)

A script for obtaining Let's Encrypt **wildcard** certificates (`*.example.com` + `example.com`) via the Cloudflare DNS API with automatic renewal.

---

## Requirements

- Ubuntu / Debian (or any distribution using `apt`)
- Root access (`sudo`)
- A domain whose DNS is hosted on Cloudflare
- Nginx (or another web server) — for the post-hook reload

---

## Quick Start

```bash
sudo python3 wildcard_ssl.py
```

The script will prompt you interactively for:
1. Domain
2. Cloudflare API Token

---

## How to Create a Cloudflare API Token

1. Go to Cloudflare → **My Profile** → **API Tokens** → **Create Token**
2. Use the **Edit zone DNS** template  
   or Custom: Permission `Zone.DNS:Edit`
3. Zone Resources → Include → Specific zone → your domain
4. Create the token and paste it into the script

---

## What the Script Does

- Installs `certbot` + `python3-certbot-dns-cloudflare`
- Saves the token to `/root/.secrets/certbot/cloudflare.ini` (permissions `600`)
- Issues a certificate for `*.domain` and `domain`
- Creates a renewal script at `/root/<domain>-ssl-renew.sh`
- Adds a cron job: every 7 days at 04:05

### Example Issuance Command

```bash
certbot certonly --dns-cloudflare \
  --dns-cloudflare-credentials /root/.secrets/certbot/cloudflare.ini \
  -d 'example.com' -d '*.example.com' \
  --agree-tos --non-interactive \
  --register-unsafely-without-email \
  --server https://acme-v02.api.letsencrypt.org/directory
```

---

## Certificate Locations

```
/etc/letsencrypt/live/<domain>/
├── fullchain.pem
├── privkey.pem
├── cert.pem
└── chain.pem
```

Example Nginx configuration:

```nginx
ssl_certificate     /etc/letsencrypt/live/example.com/fullchain.pem;
ssl_certificate_key /etc/letsencrypt/live/example.com/privkey.pem;
```

After a certificate is renewed, the script automatically runs `systemctl reload nginx`.

---

## Testing Renewal

```bash
# Dry run
sudo certbot renew --dry-run

# Or run the renewal script directly
sudo /root/example.com-ssl-renew.sh
```

---

## Notes

- No email is required (`--register-unsafely-without-email` is used)
- The script does not overwrite your existing crontab — it only adds or updates its own entry
- Running as `root` is recommended