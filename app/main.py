"""Runnable standard-library HTTP API for the sample perfume catalog."""

import json
from http import HTTPStatus
from pathlib import Path
from urllib.parse import parse_qs
from wsgiref.simple_server import make_server

from app.api.routes import advanced_search, basic_search
from app.catalog import SAMPLE_CATALOG
from app.search import CatalogSearch


search_service = CatalogSearch(SAMPLE_CATALOG)
WEB_ROOT = Path(__file__).with_name("web")
WEB_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/static/catalog.css": ("catalog.css", "text/css; charset=utf-8"),
    "/static/catalog.js": ("catalog.js", "text/javascript; charset=utf-8"),
    "/static/perfume.svg": ("perfume.svg", "image/svg+xml"),
}


def application(environ: dict, start_response):
    path = environ.get("PATH_INFO", "/")
    if path in WEB_FILES:
        filename, content_type = WEB_FILES[path]
        body = (WEB_ROOT / filename).read_bytes()
        start_response("200 OK", [("Content-Type", content_type), ("Content-Length", str(len(body)))])
        return [body]
    params = parse_qs(environ.get("QUERY_STRING", ""), keep_blank_values=True)
    query = {key: values[-1] for key, values in params.items()}
    status = HTTPStatus.OK

    try:
        if path == "/api/search/basic":
            result = basic_search(search_service, query.get("q", ""))
        elif path == "/api/search/advanced":
            result = advanced_search(search_service, query)
        elif path == "/health":
            result = {"status": "ok"}
        else:
            status = HTTPStatus.NOT_FOUND
            result = {"error": "Ruta no encontrada"}
    except (TypeError, ValueError) as error:
        status = HTTPStatus.BAD_REQUEST
        result = {"error": f"Parámetro inválido: {error}"}

    body = json.dumps(result, ensure_ascii=False).encode("utf-8")
    start_response(
        f"{status.value} {status.phrase}",
        [("Content-Type", "application/json; charset=utf-8"), ("Content-Length", str(len(body)))],
    )
    return [body]


if __name__ == "__main__":
    with make_server("127.0.0.1", 8000, application) as server:
        print("API de búsqueda disponible en http://127.0.0.1:8000")
        server.serve_forever()
