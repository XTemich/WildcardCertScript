#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import List, Optional

SECRETS_DIR = Path("/root/.secrets/certbot")
CLOUDFLARE_INI = SECRETS_DIR / "cloudflare.ini"
RENEW_SCRIPTS_DIR = Path("/root")
MANUAL_CERTS_BASE = Path("/etc/ssl/custom")


def check_root() -> None:
    if os.geteuid() != 0:
        print("❌ Ошибка: скрипт необходимо запускать от имени root (sudo python3 wildcard_ssl.py).")
        sys.exit(1)


def run_cmd(cmd: List[str], check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, text=True, capture_output=True, check=check)


def is_valid_domain(domain: str) -> bool:
    pattern = r"^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$"
    return bool(re.match(pattern, domain))


def ensure_dependencies() -> None:
    print("📦 Проверка и установка зависимостей (certbot, python3-certbot-dns-cloudflare)...")
    try:
        run_cmd(["apt-get", "update", "-qq"])
        run_cmd(["apt-get", "install", "-y", "-qq", "certbot", "python3-certbot-dns-cloudflare"])
    except subprocess.CalledProcessError as e:
        print(f"❌ Не удалось установить пакеты через apt:\n{e.stderr}")
        sys.exit(1)


def reload_nginx_if_present() -> None:
    if shutil.which("nginx") is None:
        print("ℹ️ Nginx не найден в системе, перезагрузка пропущена.")
        return
    test = run_cmd(["nginx", "-t"], check=False)
    if test.returncode != 0:
        print(f"⚠️ Внимание: 'nginx -t' завершился с ошибкой, reload не выполнен:\n{test.stderr}")
        return
    reload_res = run_cmd(["systemctl", "reload", "nginx"], check=False)
    if reload_res.returncode == 0:
        print("🔄 Nginx успешно перезагружен.")
    else:
        print(f"⚠️ Не удалось перезагрузить Nginx:\n{reload_res.stderr}")


def save_cloudflare_token(token: str) -> None:
    SECRETS_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(SECRETS_DIR, 0o700)
    CLOUDFLARE_INI.write_text(f"dns_cloudflare_api_token = {token.strip()}\n", encoding="utf-8")
    os.chmod(CLOUDFLARE_INI, 0o600)
    print(f"🔐 Cloudflare API Token сохранён в {CLOUDFLARE_INI} (права 600).")


def cf_api_request(method: str, endpoint: str, token: str, payload: Optional[dict] = None) -> dict:
    url = f"https://api.cloudflare.com/client/v4{endpoint}"
    headers = {
        "Authorization": f"Bearer {token.strip()}",
        "Content-Type": "application/json",
    }
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"Cloudflare API HTTP {e.code}: {body}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Ошибка сети при обращении к Cloudflare API: {e.reason}") from e


def ensure_cf_ssl_strict(domain: str, token: str) -> None:
    """
    Находит Zone ID для домена, проверяет текущий SSL-режим в Cloudflare
    и при необходимости переключает его на 'strict' (Full (strict)).
    """
    print(f"🔍 Поиск зоны Cloudflare для {domain} и проверка режима SSL/TLS...")
    parts = domain.split(".")
    zone_id: Optional[str] = None
    zone_name: Optional[str] = None

    for i in range(len(parts) - 1):
        candidate = ".".join(parts[i:])
        res = cf_api_request("GET", f"/zones?name={candidate}", token)
        if res.get("success") and res.get("result"):
            zone_id = res["result"][0]["id"]
            zone_name = res["result"][0]["name"]
            break

    if not zone_id:
        print("⚠️ Не удалось найти зону в Cloudflare. Проверьте права токена (Zone:Read) и домен.")
        return

    ssl_res = cf_api_request("GET", f"/zones/{zone_id}/settings/ssl", token)
    current_mode = ssl_res.get("result", {}).get("value", "unknown")
    print(f"ℹ️ Зона: {zone_name} ({zone_id}) | Текущий SSL-режим: {current_mode}")

    if current_mode == "strict":
        print("✅ В Cloudflare уже установлен режим Full (strict).")
        return

    print("⚙️ Переключаем SSL-режим Cloudflare на 'strict' (Full (strict))...")
    try:
        patch_res = cf_api_request("PATCH", f"/zones/{zone_id}/settings/ssl", token, {"value": "strict"})
        if patch_res.get("success"):
            print("✅ SSL-режим в Cloudflare успешно изменён на Full (strict)!")
        else:
            print(f"⚠️ Не удалось изменить SSL-режим: {patch_res.get('errors')}")
    except RuntimeError as err:
        print(f"⚠️ Ошибка при изменении SSL-режима (убедитесь, что у токена есть право Zone.SSL and Certificates:Edit):\n{err}")


def setup_renewal_and_cron(domain: str) -> None:
    renew_script = RENEW_SCRIPTS_DIR / f"{domain}-ssl-renew.sh"
    script_content = f"""#!/usr/bin/env bash
set -euo pipefail

certbot renew --cert-name "{domain}" --non-interactive --quiet

if command -v nginx >/dev/null 2>&1 && nginx -t >/dev/null 2>&1; then
    systemctl reload nginx
fi
"""
    renew_script.write_text(script_content, encoding="utf-8")
    os.chmod(renew_script, 0o700)
    print(f"📝 Скрипт автообновления создан: {renew_script}")

    cron_line = f"5 4 */7 * * {renew_script} >/var/log/{domain}-ssl-renew.log 2>&1"
    current_cron_res = run_cmd(["crontab", "-l"], check=False)
    existing_lines = current_cron_res.stdout.splitlines() if current_cron_res.returncode == 0 else []

    filtered_lines = [line for line in existing_lines if str(renew_script) not in line]
    filtered_lines.append(cron_line)

    new_cron = "\n".join(filtered_lines).strip() + "\n"
    proc = subprocess.run(["crontab", "-"], input=new_cron, text=True, capture_output=True)
    if proc.returncode == 0:
        print("⏰ Cron-задача настроена (каждые 7 дней в 04:05).")
    else:
        print(f"⚠️ Ошибка при обновлении crontab:\n{proc.stderr}")


