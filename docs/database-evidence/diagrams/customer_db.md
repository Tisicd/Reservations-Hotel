# Diagrama ER — `customer_db`

Fuente Mermaid generada desde el catálogo real. GitHub la renderiza;
para exportar PNG/SVG, pega el bloque en <https://mermaid.live>.
Se omiten `alembic_version` (infraestructura) y los datos. Dueño: `customer`.

```mermaid
erDiagram
    CUSTOMERS {
        uuid id PK
        varchar name
        varchar email
        timestamptz created_at
        text password_hash
        int failed_attempts
        timestamptz locked_until
        timestamptz last_login_at
    }
    SESSIONS {
        varchar token_hash PK
        uuid customer_id FK
        timestamptz created_at
        timestamptz expires_at
    }
    CUSTOMERS ||--o{ SESSIONS : "sessions_customer_id_fkey"
```

## Restricciones CHECK y UNIQUE compuestas

Se validan en la base y no se dibujan como aristas:

