# Diagrama ER — `hotel_db`

Fuente Mermaid generada desde el catálogo real. GitHub la renderiza;
para exportar PNG/SVG, pega el bloque en <https://mermaid.live>.
Se omiten `alembic_version` (infraestructura) y los datos. Dueño: `hotel`.

```mermaid
erDiagram
    HOTELS {
        uuid id PK
        varchar name
        varchar city
        timestamptz created_at
    }
    ROOMS {
        uuid id PK
        uuid hotel_id FK
        varchar name
        int capacity
        int price_per_night_cents
        varchar currency
        timestamptz created_at
    }
    HOTELS ||--o{ ROOMS : "rooms_hotel_id_fkey"
```

## Restricciones CHECK y UNIQUE compuestas

Se validan en la base y no se dibujan como aristas:

- `rooms.rooms_capacity_check`: `CHECK (((capacity >= 1) AND (capacity <= 10)))`
- `rooms.rooms_currency_check`: `CHECK (((currency)::text = 'USD'::text))`
- `rooms.rooms_price_check`: `CHECK ((price_per_night_cents > 0))`
