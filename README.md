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

Django 5.2 (LTS) · **PostgreSQL** (dev va prod) · Tailwind CSS 4 (standalone CLI) ·
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
| `panel` | Xodim (kutubxonachi) paneli — to'liq CRUD |
| `audit` | Audit jurnali (`ActionLog`) + davriy vazifalar jurnali (`JobRun`) |

## Rollar

`Student` · `Employee` · `LibraryAdmin` (kutubxonachi) · `Admin` —
ruxsat `user_app.roles.effective_role()` orqali aniqlanadi.

## O'rnatish (lokal)

```bash
# 1. Virtual muhit (Python 3.12+; 3.14 uchun Django 5.2 shart)
python3 -m venv venv && source venv/bin/activate
pip install -r requirements-dev.txt

# 2. .env yarating (.env.sample asosida) — SECRET_KEY, HEMIS oAuth, DB_*

# 3. PostgreSQL (docker) — v3'dan boshlab dev'da ham Postgres ishlatiladi
make db-up                 # docker compose up -d db + tayyor bo'lguncha kutadi
make migrate
make superuser

# 4. Tailwind CSS (standalone CLI — Node shart emas)
make css                   # bir martalik build
make css-watch             # dev paytida kuzatuv

# 5. Ishga tushirish
make run                   # http://localhost:8000
```

`make help` — barcha buyruqlar ro'yxati.

> **SQLite kerak bo'lsa** (vaqtincha): `USE_SQLITE=1 python manage.py runserver`.
> Lekin to'liq matnli qidiruv va trigram faqat Postgres'da ishlaydi.

### SQLite'dan Postgres'ga ko'chirish (bir martalik)

```bash
make data-dump             # eski db.sqlite3 -> var/sqlite-dump.json
make db-up && make data-load
```

## Dizayn tizimi

Ikki qiyofa (dual shell): **OPAC** (o'quvchi — issiq qog'oz, bo'sh joy ko'p) va
**Staff** (xodim — neytral, zich ish quroli). Ikkisi bir xil komponent klasslarini
ishlatadi; farq `data-shell` atributidagi semantik tokenlarda.

| Fayl | Vazifasi |
|------|----------|
| `theme/tokens.css` | rang/shrift/zichlik tokenlari + qiyofa farqlari |
| `theme/components.css` | komponentlar (btn, input, table, badge, modal, ...) |
| `templates/layouts/opac.html` | o'quvchi shell'i |
| `templates/layouts/staff.html` | xodim shell'i |
| `templates/ui/*.html` | qayta ishlatiladigan partial'lar (icon, stat, badge, pager, ...) |

Barcha komponentlarni ko'rish: **`/_design/`** (xodim uchun, `design_styleguide` flagi).

## Funksiya flaglari

Yarim tayyor modullarni yoqib/o'chirish: `core/flags.py`. Muhitdan ham boshqariladi —
masalan `FLAG_ACQUISITIONS=1`. Shablonda: `{{ flags.acquisitions }}`.

## Davriy vazifalar

**Production'da cron shart emas.** Ertalab 06:00 dan (Toshkent vaqti) keyingi
birinchi so'rov bugungi vazifalarni fonda ishga tushiradi (`core/autojobs.py`).
Bugun muvaffaqiyatli bajarilgan vazifa qayta yurmaydi, xato bo'lsa kuniga
3 martagacha uriniladi. O'chirish: `.env` ga `AUTO_JOBS=0`. Dev muhitda
o'chiq, yoqish: `AUTO_JOBS=1`.

Har ishga tushish `audit.JobRun` jadvaliga yoziladi. Qo'lda yurgizish:

```bash
make jobs-list                       # vazifalar ro'yxati
python manage.py run_jobs --schedule daily
python manage.py run_jobs fines_accrual
```

Aniq soatda yurishi kerak bo'lsa cron ham qo'shish mumkin — ikkalasi bir-biriga
xalaqit bermaydi:

```cron
0 1 * * *  /path/to/venv/bin/python /path/to/manage.py run_jobs --schedule daily
```

Hozirgi vazifalar: `due_soon_notices`, `fines_accrual`, `reservation_expiry`.
(Eski `circulation_tick` buyrug'i orqaga moslik uchun qoldirilgan.)

## Testlar va linter

```bash
make test     # 57 ta test (rol, ijara, stream, engagement, audit, vazifalar, dizayn)
make cov      # testlar + qamrov hisoboti
make lint     # ruff linter
```

## Production deploy

Serverda **Docker kerak emas** — tizim PostgreSQL'i, gunicorn va nginx.

```bash
sudo ./bin/server-setup.sh     # bir marta: paketlar, baza, .env, systemd, nginx, cron
./deploy.sh                    # har safar: zaxira -> pull -> migrate -> statik -> restart
```

To'liq yo'riqnoma: [`DEPLOY.md`](DEPLOY.md).

> Dizayn o'zgarsa, **lokalda `make css` ishlatib natijani commit qiling** —
> serverda Tailwind build qilinmaydi, `static/css/app.css` git orqali boradi.
