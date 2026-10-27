# Guía DBeaver Community — ver y exportar los diagramas

DBeaver **no está instalado** en este entorno. Esta guía son pasos manuales
(no se descargó ni instaló nada). Verificado solo lo que depende del servidor:
puerto `5433`, usuario `postgres`, las 6 bases y el aislamiento de roles.

## 1. Instalar (manual, una vez)

1. Descarga **DBeaver Community** desde <https://dbeaver.io/download/>.
2. Instala con las opciones por defecto.
3. La primera conexión a PostgreSQL descarga el driver JDBC (necesita
   internet). Acepta la descarga que propone DBeaver.

## 2. Crear la conexión (parámetros reales)

`Database` → `New Database Connection` → **PostgreSQL** → `Next`.

| Campo | Valor |
|---|---|
| Server Host | `127.0.0.1` |
| Port | `5433` |
| Database | `postgres` |
| Username | `postgres` |
| Password | la de `POSTGRES_PASSWORD` en `reservas-platform/.env` |

- No copies la contraseña a apuntes, capturas ni al repositorio.
- Marca `Save password` solo si el equipo es personal.
- `Test Connection` → si falla, revisa que el stack dev esté arriba
  (`docker compose -f compose.yaml -f compose.dev.yaml ps`) y que el puerto
  `5433` esté publicado (solo existe en `compose.dev.yaml`).

### Ver las 6 bases en una sola conexión

`Edit Connection` → pestaña **PostgreSQL** → marca `Show all databases`
(según la versión puede estar en las propiedades del driver). Cierra y
reconecta. En el navegador verás:

```
reservas-platform (postgres@127.0.0.1:5433)
└── Databases
    ├── customer_db
    ├── hotel_db
    ├── availability_db
    ├── payment_db
    ├── reservation_db
    └── notification_db
```

Alternativa: una conexión por base, cambiando `Database` y el usuario
(`customer`, `hotel`, …) con la contraseña de `secrets/<servicio>_db_password.txt`.

## 3. Explorar tablas y columnas

`Databases` → `<db>` → `Schemas` → `public` → `Tables` → doble clic en una
tabla para ver datos y en la pestaña `Columns` para tipos, nulabilidad y
defaults. `Constraints` muestra PK/FK/UQ/CHECK e `Indexes` los índices.

Para el informe es más seguro usar `queries.sql` que abrir las tablas crudas:
DBeaver no enmascara `password_hash`, `token_hash` ni `payment_token`.

## 4. Diagrama ER por base

1. Expande `public` → `Tables`.
2. Selecciona todas las tablas (`Ctrl+A`) → clic derecho → **View Diagram**
   (o abre la pestaña `ER Diagram`).
3. Arrastra las entidades para ordenarlas.
4. Exportar: clic derecho sobre el diagrama → **Export Diagram** →
   `PNG` o `SVG` (para el informe conviene SVG; para PowerPoint, PNG).

DBeaver dibuja solo las **FK reales** de esa conexión/base. No puede dibujar
las referencias entre bases distintas porque no existen como FK: para eso usa
`diagrams/logical-global.md`.

## 5. Demostrar el aislamiento por rol

Crea una segunda conexión:

| Campo | Valor |
|---|---|
| Database | `customer_db` |
| Username | `customer` |
| Password | `secrets/customer_db_password.txt` |

Funciona contra `customer_db`. Si cambias `Database` a `hotel_db` y pruebas,
DBeaver muestra `permission denied for database "hotel_db"`: es el diseño
(ADR-0002), no un error de configuración.

## 6. Problemas frecuentes

| Síntoma | Causa / solución |
|---|---|
| `Connection refused` en 5433 | stack apagado o levantado sin `compose.dev.yaml`; usa `make up` |
| `password authentication failed` | contraseña de `.env` (admin) vs `secrets/*.txt` (rol de servicio) |
| No aparecen las 6 bases | activa `Show all databases` o crea conexiones por base |
| El diagrama no muestra relaciones | las relaciones entre servicios son lógicas, no FK (ver `integrity.md`) |
| Quieres una GUI sin instalar nada | Adminer en <http://127.0.0.1:8082> (ver `README.md`) |

## 7. Alternativas

- **Adminer** (web, un contenedor): `README.md` → “Opción rápida”.
- **pgAdmin**, **TablePlus**, **DataGrip**: misma conexión (`127.0.0.1:5433`).
- **Mermaid** para los diagramas ya generados: se renderizan en GitHub;
  para PNG/SVG pega el bloque en <https://mermaid.live>.
