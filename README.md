# Buscador del catálogo de perfumes

Prototipo académico en Python. Incluye búsqueda básica por nombre y búsqueda avanzada por marca, género, familia olfativa, rango de precio, presentación y disponibilidad.

## Ejecutar localmente

Desde la carpeta del repositorio:

```bash
python -m app.main
```

El servidor local escucha en `http://127.0.0.1:8000`.

## Rutas disponibles

- `GET /health`: comprueba que el servicio esté activo.
- `GET /api/search/basic?q=alba`: busca coincidencias en el nombre del perfume y ordena por relevancia.
- `GET /api/search/advanced?gender=Femenino&family=Floral&min_price=70000&in_stock=true`: filtra el catálogo por características. Los filtros se pueden combinar y todos son opcionales.
- La ruta avanzada también acepta `q`, `brand`, `max_price` y `presentation_ml`.

El catálogo actual contiene datos ficticios de demostración en `app/catalog.py`. Deben reemplazarse por los productos acordados por el equipo. La búsqueda funciona sobre esos datos locales; no depende de una API externa de perfumes.
