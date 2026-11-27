# Production deploy — library.xiuedu.uz

Stack: **gunicorn + nginx + PostgreSQL + WhiteNoise**, Django 5.2, Python 3.12+.

> **Docker KERAK EMAS.** Loyihadagi `docker-compose.yml` faqat dasturchining
> kompyuteridagi PostgreSQL uchun. Serverda tizimning o'z PostgreSQL'i ishlatiladi.

Ikkita skript bor:

| Skript | Qachon | Nima qiladi |
|---|---|---|
| `bin/server-setup.sh` | **bir marta**, yangi serverda | Paketlar, PostgreSQL, `.env`, venv, systemd, nginx, cron |
| `./deploy.sh` | **har safar** yangilaganda | Zaxira → git pull → pip → migrate → statik → restart → tekshiruv |

---

## 1. Birinchi o'rnatish (bir marta)

```bash
sudo apt-get update && sudo apt-get install -y git
sudo mkdir -p /srv && cd /srv
sudo git clone https://github.com/AsliddinWeb/library.xiuedu.uz.git library
sudo chown -R $USER:www-data /srv/library
cd /srv/library

sudo ./bin/server-setup.sh
```

Skript idempotent — qayta ishga tushirsa ham zarari yo'q. U:

1. `python3-venv`, `postgresql`, `nginx`, `git`, `curl` paketlarini o'rnatadi;
2. `library_db` bazasi va `library_user` foydalanuvchisini yaratadi
   (+ `pg_trgm`, `unaccent` kengaytmalari);
3. `.env` faylini yaratadi — **SECRET_KEY va DB paroli avtomatik generatsiya qilinadi**;
4. `venv` yaratib kutubxonalarni o'rnatadi, migratsiya va `collectstatic` bajaradi;
5. `/etc/systemd/system/library.service` (gunicorn, 127.0.0.1:8001) yozadi;
6. nginx konfiguratsiyasini yozadi (statik, media va **himoyalangan** `/protected-media/`);
7. `/etc/cron.d/library` — kunlik vazifalar (01:00 da).

Sozlamalarni o'zgartirish kerak bo'lsa, muhit o'zgaruvchilari bilan:

```bash
sudo LIBRARY_DOMAIN=kutubxona.xiuedu.uz LIBRARY_WORKERS=5 ./bin/server-setup.sh
```

### Skriptdan keyin qo'lda bajariladi

```bash
# 1. HEMIS kalitlari
nano /srv/library/.env            # CLIENT_ID, CLIENT_SECRET
sudo systemctl restart library

# 2. Administrator
cd /srv/library
sudo -u $USER env DJANGO_ENV=production venv/bin/python manage.py createsuperuser

# 3. HTTPS
sudo apt-get install -y certbot python3-certbot-nginx
sudo certbot --nginx -d library.xiuedu.uz -d www.library.xiuedu.uz
```

---

## 1-B. MAVJUD serverga o'rnatish (baza va kitoblar allaqachon bor)

Agar serverda loyiha allaqachon ishlab turgan bo'lsa — PostgreSQL o'rnatilgan,
bazada real kitoblar bor — **yangi baza yaratilmaydi**. Skript baza nomini
mavjud `.env` dan oladi va o'sha nomli baza topilsa unga tegmaydi:

```
==> 2. PostgreSQL
    ✓ Baza 'library_db' ALLAQACHON MAVJUD — tegilmaydi
      jadvallar: 42, kitoblar: 1 284
      Ma'lumot saqlanadi; deploy faqat migratsiyalarni qo'llaydi.
    ✓ Foydalanuvchi 'library_user' mavjud — paroli o'zgartirilmaydi
```

Skript boshlanishidan oldin nima qilishini ko'rsatib, tasdiq so'raydi.
Baza bosqichini umuman o'tkazib yuborish uchun: `sudo ./bin/server-setup.sh --skip-db`.

### Nima o'chmaydi

| Narsa | Holati |
|---|---|
| Mavjud baza va undagi ma'lumot | **Tegilmaydi.** Faqat `CREATE EXTENSION IF NOT EXISTS` bajariladi |
| `.env` | Mavjud bo'lsa **ustidan yozilmaydi** |
| systemd / nginx konfiguratsiyasi | Mavjud bo'lsa **tegilmaydi** |
| `media/` (kitob fayllari) | Tegilmaydi |
| DB foydalanuvchisi paroli | O'zgartirilmaydi |

