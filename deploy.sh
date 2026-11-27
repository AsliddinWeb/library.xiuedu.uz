#!/usr/bin/env bash
#
# XIU Library — HAR SAFARGI DEPLOY
# =============================================================================
#
# Serverda ishlatish:
#     cd /srv/library && ./deploy.sh
#
# Nima qiladi (ketma-ket, birortasi xato bersa to'xtaydi):
#     1. Bazani zaxiralaydi      (var/backups/)
#     2. git pull                (fast-forward)
#     3. Yangi kutubxonalar      (pip install)
#     4. Migratsiyalar           (manage.py migrate)
#     5. Statik fayllar          (collectstatic)
#     6. Production tekshiruvi   (check --deploy)
#     7. Xizmatni qayta ishga tushiradi (systemctl restart)
#     8. Sayt javob berayotganini tekshiradi
#
# Bayroqlar:
#     --no-backup      bazani zaxiralamaydi (tez deploy)
#     --no-pull        git pull qilmaydi (lokal o'zgarishni sinash uchun)
#     --branch NOM     boshqa branchdan (default: main)
#     --skip-health    oxirgi tekshiruvni o'tkazib yuboradi
#
# MUHIM: Docker KERAK EMAS. docker-compose.yml faqat dasturchining
# kompyuterida ishlatiladi; serverda tizimning o'z PostgreSQL'i.
# =============================================================================
set -Eeuo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$APP_DIR"

BRANCH="main"
SERVICE="${LIBRARY_SERVICE:-library}"
HEALTH_URL="${LIBRARY_HEALTH_URL:-http://127.0.0.1:8001/}"
HEALTH_HOST="${LIBRARY_HEALTH_HOST:-library.xiuedu.uz}"
BACKUP_DIR="$APP_DIR/var/backups"
KEEP_BACKUPS=10

DO_BACKUP=1
DO_PULL=1
DO_HEALTH=1

while [[ $# -gt 0 ]]; do
    case "$1" in
        --no-backup)   DO_BACKUP=0; shift ;;
        --no-pull)     DO_PULL=0; shift ;;
        --skip-health) DO_HEALTH=0; shift ;;
        --branch)      BRANCH="${2:?--branch uchun nom kerak}"; shift 2 ;;
        -h|--help)     sed -n '2,30p' "$0"; exit 0 ;;
        *)             echo "Noma'lum bayroq: $1 (yordam: ./deploy.sh --help)"; exit 2 ;;
    esac
done

# --- Chiqish formati -----------------------------------------------------
BOLD=$'\033[1m'; GREEN=$'\033[32m'; RED=$'\033[31m'; YELLOW=$'\033[33m'; OFF=$'\033[0m'
STEP=""
step() { STEP="$1"; printf '\n%s==> %s%s\n' "$BOLD" "$1" "$OFF"; }
ok()   { printf '%s    ✓ %s%s\n' "$GREEN" "$1" "$OFF"; }
warn() { printf '%s    ! %s%s\n' "$YELLOW" "$1" "$OFF"; }

on_error() {
    printf '\n%s╳ DEPLOY TO\xe2\x80\x98XTADI — bosqich: %s%s\n' "$RED" "$STEP" "$OFF"
    echo "  Xizmat holati:   systemctl status $SERVICE --no-pager -n 30"
    echo "  Loglar:          journalctl -u $SERVICE -n 50 --no-pager"
    if [[ -n "${BACKUP_FILE:-}" && -f "${BACKUP_FILE:-}" ]]; then
        echo "  Bazani tiklash:  psql -U \$DB_USER -d \$DB_NAME < $BACKUP_FILE"
    fi
    echo "  Eski kodga qaytish: git reset --hard ${OLD_COMMIT:-<eski-commit>} && ./deploy.sh --no-pull"
    exit 1
}
trap on_error ERR

# --- Yordamchilar --------------------------------------------------------
env_value() {
    # .env dan bitta qiymatni oladi (qo'shtirnoq va chetki bo'shliqlarsiz)
    local key="$1" value
    [[ -f "$APP_DIR/.env" ]] || return 0
    value="$(grep -E "^${key}=" "$APP_DIR/.env" | tail -1 | cut -d= -f2- || true)"
    value="$(printf '%s' "$value" | tr -d "\"'" )"
    printf '%s' "${value%% }"
}

as_root() {
    if [[ $EUID -eq 0 ]]; then "$@"; else sudo "$@"; fi
}

PY="$APP_DIR/venv/bin/python"
PIP="$APP_DIR/venv/bin/pip"

# =============================================================================
step "Tekshiruv"
# =============================================================================
[[ -f "$APP_DIR/manage.py" ]] || { echo "manage.py topilmadi — noto'g'ri papka"; exit 1; }
[[ -x "$PY" ]] || { echo "venv topilmadi: $PY — avval bin/server-setup.sh ni ishlating"; exit 1; }
[[ -f "$APP_DIR/.env" ]] || { echo ".env topilmadi — DEPLOY.md ga qarang"; exit 1; }

DJANGO_ENV_VALUE="$(env_value DJANGO_ENV)"
if [[ "$DJANGO_ENV_VALUE" != "production" ]]; then
    warn ".env dagi DJANGO_ENV='$DJANGO_ENV_VALUE' (production emas!)"
fi

OLD_COMMIT="$(git rev-parse --short HEAD)"
ok "Joriy versiya: $OLD_COMMIT"

