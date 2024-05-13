# HEMIS Universitet Django bilan oAuth Integratsiyasi

Ushbu repozitoriya HEMIS Universitet tizimi bilan oAuth autentifikatsiyasini integratsiya qilish uchun Django kodini o'z ichiga oladi. Bu integratsiya bilan foydalanuvchilar HEMIS Universitet hisoblarini oAuth2 standartida boshqa tizimlarda ro'yxatdan o'tkazish yoki autentifikatsiyani amalga oshirishi mumkin.

## Getting Started

### Prerequisites

Quyidagilarni o'rnatilganiga ishonching:

- Python
- Django
- requests
- python-dotenv
- requests

### Installation

1. Repozitoriyani klonlang:

   ```bash
   git clone https://github.com/djumanov/oAuth2-by-hemis.git
   ```

2. Kerakli kutubxonalarni o'rnatish:

   ```bash
   pip install -r requirements.txt
   ```

### Sozlash

1. HEMIS Universitet tizimida oAuth mijozlarini yaratish:

   - HEMIS Universitetning ma'muriy panelida **Tizim / oAuth klientlar** bo'limiga kirin.
   - Mijoz nomini va ruxsat etilgan qayta yo'naltirish manzillarini (bir nechta manzil, vergul orqali ajratilgan) ko'rsatgan yangi mijoz yarating.
   - Mijozni saqlang va **Klient ID** va **Klient maxfiy kodi**ni olishingiz mumkin.

2. `.env` faylini mijoz ma'lumotlari bilan yangilang:

   ```bash
    CLIENT_ID=CLIENT_ID # hemis client id :int
    CLIENT_SECRET=CLIENT_SECRET # secret key in hemis client :str
    REDIRECT_URI=REDIRECT_URI # to get access code in your project :str
    AUTHORIZE_URL=https://{university_hemis_url}/oauth/authorize
    ACCESS_TOKEN_URL=https://{university_hemis_url}/oauth/access-token
    RESOURCE_OWNER_URL=https://{university_hemis_url}/oauth/api/user?fields=id,uuid,employee_id_number,type,roles,name,login,email,picture,firstname,surname,patronymic,birth_date,university_id,phone
   ```

3. `REDIRECT_URI` ni o'zingizning ilovangizning qayta yo'naltirish manziliga moslashtiring.

### Foydalanish

Django serverini ishga tushiring:

```bash
python manage.py runserver
```

Brauzeringizda taqdim etilgan URL'ga kirib, oAuth jarayonini boshlang.

## Eslatmalar

- HEMIS Universitet oAuth mijozlari sozlamalariga mos keladigan qayta yo'naltirish manzillarni ta'minlang.
- Ushbu integratsiya hozirda faqat HEMIS Universitet xodimlarining hisoblarini qo'llab-quvvatlaydi. Talabalar uchun, manzillarni moslashtiring.
- Qo'shimcha foydalanuvchi ma'lumotlari, `RESOURCE_OWNER_URL` parametrlarini o'zgartirib olish orqali olinadi.
