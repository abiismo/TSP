"""Integration checks for David's catalog and the existing search API."""

import json
import unittest
from urllib.parse import urlencode
from wsgiref.util import setup_testing_defaults

from app.main import application


def request(path, params=None):
    environ = {}
    setup_testing_defaults(environ)
    environ["PATH_INFO"] = path
    environ["QUERY_STRING"] = urlencode(params or {})
    response = {}

    def start_response(status, headers):
        response["status"] = status
        response["headers"] = dict(headers)

    response["body"] = b"".join(application(environ, start_response))
    return response


class CatalogIntegrationTests(unittest.TestCase):
    def test_catalog_page_and_assets_are_served(self):
        for path, mime in [("/", "text/html"), ("/static/catalog.css", "text/css"),
                           ("/static/catalog.js", "text/javascript"), ("/static/perfume.svg", "image/svg+xml"),
                           ("/static/auth.js", "text/javascript"), ("/static/auth.css", "text/css")]:
            with self.subTest(path=path):
                response = request(path)
                self.assertEqual(response["status"], "200 OK")
                self.assertTrue(response["headers"]["Content-Type"].startswith(mime))
                self.assertEqual(int(response["headers"]["Content-Length"]), len(response["body"]))
                self.assertTrue(response["body"])

    def test_static_file_allowlist_does_not_expose_source(self):
        for path in ["/static/../main.py", "/static/main.py", "/static/../../pyproject.toml"]:
            with self.subTest(path=path):
                self.assertEqual(request(path)["status"], "404 Not Found")

    def test_health_endpoint_still_works(self):
        self.assertEqual(json.loads(request("/health")["body"]), {"status": "ok"})

    def test_initial_catalog_contains_twenty_distinct_products_with_details(self):
        result = json.loads(request("/api/search/advanced")["body"])
        self.assertEqual(len(result), 20)
        self.assertEqual(len({product["id"] for product in result}), 20)
        for product in result:
            for field in ["name", "brand", "gender", "family", "price", "presentation_ml", "stock", "description", "image_url"]:
                self.assertIn(field, product)
            self.assertGreaterEqual(product["stock"], 0)

    def test_search_is_case_and_accent_insensitive(self):
        for path in ["/api/search/basic", "/api/search/advanced"]:
            with self.subTest(path=path):
                result = json.loads(request(path, {"q": "INDIGO"})["body"])
                self.assertEqual([product["id"] for product in result], ["P009"])

    def test_combined_filters_must_all_match(self):
        result = json.loads(request("/api/search/advanced", {
            "q": "aroma", "brand": "Esencia Demo", "gender": "Femenino",
            "family": "Floral", "min_price": 89000, "max_price": 92000,
            "presentation_ml": 50, "in_stock": "true",
        })["body"])
        self.assertEqual({product["id"] for product in result}, {"P001", "P010"})

    def test_unknown_name_has_no_results(self):
        self.assertEqual(json.loads(request("/api/search/advanced", {"q": "inexistente"})["body"]), [])

    def test_available_filter_excludes_sold_out_perfume(self):
        result = json.loads(request("/api/search/advanced", {"in_stock": "true"})["body"])
        self.assertEqual(len(result), 19)
        self.assertTrue(all(product["stock"] > 0 for product in result))
        sold_out = json.loads(request("/api/search/advanced", {"q": "Faro"})["body"])
        self.assertEqual(sold_out[0]["stock"], 0)

    def test_price_boundaries_are_inclusive(self):
        result = json.loads(request("/api/search/advanced", {"min_price": 89000, "max_price": 89000})["body"])
        self.assertEqual([product["id"] for product in result], ["P001"])

    def test_invalid_numeric_filter_returns_useful_error(self):
        response = request("/api/search/advanced", {"min_price": "texto"})
        self.assertEqual(response["status"], "400 Bad Request")
        self.assertIn("error", json.loads(response["body"]))


if __name__ == "__main__":
    unittest.main()
