#!/usr/bin/env python3
"""
Mock competitor website server for testing the monitoring pipeline.

Serves HTML pages from v1/ or v2/ directories. Switch versions at runtime
to simulate a competitor updating their website.

Usage:
    python3 test-site/server.py              # Start on port 8888
    python3 test-site/server.py --port 9999  # Custom port

Endpoints:
    /pricing    — Pricing page
    /product    — Product page
    /partners   — Partners page
    /blog       — Blog page
    /switch/v1  — Switch all pages to version 1 (original)
    /switch/v2  — Switch all pages to version 2 (updated — triggers changes)
    /status     — Show current version being served
    /sitemap.xml — XML sitemap (for source discovery testing)
"""

import argparse
import json
import os
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

BASE_DIR = Path(__file__).parent
CURRENT_VERSION = "v1"

PAGES = {
    "/pricing": "pricing.html",
    "/product": "product.html",
    "/partners": "partners.html",
    "/blog": "blog.html",
    "/careers": "careers.html",
}


class MockCompetitorHandler(SimpleHTTPRequestHandler):

    def do_GET(self):
        global CURRENT_VERSION
        path = self.path.split("?")[0]  # strip query params

        # Version switching
        if path == "/switch/v1":
            CURRENT_VERSION = "v1"
            self._json_response({"version": "v1", "message": "Switched to v1 (original). Scrape again to get baseline."})
            return
        if path == "/switch/v2":
            CURRENT_VERSION = "v2"
            self._json_response({"version": "v2", "message": "Switched to v2 (updated). Scrape again to detect changes!"})
            return

        # Status
        if path == "/status":
            self._json_response({
                "version": CURRENT_VERSION,
                "pages": list(PAGES.keys()),
                "hint": "Visit /switch/v2 to simulate competitor updates, then re-scrape.",
            })
            return

        # Sitemap
        if path == "/sitemap.xml":
            self._serve_sitemap()
            return

        # Static files (CSS, JS, images)
        if path.startswith("/static/"):
            file_path = BASE_DIR / path.lstrip("/")
            if file_path.exists():
                content_types = {
                    ".css": "text/css",
                    ".js": "application/javascript",
                    ".png": "image/png",
                    ".jpg": "image/jpeg",
                    ".svg": "image/svg+xml",
                    ".ico": "image/x-icon",
                }
                ext = file_path.suffix
                self.send_response(200)
                self.send_header("Content-Type", content_types.get(ext, "application/octet-stream"))
                self.end_headers()
                self.wfile.write(file_path.read_bytes())
                return

        # Serve pages
        if path in PAGES:
            file_path = BASE_DIR / CURRENT_VERSION / PAGES[path]
            if file_path.exists():
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(file_path.read_bytes())
                return

        # Homepage
        if path == "/" or path == "":
            self._serve_homepage()
            return

        self.send_error(404, f"Page not found: {path}")

    def _json_response(self, data):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2).encode())

    def _serve_homepage(self):
        html = f"""<!DOCTYPE html>
<html><head><title>TestRival — Test Server</title><link rel="stylesheet" href="/static/style.css"></head>
<body>
<nav class="navbar"><div class="navbar-inner">
  <a href="/" class="navbar-logo">&#9670; Test<span>Rival</span></a>
  <ul class="navbar-links">
    <li><a href="/product">Product</a></li>
    <li><a href="/pricing">Pricing</a></li>
    <li><a href="/partners">Partners</a></li>
    <li><a href="/blog">Blog</a></li>
  </ul>
</div></nav>
<section class="hero">
  <span class="badge badge-{'green' if CURRENT_VERSION == 'v1' else 'orange'}">Serving Version {CURRENT_VERSION[1:]}</span>
  <h1>TestRival Mock Server</h1>
  <p>Test competitor website for the monitoring pipeline. Browse the pages below, then switch versions to simulate competitor updates.</p>
  <div class="hero-buttons">
    <a href="/switch/v1" class="btn-{'primary' if CURRENT_VERSION == 'v1' else 'secondary'}">v1 (Original)</a>
    <a href="/switch/v2" class="btn-{'primary' if CURRENT_VERSION == 'v2' else 'secondary'}">v2 (Updated)</a>
  </div>
</section>
<section class="section">
  <div class="section-header"><h2>Changes between v1 and v2</h2><p>Switch to v2, then re-scrape to test change detection.</p></div>
  <div style="max-width:900px; margin:0 auto; overflow-x:auto;">
    <table class="comparison-table">
      <thead><tr><th>Page</th><th>Key Changes in v2</th><th>Expected Detection</th></tr></thead>
      <tbody>
        <tr><td><a href="/pricing">/pricing</a></td><td>Starter $29&rarr;$39 (+34%), Pro $79&rarr;$99 (+25%), Enterprise "Custom"&rarr;$249/user, trial 14d&rarr;7d, CC now required, RivalAI tiers added, HIPAA &amp; data residency</td><td><span class="badge badge-red">CRITICAL</span></td></tr>
        <tr><td><a href="/product">/product</a></td><td>New RivalAI section (6 AI features), multi-cloud (AWS+GCP), ISO 27001 + HIPAA, AI/ML tech stack (PyTorch, RAG), 100+ integrations, new testimonials</td><td><span class="badge badge-orange">HIGH</span></td></tr>
        <tr><td><a href="/partners">/partners</a></td><td>New Strategic Partners section (Salesforce, Microsoft, OpenAI), +Datadog +PagerDuty +Linear, Accenture solution partner, APAC &amp; LATAM resellers</td><td><span class="badge badge-orange">HIGH</span></td></tr>
        <tr><td><a href="/blog">/blog</a></td><td>$75M Series C (Sequoia), RivalAI launch announcement, Salesforce partnership post, team growing to 500+</td><td><span class="badge badge-purple">MEDIUM</span></td></tr>
        <tr><td><a href="/careers">/careers</a></td><td><em>NEW PAGE in v2</em> — 47 open roles, $180K-$300K salaries, hiring ML engineers, remote-first, $75M raised, 500+ employees</td><td><span class="badge badge-orange">HIGH (new page)</span></td></tr>
      </tbody>
    </table>
  </div>
</section>
<footer class="footer"><div class="footer-bottom"><p>Mock server for Competitor Monitoring pipeline testing. Not a real company.</p></div></footer>
</body></html>"""
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode())

    def _serve_sitemap(self):
        port = self.server.server_address[1]
        # Base pages (always present)
        urls = [
            f'  <url><loc>http://localhost:{port}/pricing</loc><changefreq>weekly</changefreq></url>',
            f'  <url><loc>http://localhost:{port}/product</loc><changefreq>monthly</changefreq></url>',
            f'  <url><loc>http://localhost:{port}/partners</loc><changefreq>monthly</changefreq></url>',
            f'  <url><loc>http://localhost:{port}/blog</loc><changefreq>daily</changefreq></url>',
        ]
        # v2 adds new pages (simulates competitor expanding their site)
        if CURRENT_VERSION == "v2":
            urls.append(f'  <url><loc>http://localhost:{port}/careers</loc><changefreq>monthly</changefreq></url>')
        url_block = "\n".join(urls)
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{url_block}
</urlset>"""
        self.send_response(200)
        self.send_header("Content-Type", "application/xml")
        self.end_headers()
        self.wfile.write(xml.encode())

    def log_message(self, format, *args):
        print(f"  [{CURRENT_VERSION}] {args[0]}")


def main():
    parser = argparse.ArgumentParser(description="Mock competitor website server")
    parser.add_argument("--port", type=int, default=8888, help="Port to serve on (default: 8888)")
    args = parser.parse_args()

    server = HTTPServer(("127.0.0.1", args.port), MockCompetitorHandler)
    print(f"Mock competitor 'TestRival' running at http://localhost:{args.port}")
    print(f"  Serving version: {CURRENT_VERSION}")
    print(f"  Pages: {', '.join(PAGES.keys())}")
    print(f"  Switch to v2: http://localhost:{args.port}/switch/v2")
    print(f"  Status: http://localhost:{args.port}/status")
    print()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.shutdown()


if __name__ == "__main__":
    main()
