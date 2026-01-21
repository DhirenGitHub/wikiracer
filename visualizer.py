import asyncio
import json
import threading
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
import websockets
import os
import requests
from urllib.parse import urlparse, parse_qs, urljoin
import re

# Global state for communication
connected_clients = set()
current_highlight = None  # Store current link to highlight

# Cache for resources to speed up loading
resource_cache = {}


class WikiProxyHandler(BaseHTTPRequestHandler):
    """HTTP handler that proxies Wikipedia and injects highlight script."""

    def log_message(self, format, *args):
        pass  # Suppress logging

    def do_GET(self):
        path = self.path

        if path == '/viewer.html':
            self._serve_file('viewer.html', 'text/html')
        elif path.startswith('/wiki/'):
            self._proxy_wikipedia(f'https://en.wikipedia.org{path}')
        elif path.startswith('/w/'):
            self._proxy_resource(f'https://en.wikipedia.org{path}')
        elif path.startswith('/static/'):
            self._proxy_resource(f'https://en.wikipedia.org{path}')
        elif path.startswith('//upload.wikimedia.org/') or path.startswith('/upload.wikimedia.org/'):
            clean_path = path.lstrip('/')
            self._proxy_resource(f'https://{clean_path}')
        elif 'upload.wikimedia.org' in path:
            # Handle various formats of wikimedia URLs
            if path.startswith('/https://'):
                self._proxy_resource(path[1:])
            else:
                self._proxy_resource(f'https://upload.wikimedia.org{path}')
        else:
            # Try to serve as Wikipedia resource
            self._proxy_resource(f'https://en.wikipedia.org{path}')

    def _serve_file(self, filename, content_type):
        try:
            filepath = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
            with open(filepath, 'rb') as f:
                content = f.read()
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', len(content))
            self.end_headers()
            self.wfile.write(content)
        except FileNotFoundError:
            self.send_error(404, 'File not found')

    def _proxy_wikipedia(self, url):
        """Fetch Wikipedia page and inject highlighting script."""
        global current_highlight
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
            }
            resp = requests.get(url, headers=headers)

            content = resp.text

            # Rewrite URLs to go through our proxy
            # Fix protocol-relative URLs for upload.wikimedia.org
            content = content.replace('//upload.wikimedia.org', '/upload.wikimedia.org')

            # Inject our highlight script before </body>
            highlight_script = '''
            <style>
                .wikiracer-highlight {
                    background: linear-gradient(90deg, #e94560, #ff6b6b) !important;
                    color: white !important;
                    padding: 4px 12px !important;
                    border-radius: 6px !important;
                    box-shadow: 0 0 20px #e94560, 0 0 40px #e94560, 0 0 60px rgba(233, 69, 96, 0.5) !important;
                    animation: wikiracer-pulse 0.8s ease-in-out infinite !important;
                    position: relative !important;
                    z-index: 9999 !important;
                    text-decoration: none !important;
                    font-weight: bold !important;
                }
                @keyframes wikiracer-pulse {
                    0%, 100% {
                        box-shadow: 0 0 20px #e94560, 0 0 40px #e94560;
                        transform: scale(1);
                    }
                    50% {
                        box-shadow: 0 0 30px #e94560, 0 0 60px #e94560, 0 0 90px rgba(233, 69, 96, 0.7);
                        transform: scale(1.05);
                    }
                }
                .wikiracer-highlight::before {
                    content: "→ NEXT CLICK";
                    position: absolute;
                    top: -30px;
                    left: 50%;
                    transform: translateX(-50%);
                    background: linear-gradient(90deg, #e94560, #ff6b6b);
                    color: white;
                    padding: 4px 12px;
                    border-radius: 6px;
                    font-size: 11px;
                    font-weight: bold;
                    white-space: nowrap;
                    box-shadow: 0 4px 15px rgba(233, 69, 96, 0.4);
                    animation: bounce 1s ease-in-out infinite;
                }
                @keyframes bounce {
                    0%, 100% { transform: translateX(-50%) translateY(0); }
                    50% { transform: translateX(-50%) translateY(-5px); }
                }
            </style>
            <script>
                let ws;
                function connectWS() {
                    ws = new WebSocket('ws://localhost:8765');
                    ws.onopen = () => {
                        console.log('WikiRacer connected');
                        ws.send(JSON.stringify({ type: 'page_loaded', url: window.location.href }));
                    };
                    ws.onmessage = (event) => {
                        const data = JSON.parse(event.data);
                        if (data.type === 'highlight_link') {
                            highlightLink(data.url, data.name);
                        }
                    };
                    ws.onclose = () => {
                        console.log('WikiRacer disconnected, reconnecting...');
                        setTimeout(connectWS, 1000);
                    };
                }
                connectWS();

                function highlightLink(targetUrl, name) {
                    // Remove previous highlights
                    document.querySelectorAll('.wikiracer-highlight').forEach(el => {
                        el.classList.remove('wikiracer-highlight');
                    });

                    // Extract the wiki path from target URL
                    let targetPath = targetUrl;
                    if (targetUrl.includes('/wiki/')) {
                        targetPath = '/wiki/' + targetUrl.split('/wiki/')[1];
                    }

                    // Find and highlight the link in the main content
                    const contentArea = document.querySelector('#mw-content-text') || document.body;
                    const links = contentArea.querySelectorAll('a[href*="/wiki/"]');

                    for (const link of links) {
                        const href = link.getAttribute('href') || '';

                        // Match by href path
                        if (href === targetPath ||
                            href === targetUrl ||
                            decodeURIComponent(href) === decodeURIComponent(targetPath)) {

                            link.classList.add('wikiracer-highlight');

                            // Scroll to the link with offset
                            setTimeout(() => {
                                const rect = link.getBoundingClientRect();
                                const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
                                const targetY = rect.top + scrollTop - (window.innerHeight / 2);

                                window.scrollTo({
                                    top: targetY,
                                    behavior: 'smooth'
                                });
                            }, 200);

                            console.log('Highlighted:', name, link);
                            return;
                        }
                    }
                    console.log('Could not find link for:', name, targetPath);
                }
            </script>
            '''

            # Inject before </body>
            if '</body>' in content:
                content = content.replace('</body>', highlight_script + '</body>')
            else:
                content += highlight_script

            content_bytes = content.encode('utf-8')

            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', len(content_bytes))
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(content_bytes)

        except Exception as e:
            print(f"Proxy error for {url}: {e}")
            self.send_error(500, str(e))

    def _proxy_resource(self, url):
        """Proxy static resources from Wikipedia/Wikimedia."""
        global resource_cache

        try:
            # Check cache first
            if url in resource_cache:
                cached = resource_cache[url]
                self.send_response(200)
                self.send_header('Content-Type', cached['content_type'])
                self.send_header('Content-Length', len(cached['content']))
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Cache-Control', 'max-age=3600')
                self.end_headers()
                self.wfile.write(cached['content'])
                return

            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': '*/*',
            }
            resp = requests.get(url, headers=headers, timeout=10)

            content_type = resp.headers.get('Content-Type', 'application/octet-stream')

            # Cache the resource
            if len(resp.content) < 1000000:  # Cache files under 1MB
                resource_cache[url] = {
                    'content': resp.content,
                    'content_type': content_type
                }

            self.send_response(resp.status_code)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', len(resp.content))
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Cache-Control', 'max-age=3600')
            self.end_headers()
            self.wfile.write(resp.content)
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
            # Browser cancelled the request - this is normal when navigating away
            pass
        except Exception as e:
            # Return empty response for missing resources
            try:
                self.send_response(404)
                self.end_headers()
            except:
                pass


class VisualizationServer:
    def __init__(self, http_port=8080, ws_port=8765):
        self.http_port = http_port
        self.ws_port = ws_port
        self.loop = None
        self.ws_server = None

    def start(self):
        """Start both HTTP and WebSocket servers in background threads."""
        # Start HTTP server for serving the HTML page and proxying Wikipedia
        http_thread = threading.Thread(target=self._run_http_server, daemon=True)
        http_thread.start()

        # Start WebSocket server for real-time communication
        ws_thread = threading.Thread(target=self._run_ws_server, daemon=True)
        ws_thread.start()

        # Give servers time to start
        import time
        time.sleep(1)

        # Open browser
        webbrowser.open(f'http://localhost:{self.http_port}/viewer.html')

        # Wait for client to connect
        print("  Waiting for browser to connect...")
        timeout = 10
        start = time.time()
        while len(connected_clients) == 0 and (time.time() - start) < timeout:
            time.sleep(0.2)

        if len(connected_clients) == 0:
            print("  Warning: Browser did not connect in time")
            return False

        print("  Browser connected!")
        return True

    def _run_http_server(self):
        """Run HTTP server to serve static files and proxy Wikipedia."""
        os.chdir(os.path.dirname(os.path.abspath(__file__)))
        httpd = HTTPServer(('localhost', self.http_port), WikiProxyHandler)
        httpd.serve_forever()

    def _run_ws_server(self):
        """Run WebSocket server for real-time updates."""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        async def handler(websocket):
            connected_clients.add(websocket)
            try:
                async for message in websocket:
                    # Handle messages from client (like page_loaded)
                    try:
                        data = json.loads(message)
                        if data.get('type') == 'page_loaded':
                            # Page loaded, send pending highlight if any
                            global current_highlight
                            if current_highlight:
                                await websocket.send(json.dumps({
                                    "type": "highlight_link",
                                    **current_highlight
                                }))
                    except:
                        pass
            finally:
                connected_clients.discard(websocket)

        async def main():
            async with websockets.serve(handler, "localhost", self.ws_port):
                await asyncio.Future()  # Run forever

        self.loop.run_until_complete(main())

    def send_event(self, event_type: str, data: dict):
        """Send an event to all connected browsers."""
        if not connected_clients:
            return

        message = json.dumps({"type": event_type, **data})

        # Send to all clients
        async def broadcast():
            for client in connected_clients.copy():
                try:
                    await client.send(message)
                except:
                    connected_clients.discard(client)

        if self.loop:
            asyncio.run_coroutine_threadsafe(broadcast(), self.loop)

    def navigate_to(self, url: str):
        """Tell browser to navigate to a Wikipedia page via proxy."""
        # Convert Wikipedia URL to proxy URL
        proxy_url = url.replace('https://en.wikipedia.org', '')
        self.send_event("navigate", {"url": proxy_url})
        import time
        time.sleep(2.5)  # Wait for page to load

    def highlight_link(self, url: str, name: str):
        """Highlight a link on the current page."""
        global current_highlight
        current_highlight = {"url": url, "name": name}
        self.send_event("highlight_link", {"url": url, "name": name})
        import time
        time.sleep(2)  # Let user see the highlight

    def click_link(self, url: str):
        """Navigate to the next page."""
        global current_highlight
        current_highlight = None  # Clear highlight
        proxy_url = url.replace('https://en.wikipedia.org', '')
        self.send_event("navigate", {"url": proxy_url})
        import time
        time.sleep(2.5)  # Wait for navigation

    def show_status(self, message: str, step: int = None, total: int = None):
        """Show status message in the browser."""
        self.send_event("status", {"message": message, "step": step, "total": total})

    def show_success(self, path: list):
        """Show success message with the path taken."""
        self.send_event("success", {"path": path})

    def show_failure(self, message: str):
        """Show failure message."""
        self.send_event("failure", {"message": message})


# Global visualizer instance
_visualizer = None


def get_visualizer():
    global _visualizer
    if _visualizer is None:
        _visualizer = VisualizationServer()
    return _visualizer
