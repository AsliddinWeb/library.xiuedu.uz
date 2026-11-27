#!/usr/bin/env bash
#
# XIU Library — SERVERNI BIR MARTALIK SOZLASH (Docker'siz)
# =============================================================================
#
#     sudo ./bin/server-setup.sh            # yangi server
#     sudo ./bin/server-setup.sh --skip-db  # baza allaqachon bor va sozlangan
#
# Nima qiladi (hammasi idempotent — qayta ishga tushirsa zarari yo'q):
#     1. Kerakli paketlar: python3-venv, postgresql, nginx, git, curl
#     2. PostgreSQL: baza va foydalanuvchi + pg_trgm/unaccent kengaytmalari
#     3. .env fayli (SECRET_KEY va DB paroli avtomatik generatsiya qilinadi)
#     4. venv + kutubxonalar + migratsiya + statik fayllar
#     5. systemd xizmati (gunicorn)
#     6. nginx konfiguratsiyasi (himoyalangan /protected-media/ bilan)
#     7. cron: kunlik vazifalar (jarima, muddat, navbat)
#
# MAVJUD BAZA BOR SERVERDA:
#     Skript HECH NARSANI O'CHIRMAYDI va ustidan yozmaydi. Baza nomini avval
#     mavjud `.env` dan oladi; o'sha nomli baza topilsa — "mavjud" deb o'tkazib
#     yuboradi va ichidagi kitoblar sonini ko'rsatadi. Yangi bo'sh baza faqat
#     hech narsa topilmaganda yaratiladi. Boshlashdan oldin nima qilishini
#     ko'rsatib, tasdiq so'raydi (`--yes` bilan so'ramaydi).
#
# Bayroqlar:
#     --skip-db    baza bosqichini butunlay o'tkazib yuboradi
#     --yes, -y    tasdiq so'ramaydi
#
# Keyin har safar yangilash uchun: ./deploy.sh
#
# ESLATMA: Docker TALAB QILINMAYDI. Loyihadagi docker-compose.yml faqat
# dasturchining kompyuteridagi PostgreSQL uchun.
# =============================================================================
set -Eeuo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$APP_DIR"

DOMAIN="${LIBRARY_DOMAIN:-library.xiuedu.uz}"
SERVICE="${LIBRARY_SERVICE:-library}"
APP_USER="${LIBRARY_USER:-$(stat -c '%U' "$APP_DIR" 2>/dev/null || echo www-data)}"
GUNICORN_BIND="127.0.0.1:8001"
GUNICORN_WORKERS="${LIBRARY_WORKERS:-3}"

SKIP_DB=0
ASSUME_YES=0
while [[ $# -gt 0 ]]; do
    case "$1" in
        --skip-db) SKIP_DB=1; shift ;;
        --yes|-y)  ASSUME_YES=1; shift ;;
        -h|--help) sed -n '2,30p' "$0"; exit 0 ;;
        *) echo "Noma'lum bayroq: $1"; exit 2 ;;
    esac
done

# --- MAVJUD .env BIRINCHI O'RINDA ----------------------------------------
# Serverda ishlayotgan baza bo'lsa, uning nomi .env da yozilgan. Skript YANGI
# baza yaratishdan oldin aynan shu nomlarni oladi — shuning uchun mavjud
# ma'lumotli bazaning yoniga bo'sh baza yaratilib qolmaydi.
env_value() {
    local key="$1" value
    [[ -f "$APP_DIR/.env" ]] || return 0
    value="$(grep -E "^${key}=" "$APP_DIR/.env" | tail -1 | cut -d= -f2- || true)"
    printf '%s' "$(printf '%s' "$value" | tr -d "\"'")"
}

ENV_DB_NAME="$(env_value DB_NAME)"
ENV_DB_USER="$(env_value DB_USER)"
ENV_DB_PASSWORD="$(env_value DB_PASSWORD)"

DB_NAME="${LIBRARY_DB_NAME:-${ENV_DB_NAME:-library_db}}"
DB_USER="${LIBRARY_DB_USER:-${ENV_DB_USER:-library_user}}"

BOLD=$'\033[1m'; GREEN=$'\033[32m'; YELLOW=$'\033[33m'; OFF=$'\033[0m'
step() { printf '\n%s==> %s%s\n' "$BOLD" "$1" "$OFF"; }
ok()   { printf '%s    ✓ %s%s\n' "$GREEN" "$1" "$OFF"; }
warn() { printf '%s    ! %s%s\n' "$YELLOW" "$1" "$OFF"; }

