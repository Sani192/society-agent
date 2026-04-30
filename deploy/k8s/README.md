# Kubernetes deployment notes

## Reverse-proxy headers required for API security middleware

When deploying `society-agent-api` behind an ingress/controller or external reverse proxy, forward these headers to the upstream application pod:

- `X-Forwarded-Proto` (required for HTTPS/HSTS detection)
- `X-Forwarded-For` (client IP chain)
- `X-Forwarded-Host` (original host)
- `Forwarded` (RFC 7239 alternate form, optional but supported)

`deploy/k8s/api-deployment.yaml` starts Uvicorn with:

- `--proxy-headers`
- `--forwarded-allow-ips "*"`

so the application can trust forwarded proxy metadata in cluster environments where the upstream ingress/controller sanitizes these headers.

## Public endpoint request-size defaults

The API deployment manifest also sets baseline limits:

- `PUBLIC_ENDPOINT_MAX_BODY_BYTES=131072`
- `WHATSAPP_WEBHOOK_MAX_BODY_BYTES=65536`
- `TELEGRAM_WEBHOOK_MAX_BODY_BYTES=65536`

Webhook limits are intentionally stricter than the global public-endpoint limit.

## Security / trust configuration

- Configure `TRUSTED_PROXY_CIDRS` in your Deployment env to your ingress/load-balancer proxy ranges.
- Do not include untrusted public ranges; forwarded headers are ignored unless source IP is trusted.
- Ensure `WHATSAPP_WEBHOOK_MAX_BODY_BYTES <= PUBLIC_ENDPOINT_MAX_BODY_BYTES` and all WhatsApp rate-limit windows/max values are positive; app startup now fails fast on invalid combinations.
