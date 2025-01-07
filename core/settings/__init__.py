import os

from dotenv import load_dotenv

# loading env
load_dotenv()

environment = os.getenv('DJANGO_ENV', 'local')

print(environment)
print("+")

if environment == 'production':
    from .production import *
else:
    from .local import *
