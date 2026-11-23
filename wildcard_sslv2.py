#!/usr/bin/env python3

import os
import sys
import shutil
from pathlib import Path


def run(cmd: str, check: bool = True) -> int:
    """Run a shell command and return exit code."""
    print(f"→ {cmd}")
    result = os.system(cmd)
    if check and result != 0:
        print(f"[!] Command failed with exit code {result}", file=sys.stderr)
        sys.exit(1)
    return result


def ensure_root() -> None:
    if os.geteuid() != 0:
        print("[!] Этот скрипт нужно запускать от root (sudo).")
        sys.exit(1)


def install_dependencies(mode: str) -> None:
    print("\n[+] Обновление пакетов и установка зависимостей...")
    run("apt update -y", check=False)

    if mode == "cloudflare":
        run(
            "apt install -y software-properties-common certbot python3-certbot-dns-cloudflare",
            check=False,
        )
    else:
        run("apt install -y software-properties-common certbot", check=False)

    if shutil.which("certbot") is None:
        print("[!] certbot не найден. Установите его вручную.")
        sys.exit(1)


def get_mode() -> str:
    print("\nВыберите режим получения wildcard-сертификата:")
    print("  1) Автоматический через Cloudflare API (рекомендуется)")
    print("  2) Ручной DNS (--manual, TXT-записи добавляются вручную)")
    choice = input("Введите 1 или 2 [по умолчанию 1]: ").strip()

    if choice in ("", "1"):
        return "cloudflare"
    if choice == "2":
        return "manual"

    print("[!] Некорректный выбор режима.")
    sys.exit(1)


def get_domain() -> str:
    domain = input("Введите домен (без *. и без http://): ").strip().lower()
    if not domain or " " in domain or domain.startswith("*") or "/" in domain:
        print("[!] Некорректный домен.")
        sys.exit(1)
    return domain


def get_cloudflare_token() -> str:
    print("\nСоздайте API Token в Cloudflare:")
    print("  My Profile → API Tokens → Create Token")
    print("  Template: Edit zone DNS  (или Custom: Zone.DNS:Edit)")
    print("  Zone Resources: Include → Specific zone → ваш домен")
    token = input("\nВставьте Cloudflare API Token: ").strip()
    if not token:
        print("[!] Токен не может быть пустым.")
        sys.exit(1)
    return token


def create_cloudflare_credentials(token: str) -> Path:
    secret_dir = Path("/root/.secrets/certbot")
    secret_dir.mkdir(parents=True, exist_ok=True)
    ini_path = secret_dir / "cloudflare.ini"

    with open(ini_path, "w", encoding="utf-8") as f:
        f.write(f"dns_cloudflare_api_token = {token}\n")

    os.chmod(ini_path, 0o600)
    print(f"[+] Credentials сохранены: {ini_path} (права 600)")
    return ini_path


def issue_certificate_cloudflare(domain: str, ini_path: Path) -> None:
    print(f"\n[+] Получение wildcard-сертификата для *.{domain} и {domain} (Cloudflare API)...")
    cmd = (
        f"certbot certonly --dns-cloudflare "
        f"--dns-cloudflare-credentials '{ini_path}' "
        f"-d '{domain}' -d '*.{domain}' "
        f"--agree-tos --non-interactive "
        f"--register-unsafely-without-email "
        f"--server https://acme-v02.api.letsencrypt.org/directory "
        f"--dns-cloudflare-propagation-seconds 30"
    )
    run(cmd)


def issue_certificate_manual(domain: str) -> None:
    print(f"\n[+] Ручной режим (--manual) для *.{domain} и {domain}...")
    print("[!] Certbot выведет значения TXT-записей для _acme-challenge.")
    print("[!] Добавьте их в DNS и дождитесь обновления перед нажатием Enter в certbot.")
    cmd = (
        f"certbot certonly --manual --preferred-challenges dns "
        f"-d '{domain}' -d '*.{domain}' "
        f"--agree-tos "
        f"--register-unsafely-without-email "
        f"--server https://acme-v02.api.letsencrypt.org/directory"
    )
    run(cmd)


def setup_renewal_script(domain: str, mode: str, ini_path: Path | None = None) -> Path:
    script_path = Path(f"/root/{domain}-ssl-renew.sh")

    if mode == "cloudflare":
        if ini_path is None:
            print("[!] Внутренняя ошибка: не указан путь к cloudflare.ini", file=sys.stderr)
            sys.exit(1)

        content = f"""#!/bin/bash
# Auto-renew wildcard certificate for {domain} via Cloudflare DNS
/usr/bin/certbot renew \\
  --dns-cloudflare \\
  --dns-cloudflare-credentials '{ini_path}' \\
  --quiet \\
  --post-hook "systemctl reload nginx || service nginx reload || true"
"""
    else:
        content = f"""#!/bin/bash
# Renewal check for manual DNS certificate ({domain})
# Note: non-interactive --manual renewal requires a custom --manual-auth-hook.
/usr/bin/certbot renew \\
  --cert-name '{domain}' \\
  --quiet \\
  --post-hook "systemctl reload nginx || service nginx reload || true"
"""

    with open(script_path, "w", encoding="utf-8") as f:
        f.write(content)

    os.chmod(script_path, 0o755)
    print(f"[+] Скрипт обновления создан: {script_path}")

    cron_line = f"5 4 */7 * * '{script_path}'"
    run(f"(crontab -l 2>/dev/null | grep -Fv '{script_path}'; echo \"{cron_line}\") | crontab -")
    print(f"[+] Cron-задача добавлена: {cron_line}")

    return script_path


def main() -> None:
    ensure_root()

    print("=" * 60)
    print("  Wildcard SSL Certificate Setup (Let's Encrypt)")
    print("=" * 60)

    mode = get_mode()
    install_dependencies(mode)
    domain = get_domain()

    ini_path: Path | None = None
    if mode == "cloudflare":
        token = get_cloudflare_token()
        ini_path = create_cloudflare_credentials(token)
        issue_certificate_cloudflare(domain, ini_path)
    else:
        issue_certificate_manual(domain)

    setup_renewal_script(domain, mode, ini_path)

    print("\n" + "=" * 60)
    print("[✓] Готово!")
    print(f"    Режим:        {mode}")
    print(f"    Сертификаты: /etc/letsencrypt/live/{domain}/")
    print("    Файлы:       fullchain.pem + privkey.pem")
    if mode == "cloudflare":
        print("    Автообновление: каждые 7 дней в 04:05")
    else:
        print("    Внимание: для ручного DNS продление может потребовать ручного ввода TXT")
    print("=" * 60)


if __name__ == "__main__":
    main()