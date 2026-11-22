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
parte incluye ahora inicio y cierre de sesión. El registro público y el carrito
siguen pendientes de integrar con el equipo.

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

## Inicio de sesión

El botón «Iniciar sesión» del catálogo permite entrar con correo y contraseña.
La sesión se conserva al recargar y se puede cerrar desde el encabezado.
Una cuenta inexistente y una contraseña incorrecta muestran el mismo mensaje.
El catálogo continúa siendo público, como en la versión anterior.

Para crear una cuenta local de prueba, desde la carpeta del repositorio:

```bash
python -m app.auth
python -m app.main
```

La primera orden solicita correo, nombre y contraseña sin mostrarla en pantalla.
No hay cuentas ni contraseñas predefinidas. La contraseña nueva debe tener entre
15 y 128 caracteres. La base SQLite se crea en `data/auth.sqlite3`, excluida de Git.
Se puede elegir otra ubicación con la variable de entorno `TSP_AUTH_DB`.
La base contiene datos privados y no debe subirse a GitHub ni compartirse.

### Conexión con el registro de Timoteo

El registro aún no aparece en el repositorio revisado. Su integración debe crear
las cuentas mediante el mismo almacén, desde su manejador de registro:

```python
from app.auth import AuthStore

account = AuthStore().create_user(email, password, name)
```

Devuelve `id`, `email` y `name`. Rechaza correos duplicados y entradas inválidas con
`ValueError`. Ambos módulos deben usar la misma base y variable `TSP_AUTH_DB`.
Si su registro ya usa otra base o esquema, debemos adaptar este almacén antes de
considerar terminada la integración. No se añadió una segunda pantalla de registro.

### Rutas de autenticación y protección

- `POST /api/auth/login`: JSON con `email` y `password`; devuelve usuario y token
  CSRF. La cookie de sesión se envía en `Set-Cookie`.
- `GET /api/auth/session`: devuelve `authenticated` y, si corresponde, usuario y
  token CSRF. No devuelve contraseñas ni el identificador de sesión en el cuerpo.
- `POST /api/auth/logout`: JSON vacío y cabecera `X-CSRF-Token` obtenida de la sesión.

Las escrituras requieren `Origin` exactamente igual al origen de la aplicación y
`Content-Type: application/json`. No se habilita CORS. Las respuestas de cuenta
usan `Cache-Control: no-store`. La cookie es `HttpOnly`, `SameSite=Lax` y dura ocho
horas; el servidor también comprueba el vencimiento. En HTTPS añade `Secure`.
Cerrar sesión invalida el token en el servidor. Al entrar de nuevo se reemplaza
la cookie anterior. Las contraseñas usan PBKDF2-HMAC-SHA256 con 600 000 iteraciones
y sal aleatoria por cuenta; los identificadores de sesión se guardan como hashes.
Después de cinco fallos por correo o veinte por IP en quince minutos se limita el
acceso temporalmente. Los intentos se conservan al reiniciar el servidor.

Esta ejecución con `wsgiref` es para demostración local. Una publicación real
requiere un servidor de aplicación y HTTPS correctamente configurado.

Referencias: [OWASP Password Storage](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html),
[OWASP Session Management](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html).
