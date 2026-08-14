# cloudflared

Bu papkada Cloudflare tunnel kirish ma'lumotlari saqlanadi:

- `cert.pem` — hisobingizga kirish sertifikati
- `<tunnel-id>.json` — tunnel kaliti

**Bu fayllar SIR.** Ular bilan istalgan odam sizning domeningizga tunnel
ocha oladi, shuning uchun `.gitignore` da va hech qachon Git'ga tushmaydi.

Yaratish uchun loyiha ildizida:

    sh setup-tunnel.sh cashflow.sizningdomen.uz
