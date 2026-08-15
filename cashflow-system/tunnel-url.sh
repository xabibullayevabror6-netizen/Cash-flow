#!/bin/sh
# Tunnel manzilini ko'rsatadi va oson topiladigan joyga yozib qo'yadi.
#
# Ishlatish:
#     sh tunnel-url.sh
#
# Tekin Cloudflare tunneli har qayta ishga tushganda YANGI manzil beradi
# (kompyuter o'chib-yonsa ham). Shuning uchun bu skript manzilni:
#   • ekranga chiqaradi
#   • tunnel-url.txt fayliga yozadi
#   • ish stolida bosiladigan yorliq yaratadi
# Shunda manzilni qidirib yurish shart bo'lmaydi.

CONTAINER=cashflow-system-tunnel-1
NAMED_CONTAINER=cashflow-system-tunnel-named-1
DIR="$(cd "$(dirname "$0")" && pwd)"

# Doimiy tunnel ishlayotgan bo'lsa, manzil o'zgarmaydi — bu skript kerak emas
if docker ps --format '{{.Names}}' | grep -q "^${NAMED_CONTAINER}$"; then
    echo "Doimiy tunnel ishlayapti — manzil o'zgarmaydi."
    echo "U sizning domeningizda (setup-tunnel.sh da ko'rsatgan manzilingiz)."
    exit 0
fi

if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER}$"; then
    echo "Tunnel ishlamayapti. Ishga tushirish:"
    echo "    docker compose --profile tunnel up -d tunnel"
    exit 1
fi

URL=$(docker logs "$CONTAINER" 2>&1 | grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' | tail -1)

if [ -z "$URL" ]; then
    echo "Manzil hali tayyor emas — bir necha soniyadan so'ng qayta urinib ko'ring."
    exit 1
fi

# Manzil haqiqatan javob berayotganini tekshiramiz — eski log qolgan bo'lishi mumkin
if command -v curl >/dev/null 2>&1; then
    CODE=$(curl -s -o /dev/null -w '%{http_code}' --max-time 12 "$URL/api/health" 2>/dev/null)
    if [ "$CODE" != "200" ]; then
        echo "Loglardagi manzil javob bermayapti ($URL)."
        echo "Tunnel'ni qayta ishga tushiring:"
        echo "    docker compose --profile tunnel up -d --force-recreate tunnel"
        exit 1
    fi
fi

echo "$URL" > "$DIR/tunnel-url.txt"

# Ish stolida bosiladigan yorliq — har safar yangi manzilga yo'naltiradi
DESKTOP="$HOME/Desktop"
if [ -d "$DESKTOP" ]; then
    printf '[InternetShortcut]\r\nURL=%s\r\n' "$URL" > "$DESKTOP/Cash Flow (tunnel).url"
fi

echo "$URL"
echo ""
echo "Saqlandi:"
echo "  • $DIR/tunnel-url.txt"
[ -d "$DESKTOP" ] && echo "  • Ish stolida «Cash Flow (tunnel)» yorlig'i"
echo ""
echo "Manzil har qayta ishga tushganda o'zgaradi. Doimiy manzil uchun:"
echo "    sh setup-tunnel.sh cashflow.sizningdomeningiz.uz"
