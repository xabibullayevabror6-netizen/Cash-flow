FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Windows'da tahrirlangan fayl CRLF bilan kelishi mumkin — sh uni tushunmaydi
RUN sed -i 's/\r$//' entrypoint.sh && chmod +x entrypoint.sh

CMD ["./entrypoint.sh"]
