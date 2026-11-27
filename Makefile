# XIU Library — tez-tez ishlatiladigan buyruqlar.
# Ishlatish:  make <maqsad>     (masalan: make run, make test, make db-up)

PY       := venv/bin/python
MANAGE   := $(PY) manage.py
DUMP     := var/sqlite-dump.json
DB_USER  ?= library_user
DB_NAME  ?= library_db

.DEFAULT_GOAL := help
.PHONY: help run shell superuser check deploy-check test cov lint fix \
        migrations migrate db-up db-wait db-down db-shell db-logs backup \
        data-dump data-load css css-watch jobs jobs-list

help: ## Mavjud buyruqlar
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[1m%-16s\033[0m %s\n", $$1, $$2}'

# --- Ishga tushirish ---
run: ## Dev serverni ishga tushirish (8000-port)
	$(MANAGE) runserver 8000

shell: ## Django shell
	$(MANAGE) shell

superuser: ## Superuser yaratish
	$(MANAGE) createsuperuser

# --- Sifat ---
check: ## Django tekshiruvi
	$(MANAGE) check

deploy-check: ## Production tekshiruvi
	DJANGO_ENV=production $(MANAGE) check --deploy

test: ## Barcha testlar
	$(MANAGE) test --shuffle --noinput

cov: ## Testlar + qamrov hisoboti
	$(PY) -m coverage run manage.py test --noinput && $(PY) -m coverage report -m

lint: ## ruff linter
	venv/bin/ruff check .

fix: ## ruff — avtomatik tuzatish
	venv/bin/ruff check . --fix

# --- Ma'lumotlar bazasi ---
db-up: ## Lokal PostgreSQL'ni ko'tarish (docker)
	docker compose up -d db
	@$(MAKE) --no-print-directory db-wait

db-wait: ## Postgres tayyor bo'lishini kutish
	@printf "PostgreSQL kutilmoqda"
	@for i in $$(seq 1 40); do \
		if docker compose exec -T db pg_isready -q 2>/dev/null; then echo " — tayyor."; exit 0; fi; \
		printf "."; sleep 1; \
	done; echo " — javob bermadi."; exit 1

db-down: ## PostgreSQL'ni to'xtatish (ma'lumot saqlanadi)
	docker compose down

db-shell: ## psql konsoli
	docker compose exec db psql -U $(DB_USER) -d $(DB_NAME)

db-logs: ## Postgres loglari
	docker compose logs -f db

migrations: ## Migratsiya fayllarini yaratish
	$(MANAGE) makemigrations

migrate: ## Migratsiyalarni qo'llash
	$(MANAGE) migrate

backup: ## Bazani zaxiralash (var/backup-<sana>.sql)
	@mkdir -p var
	docker compose exec -T db pg_dump -U $(DB_USER) $(DB_NAME) > var/backup-$$(date +%Y%m%d-%H%M%S).sql
	@echo "Zaxira var/ papkasida."

# --- SQLite -> PostgreSQL bir martalik ko'chirish ---
data-dump: ## SQLite'dagi ma'lumotni JSON'ga chiqarish
	@mkdir -p var
	USE_SQLITE=1 $(MANAGE) dumpdata --natural-foreign --natural-primary --indent 2 \
		-e contenttypes -e auth.Permission -e admin.logentry -e sessions -e audit > $(DUMP)
	@echo "Chiqarildi: $(DUMP)"

data-load: ## JSON'ni PostgreSQL'ga yuklash
	$(MANAGE) migrate
	$(MANAGE) loaddata $(DUMP)

# --- Dizayn (Tailwind) ---
css: ## Tailwind build (minify)
	./bin/css-build.sh

css-watch: ## Tailwind kuzatuv rejimi
	./bin/css-watch.sh

# --- Davriy vazifalar ---
jobs: ## Kunlik vazifalarni bajarish
	$(MANAGE) run_jobs --schedule daily

jobs-list: ## Vazifalar ro'yxati
	$(MANAGE) run_jobs --list
