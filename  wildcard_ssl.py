#!/usr/bin/env python3

import os
import sys
import shutil
from pathlib import Path
from typing import Optional


def run(cmd: str, check: bool = True) -> int:
    """Run a shell command and return exit code."""
    print(f"→ {cmd}")
    result = os.system(cmd)
    if check and result != 0:
        print(f"[!] Command failed with exit code {result}", file=sys.stderr)
        sys.exit(1)
    return result


def ensure_root():
    if os.geteuid() != 0:
        print("[!] Этот скрипт нужно запускать от root (sudo).")
        sys.exit(1)


def install_dependencies():
    print("\n[+] Обновление пакетов и установка зависимостей...")
    run("apt update -y", check=False)
    run("apt install -y software-properties-common certbot python3-certbot-dns-cloudflare", check=False)

    if shutil.which("certbot") is None:
        print("[!] certbot не найден. Установите его вручную.")
        sys.exit(1)


def get_domain() -> str:
    domain = input("Введите домен (без *. и без http://): ").strip().lower()
    if not domain or " " in domain or domain.startswith("*"):
        print("[!] Некорректный домен.")
        sys.exit(1)
    return domain


def create_cloudflare_credentials(token: str) -> Path:
    secret_dir = Path("/root/.secrets/certbot")
    secret_dir.mkdir(parents=True, exist_ok=True)
    ini_path = secret_dir / "cloudflare.ini"

    with open(ini_path, "w") as f:
        f.write(f"dns_cloudflare_api_token = {token}\n")

    os.chmod(ini_path, 0o600)
    print(f"[+] Credentials сохранены: {ini_path} (права 600)")
    return ini_path


def issue_certificate(domain: str, ini_path: Path):
    print(f"\n[+] Получение wildcard-сертификата для *.{domain} и {domain}...")
    cmd = (
        f"certbot certonly --dns-cloudflare "
        f"--dns-cloudflare-credentials {ini_path} "
        f"-d '{domain}' -d '*.{domain}' "
        f"--agree-tos --non-interactive "
        f"--register-unsafely-without-email "
        f"--server https://acme-v02.api.letsencrypt.org/directory "
        f"--dns-cloudflare-propagation-seconds 30"
    )
    run(cmd)


def setup_renewal_script(domain: str, ini_path: Path):
    script_path = Path(f"/root/{domain}-ssl-renew.sh")

    content = f"""#!/bin/bash
# Auto-renew wildcard certificate for {domain}
/usr/bin/certbot renew \\
  --dns-cloudflare \\
  --dns-cloudflare-credentials {ini_path} \\
  --quiet \\
  --post-hook "systemctl reload nginx || service nginx reload || true"
"""

    with open(script_path, "w") as f:
        f.write(content)

    os.chmod(script_path, 0o755)
    print(f"[+] Скрипт обновления создан: {script_path}")

    # Add to crontab (once every 7 days at 04:05), without overwriting existing jobs
    cron_line = f"5 4 */7 * * {script_path}"
    run(f"(crontab -l 2>/dev/null | grep -v '{script_path}'; echo '{cron_line}') | crontab -")
    print(f"[+] Cron-задача добавлена: {cron_line}")

    return script_path


def main():
    ensure_root()

    print("=" * 60)
    print("  Wildcard SSL Certificate Setup (Let's Encrypt + Cloudflare)")
    print("=" * 60)

    install_dependencies()

    domain = get_domain()

    print("\nСоздайте API Token в Cloudflare:")
    print("  My Profile → API Tokens → Create Token")
    print("  Template: Edit zone DNS  (или Custom: Zone.DNS:Edit)")
    print("  Zone Resources: Include → Specific zone → ваш домен")
    token = input("\nВставьте Cloudflare API Token: ").strip()
    if not token:
        print("[!] Токен не может быть пустым.")
        sys.exit(1)

    ini_path = create_cloudflare_credentials(token)
    issue_certificate(domain, ini_path)
    setup_renewal_script(domain, ini_path)

    print("\n" + "=" * 60)
    print(f"[✓] Готово!")
    print(f"    Сертификаты: /etc/letsencrypt/live/{domain}/")
    print(f"    fullchain.pem  +  privkey.pem")
    print(f"    Автообновление: каждые 7 дней в 04:05")
    print("=" * 60)


if __name__ == "__main__":
    main()