[[ $EUID -eq 0 ]] || { echo "Bu skript root huquqini talab qiladi: sudo ./bin/server-setup.sh"; exit 1; }
command -v apt-get >/dev/null || { echo "Faqat Debian/Ubuntu uchun yozilgan."; exit 1; }

# =============================================================================
#  OLDINDAN KO'RISH — skript nima qilishini oldindan ko'rsatadi va so'raydi
# =============================================================================
printf '\n%sNima qilinadi%s\n' "$BOLD" "$OFF"
echo "  Loyiha:   $APP_DIR"
echo "  Domen:    $DOMAIN"
echo "  Xizmat:   $SERVICE (foydalanuvchi: $APP_USER)"
echo "  Baza:     $DB_NAME / $DB_USER"

if [[ -f "$APP_DIR/.env" ]]; then
    echo "  .env:     MAVJUD — tegilmaydi (baza nomi ham shundan olindi)"
else
    echo "  .env:     yaratiladi (SECRET_KEY va DB paroli generatsiya qilinadi)"
fi

if command -v psql >/dev/null 2>&1; then
    if sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'" 2>/dev/null | grep -q 1; then
        PREFLIGHT_BOOKS="$(sudo -u postgres psql -tAd "$DB_NAME" \
            -c "SELECT count(*) FROM book_app_book" 2>/dev/null | tr -d ' ' || true)"
        printf '  %sBaza holati: MAVJUD%s' "$GREEN" "$OFF"
        [[ -n "$PREFLIGHT_BOOKS" ]] && printf ' (%s ta kitob)' "$PREFLIGHT_BOOKS"
        printf ' — yangisi yaratilmaydi, ma%slumot saqlanadi\n' "'"
    else
        echo "  Baza holati: yo'q — yangi bo'sh baza yaratiladi"
    fi
else
    echo "  Baza holati: PostgreSQL hali o'rnatilmagan — o'rnatiladi"
fi

cat <<'PLAN'

  Hech qachon o'chirilmaydi: mavjud baza, .env, systemd/nginx konfiguratsiyasi.
  Mavjud bo'lsa — ustidan yozilmaydi, "mavjud" deb o'tkazib yuboriladi.
PLAN

if [[ $ASSUME_YES -eq 0 ]]; then
    read -rp $'\nDavom etilsinmi? [y/N] ' answer
    [[ "$answer" =~ ^[Yy]$ ]] || { echo "Bekor qilindi."; exit 0; }
fi

# =============================================================================
step "1. Tizim paketlari"
# =============================================================================
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3-venv python3-dev postgresql postgresql-contrib \
                       nginx git curl ca-certificates >/dev/null
systemctl enable --now postgresql >/dev/null 2>&1 || true
ok "python3-venv, postgresql, nginx o'rnatildi"

# =============================================================================
step "2. PostgreSQL"
# =============================================================================
if [[ $SKIP_DB -eq 1 ]]; then
    warn "Baza bosqichi o'tkazib yuborildi (--skip-db)"
else
    DB_PASSWORD="$ENV_DB_PASSWORD"

    ROLE_EXISTS=0; DB_EXISTS=0
    sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='$DB_USER'" \
        | grep -q 1 && ROLE_EXISTS=1
    sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'" \
        | grep -q 1 && DB_EXISTS=1

    if [[ $DB_EXISTS -eq 1 ]]; then
        # Mavjud bazaga TEGILMAYDI — faqat ichida nima borligi ko'rsatiladi
        TABLES="$(sudo -u postgres psql -tAd "$DB_NAME" \
                  -c "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'" \
                  2>/dev/null | tr -d ' ')"
        BOOKS="$(sudo -u postgres psql -tAd "$DB_NAME" \
                 -c "SELECT count(*) FROM book_app_book" 2>/dev/null | tr -d ' ' || true)"
        ok "Baza '$DB_NAME' ALLAQACHON MAVJUD — tegilmaydi"
        echo "      jadvallar: ${TABLES:-?}${BOOKS:+, kitoblar: $BOOKS}"
        echo "      Ma'lumot saqlanadi; deploy faqat migratsiyalarni qo'llaydi."
    fi

    if [[ $ROLE_EXISTS -eq 1 ]]; then
        ok "Foydalanuvchi '$DB_USER' mavjud — paroli o'zgartirilmaydi"
    else
        [[ -n "$DB_PASSWORD" ]] || \
            DB_PASSWORD="$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')"
        sudo -u postgres psql -qc "CREATE ROLE \"$DB_USER\" LOGIN PASSWORD '$DB_PASSWORD';"
        ok "Foydalanuvchi '$DB_USER' yaratildi"
    fi

    if [[ $DB_EXISTS -eq 0 ]]; then
        sudo -u postgres createdb -O "$DB_USER" -E UTF8 "$DB_NAME"
        ok "Baza '$DB_NAME' yaratildi (bo'sh)"
    fi

    # Kengaytmalar: PG 13+ da pg_trgm/unaccent "trusted" — migratsiya o'zi ham
    # yarata oladi, lekin kafolat uchun shu yerda superuser bilan qo'yamiz.
    # `IF NOT EXISTS` — mavjud bazaga hech qanday ta'sir qilmaydi.
    sudo -u postgres psql -q -d "$DB_NAME" -c "CREATE EXTENSION IF NOT EXISTS pg_trgm;"
    sudo -u postgres psql -q -d "$DB_NAME" -c "CREATE EXTENSION IF NOT EXISTS unaccent;"
    ok "pg_trgm va unaccent kengaytmalari tayyor"
