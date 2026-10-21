FROM python:3.12-slim AS builder
WORKDIR /build
# Solo pyproject.toml: la capa de dependencias queda cacheada y no se invalida
# cuando cambia el codigo de app/. pyproject.toml es la unica fuente de deps.
COPY pyproject.toml ./
RUN python -c "import tomllib;d=tomllib.load(open('pyproject.toml','rb'))['project']['dependencies'];open('deps.txt','w').write(chr(10).join(d))" \
    && pip install --prefix=/install -r deps.txt

FROM python:3.12-slim AS runtime
RUN useradd --create-home --uid 10001 appuser
ENV PYTHONPATH=/app
WORKDIR /app
COPY --from=builder /install /usr/local
COPY app ./app
COPY migrations ./migrations
COPY alembic.ini ./
USER appuser
EXPOSE 8000
HEALTHCHECK --interval=5s --timeout=5s --start-period=15s --retries=12 \
  CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/ready', timeout=2).status==200 else 1)"]
LABEL com.reservas.project=reservas-platform
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
