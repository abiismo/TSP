"""Same-origin JSON endpoints for the catalog login."""

import hmac
import json
import sqlite3
from http.cookies import CookieError, SimpleCookie

from app.auth import AuthError, SESSION_SECONDS

COOKIE_NAME = "tsp_session"


def session_token(environ):
    cookie = SimpleCookie()
    try:
        cookie.load(environ.get("HTTP_COOKIE", ""))
        return cookie[COOKIE_NAME].value if COOKIE_NAME in cookie else ""
    except CookieError:
        return ""


def cookie_header(token, secure, clear=False):
    value = f"{COOKIE_NAME}={token}; Path=/; HttpOnly; SameSite=Lax; Max-Age={0 if clear else SESSION_SECONDS}"
    if secure:
        value += "; Secure"
    return ("Set-Cookie", value)


def auth_response(environ, store):
    path = environ["PATH_INFO"]
    method = environ.get("REQUEST_METHOD", "GET").upper()
    headers = [("Cache-Control", "no-store"), ("X-Content-Type-Options", "nosniff")]
    token = session_token(environ)
    secure = environ.get("wsgi.url_scheme") == "https"
    try:
        if path not in {"/api/auth/login", "/api/auth/session", "/api/auth/logout"}:
            raise AuthError(404, "Ruta no encontrada")
        expected_method = "GET" if path.endswith("/session") else "POST"
        if method != expected_method:
            headers.append(("Allow", expected_method))
            raise AuthError(405, "Método no permitido.")
        if method == "GET":
            result = store.session(token)
            if token and not result["authenticated"]:
                headers.append(cookie_header("", secure, clear=True))
            return 200, result, headers

        # Reject cross-site writes, including login CSRF; no CORS is enabled.
        host = environ.get("HTTP_HOST") or environ.get("SERVER_NAME", "localhost")
        expected_origin = f"{environ.get('wsgi.url_scheme', 'http')}://{host}"
        origin = environ.get("HTTP_ORIGIN", "")
        if not origin or origin != expected_origin:
            raise AuthError(403, "La solicitud debe realizarse desde el catálogo.")
        if environ.get("CONTENT_TYPE", "").split(";", 1)[0].strip() != "application/json":
            raise AuthError(415, "Envía la solicitud en formato JSON.")
        try:
            length = int(environ.get("CONTENT_LENGTH") or 0)
        except (TypeError, ValueError):
            raise AuthError(400, "La solicitud no es válida.")
        if length <= 0 or length > 4096:
            raise AuthError(413 if length > 4096 else 400, "La solicitud no es válida.")
        try:
            data = json.loads(environ["wsgi.input"].read(length).decode("utf-8"))
        except (ValueError, UnicodeError):
            raise AuthError(400, "La solicitud no contiene un JSON válido.")
        if not isinstance(data, dict):
            raise AuthError(400, "La solicitud no es válida.")
        if path.endswith("/login"):
            new_token, result = store.login(data.get("email"), data.get("password"), environ.get("REMOTE_ADDR", ""))
            store.logout(token)
            headers.append(cookie_header(new_token, secure))
            return 200, result, headers
        session = store.session(token)
        if not session["authenticated"]:
            raise AuthError(401, "La sesión ya terminó. Vuelve a iniciar sesión.")
        csrf = environ.get("HTTP_X_CSRF_TOKEN", "")
        if not csrf or not hmac.compare_digest(csrf.encode(), session["csrf_token"].encode()):
            raise AuthError(403, "No pudimos verificar la solicitud. Recarga la página.")
        store.logout(token)
        headers.append(cookie_header("", secure, clear=True))
        return 200, {"authenticated": False}, headers
    except AuthError as error:
        if error.status == 429:
            headers.append(("Retry-After", "900"))
        return error.status, {"error": str(error)}, headers
    except (sqlite3.Error, OSError):
        return 503, {"error": "No pudimos acceder a tu cuenta. Inténtalo más tarde."}, headers
