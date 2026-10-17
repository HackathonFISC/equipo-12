# Despliegue en k3s-cp-de-01 — http://equipo12.belta.dev/

## Estado (2026-10-17)

- Despliegue por **Docker Compose** en `k3s-cp-de-01:~/equipo-12`.
  `deploy/up.sh` sincroniza el repo y ejecuta `sudo docker compose up -d --build`.
- En línea desde 2026-10-17. `https://equipo12.belta.dev/api/health` responde 200.
  `http://equipo12.belta.dev/` redirige a HTTPS (Cloudflare). El vhost está en
  `~/gong-cha/Caddyfile` del nodo y hace `reverse_proxy` a `127.0.0.1:18081`.

## Que hace cada archivo

| Archivo | Rol |
| --- | --- |
| `compose.yml` | Servicio `app` (`HOST=0.0.0.0`, `PORT=8000`, `MODO=test`) en la red `gongcha_gongcha`, y un sidecar que escucha `127.0.0.1:18081` (panel) y `127.0.0.1:18082` (bot) dentro del netns de `gongcha-caddy-1`. El bot es el perfil `whatsapp`. |
| `deploy/up.sh` | rsync del repo a `k3s-cp-de-01:~/equipo-12` (excluye `.git`, `.env`, `.venv`, `node_modules`, `data/*.db`, `.cursor`), `sudo docker compose up -d --build` y recarga de Caddy. Activa `--profile whatsapp` solo si el `.env` del nodo tiene token, verify token e id de teléfono. |
| `Dockerfile` | Python 3.12-slim, `MODO=test`, usuario sin privilegios, sin secretos. |
| `whatsapp-bot/Dockerfile` | Bun 1.4.0 Alpine, `bun src/server.js`, usuario `bun`, sin secretos. |
| `.dockerignore` | Excluye `.env`, `.git`, la base SQLite local, `whatsapp-bot/` y archivos privados del equipo. |

## Ejecutar

```bash
./deploy/up.sh              # o --dry-run para ver el rsync sin aplicar
curl -s http://equipo12.belta.dev/api/health
```

## WhatsApp

El bot no entra en la imagen de Python. Corre con Bun:

```bash
cd whatsapp-bot
bun install
bun run start
```

Hacen falta `WHATSAPP_TOKEN`, `PHONE_NUMBER_ID` (o `WHATSAPP_PHONE_NUMBER_ID`) y
`WHATSAPP_VERIFY_TOKEN`. Sin esas tres el proceso no arranca. La firma
`WHATSAPP_APP_SECRET` es opcional. El ejemplo está en `whatsapp-bot/.env.example`.

En el nodo, Caddy manda `https://equipo12.belta.dev/webhook` a `127.0.0.1:18082`.
El resto del sitio sigue en el panel. `deploy/up.sh` escribe ese bloque la primera
vez y recarga Caddy.

## Secretos

La app corre en `MODO=test` con stubs y no lleva credenciales. `deploy/up.sh` no
copia `.env`. El bot lee las variables del `.env` que ya esté en el nodo
(`~/equipo-12/.env`); no van en la imagen ni en git. Si faltan, el perfil
`whatsapp` no se levanta y el panel sigue en línea.