### v2 dan v3 ga o'tish — tavsiya etilgan tartib

v3 migratsiyalari mavjud ma'lumot ustida ishlaydi: har foydalanuvchiga kutubxona
bileti ochiladi, har nusxaga shtrix-kod beriladi, mualliflar rol bilan
bog'lanadi. Buni **avval nusxada mashq qilish** kerak:

```bash
# 1. Serverdan bazaning nusxasini olish
ssh server "sudo -u postgres pg_dump library_db | gzip" > prod-nusxa.sql.gz

# 2. O'z kompyuteringizda sinab ko'rish
make db-up
gunzip -c prod-nusxa.sql.gz | docker compose exec -T db psql -U library_user -d library_db
make migrate                       # v3 migratsiyalari real ma'lumot ustida
make run                           # sahifalarni ko'zdan kechiring

# 3. Hammasi joyida bo'lsa — serverda
ssh server
cd /srv/library && ./deploy.sh     # zaxira avtomatik olinadi
```

### Deploy'dan keyin tekshirish

```bash
cd /srv/library
DJANGO_ENV=production venv/bin/python manage.py shell -c "
from book_app.models import Book, Item
from user_app.models import Patron
print('Kitob:', Book.objects.count())
print('Nusxa:', Item.objects.count(), '| shtrix-kodli:', Item.objects.exclude(barcode=None).count())
print('A\'zo:', Patron.objects.count())
"
```

Sonlar deploy'dan oldingi holat bilan mos kelishi kerak (a'zolar soni —
foydalanuvchilar soniga teng bo'ladi, bu yangi).

---

## 2. Har safargi deploy

```bash
cd /srv/library && ./deploy.sh
```

Bosqichlar (birortasi xato bersa — to'xtaydi va tiklash yo'lini ko'rsatadi):

1. **Zaxira** — `var/backups/YYYYmmdd-HHMMSS-<commit>.sql.gz` (oxirgi 10 tasi saqlanadi)
2. **git pull** — faqat fast-forward; yangi commitlar ro'yxati ko'rsatiladi
3. **pip install -r requirements.txt**
4. **migrate** — avval qo'llanadigan migratsiyalar ro'yxati chiqadi
5. **collectstatic**
6. **check --deploy**
7. **systemctl restart library** + xizmat ko'tarilganini tekshirish
8. **HTTP tekshiruvi** — sayt 200/301/302 qaytarishi kerak

Bayroqlar:

```bash
./deploy.sh --no-backup          # zaxirasiz (tez)
./deploy.sh --branch hotfix      # boshqa branchdan
./deploy.sh --no-pull            # serverdagi mavjud kod bilan qayta yig'ish
./deploy.sh --skip-health        # oxirgi HTTP tekshiruvisiz
```

### Health check

Oxirgi bosqich saytni **nginx orqali** tekshiradi (`http://127.0.0.1/`, `Host:` sarlavhasi
bilan) — shuning uchun gunicorn port orqali ham, **unix-socket** orqali ham ishlayversin,
farqi yo'q. Boshqa manzilni tekshirish kerak bo'lsa:

```bash
LIBRARY_HEALTH_URL=http://127.0.0.1:8001/ LIBRARY_HEALTH_HOST=library.xiuedu.uz ./deploy.sh
```

> **Tailwind CSS:** `static/css/app.css` git orqali keladi — serverda Node ham,
> Tailwind binar fayli ham kerak emas. Dizaynni o'zgartirgandan keyin
> **lokalda `make css` ishlatib, natijani commit qiling**, aks holda serverda
> eski CSS qoladi.

---

## 2-B. Birinchi deploy'da uchraydigan xatolar

### `SECRET_KEY muhit o'zgaruvchisi production'da o'rnatilishi shart`

v2 da `SECRET_KEY` ning standart qiymati bor edi; v3 da production'da u **majburiy**
(standart kalit bilan ishlash xavfsiz emas). `.env` ga qo'shing:

```bash
cd ~/projects/library.xiuedu.uz
echo "SECRET_KEY=$(venv/bin/python -c 'import secrets; print(secrets.token_urlsafe(64))')" >> .env
```

Yangi kalit bilan mavjud sessiyalar bekor bo'ladi — foydalanuvchilar bir marta
qayta kirishadi. Eski kalitni git'dagi fayldan qayta ishlatmang: u ochiq
repozitoriyda turgan, ya'ni sir emas.

`./deploy.sh` endi buni **oldindan** tekshiradi: zaxira va `pip install` dan
oldin to'xtaydi va generatsiya buyrug'ini ko'rsatadi.

### `FATAL: password authentication failed` yoki `role ... does not exist`

`.env` dagi `DB_PASSWORD` yo'q yoki noto'g'ri. Parolni yangilash:

```bash
sudo -u postgres psql -c "ALTER ROLE library_user PASSWORD 'yangi-parol';"
echo "DB_PASSWORD=yangi-parol" >> .env
```

### Statik fayllar 404 yoki eski CSS

nginx `/static/` ni `staticfiles/` ga ko'rsatishi kerak (namuna:
`bin/nginx-site.conf.example`). Uy papkasi huquqi ham tekshiring:

