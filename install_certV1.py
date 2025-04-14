import os

def willdcard():
    # обновление и установка софта
    os.system("sudo apt update && sudo apt upgrade -y")
    os.system("sudo apt install software-properties-common -y")
    # проверка на наличии установленного certbota
    checkcertbot = os.system("which certbot")
    if not os.path.exists(checkcertbot):
        os.system("sudo apt install certbot -y")
    enter = input("Ведите домен:")
    os.system("sudo certbot -d *."+enter+" -d "+enter+" --manual --preferred-challenges dns certonly --server https://acme-v02.api.letsencrypt.org/directory")
    # создаем скрипт для обновления сертов
    os.system("sudo touch /root/"+enter+"-ssl-new.sh")
    # открываем созданный скрипт
    fileop = open("/root/"+enter+"-ssl-new.sh", "w+")
    # записываем конфигурацию скрипта
    autofilecert = "#!/bin/bash\n/usr/bin/certbot renew --post-hook \"service nginx reload\""
    fileop.write(autofilecert)
    fileop.close()
    # даем права на исполнение скрипта
    os.system("sudo chmod +x /root/"+enter+"-ssl-new.sh")
    # вносим изменения в crontab
    os.system("echo -e '05 04 */7 * * /root/"+enter+"-ssl-new.sh' | sudo crontab -")

if __name__ == "__main__":
    willdcard()