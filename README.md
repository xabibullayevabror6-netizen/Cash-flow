# Cash Flow Boshqaruv Tizimi

1C bank eksporti (Excel) asosida CFO darajasidagi pul oqimi tahlili, dashboard va prognoz.
To'liq texnik hujjat: `texnik-hujjat.md`.

## Nima qiladi

Bank ko'chirmasini yuklaysiz — tizim har bir operatsiyani buxgalteriya provodkasi
(Кор. счет) bo'yicha uch qatlamga ajratadi va haqiqiy moliyaviy holatni ko'rsatadi:

- **Asosiy faoliyat** — biznes o'zi ishlab topgan va sarflagan pul
- **Investitsion faoliyat** — asosiy vositalar va uzoq muddatli qo'yilmalar
- **Moliyaviy faoliyat** — kreditlar, qarzlar, dividendlar

Ichki ko'chirmalar (o'z hisoblari orasidagi harakat) **alohida ajratiladi va
aylanmaga qo'shilmaydi** — aks holda ko'rsatkichlar sun'iy ravishda shishadi.

## Tuzilma

```
cashflow-system/
├── backend/                    FastAPI + PostgreSQL
│   ├── app/
│   │   ├── main.py
│   │   ├── models.py           ma'lumot modeli
│   │   ├── config.py           sozlamalar + xavfsizlik tekshiruvi
│   │   ├── security.py         parol siyosati, login cheklovi
│   │   ├── i18n.py             backend xabarlari (4 til)
│   │   ├── routers/            API endpointlar
│   │   └── services/
│   │       ├── excel_parser.py         1C formatini o'qish
│   │       ├── cash_flow_structure.py  provodka klassifikatori
│   │       ├── categorizer.py          qoida + AI kategoriyalash
│   │       └── forecast_service.py     haftalik prognoz
│   ├── alembic/                baza migratsiyalari
│   ├── tests/                  pytest to'plami
│   └── seed.py                 boshlang'ich kategoriyalar
├── frontend/                   React + Vite
│   └── src/
│       ├── pages/              Login, Bank, Import, Dashboard, Review, Forecast, Categories
│       ├── i18n/               uz / uz-Cyrl / ru / en
│       └── api/client.js
└── docker-compose.yml
```

## 1. Talablar

