#!/usr/bin/env bash
# Tailwind'ni production uchun (minify) bir marta build qiladi.
cd "$(dirname "$0")/.."
exec ./bin/tailwindcss -i theme/input.css -o static/css/app.css --minify
