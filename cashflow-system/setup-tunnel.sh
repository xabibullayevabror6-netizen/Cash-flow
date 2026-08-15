#!/bin/sh
# Doimiy tunnel sozlash (o'z domeningiz bilan).
#
# Ishlatish:
#     sh setup-tunnel.sh cashflow.sizningdomen.uz
#
# Shart: domeningiz Cloudflare'ga ulangan bo'lishi kerak (nameserver'lar
# Cloudflare'niki). Buni https://dash.cloudflare.com da bir marta qilinadi.

set -e

HOSTNAME="$1"
TUNNEL_NAME="${TUNNEL_NAME:-cashflow}"
DIR="$(cd "$(dirname "$0")" && pwd)"
CF_DIR="$DIR/cloudflared"
IMAGE=cloudflare/cloudflared:latest

if [ -z "$HOSTNAME" ]; then
    echo "Manzilni ko'rsating. Masalan:"
    echo "    sh setup-tunnel.sh cashflow.sizningdomen.uz"
    exit 1
fi

mkdir -p "$CF_DIR"

run_cf() {
    docker run --rm -v "$CF_DIR:/home/nonroot/.cloudflared" "$IMAGE" "$@"
}

# --- 1-qadam: Cloudflare hisobiga kirish ---
if [ ! -f "$CF_DIR/cert.pem" ]; then
    echo "=== 1/3: Cloudflare hisobiga kirish ==="
    echo "Quyida chiqadigan havolani brauzerda oching va domeningizni tanlang."
    echo ""
    docker run --rm -it -v "$CF_DIR:/home/nonroot/.cloudflared" "$IMAGE" tunnel login
    echo ""
fi

if [ ! -f "$CF_DIR/cert.pem" ]; then
    echo "Kirish amalga oshmadi (cert.pem yaratilmadi). Qaytadan urinib ko'ring."
    exit 1
fi

# --- 2-qadam: tunnel yaratish ---
if ! run_cf tunnel list 2>/dev/null | grep -q "[[:space:]]${TUNNEL_NAME}[[:space:]]"; then
    echo "=== 2/3: '$TUNNEL_NAME' tunneli yaratilmoqda ==="
    run_cf tunnel create "$TUNNEL_NAME"
else
    echo "=== 2/3: '$TUNNEL_NAME' tunneli allaqachon mavjud ==="
fi

# --- 3-qadam: DNS yozuvi ---
echo "=== 3/3: $HOSTNAME manzili tunnel'ga bog'lanmoqda ==="
run_cf tunnel route dns "$TUNNEL_NAME" "$HOSTNAME"

echo ""
echo "Tayyor. Endi ishga tushiring:"
echo "    docker compose stop tunnel"
echo "    docker compose --profile named up -d tunnel-named"
echo ""
echo "Sayt doimiy manzilda ochiladi:"
echo "    https://$HOSTNAME"