- Docker va Docker Compose (eng oson yo'l), YOKI
- Python 3.12+, Node.js 20+, PostgreSQL 16+
- Anthropic API kaliti — ixtiyoriy, AI kategoriyalash uchun (https://console.anthropic.com)

> Kalitsiz ham tizim to'liq ishlaydi: operatsiyalar «Boshqa» kategoriyasiga tushadi
> va «Tasdiqlash» bo'limida qo'lda taqsimlanadi.

## 2. Docker bilan ishga tushirish

```bash
cd cashflow-system
cp backend/.env.example backend/.env
```

`backend/.env` faylida **majburiy** to'ldiriladigan qiymat — `JWT_SECRET_KEY`.
Yangi kalit yarating:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

So'ng ishga tushiring:

```bash
docker compose up --build
```

Baza sxemasi ishga tushishda avtomatik migratsiya qilinadi (`alembic upgrade head`).

Boshlang'ich kategoriyalarni qo'shish (bir marta):

```bash
docker compose exec backend python seed.py
```

Manzillar:
- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- Swagger: http://localhost:8000/docs

## 3. Qo'lda ishga tushirish (Docker'siz)

### Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env            # DATABASE_URL va JWT_SECRET_KEY to'ldiring
createdb cashflow_db

alembic upgrade head            # sxemani yaratadi
python seed.py                  # boshlang'ich kategoriyalar
uvicorn app.main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

## 4. Birinchi foydalanish

1. http://localhost:5173 ga o'ting va «Kompaniya ro'yxatdan o'tkazish»ni tanlang
   (parol kamida 10 belgi bo'lishi kerak)
2. **Bank hisoblari** — bank nomi, hisob raqami va valyutani kiriting.
   Prognoz likvidlikni ko'rsatishi uchun shu yerda **haqiqiy bank qoldig'ini**
   va u qaysi kunga tegishli ekanini ham belgilang
3. **Import** — 1C dan eksport qilingan Excel faylni yuklang va davr sanasini belgilang
4. **Dashboard** — pul oqimi tuzilmasi, xarajatlar tahlili, kontragentlarga
   bog'liqlik va Excel eksport
5. **Tasdiqlash** — AI taklif qilgan kategoriyalarni tekshiring va tasdiqlang
6. **Prognoz** — kamida 4 haftalik tarix to'plangach ishlaydi

## 5. Boshqa kompyuterdan kirish

Frontend va API **bitta portda** (5173) ishlaydi — nginx `/api/` so'rovlarini
backend'ga uzatadi. Shu sababli sayt qaysi manzildan ochilsa, API ham o'sha
manzilda bo'ladi: hech narsa sozlash shart emas.

### Bir tarmoq ichida (uy/ofis Wi-Fi)

Server turgan kompyuterning IP'sini bilib oling:

```bash
ipconfig
```

Boshqa kompyuterda brauzerga yozing: `http://<IP>:5173`

Ishlamasa: ikkala qurilma bir tarmoqda ekanini tekshiring. Telefon hotspot'ida
qurilmalar ba'zan bir-birini ko'rmaydi ("client isolation") — bunda oddiy
Wi-Fi router ishlating yoki quyidagi tunnel yo'lidan boring.

### Boshqa tarmoqdan — tez yo'l (vaqtinchalik manzil)

```bash
docker compose --profile tunnel up -d tunnel
sh tunnel-url.sh
```

`https://...trycloudflare.com` ko'rinishidagi manzil chiqadi — uni istalgan
joydan ochish mumkin. To'xtatish:

```bash
docker compose stop tunnel
```

**Manzil har qayta ishga tushganda o'zgaradi** (kompyuter o'chib-yonsa ham).
`sh tunnel-url.sh` joriy manzilni topadi, uni tekshiradi (eski log qolgan
bo'lsa ogohlantiradi) va ikki joyga yozib qo'yadi:

- `tunnel-url.txt` fayli
- ish stolida **«Cash Flow (tunnel)»** yorlig'i

Ya'ni har safar manzilni qidirish shart emas — kompyuter yonganidan keyin
bir marta shu buyruqni ishlatasiz.

> Har kuni shu ishni takrorlamaslik uchun quyidagi doimiy manzilni sozlang —
> u bir marta qilinadi va keyin hech qachon o'zgarmaydi.

### Boshqa tarmoqdan — doimiy manzil (o'z domeningiz bilan)

Manzil hech qachon o'zgarmaydi, HTTPS avtomatik. Tekin.

**Shart:** domeningiz Cloudflare'ga ulangan bo'lishi kerak — https://dash.cloudflare.com
da domenni qo'shib, nameserver'larni Cloudflare'nikiga o'zgartirasiz (bir marta,
domen registratoringiz panelida).

So'ng bitta buyruq:

```bash
sh setup-tunnel.sh cashflow.sizningdomen.uz
```

Skript uchta ishni bajaradi: Cloudflare hisobingizga kiritadi (brauzerda
tasdiqlaysiz), tunnel yaratadi va DNS yozuvini qo'shadi.

Keyin vaqtinchalik tunnel'ni to'xtatib, doimiysini yoqing:

```bash
docker compose stop tunnel
docker compose --profile named up -d tunnel-named
```

Tayyor — sayt doimo `https://cashflow.sizningdomen.uz` da ochiladi.

> Kirish ma'lumotlari `cloudflared/` papkasida saqlanadi va **sir** — ular
> `.gitignore` da. Nusxa ko'chirsangiz ham, ularni hech kimga bermang.

**Xavfsizlik.** Tunnel yoqilgan paytda (vaqtinchalik yoki doimiy — farqi yo'q)
sayt butun internetga ochiq bo'ladi: manzilni bilgan har kim login sahifasini
ko'radi. Ma'lumotni parolingiz himoya qiladi (login urinishlari cheklangan,
parol talablari bor). Kerak bo'lmaganda tunnel'ni to'xtating.

Har ikkala holatda ham **kompyuteringiz yoqiq turishi kerak** — server shu
mashinada. Kompyuterdan mustaqil ishlashi uchun ilovani haqiqiy serverga
joylash kerak (8-bo'lim).

### Tunnel ishlamay qolsa

Uzluksiz uzilib tursa (loglarda `control stream failure`), tarmoq QUIC/UDP'ni
bloklayotgan bo'lishi mumkin — telefon hotspotlarida keng tarqalgan. Sozlamada
`--protocol http2` allaqachon yoqilgan; qayta ishga tushiring:

```bash
docker compose --profile tunnel up -d --force-recreate tunnel
```

## 6. Testlar

```bash
docker compose exec backend pytest
```

Testlar alohida vaqtinchalik bazada ishlaydi — ishchi ma'lumotga tegmaydi.

## 7. Baza sxemasini o'zgartirish

Model o'zgartirilgandan so'ng migratsiya yarating:

```bash
docker compose exec backend alembic revision --autogenerate -m "nima o'zgardi"
docker compose exec backend alembic upgrade head
```

## 8. Bulutga joylash — doimiy manzil

Bu yo'l tunnel muammosini butunlay hal qiladi:

- manzil **hech qachon o'zgarmaydi**
- kompyuteringiz o'chsa ham sayt **ishlayveradi**
- HTTPS avtomatik

Ilova bitta konteynerga yig'ilgan (`Dockerfile` loyiha ildizida): frontend
qurilib, backend uni o'zi tarqatadi. Shuning uchun bitta veb-xizmat yetarli.

### Render.com orqali (tekin tarifdan boshlash mumkin)

**1. Kodni GitHub'ga joylang.** Render kodni shu yerdan oladi.

```bash
git init
git add .
git commit -m "Cash flow tizimi"
```

So'ng GitHub'da bo'sh repozitoriy yaratib, uni yuklang.

> `.gitignore` sirlarni (`.env`, tunnel kalitlari) allaqachon chetlab o'tadi —
> ular Git'ga tushmaydi.

**2. Render'da hisob oching** — https://render.com (GitHub bilan kirish mumkin).

**3. Blueprint yarating.** Render panelida **New → Blueprint** tanlang va
repozitoriyangizni ko'rsating. `render.yaml` fayli allaqachon tayyor: u
veb-xizmat va PostgreSQL bazasini birga yaratadi, `JWT_SECRET_KEY` ni
avtomatik generatsiya qiladi.

**4. Kuting.** Birinchi joylash 5–10 daqiqa oladi. Baza sxemasi va
boshlang'ich kategoriyalar avtomatik yaratiladi.

**5. Manzilingizni oling** — `https://cashflow-xxxx.onrender.com` ko'rinishida.
Bu manzil doimiy. Uni `render.yaml` dagi `FRONTEND_ORIGIN` ga ham yozib qo'ying.

**6. Ro'yxatdan o'ting** va ma'lumotlarni qaytadan yuklang (bulutdagi baza
bo'sh bo'ladi — lokal ma'lumot ko'chirilmaydi).

### Tekin tarif cheklovlari

| Cheklov | Ma'nosi |
|---|---|
| Xizmat 15 daqiqa faoliyatsizlikdan keyin uxlaydi | Birinchi ochilish 30–60 soniya kutdiradi |
| Tekin baza cheklangan muddatga beriladi | Ma'lumot muhim bo'lsa pullik tarifga o'ting |

Haqiqiy ish uchun oyiga ~7$ lik tarif bu ikkala cheklovni ham olib tashlaydi.

### Boshqa variantlar

`Dockerfile` standart — Railway, Fly.io, Koyeb yoki oddiy VPS'da ham
xuddi shunday ishlaydi. VPS'da `docker compose up -d` yetarli.

## 9. Server sozlamalari

- **Backend + baza**: Railway, Render yoki VPS — `docker-compose.yml` shu yerda ham ishlaydi
- **Frontend**: Vercel, Netlify yoki `frontend/Dockerfile` orqali Nginx bilan
- Majburiy sozlamalar:
  - `ENVIRONMENT=production` — bu holatda zaif `JWT_SECRET_KEY` bilan server
    **umuman ishga tushmaydi**
  - `DATABASE_URL`, `JWT_SECRET_KEY`, `ANTHROPIC_API_KEY` — server environment
    o'zgaruvchilarida (hech qachon Git'ga qo'yilmaydi, `.gitignore` da)
  - `FRONTEND_ORIGIN` — haqiqiy domen (CORS uchun)
  - PostgreSQL uchun avtomatik backup

## 10. Xavfsizlik

Amalda qo'llangan himoya choralari:

| Chora | Tafsilot |
|---|---|
| Parol saqlash | bcrypt xesh, ochiq matnda hech qayerda saqlanmaydi |
| Parol talabi | kamida 10 belgi, keng tarqalgan parollar rad etiladi |
| Login cheklovi | 5 muvaffaqiyatsiz urinishdan keyin 15 daqiqa blok (email+IP bo'yicha) |
| Ro'yxatdan o'tish cheklovi | bir IP dan soatiga 3 ta |
| Token bekor qilish | parol o'zgartirilganda barcha eski JWT darhol kuchini yo'qotadi |
| Token muddati | 24 soat (`JWT_EXPIRE_MINUTES`) |
| Ochiq portlar | faqat 5173. Baza va API tarmoqqa umuman chiqarilmagan |
| Xavfsizlik sarlavhalari | CSP, X-Frame-Options, nosniff, Referrer-Policy, HSTS, Permissions-Policy |
| Ko'p ijarachilik | har bir so'rov `company_id` bo'yicha cheklangan, testlar bilan qoplangan |
| Swagger | `ENVIRONMENT=production` bo'lsa butunlay o'chadi |
| Sirlar | `.env` faylida, `.gitignore` da; kodda hech qanday parol yo'q |

### Nima qilish kerak

**Parolni almashtirish.** Ilovadagi «Sozlamalar» bo'limida. Parol o'zgarganda
boshqa qurilmalardagi ochiq seanslar avtomatik uziladi.

**Tunnel'ni faqat kerak paytda yoqing** (5-bo'lim). Yoqilgan paytda sayt butun
internetga ochiq bo'ladi.

**Internetga doimiy chiqarishdan oldin:**

```bash
ENVIRONMENT=production          # zaif kalit bilan server ishga tushmaydi
CORS_ALLOW_LAN=false            # faqat aniq domenlar
FRONTEND_ORIGIN=https://sizning-domeningiz
```

### Hali qilinmagan

- **Ikki faktorli autentifikatsiya (2FA)** — yo'q
- **Audit jurnali** — kim qachon nima o'zgartirgani yozilmaydi
- **Parolni tiklash (email orqali)** — yo'q, parolni faqat joriy parolni bilgan holda o'zgartirish mumkin
- **Login cheklovi xotirada** — server qayta ishga tushsa hisoblagich nolga tushadi;
  bir nechta nusxada ishlatilsa Redis kerak bo'ladi
- **Rollar bo'yicha huquq cheklovi** — `admin`/`accountant` modelda bor, lekin
  amalda tekshirilmaydi: har bir foydalanuvchi hamma amalni bajara oladi

## 11. Dashboard nimalarni ko'rsatadi

| Bo'lim | Savol |
|---|---|
| Bosh xulosa | Biznes o'z faoliyatidan pul ishlab topdimi yoki sarfladimi? |
| Davrlar dinamikasi | O'tgan davrga nisbatan nima o'zgardi? (2+ davr kerak) |
| Uch qatlam | Pul asosiy faoliyatdan keldimi, kreditdanmi yoki aktiv sotishdanmi? |
| Xarajatlar tuzilmasi | Pul qayerga ketdi — buxgalteriya provodkalari bo'yicha |
| Kategoriyalar bo'yicha | Xuddi shu savol, boshqaruv kategoriyalarida |
| Kontragentlarga bog'liqlik | Bitta yetkazib beruvchi yiqilsa nima bo'ladi? |
| Yirik kontragentlar | Kimga ko'p to'laymiz, kimdan ko'p olamiz |

**Eksport.** Sarlavhadagi ikkita tugma Excel fayl beradi: to'liq hisobot
(4 varaq — umumiy, tuzilma, kategoriyalar, kontragentlar) va operatsiyalar
ro'yxati. Ikkalasi ham dashboarddagi faol filtrlarni hisobga oladi.

**Konsentratsiya haqida.** Top-1 ulushi 30% dan oshsa ogohlantirish chiqadi.
Bu buxgalteriya emas, boshqaruv ko'rsatkichi: bitta kontragentga bog'liqlik
narx muzokarasida kuchni yo'qotadi va yetkazib berish uzilsa faoliyatni
to'xtatadi.

## 12. Muhim texnik qarorlar

**Provodka klassifikatori qat'iy qoida, AI emas.** `7810` — bu kredit, `5110` — o'z
hisobi: bu buxgalteriya fakti, taxmin emas. CFO hisoboti auditga bardosh berishi
kerak, shuning uchun pul oqimi tuzilmasi qat'iy jadval bilan aniqlanadi
(`services/cash_flow_structure.py`).

**Kategoriya uch bosqichda aniqlanadi** — arzondan qimmatga qarab
(`services/categorizer.py`):

1. **Kontragent qoidasi** — buxgalter avval tasdiqlagan bilim. Eng ishonchli,
   shuning uchun birinchi.
2. **Provodka (Кор. счет)** — buxgalteriya fakti, bepul va darhol. Kodlarning
   xaritasi `services/provodka_categories.py` da. Ikki darajali ishonch:
   - *yuqori* (6973 = ish haqi, 6980 = ijara) → avtomatik tasdiqlanadi
   - *o'rtacha* (4310 = ta'minotchi — nima sotgani noma'lum) → kategoriya
     qo'yiladi, lekin buxgalter tasdig'iga yuboriladi
3. **AI** — faqat yuqoridagilar hal qila olmagan holatlar uchun.

Provodka bosqichi kiritilgach, AI kalitisiz ham operatsiyalarning katta qismi
to'g'ri taqsimlanadi. Eski ma'lumotni yangi qoidalarga o'tkazish uchun
«Tasdiqlash» bo'limida **«Provodkalar bo'yicha taqsimlash»** tugmasi bor —
u qo'lda tuzatilgan operatsiyalarga tegmaydi.

**Valyutalar hech qachon qo'shilmaydi.** Hisobot doimo bitta valyuta ichida
yig'iladi; kurs bo'yicha konvertatsiya qilinmaydi.

**Bir hisobga bir sana uchun bitta import.** Ilova darajasida ham, bazada unique
indeks bilan ham himoyalangan.

**Prognoz — to'g'ridan-to'g'ri (direct) usul, treasury amaliyotidagidek.**
Model `services/forecast_service.py` da, asosiy qarorlar:

- **Ish kunlari bo'yicha.** Bank ko'chirmasi dam olish kunlarida kelmaydi;
  kalendar kunlari bo'yicha o'rtacha olish darajani 5/7 ga pasaytiradi.
- **Daraja mediana orqali.** Bitta yirik to'lov o'rtachani buzadi, medianani
  buzmaydi.
- **Hafta kuni mavsumiyligi.** Amalda dushanba va chorshanba oqimi 40% ga
  farq qiladi. Kam kuzatuvda koeffitsient 1.0 ga tortiladi (shrinkage) —
  tasodif naqsh deb qabul qilinmasligi uchun.
- **Noaniqlik oralig'i (P10/P50/P90).** Tarixiy kunlik chetlanishlardan
  2000 ta yo'l generatsiya qilinadi (bootstrap). Bitta raqamli prognoz
  aniqlik illyuziyasini beradi — bu xavfli.
- **O'z-o'zini tekshirish.** Oxirgi kunlar tarixdan olib tashlanadi,
  bashorat qilinadi va xato (MAPE) o'lchanadi. Foydalanuvchi prognozga
  qanchalik ishonish mumkinligini biladi.
- **Stsenariy.** Tushum −10% / −20% bo'lsa nima bo'lishini ko'rish mumkin.
- **Muntazam to'lovlar** alohida ajratiladi — ular prognozning eng
  ishonchli qismi.
- **Tarix yetarli bo'lmasa (15 ish kunidan kam) prognoz ko'rsatilmaydi.**

**Likvidlik uchun bank qoldig'i kerak.** Importlardagi kirim-chiqim yig'indisi
qoldiq emas — u faqat oqim. «Bank hisoblari» bo'limida haqiqiy qoldiqni
kiritmaguningizcha prognoz «pul qachon tugaydi» savoliga javob bermaydi va
buni ochiq aytadi.

## 13. Hali qilinmagan

- Filial (branch) aniqlash mantiqi — model tayyor, ajratish qoidalari yozilmagan
- Rollar (admin / buxgalter) bo'yicha huquq cheklovi — model tayyor, tekshiruv yo'q
- Bir nechta bank orasidagi transferlarni juftlashtirish
- Mavsumiylikni hisobga oluvchi prognoz modeli
