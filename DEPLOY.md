# Production deploy — library.xiuedu.uz

Stack: **gunicorn + nginx + PostgreSQL + WhiteNoise**, Django 5.2, Python 3.12+.

## 1. Tayyorgarlik

```bash
git clone <repo> /srv/library && cd /srv/library
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

`.env` (`.env.sample` asosida) — production:

```env
DJANGO_ENV=production
SECRET_KEY=<uzun-tasodifiy>            # MAJBURIY
ALLOWED_HOSTS=library.xiuedu.uz,www.library.xiuedu.uz
DB_NAME=library_db
DB_USER=library_user
DB_PASSWORD=...
DB_HOST=127.0.0.1
DB_PORT=5432
# HEMIS oAuth (CLIENT_ID/SECRET/REDIRECT_URI + URL'lar)
```

## 2. DB, statik, tekshiruv

```bash
python manage.py migrate                 # default rollar avtomatik seed
python manage.py collectstatic --noinput # -> staticfiles/ (WhiteNoise)
./bin/css-build.sh                       # Tailwind app.css (yoki CI'da)
python manage.py check --deploy          # 0 ogohlantirish bo'lishi kerak
python manage.py createsuperuser
```

## 3. gunicorn (systemd)

`/etc/systemd/system/library.service`:

```ini
[Unit]
Description=XIU Library (gunicorn)
After=network.target

[Service]
User=www-data
WorkingDirectory=/srv/library
EnvironmentFile=/srv/library/.env
ExecStart=/srv/library/venv/bin/gunicorn core.wsgi:application \
          --bind 127.0.0.1:8001 --workers 3 --timeout 60
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
systemctl enable --now library
```

## 4. nginx

```nginx
server {
    listen 80;
    server_name library.xiuedu.uz www.library.xiuedu.uz;

    client_max_body_size 200M;   # katta ebook/audio yuklash uchun

    location /static/ {
        alias /srv/library/staticfiles/;
        expires 30d;
    }

    # Ommaviy media (muqovalar, profil rasmlari)
    location /media/ {
        alias /srv/library/media/;
    }

    # Himoyalangan raqamli kitoblar — FAQAT Django X-Accel orqali (internal)
    location /protected-media/ {
        internal;
        alias /srv/library/media/;
    }

    location / {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

> **Raqamli kitob himoyasi:** `reading` app stream view production'da `X-Accel-Redirect:
> /protected-media/<fayl>` qaytaradi. `/protected-media/` `internal` bo'lgani uchun uni
> faqat Django ruxsat bergandagina nginx beradi — to'g'ridan-to'g'ri URL ishlamaydi.
> (Sozlamalar: `USE_X_ACCEL_REDIRECT=True`, `X_ACCEL_LOCATION=/protected-media`.)

HTTPS uchun **certbot** (Let's Encrypt) — `SECURE_SSL_REDIRECT` allaqachon yoqilgan.

## 5. Cron (davriy vazifa)

```cron
0 1 * * *  /srv/library/venv/bin/python /srv/library/manage.py circulation_tick
```

Jarima hisoblash, muddat-yaqin ogohlantirish, navbat muddati.

## 6. Yangilash (deploy)

```bash
git pull && source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
./bin/css-build.sh && python manage.py collectstatic --noinput
systemctl restart library
```

## Checklist
- [ ] `.env` to'liq, `SECRET_KEY` o'rnatilgan
- [ ] `check --deploy` 0 ogohlantirish
- [ ] `/protected-media/` nginx'da `internal`
- [ ] HTTPS (certbot) + sertifikat avto-yangilanishi
- [ ] cron `circulation_tick` o'rnatilgan
- [ ] DB backup rejasi
