"""
Funksiya flaglari (feature flags).

Nega kerak: v3 phase'lari ketma-ket chiqadi — yarim tayyor modul kodda turishi mumkin,
lekin foydalanuvchiga ko'rinmasligi kerak.

Qiymat qaydan olinadi (ustunlik tartibida):
  1. muhit o'zgaruvchisi  FLAG_<NOM>=1 / 0 / true / false
  2. settings.FEATURE_FLAGS (loyihada o'rnatilgan)
  3. shu fayldagi DEFAULTS

Kodda:       from core.flags import flag_enabled;  if flag_enabled('acquisitions'): ...
Shablonda:   {% if flags.acquisitions %} ... {% endif %}
"""
import os

from django.conf import settings

DEFAULTS = {
    # --- v3 modullari (phase'lar bilan yoqiladi) ---
    'patrons': False,          # P1 — a'zolik (Patron) tizimi
    'catalog_v3': False,       # P2 — boyitilgan katalog + Item/fond
    'circulation_v3': False,   # P3 — qoida matritsasi + skaner deski
    'billing': False,          # P4 — AccountLine hisob-kitobi
    'opac_v3': False,          # P5 — yangi o'quvchi tomoni
    'digital_v2': False,       # P6 — EPUB, ko'p fayl, suv belgisi
    'marc_import': False,      # P7 — MARC/Z39.50
    'reports_official': False,  # P8 — inventar kitobi, KSU, aktlar
    'reading_room': False,     # P9 — zal va davomat
    'kiosk': False,            # P9 — self-checkout
    'acquisitions': False,     # P10 — ta'minot
    'serials': False,          # P10 — davriy nashrlar

    # --- D-trek (dizayn) ---
    'design_v3': True,         # yangi ikki qiyofa dizayn tizimi
    'design_styleguide': True,  # /_design/ sahifasi (xodim uchun)
}

_TRUE = {'1', 'true', 'yes', 'on', 'ha'}
_FALSE = {'0', 'false', 'no', 'off', "yo'q"}


def all_flags() -> dict:
    """Barcha flaglarning amaldagi qiymati."""
    merged = dict(DEFAULTS)
    merged.update(getattr(settings, 'FEATURE_FLAGS', {}) or {})
    for name in list(merged):
        env_value = os.getenv(f'FLAG_{name.upper()}')
        if env_value is None:
            continue
        value = env_value.strip().lower()
        if value in _TRUE:
            merged[name] = True
        elif value in _FALSE:
            merged[name] = False
    return merged


def flag_enabled(name: str) -> bool:
    return bool(all_flags().get(name, False))
