import json
from http.server import BaseHTTPRequestHandler, HTTPServer

from app.backend.anomalies import handler as anomalies_handler
from app.backend.chat import handler as chat_handler
from app.backend.consumption import handler as consumption_handler
from app.backend.forecast import handler as forecast_handler

PORT = 8080

# Çdo adresë lidhet me handler-in e vet
ROUTES = {
    ("GET", "/consumption"): consumption_handler,
    ("GET", "/anomalies"): anomalies_handler,
    ("GET", "/forecast"): forecast_handler,
    ("POST", "/chat"): chat_handler,
}


class ApiRequestHandler(BaseHTTPRequestHandler):
    def _send(self, status, body):
        data = body.encode("utf-8") if body else b""
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        # Lejon React (një port tjetër) ta thërrasë këtë API
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _handle(self, method):
        path = self.path.split("?")[0]
        route = ROUTES.get((method, path))
        if route is None:
            self._send(404, json.dumps({"error": "Not found"}))
            return

        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8") if length else None

        # Formë e thjeshtuar e ngjarjes që AWS Lambda i jep handler-it
        event = {"httpMethod": method, "path": path, "body": body}
        result = route(event, None)
        self._send(result["statusCode"], result["body"])

    def do_GET(self):
        self._handle("GET")

    def do_POST(self):
        self._handle("POST")

    def do_OPTIONS(self):
        self._send(204, "")


if __name__ == "__main__":
    print(f"Server running at http://localhost:{PORT}")
    HTTPServer(("", PORT), ApiRequestHandler).serve_forever()