# F5: Documentación y entrega (entrega: dom 25 oct)

**Regla:** el informe se **ensambla** desde lo ya escrito; no se redacta desde cero (`informe/ESTRUCTURA.md`).

## Documentos por completar
| Documento | Punto del enunciado | Fuente |
|---|---|---|
| `docs/manual.md` | Manual (instalación, uso, pruebas, problemas, reinicio desde cero) | `README`, `F3` |
| `docs/fallos.md` | 9 | `resultados/chaos_*` |
| `docs/seguridad.md` | 12 | ADR-0007, amenazas de `02-plan` §7 |
| `docs/produccion.md` | Evolución | `02-plan` §8, limitaciones |
| `docs/swarm.md` | 10 | qué replicar (availability, reservation-api, payment-api, notification-worker), `deploy.replicas`, `update_config`, secretos, *placement*; qué no (PostgreSQL) |
| `docs/imagenes.md` | 4 | tamaños y decisiones de optimización |
| Costos | Informe §10 | `costos/registro.md` + **precios vigentes con fuente** (se buscan al redactar) |
| `README.md` final | 13/14 | comandos, arquitectura, hallazgos |

## Entrega
- [ ] Trazabilidad requisito → evidencia de los 14 puntos (anexo del informe).
- [ ] **Ensayo desde cero** en una carpeta limpia: `git clone` → `make up seed test e2e invariants chaos perf report` sin intervención.
- [ ] CI en verde; `main` etiquetado **`v1.0-entrega`**; zip de entrega.
- [ ] Informe en el formato que pida la universidad (Word/PDF), con la tesis "más adecuada para este caso", alternativas, costos y limitaciones.
- [ ] Capturas y/o video corto de la demo (plan B de la defensa).
- [ ] Despliegue en línea **solo** si todo lo anterior está hecho (ver `02-plan.md` §6).
