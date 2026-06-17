#!/usr/bin/env bash
# Tailwind'ni kuzatuv (watch) rejimida ishga tushiradi — dev paytida ochiq turadi.
cd "$(dirname "$0")/.."
exec ./bin/tailwindcss -i theme/input.css -o static/css/app.css --watch
