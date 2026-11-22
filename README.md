# Buscador del catálogo de perfumes

Prototipo en Python. Incluye búsqueda básica por nombre y búsqueda avanzada por marca, género, familia olfativa, rango de precio, presentación y disponibilidad.

## Ejecutar localmente

Desde la carpeta del repositorio:

```bash
python -m app.main
```

El servidor local escucha en `http://127.0.0.1:8000`.

Al abrir esa dirección aparece el catálogo visual. Se pueden consultar los 20
perfumes, buscar por nombre, combinar filtros y abrir el detalle al pulsar una
tarjeta o su imagen. La presentación se adapta a pantallas pequeñas y el detalle
se puede cerrar con el botón o con Escape.

El catálogo utiliza las rutas de búsqueda existentes. Los cambios de esta copia
añaden la interfaz en `app/web` y la entrega de esos archivos desde `app/main.py`.
Los módulos de búsqueda y los datos de Losada se conservan.

Las ilustraciones locales se usan cuando un producto no tiene `image_url` o la
fotografía falla. Las imágenes definitivas deben acordarse con el equipo. Esta
parte todavía no implementa registro, inicio de sesión ni carrito.

## Comprobar la integración

```bash
python -m unittest discover -s tests -v
```

La base de esta copia es el commit
`37c6325bf78f6fd46f14d7bb708f881186112a83` de `abiismo/TSP`.
La propuesta debe integrarse con el equipo antes de reemplazar su versión.

## Rutas disponibles

- `GET /health`: comprueba que el servicio esté activo.
- `GET /api/search/basic?q=alba`: busca coincidencias en el nombre del perfume y ordena por relevancia.
- `GET /api/search/advanced?gender=Femenino&family=Floral&min_price=70000&in_stock=true`: filtra el catálogo por características. Los filtros se pueden combinar y todos son opcionales.
- La ruta avanzada también acepta `q`, `brand`, `max_price` y `presentation_ml`.

El catálogo actual contiene datos ficticios de demostración en `app/catalog.py`. Deben reemplazarse por los productos acordados por el equipo. La búsqueda funciona sobre esos datos locales; no depende de una API externa de perfumes.
