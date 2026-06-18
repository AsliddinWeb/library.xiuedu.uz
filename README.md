# XIU Elektron Kutubxona — library.xiuedu.uz

Xalqaro Innovatsion Universitet (XIU) uchun **elektron kutubxona platformasi**.
Talabalar va xodimlar HEMIS oAuth2 orqali kiradi, kitoblarni onlayn o'qiydi/tinglaydi,
jismoniy nusxalarni ijaraga oladi, sharh/baho qoldiradi va sevimlilarini yuritadi.

## Imkoniyatlar

- 🔐 **HEMIS oAuth2** autentifikatsiya (talaba va xodim)
- 📚 **Katalog** — qidiruv, kategoriya filtri (HTMX, sahifa qayta yuklanmasdan)
- 📖 **Onlayn o'qish** (PDF.js reader) va **tinglash** (audio player) — himoyalangan, yuklab bo'lmaydi
- 🔄 **Gibrid ijara** — so'rov → kutubxonachi tasdig'i → qaytarish → jarima; band kitobga **navbat**
- ⭐ **Sharh/reyting** (moderatsiya bilan) + **sevimlilar** + "Mening kutubxonam"
- 🔔 **In-app bildirishnomalar** (so'rov, muddat, navbat, jarima, sharh)
- 📊 **Analitika** dashboard (kutubxonachi uchun)
- ⚙️ **Unfold** asosidagi admin panel (brend ranglar, counterlar, status badge'lar)

## Texnologiyalar

Django 5.2 (LTS) · PostgreSQL (prod) / SQLite (dev) · Tailwind CSS (standalone CLI) ·
HTMX + Alpine.js · PDF.js · django-unfold · WhiteNoise · gunicorn

## Loyiha tuzilishi

| App | Vazifasi |
|-----|----------|
| `oauth` | HEMIS oAuth2 oqimi |
| `user_app` | User, profillar (talaba/xodim), rollar |
| `book_app` | Author, Genre (katalog), Book, Copy, Rental |
| `circulation` | RentalRequest, Reservation, Fine, LibrarySettings |
| `reading` | Himoyalangan stream, reader/player, o'qish jarayoni/tarixi |
| `engagement` | Review, Favorite |
| `notifications` | In-app bildirishnomalar |
| `dashboard_app` | Rol-based dashboard + analitika |

## Rollar

`Student` · `Employee` · `LibraryAdmin` (kutubxonachi) · `Admin` —
ruxsat `user_app.roles.effective_role()` orqali aniqlanadi.

## O'rnatish (lokal)

```bash
# 1. Virtual muhit (Python 3.12+ tavsiya; 3.14 uchun Django 5.2 shart)
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# 2. .env yarating (.env.sample asosida) — SECRET_KEY, HEMIS oAuth, DB

# 3. Migratsiya (default rollar avtomatik seed qilinadi)
python manage.py migrate
python manage.py createsuperuser

# 4. Tailwind CSS (standalone CLI — Node shart emas)
#    Binar: https://github.com/tailwindlabs/tailwindcss/releases  -> bin/tailwindcss
./bin/css-build.sh        # bir martalik build
./bin/css-watch.sh        # dev paytida kuzatuv

# 5. Ishga tushirish
python manage.py runserver
```

## Cron (davriy vazifa)

Jarima hisoblash, muddat-yaqin ogohlantirish va navbat muddatini tekshirish —
kuniga bir marta:

```cron
0 1 * * *  /path/to/venv/bin/python /path/to/manage.py circulation_tick
```

## Testlar va linter

```bash
python manage.py test          # 31 ta test (rol, ijara, stream, engagement, ...)
ruff check .                    # linter (pip install -r requirements-dev.txt)
```

## Production deploy

To'liq yo'riqnoma: [`DEPLOY.md`](DEPLOY.md)
(gunicorn + nginx + WhiteNoise + raqamli kitoblar uchun `X-Accel-Redirect` himoyasi).

Asosiy: `DJANGO_ENV=production`, `SECRET_KEY` majburiy, `collectstatic`,
`python manage.py check --deploy`.