```bash
chmod o+x /home/ubuntu /home/ubuntu/projects
```

---

## 3. Xatolik bo'lsa

```bash
systemctl status library --no-pager -n 30     # xizmat holati
journalctl -u library -n 100 --no-pager       # loglar
journalctl -u library -f                      # jonli loglar
nginx -t && systemctl reload nginx            # nginx konfiguratsiyasi
```

**Eski versiyaga qaytish:**

```bash
cd /srv/library
git log --oneline -5
git reset --hard <eski-commit>
./deploy.sh --no-pull
```

**Bazani zaxiradan tiklash:**

```bash
gunzip -c var/backups/20261127-120000-abc1234.sql.gz | \
    PGPASSWORD=<parol> psql -h 127.0.0.1 -U library_user -d library_db
```

---

## 4. Davriy vazifalar

`/etc/cron.d/library` orqali har kuni 01:00 da:

```cron
0 1 * * * <user> cd /srv/library && DJANGO_ENV=production venv/bin/python manage.py run_jobs --schedule daily >> /srv/library/var/jobs.log 2>&1
```

Jarima hisoblash, muddat-yaqin ogohlantirish, navbat muddati. Har ishga tushish
`audit.JobRun` jadvaliga yoziladi — admin panelda ko'rinadi
(**Audit va vazifalar → Vazifalar jurnali**), natijalar `var/jobs.log` da.

Qo'lda ishga tushirish:

```bash
cd /srv/library
DJANGO_ENV=production venv/bin/python manage.py run_jobs --list
DJANGO_ENV=production venv/bin/python manage.py run_jobs fines_accrual
```

---

## 5. Raqamli kitoblar himoyasi

`reading` app stream view production'da `X-Accel-Redirect: /protected-media/<fayl>`
qaytaradi. nginx'da `/protected-media/` **`internal`** bo'lgani uchun uni faqat
Django ruxsat bergandagina beradi — to'g'ridan-to'g'ri URL ishlamaydi.

Sozlamalar (`core/settings/production.py`): `USE_X_ACCEL_REDIRECT=True`,
`X_ACCEL_LOCATION=/protected-media`.

---

## 6. Qo'lda o'rnatish (skriptsiz)

`bin/server-setup.sh` ichidagi qadamlarni qo'lda bajarish kerak bo'lsa, skriptni
o'qing — har bosqich izohlangan. Asosiylari:

```bash
sudo -u postgres createuser library_user --pwprompt
sudo -u postgres createdb -O library_user -E UTF8 library_db
python3 -m venv venv && venv/bin/pip install -r requirements.txt
DJANGO_ENV=production venv/bin/python manage.py migrate
DJANGO_ENV=production venv/bin/python manage.py collectstatic --noinput
```

---

## Checklist

- [ ] `.env` to'liq, `SECRET_KEY` va HEMIS kalitlari o'rnatilgan
- [ ] `DJANGO_ENV=production`
- [ ] `check --deploy` 0 xato
- [ ] `/protected-media/` nginx'da `internal`
- [ ] HTTPS (certbot) + sertifikat avto-yangilanishi
- [ ] cron `run_jobs --schedule daily` ishlayapti
- [ ] `var/backups/` to'ldirilmoqda va boshqa diskka ham nusxalanadi
- [ ] `media/` papkasi zaxiraga kiritilgan (kitob fayllari!)
