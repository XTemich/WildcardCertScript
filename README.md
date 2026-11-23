# Wildcard SSL Certificate Manager

**Русский** | [English](README.en.md)

Скрипт для установки и управления SSL/TLS-сертификатами (`*.example.com` + `example.com`) в трёх режимах: ручная установка, Let's Encrypt wildcard при выключенном проксировании (DNS-only) и Let's Encrypt wildcard при включённом проксировании Cloudflare с проверкой `Full (strict)`.

---

## Режимы работы

1. **Ручной (`1`)** — копирует готовые файлы сертификата и ключа в `/etc/ssl/custom/<domain>/`, выставляет безопасные права (`644` / `600`) и при наличии перезагружает Nginx.
2. **Выключенное облачко (DNS-only) + Let's Encrypt Wildcard (`2`)** — выпускает сертификат для `*.example.com` и `example.com` через `certbot --dns-cloudflare`, создаёт `/root/<domain>-ssl-renew.sh` и настраивает cron-задачу каждые 7 дней в `04:05`.
3. **Включённое облачко (Проксирование Cloudflare) + Let's Encrypt Wildcard + `Full (strict)` (`3`)** — делает всё то же, что и режим 2, плюс проверяет и при необходимости переключает режим шифрования зоны в Cloudflare на `Full (strict)` (`strict`) через API.

---

## Требования

- Python 3.8+ и Ubuntu / Debian (или другой дистрибутив с `apt` для режимов 2 и 3)
- Root-доступ (`sudo`)
- Для режимов 2 и 3: домен на Cloudflare и Cloudflare API Token
- Nginx (опционально) — при наличии проверяется (`nginx -t`) и перезагружается (`systemctl reload nginx`)

---

## Быстрый старт

Интерактивный запуск:

```bash
sudo python3 wildcard_ssl.py
```

Запуск с параметрами командной строки:

```bash
sudo python3 wildcard_ssl.py --mode 3 --domain example.com --token ВАШ_ТОКЕН
```

---

## Как создать Cloudflare API Token

1. Зайдите в Cloudflare → **My Profile** → **API Tokens** → **Create Token**
2. Для **режима 2 (DNS-only)**: используйте шаблон **Edit zone DNS** (`Zone → DNS → Edit`)
3. Для **режима 3 (Проксирование + `Full (strict)`)**: добавьте `Zone → DNS → Edit` и `Zone → SSL and Certificates → Edit` (при необходимости также `Zone → Zone → Read` для поиска зоны)
4. В разделе **Zone Resources** выберите **Include** → **Specific zone** → ваш домен

---

## Что делает скрипт

- **Режим 1:** копирует `fullchain.pem` и `privkey.pem` в `/etc/ssl/custom/<domain>/` и перезагружает Nginx
- **Режимы 2 и 3:**
  - Устанавливает `certbot` и `python3-certbot-dns-cloudflare`
  - Сохраняет токен в `/root/.secrets/certbot/cloudflare.ini` (права `600`)
  - Выпускает wildcard-сертификат на `<domain>` и `*.<domain>`
  - Создаёт `/root/<domain>-ssl-renew.sh` и добавляет задачу в `crontab` (`5 4 */7 * *`)
  - В **режиме 3** проверяет настройку SSL/TLS зоны и переключает её на `strict` (`Full (strict)`)

---

## Где лежат сертификаты и пример для Nginx

- Let's Encrypt (режимы 2 и 3): `/etc/letsencrypt/live/<domain>/fullchain.pem` и `privkey.pem`
- Ручной режим (режим 1): `/etc/ssl/custom/<domain>/fullchain.pem` и `privkey.pem`

```nginx
ssl_certificate     /etc/letsencrypt/live/example.com/fullchain.pem;
ssl_certificate_key /etc/letsencrypt/live/example.com/privkey.pem;
```

---

## Проверка обновления

```bash
sudo certbot renew --dry-run
sudo /root/example.com-ssl-renew.sh
```

---

## Замечания

- Email не требуется (используется `--register-unsafely-without-email`)
- Существующие строки в `crontab` не затираются — обновляется только задача для выбранного домена
- Требуется запуск от `root`