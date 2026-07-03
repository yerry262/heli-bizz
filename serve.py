#!/usr/bin/env python3
"""Serve the heli-bizz repo on localhost:8777 and open the dashboard."""
import http.server
import os
import webbrowser

PORT = 8777
ROOT = os.path.dirname(os.path.abspath(__file__))
URL = f"http://localhost:{PORT}/dashboard/"


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)


def main():
    with http.server.ThreadingHTTPServer(("127.0.0.1", PORT), Handler) as httpd:
        print(f"Serving {ROOT}")
        print(f"Dashboard: {URL}")
        try:
            webbrowser.open(URL)
        except Exception:
            pass
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nStopped.")


if __name__ == "__main__":
    main()
