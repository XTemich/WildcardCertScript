#!/usr/bin/python3
import os
import shutil

def wildcard():
    # Обновление и установка зависимостей
    os.system("sudo apt update && sudo apt upgrade -y")
    os.system("sudo apt install software-properties-common -y")
    os.system("sudo apt install certbot python3-certbot-dns-cloudflare -y")

    domain = input("Введите домен (без *): ").strip()
    token = input("Вставьте Cloudflare API Token: ").strip()

    # Создание .ini файла для Cloudflare API
    secret_path = "/root/.secrets/certbot"
    ini_path = f"{secret_path}/cloudflare.ini"

    os.makedirs(secret_path, exist_ok=True)
    with open(ini_path, "w") as f:
        f.write(f"dns_cloudflare_api_token = {token}\n")
    os.system(f"sudo chmod 600 {ini_path}")

    # Получение wildcard-сертификата через Cloudflare DNS API
    cert_cmd = (
        f"sudo certbot certonly --dns-cloudflare "
        f"--dns-cloudflare-credentials {ini_path} "
        f"-d '*.{domain}' -d {domain} "
        f"--agree-tos --non-interactive --email admin@{domain} "
        f"--server https://acme-v02.api.letsencrypt.org/directory"
    )
    os.system(cert_cmd)

    # Создание скрипта для обновления сертификатов
    script_path = f"/root/{domain}-ssl-renew.sh"
    with open(script_path, "w") as f:
        f.write(f"""#!/bin/bash
certbot renew --dns-cloudflare \\
  --dns-cloudflare-credentials {ini_path} \\
  --quiet \\
  --post-hook "systemctl reload nginx"
""")
    os.system(f"sudo chmod +x {script_path}")

    # Добавление cron-задачи
    os.system(f"(crontab -l 2>/dev/null; echo '5 4 */7 * * {script_path}') | crontab -")

    print(f"[+] Сертификат для *.{domain} и {domain} получен.")
    print(f"[+] Скрипт автообновления создан: {script_path}")
    print("[+] Cron задача добавлена на каждые 7 дней в 04:05.")

if __name__ == "__main__":
    wildcard()