# =============================================================================
step "Bazani zaxiralash"
# =============================================================================
if [[ $DO_BACKUP -eq 1 ]]; then
    DB_NAME="$(env_value DB_NAME)"; DB_USER="$(env_value DB_USER)"
    DB_HOST="$(env_value DB_HOST)"; DB_PORT="$(env_value DB_PORT)"
    DB_PASSWORD="$(env_value DB_PASSWORD)"

    if command -v pg_dump >/dev/null 2>&1 && [[ -n "$DB_NAME" ]]; then
        mkdir -p "$BACKUP_DIR"
        BACKUP_FILE="$BACKUP_DIR/$(date +%Y%m%d-%H%M%S)-${OLD_COMMIT}.sql"
        PGPASSWORD="$DB_PASSWORD" pg_dump \
            -h "${DB_HOST:-127.0.0.1}" -p "${DB_PORT:-5432}" \
            -U "$DB_USER" "$DB_NAME" > "$BACKUP_FILE"
        gzip -f "$BACKUP_FILE" && BACKUP_FILE="${BACKUP_FILE}.gz"
        ok "Zaxira: $BACKUP_FILE ($(du -h "$BACKUP_FILE" | cut -f1))"

        # Eski zaxiralarni tozalash (oxirgi $KEEP_BACKUPS tasi qoladi)
        ls -1t "$BACKUP_DIR"/*.sql.gz 2>/dev/null | tail -n +$((KEEP_BACKUPS + 1)) \
            | while read -r old; do rm -f -- "$old"; done
    else
        warn "pg_dump yo'q yoki DB_NAME bo'sh — zaxirasiz davom etilmoqda"
    fi
else
    warn "Zaxira o'tkazib yuborildi (--no-backup)"
fi

# =============================================================================
step "Kodni yangilash"
# =============================================================================
if [[ $DO_PULL -eq 1 ]]; then
    if [[ -n "$(git status --porcelain)" ]]; then
        warn "Serverda saqlanmagan o'zgarishlar bor:"
        git status --short | sed 's/^/      /'
        warn "Ular saqlanib qoladi; agar xalaqit bersa: git checkout -- <fayl>"
    fi
    git fetch --prune origin
    git checkout "$BRANCH"
    git merge --ff-only "origin/$BRANCH"
    NEW_COMMIT="$(git rev-parse --short HEAD)"
    if [[ "$NEW_COMMIT" == "$OLD_COMMIT" ]]; then
        ok "Yangilanish yo'q ($NEW_COMMIT)"
    else
        ok "$OLD_COMMIT -> $NEW_COMMIT"
        git --no-pager log --oneline "$OLD_COMMIT..$NEW_COMMIT" | sed 's/^/      /'
    fi
else
    warn "git pull o'tkazib yuborildi (--no-pull)"
fi

# =============================================================================
step "Kutubxonalar (pip)"
# =============================================================================
"$PIP" install --quiet --upgrade pip
"$PIP" install --quiet -r "$APP_DIR/requirements.txt"
ok "requirements.txt o'rnatildi"

# =============================================================================
step "Migratsiyalar"
# =============================================================================
PENDING="$(DJANGO_ENV=production "$PY" manage.py showmigrations --plan 2>/dev/null | grep -c '^\[ \]' || true)"
if [[ "${PENDING:-0}" -gt 0 ]]; then
    echo "    $PENDING ta migratsiya qo'llanadi:"
    DJANGO_ENV=production "$PY" manage.py showmigrations --plan | grep '^\[ \]' | sed 's/^/      /'
fi
DJANGO_ENV=production "$PY" manage.py migrate --noinput
ok "Baza yangilandi"

# =============================================================================
step "Statik fayllar"
# =============================================================================
# Tailwind CSS dasturchining kompyuterida build qilinadi va `static/css/app.css`
# git orqali keladi — serverda Node ham, Tailwind binar fayli ham kerak emas.
if [[ -x "$APP_DIR/bin/tailwindcss" ]]; then
    "$APP_DIR/bin/css-build.sh" >/dev/null && ok "Tailwind qayta build qilindi"
fi
DJANGO_ENV=production "$PY" manage.py collectstatic --noinput --clear >/dev/null
ok "staticfiles/ yangilandi"

# =============================================================================
step "Production tekshiruvi"
# =============================================================================
DJANGO_ENV=production "$PY" manage.py check --deploy 2>&1 | sed 's/^/    /'
ok "check --deploy o'tdi"

# =============================================================================
step "Xizmatni qayta ishga tushirish"
# =============================================================================
if systemctl list-unit-files 2>/dev/null | grep -q "^${SERVICE}.service"; then
    as_root systemctl restart "$SERVICE"
    sleep 2
    if as_root systemctl is-active --quiet "$SERVICE"; then
        ok "$SERVICE qayta ishga tushdi"
    else
        echo "$SERVICE ishga tushmadi"; exit 1
    fi
else
    warn "systemd xizmati '$SERVICE' topilmadi — qo'lda qayta ishga tushiring"
fi

# =============================================================================
step "Sayt javob beryaptimi"
# =============================================================================
if [[ $DO_HEALTH -eq 1 ]]; then
    for attempt in 1 2 3 4 5; do
        CODE="$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 \
                 -H "Host: $HEALTH_HOST" "$HEALTH_URL" || true)"
        if [[ "$CODE" =~ ^(200|301|302)$ ]]; then
            ok "HTTP $CODE — sayt ishlayapti"
            break
        fi
        if [[ $attempt -eq 5 ]]; then
            echo "Sayt javob bermadi (oxirgi kod: ${CODE:-javobsiz})"; exit 1
        fi
        sleep 2
    done
else
    warn "Tekshiruv o'tkazib yuborildi (--skip-health)"
fi

trap - ERR
printf '\n%s✓ DEPLOY TUGADI%s  —  %s\n' "$GREEN" "$OFF" "$(git rev-parse --short HEAD)"
echo "  Loglar: journalctl -u $SERVICE -f"