def issue_letsencrypt_wildcard(domain: str) -> None:
    print(f"🚀 Запрос wildcard-сертификата Let's Encrypt для {domain} и *.{domain}...")
    cmd = [
        "certbot", "certonly",
        "--dns-cloudflare",
        "--dns-cloudflare-credentials", str(CLOUDFLARE_INI),
        "--dns-cloudflare-propagation-seconds", "20",
        "-d", domain,
        "-d", f"*.{domain}",
        "--agree-tos",
        "--non-interactive",
        "--register-unsafely-without-email",
        "--keep-until-expiring",
        "--server", "https://acme-v02.api.letsencrypt.org/directory",
    ]
    res = run_cmd(cmd, check=False)
    if res.returncode != 0:
        print(f"❌ Ошибка при выпуске сертификата Certbot:\n{res.stderr}\n{res.stdout}")
        sys.exit(1)

    cert_dir = Path(f"/etc/letsencrypt/live/{domain}")
    print("\n✅ Сертификат успешно получен!")
    print(f"   Fullchain : {cert_dir / 'fullchain.pem'}")
    print(f"   Privkey   : {cert_dir / 'privkey.pem'}")


def mode_manual(domain: str) -> None:
    print("\n--- Режим 1: Ручная установка сертификата ---")
    fullchain_src = input("Укажите путь к файлу сертификата (fullchain.pem / cert.crt): ").strip()
    privkey_src = input("Укажите путь к приватному ключу (privkey.pem / private.key): ").strip()

    fc_path = Path(fullchain_src)
    pk_path = Path(privkey_src)

    if not fc_path.is_file() or not pk_path.is_file():
        print("❌ Один или оба указанных файла не найдены.")
        sys.exit(1)

    target_dir = MANUAL_CERTS_BASE / domain
    target_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(target_dir, 0o755)

    target_fc = target_dir / "fullchain.pem"
    target_pk = target_dir / "privkey.pem"

    shutil.copy2(fc_path, target_fc)
    shutil.copy2(pk_path, target_pk)
    os.chmod(target_fc, 0o644)
    os.chmod(target_pk, 0o600)

    print(f"\n✅ Сертификаты установлены в {target_dir}:")
    print(f"   ssl_certificate     {target_fc};")
    print(f"   ssl_certificate_key {target_pk};")
    reload_nginx_if_present()


def mode_letsencrypt(domain: str, token: str, proxied_strict: bool) -> None:
    mode_name = (
        "Режим 3: Проксирование Cloudflare (оранжевое облачко) + Let's Encrypt + Full (strict)"
        if proxied_strict
        else "Режим 2: DNS-only (серое облачко) + Let's Encrypt Wildcard"
    )
    print(f"\n--- {mode_name} ---")
    ensure_dependencies()
    save_cloudflare_token(token)
    issue_letsencrypt_wildcard(domain)
    setup_renewal_and_cron(domain)

    if proxied_strict:
        ensure_cf_ssl_strict(domain, token)

    reload_nginx_if_present()


def main() -> None:
    check_root()

    parser = argparse.ArgumentParser(description="Wildcard SSL Certificate Manager")
    parser.add_argument("--mode", choices=["1", "2", "3"], help="Режим работы: 1 (ручной), 2 (DNS-only LE), 3 (Cloudflare Proxy LE + Full strict)")
    parser.add_argument("--domain", help="Доменное имя (например, example.com)")
    parser.add_argument("--token", help="Cloudflare API Token (для режимов 2 и 3)")
    args = parser.parse_args()

    mode = args.mode
    if not mode:
        print("Выберите режим установки SSL-сертификата:")
        print("  1) Ручной режим (установка готовых файлов сертификата и ключа)")
        print("  2) Выключенное облачко (DNS-only) + Let's Encrypt Wildcard")
        print("  3) Включённое облачко (Проксирование Cloudflare) + Let's Encrypt + проверка Full (strict)")
        mode = input("\nВведите номер режима [1/2/3]: ").strip()

    if mode not in {"1", "2", "3"}:
        print("❌ Некорректный выбор режима. Допустимые значения: 1, 2 или 3.")
        sys.exit(1)

    domain = args.domain or input("Введите домен (например, example.com): ").strip().lower()
    if domain.startswith("*."):
        domain = domain[2:]

    if not is_valid_domain(domain):
        print(f"❌ Некорректное имя домена: {domain}")
        sys.exit(1)

    if mode == "1":
        mode_manual(domain)
    else:
        token = args.token or input("Введите Cloudflare API Token: ").strip()
        if not token:
            print("❌ Cloudflare API Token не может быть пустым.")
            sys.exit(1)
        mode_letsencrypt(domain, token, proxied_strict=(mode == "3"))


if __name__ == "__main__":
    main()