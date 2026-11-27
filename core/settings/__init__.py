"""
Sozlamalarni muhitga qarab yuklaydi.

    DJANGO_ENV=production  ->  core.settings.production
    boshqa har qanday      ->  core.settings.local   (dev)

MUHIM: bu modul stdout'ga HECH NARSA yozmaydi. Ilgari bu yerda `print()` bor edi va
u `dumpdata`, `diffsettings` kabi buyruqlarning chiqishini buzib qo'yardi (JSON faylga
"dev" so'zi tushib qolardi). Muhitni bilish kerak bo'lsa: `python manage.py diffsettings`.
"""
import os

from dotenv import load_dotenv

# .env ni yuklash
load_dotenv()

environment = os.getenv('DJANGO_ENV', 'local')

if environment == 'production':
    from .production import *  # noqa: F401,F403
else:
    from .local import *  # noqa: F401,F403
