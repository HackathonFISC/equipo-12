# Webhook de WhatsApp. Sin secretos: el token entra por el entorno del compose.
FROM oven/bun:1.4.0-alpine

WORKDIR /app

COPY package.json bun.lock ./
RUN bun install --frozen-lockfile --production

COPY src ./src

USER bun

ENV PORT=3000
EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD ["bun", "-e", "const r=await fetch('http://127.0.0.1:'+(process.env.PORT||3000)+'/health'); if(!r.ok) process.exit(1)"]

CMD ["bun", "src/server.js"]
