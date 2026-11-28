"""
`SQL_ASCII` kodlashidagi bazani `UTF8` ga o'tkazadi.

    python manage.py convert_db_utf8            # faqat tekshiruv, hech narsa o'zgarmaydi
    sudo systemctl stop library
    python manage.py convert_db_utf8 --apply
    sudo systemctl start library

Nega kerak: `SQL_ASCII` bazada JSON maydonlarga kirill va maxsus harflar
yozilmaydi (import va yuklash yiqiladi), matn uzunligi harf emas, bayt bo'yicha
sanaladi, qidiruv esa lotindan boshqa yozuvda to'g'ri ishlamaydi.

Tartib: zaxira -> yangi UTF8 baza -> nusxalash -> har jadvaldagi qatorlar sonini
solishtirish -> nomlarni almashtirish. Eski baza o'chirilmaydi
(`<nom>_ascii_old`). Biror qadam o'tmasa, ishlayotgan baza o'zgarmay qoladi.
"""
import gzip
import os
import shutil
import subprocess
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, connections
from django.utils import timezone

#: Linux'da har doim bor; bo'lmasa ikkinchisi sinab ko'riladi
LOCALES = ('C.UTF-8', 'en_US.UTF-8')


def _query(cursor, sql, params=None):
    cursor.execute(sql, params)
    return cursor.fetchall()


def inspect() -> dict:
    with connection.cursor() as cursor:
        encoding, owner = _query(cursor, """
            SELECT pg_encoding_to_char(encoding), pg_get_userbyid(datdba)
            FROM pg_database WHERE datname = current_database()""")[0]
        user, can_create = _query(cursor, """
            SELECT current_user, rolcreatedb OR rolsuper
            FROM pg_roles WHERE rolname = current_user""")[0]
        others = _query(cursor, """
            SELECT count(*) FROM pg_stat_activity
            WHERE datname = current_database() AND pid <> pg_backend_pid()
              AND backend_type = 'client backend'""")[0][0]
    return {'encoding': encoding, 'owner': owner, 'user': user,
            'can_create': can_create, 'others': others}


