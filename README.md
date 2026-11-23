# Wildcard SSL Certificate Manager

Скрипт для получения **wildcard**-сертификатов Let's Encrypt (`*.example.com` + `example.com`) через Cloudflare DNS API с автоматическим обновлением.

---

## Требования

- Ubuntu / Debian (или любой дистрибутив с `apt`)
- Root-доступ (`sudo`)
- Домен, DNS которого находится на Cloudflare
- Nginx (или другой веб-сервер) — для post-hook перезагрузки

---

## Быстрый старт

```bash
sudo python3 wildcard_ssl.py
```

Скрипт задаст вопросы интерактивно:
1. Домен
2. Cloudflare API Token

---

## Как создать Cloudflare API Token

1. Зайдите в Cloudflare → **My Profile** → **API Tokens** → **Create Token**
2. Используйте шаблон **Edit zone DNS**  
   или Custom: Permission `Zone.DNS:Edit`
3. Zone Resources → Include → Specific zone → ваш домен
4. Создайте токен и вставьте его в скрипт

---

## Что делает скрипт

- Устанавливает `certbot` + `python3-certbot-dns-cloudflare`
- Сохраняет токен в `/root/.secrets/certbot/cloudflare.ini` (права `600`)
- Выдаёт сертификат для `*.domain` и `domain`
- Создаёт скрипт обновления `/root/<domain>-ssl-renew.sh`
- Добавляет cron-задачу: каждые 7 дней в 04:05

### Пример команды выдачи

```bash
certbot certonly --dns-cloudflare \
  --dns-cloudflare-credentials /root/.secrets/certbot/cloudflare.ini \
  -d 'example.com' -d '*.example.com' \
  --agree-tos --non-interactive \
  --register-unsafely-without-email \
  --server https://acme-v02.api.letsencrypt.org/directory
```

---

## Где лежат сертификаты

```
/etc/letsencrypt/live/<domain>/
├── fullchain.pem
├── privkey.pem
├── cert.pem
└── chain.pem
```

Пример конфигурации Nginx:

```nginx
ssl_certificate     /etc/letsencrypt/live/example.com/fullchain.pem;
ssl_certificate_key /etc/letsencrypt/live/example.com/privkey.pem;
```

После обновления сертификата скрипт автоматически делает `systemctl reload nginx`.

---

## Проверка обновления

```bash
# Тестовый прогон
sudo certbot renew --dry-run

# Или напрямую скрипт
sudo /root/example.com-ssl-renew.sh
```

---

## Замечания

- Email не требуется (используется `--register-unsafely-without-email`)
- Скрипт не затирает существующий crontab — только добавляет/обновляет свою строку
- Рекомендуется запускать от root

---

## Лицензия

MIT. Используйте на свой страх и риск.
