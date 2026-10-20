# Modos de caída y medición de RTO

Las pruebas de resiliencia (F4: E1, E3) distinguen dos formas de provocar una
caída. La diferencia importa porque cambia quién reinicia el componente y, por
tanto, qué se está midiendo.

## Modo A — parada externa (`docker kill` / `docker stop`)

- **Qué es:** el operador o el arnés de pruebas detiene el contenedor desde
  fuera. `docker kill` cuenta como parada manual: `restart: unless-stopped` **no**
  lo reinicia.
- **Quién reinicia:** el arnés de pruebas, explícitamente.
- **Qué mide:** el **RTO con operador**: detección, decisión y reintento manual.
  Incluye el tiempo humano/orquestado, no solo el arranque del proceso.

## Modo B — caída interna del proceso

- **Qué es:** se mata el proceso **dentro** del contenedor (p. ej.
  `docker exec <c> pkill -9 -f uvicorn`, `docker exec postgres pkill -9 -x postgres`,
  o un fallo real del proceso).
- **Quién reinicia:** la política `restart: unless-stopped` del propio Docker.
- **Qué mide:** el **RTO autónomo**, sin intervención: cuánto tarda la política de
  reinicio en levantar el proceso y volver a `healthy`.
- **Verificación:** `RestartCount` del contenedor aumenta y el healthcheck vuelve a
  `healthy`. `init: true` garantiza que PID 1 reape los hijos; si el proceso
  principal muere, el contenedor sale y Docker lo reinicia.
- **Prueba:** `tests/infra/test_restart.py`, incluida en `make test`. Requiere el
  stack arriba (`make up` previo, como hace CI); si faltan el stack o Docker la
  prueba **falla** en lugar de omitirse.

## Healthchecks

- API: `GET /ready` (BD y dependencias críticas).
- Workers: **heartbeat**. Cada iteración del bucle escribe
  `WORKER_HEARTBEAT_FILE` (por defecto `/tmp/heartbeat`). El healthcheck falla si
  el archivo no existe o tiene más de `3 × <intervalo>` segundos, de modo que un
  bucle bloqueado se detecta y el contenedor se reinicia.
- `postgres`: `pg_isready`.

Ambos modos se usarán en F4 para contrastar RTO con y sin operador.
