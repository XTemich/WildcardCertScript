#!/usr/bin/python3
import os
import shutil

def wildcard():
    # Обновление и установка зависимостей
    os.system("sudo apt update && sudo apt upgrade -y")
    os.system("sudo apt install software-properties-common -y")

    # Установка certbot, если он не установлен
    if shutil.which("certbot") is None:
        os.system("sudo apt install certbot -y")

    domain = input("Введите домен (без *): ").strip()

    # Запуск ручной валидации с DNS
    os.system(
        f"sudo certbot -d '*.{domain}' -d {domain} "
        f"--manual --preferred-challenges dns certonly "
        f"--server https://acme-v02.api.letsencrypt.org/directory"
    )

    # Автогенерация скрипта и cron
    auto = input("Создать скрипт для автообновления сертификата? (y/n): ").lower()
    if auto == "y":
        script_path = f"/root/{domain}-ssl-renew.sh"
        with open(script_path, "w") as f:
            f.write("#!/bin/bash\n/usr/bin/certbot renew --post-hook \"systemctl reload nginx\"")
        os.system(f"sudo chmod +x {script_path}")
        os.system(f"(crontab -l 2>/dev/null; echo '5 4 */7 * * {script_path}') | crontab -")
        print(f"[+] Скрипт создан: {script_path}")
        print("[+] Cron задача добавлена.")

if __name__ == "__main__":
    wildcard()
