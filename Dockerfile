# AguaJusta Oeste — imagen del panel del coordinador.
# Sin secretos: no copia .env ni credenciales. MODO=test por defecto
# (agentes con stubs, sin llamadas a proveedores de LLM).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MODO=test

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src
COPY data/fixtures ./data/fixtures
COPY web/dist ./web/dist

ENV UI=v2

# Usuario sin privilegios; solo data/ es escribible (SQLite + trazas).
RUN useradd --create-home --shell /usr/sbin/nologin appuser \
    && chown -R appuser:appuser /app/data
USER appuser

EXPOSE 8000

# HOST y PORT eligen la escucha (default 127.0.0.1:8000).
# En el contenedor k3s fija HOST=0.0.0.0 via Deployment.
CMD ["python", "-m", "src.coordinator.app"]
