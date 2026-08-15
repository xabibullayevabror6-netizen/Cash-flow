# Bitta konteyner: frontend qurilib, backend uni o'zi tarqatadi.
#
# Nima uchun bitta konteyner:
#   Bulut xizmatlarining tekin tariflarida odatda bitta veb-xizmat beriladi.
#   Ikkita alohida xizmat (nginx + API) o'rniga bitta manzil, bitta port —
#   sozlash sodda, CORS umuman kerak emas, narxi arzon.
#
# Lokal ishlash bunga ta'sir qilmaydi: docker-compose hamon alohida
# frontend/backend konteynerlarini ishlatadi.

# --- 1-bosqich: frontend build ---
FROM node:20-alpine AS frontend
WORKDIR /build
COPY frontend/package.json ./
RUN npm install
COPY frontend/ ./
# VITE_API_URL ataylab bo'sh: so'rovlar sahifa ochilgan manzilning o'ziga
# ketadi, shuning uchun ilova qaysi domenda tursa ham ishlaydi.
ENV VITE_API_URL=""
RUN npm run build


# --- 2-bosqich: backend + tayyor frontend ---
FROM python:3.12-slim
WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .
COPY --from=frontend /build/dist ./static

RUN sed -i 's/\r$//' entrypoint.sh && chmod +x entrypoint.sh

# Bulut xizmatlari portni PORT o'zgaruvchisi orqali beradi
ENV PORT=8000
EXPOSE 8000

CMD ["./entrypoint.sh"]