fi

# =============================================================================
step "3. .env fayli"
# =============================================================================
if [[ -f "$APP_DIR/.env" ]]; then
    ok ".env mavjud — tegilmadi"
else
    SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_urlsafe(64))')"
    cat > "$APP_DIR/.env" <<ENV
# XIU Library — production muhiti (server-setup.sh yaratdi)
DJANGO_ENV=production
SECRET_KEY=$SECRET_KEY
ALLOWED_HOSTS=$DOMAIN,www.$DOMAIN

# --- Ma'lumotlar bazasi ---
DB_NAME=$DB_NAME
DB_USER=$DB_USER
DB_PASSWORD=$DB_PASSWORD
DB_HOST=127.0.0.1
DB_PORT=5432

# --- HEMIS oAuth2 — TALABA (qiymatlarni to'ldiring!) ---
CLIENT_ID=
CLIENT_SECRET=
REDIRECT_URI=https://$DOMAIN/auth/callback/
AUTHORIZE_URL=https://student.xiuedu.uz/oauth/authorize
ACCESS_TOKEN_URL=https://student.xiuedu.uz/oauth/access-token
RESOURCE_OWNER_URL=https://student.xiuedu.uz/oauth/api/user?fields=id,uuid,employee_id_number,type,roles,name,login,email,picture,firstname,surname,patronymic,birth_date,university_id,phone

# --- HEMIS oAuth2 — XODIM ---
EMPLOYE_AUTHORIZE_URL=https://hemis.xiuedu.uz/oauth/authorize
EMPLOYE_ACCESS_TOKEN_URL=https://hemis.xiuedu.uz/oauth/access-token
EMPLOYE_RESOURCE_OWNER_URL=https://hemis.xiuedu.uz/oauth/api/user?fields=id,uuid,employee_id_number,type,roles,name,login,email,picture,firstname,surname,patronymic,birth_date,university_id,phone
ENV
    chmod 600 "$APP_DIR/.env"
    chown "$APP_USER" "$APP_DIR/.env"
    ok ".env yaratildi (SECRET_KEY va DB paroli generatsiya qilindi)"
    warn "HEMIS CLIENT_ID va CLIENT_SECRET ni .env ga qo'lda yozing!"
fi

# =============================================================================
step "4. Python muhiti"
# =============================================================================
if [[ ! -x "$APP_DIR/venv/bin/python" ]]; then
    sudo -u "$APP_USER" python3 -m venv "$APP_DIR/venv"
    ok "venv yaratildi"
fi
sudo -u "$APP_USER" "$APP_DIR/venv/bin/pip" install --quiet --upgrade pip
sudo -u "$APP_USER" "$APP_DIR/venv/bin/pip" install --quiet -r "$APP_DIR/requirements.txt"
ok "Kutubxonalar o'rnatildi"

mkdir -p "$APP_DIR/media" "$APP_DIR/var/backups" "$APP_DIR/staticfiles"
chown -R "$APP_USER" "$APP_DIR/media" "$APP_DIR/var" "$APP_DIR/staticfiles"