def row_counts(alias) -> dict:
    with connections[alias].cursor() as cursor:
        tables = _query(cursor, "SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
        counts = {}
        for (table,) in tables:
            counts[table] = _query(cursor, f'SELECT count(*) FROM "{table}"')[0][0]
    return counts


class Command(BaseCommand):
    help = "SQL_ASCII bazani UTF8 ga o'tkazadi. Bayroqsiz — faqat tekshiradi."

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help="Haqiqatan o'tkazadi")

    def handle(self, *args, **options):
        if connection.vendor != 'postgresql':
            raise CommandError("Faqat PostgreSQL uchun.")
        info = inspect()
        name = connection.settings_dict['NAME']
        self.stdout.write(
            f"Baza: {name} | kodlash: {info['encoding']} | egasi: {info['owner']} | "
            f"foydalanuvchi: {info['user']} | baza yarata oladi: "
            f"{'ha' if info['can_create'] else 'yo`q'} | boshqa ulanishlar: {info['others']}")
        if info['encoding'] == 'UTF8':
            self.stdout.write(self.style.SUCCESS("Baza allaqachon UTF8 — hech narsa qilish shart emas."))
            return
        needed = self._permission_help(info, name)
        if not options['apply']:
            if needed:
                self.stdout.write(self.style.WARNING(needed))
            self.stdout.write(self.style.WARNING(
                "\nHech narsa o'zgarmadi. O'tkazish: saytni to'xtating "
                "(sudo systemctl stop library), keyin --apply bilan qayta ishga tushiring."))
            return
        if needed:
            raise CommandError(needed)
        if info['others']:
            raise CommandError(
                f"Bazaga yana {info['others']} ta ulanish bor. Avval saytni to'xtating: "
                "sudo systemctl stop library (import yurayotgan bo'lsa: pkill -f import_arm).")
        for tool in ('pg_dump', 'psql'):
            if not shutil.which(tool):
                raise CommandError(f"{tool} topilmadi.")
        self._convert(name)

    @staticmethod
    def _permission_help(info, name):
        commands = []
        if not info['can_create']:
            commands.append(f'sudo -u postgres psql -c \'ALTER ROLE "{info["user"]}" CREATEDB;\'')
        if info['owner'] != info['user']:
            commands.append(
                f'sudo -u postgres psql -c \'ALTER DATABASE "{name}" OWNER TO "{info["user"]}";\'')
        if not commands:
            return ''
        return "Ruxsat yetmaydi. Avval bajaring:\n  " + "\n  ".join(commands)

    # ------------------------------------------------------------------

    def _tools(self, program, database, *extra):
        db = connection.settings_dict
        return ([program, '-h', db.get('HOST') or '127.0.0.1', '-p', str(db.get('PORT') or 5432),
                 '-U', db['USER'], *extra, database],
                {**os.environ, 'PGPASSWORD': db.get('PASSWORD') or ''})

    def _dump(self, name):
        folder = Path(settings.BASE_DIR) / 'var' / 'backups' / 'utf8'
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / f"{timezone.localtime():%Y%m%d-%H%M%S}-{name}.sql.gz"
        # `--encoding=UTF8`: tiklashda har bir bayt tekshiriladi. Busiz yaroqsiz
        # matn yangi bazaga sezdirmay o'tib ketadi
        command, env = self._tools('pg_dump', name, '--no-owner', '--no-comments',
                                   '--encoding=UTF8')
        with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              env=env) as process:
            with gzip.open(target, 'wb') as archive:
                shutil.copyfileobj(process.stdout, archive)
            error = process.stderr.read().decode(errors='replace')
        if process.returncode != 0:
            raise CommandError(f"Zaxira olinmadi:\n{error.strip()[:600]}")
        return target

    def _create(self, cursor, name):
        problem = None
        for locale in LOCALES:
            try:
                cursor.execute(
                    f'CREATE DATABASE "{name}" ENCODING \'UTF8\' LC_COLLATE \'{locale}\' '
                    f'LC_CTYPE \'{locale}\' TEMPLATE template0')
                return
            except Exception as exc:            # lokal topilmadi — keyingisi
                problem = exc
        raise CommandError(f"UTF8 baza yaratilmadi: {problem}")

    def _restore(self, backup, name):
        command, env = self._tools('psql', name, '-q', '-v', 'ON_ERROR_STOP=1', '-d')
        with gzip.open(backup, 'rb') as archive:
            done = subprocess.run(command, input=archive.read(), capture_output=True, env=env)
        if done.returncode != 0:
            raise CommandError("Nusxalash to'xtadi:\n"
                               + done.stderr.decode(errors='replace').strip()[:800])

    def _copy_counts(self, name):
        alias = 'utf8_check'
        connections.settings[alias] = {**connection.settings_dict, 'NAME': name}
        try:
            return row_counts(alias)
        finally:
            connections[alias].close()
            del connections[alias]
            del connections.settings[alias]

    def _convert(self, name):
        fresh, old = f'{name}_utf8', f'{name}_ascii_old'
        before = row_counts('default')
        backup = self._dump(name)
        self.stdout.write(self.style.SUCCESS(f"Zaxira: {backup}"))
        with connection._nodb_cursor() as cursor:
            if _query(cursor, "SELECT 1 FROM pg_database WHERE datname = %s", [old]):
                raise CommandError(f"«{old}» bazasi allaqachon bor — avval uni boshqa nomga o'tkazing.")
            cursor.execute(f'DROP DATABASE IF EXISTS "{fresh}"')   # oldingi urinishdan qolgani
            self._create(cursor, fresh)
        try:
            self.stdout.write("Nusxalanmoqda...")
            self._restore(backup, fresh)
            after = self._copy_counts(fresh)
            different = {table: (count, after.get(table)) for table, count in before.items()
                         if after.get(table) != count}
            if different:
                raise CommandError(f"Qatorlar soni mos emas: {different}")
        except Exception:
            with connection._nodb_cursor() as cursor:
                cursor.execute(f'DROP DATABASE IF EXISTS "{fresh}"')
            raise

        connections.close_all()
        with connection._nodb_cursor() as cursor:
            cursor.execute(f'ALTER DATABASE "{name}" RENAME TO "{old}"')
            try:
                cursor.execute(f'ALTER DATABASE "{fresh}" RENAME TO "{name}"')
            except Exception:
                cursor.execute(f'ALTER DATABASE "{old}" RENAME TO "{name}"')
                raise
        self.stdout.write(self.style.SUCCESS(
            f"\nTayyor: «{name}» endi UTF8. {len(before)} jadval, "
            f"{sum(before.values())} qator ko'chirildi."))
        self.stdout.write(
            f"Eski baza «{old}» nomi bilan saqlandi.\nSaytni ishga tushiring: "
            "sudo systemctl start library")