sudo -u "$APP_USER" env DJANGO_ENV=production "$APP_DIR/venv/bin/python" manage.py migrate --noinput
sudo -u "$APP_USER" env DJANGO_ENV=production "$APP_DIR/venv/bin/python" manage.py collectstatic --noinput >/dev/null
ok "Migratsiya va statik fayllar tayyor"

# =============================================================================
step "5. systemd xizmati (gunicorn)"
# =============================================================================
UNIT="/etc/systemd/system/${SERVICE}.service"
if [[ -f "$UNIT" ]]; then
    ok "$UNIT mavjud — tegilmadi"
else
    cat > "$UNIT" <<UNITFILE
[Unit]
Description=XIU Library (gunicorn)
After=network.target postgresql.service
Requires=postgresql.service

[Service]
User=$APP_USER
Group=www-data
WorkingDirectory=$APP_DIR
EnvironmentFile=$APP_DIR/.env
ExecStart=$APP_DIR/venv/bin/gunicorn core.wsgi:application \\
          --bind $GUNICORN_BIND --workers $GUNICORN_WORKERS --timeout 60 \\
          --access-logfile - --error-logfile -
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
UNITFILE
    systemctl daemon-reload
    ok "$UNIT yaratildi"
fi
systemctl enable --now "$SERVICE" >/dev/null 2>&1 || systemctl restart "$SERVICE"
ok "Xizmat ishlamoqda: $GUNICORN_BIND"

# =============================================================================
step "6. nginx"
# =============================================================================
SITE="/etc/nginx/sites-available/${SERVICE}"
if [[ -f "$SITE" ]]; then
    ok "$SITE mavjud — tegilmadi"
else
    cat > "$SITE" <<NGINX
server {
    listen 80;
    server_name $DOMAIN www.$DOMAIN;

    client_max_body_size 200M;

    location /static/ {
        alias $APP_DIR/staticfiles/;
        expires 30d;
        access_log off;
    }

    # Ommaviy media (muqovalar, profil rasmlari)
    location /media/ {
        alias $APP_DIR/media/;
    }

    # Himoyalangan raqamli kitoblar — FAQAT Django ruxsat bergandagina.
    # \`internal\` tufayli bu manzilni brauzerdan to'g'ridan-to'g'ri ochib bo'lmaydi.
    location /protected-media/ {
        internal;
        alias $APP_DIR/media/;
    }

    location / {
        proxy_pass http://$GUNICORN_BIND;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 60s;
    }
}
NGINX
    ln -sf "$SITE" "/etc/nginx/sites-enabled/${SERVICE}"
    rm -f /etc/nginx/sites-enabled/default
    ok "$SITE yaratildi va yoqildi"
fi
nginx -t >/dev/null 2>&1 && systemctl reload nginx
ok "nginx qayta yuklandi"

# =============================================================================
step "7. Davriy vazifalar (cron)"
# =============================================================================
CRON="/etc/cron.d/${SERVICE}"
if [[ -f "$CRON" ]]; then
    ok "$CRON mavjud — tegilmadi"
else
    cat > "$CRON" <<CRONFILE
# XIU Library — kunlik vazifalar: jarima hisobi, muddat eslatmasi, navbat
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
0 1 * * * $APP_USER cd $APP_DIR && DJANGO_ENV=production venv/bin/python manage.py run_jobs --schedule daily >> $APP_DIR/var/jobs.log 2>&1
CRONFILE
    chmod 644 "$CRON"
    ok "$CRON yaratildi (har kuni 01:00)"
fi

# =============================================================================
printf '\n%s✓ SERVER TAYYOR%s\n\n' "$GREEN" "$OFF"
cat <<NEXT
Keyingi qadamlar (qo'lda):

  1. HEMIS kalitlari:
       nano $APP_DIR/.env        # CLIENT_ID va CLIENT_SECRET
       systemctl restart $SERVICE

  2. Administrator yarating:
       cd $APP_DIR
       sudo -u $APP_USER env DJANGO_ENV=production venv/bin/python manage.py createsuperuser

  3. HTTPS (sertifikat):
       apt-get install -y certbot python3-certbot-nginx
       certbot --nginx -d $DOMAIN -d www.$DOMAIN

  4. Bundan keyin har safar yangilash uchun:
       cd $APP_DIR && ./deploy.sh

Foydali buyruqlar:
  journalctl -u $SERVICE -f                 # jonli loglar
  systemctl status $SERVICE --no-pager      # holat
  tail -f $APP_DIR/var/jobs.log             # cron natijalari
NEXT
