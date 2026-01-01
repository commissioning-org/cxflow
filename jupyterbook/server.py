"""
CXFlow Jupyter Book Live Server

Development server with hot reload, live preview, and file watching.
"""

from __future__ import annotations

import os
import sys
import json
import time
import asyncio
import mimetypes
import threading
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable, Set
from datetime import datetime
import logging
import hashlib
import signal

logger = logging.getLogger(__name__)


# ============================================================================
# File Watcher
# ============================================================================

@dataclass
class FileChange:
    """Represents a file change event."""
    path: Path
    event_type: str  # 'created', 'modified', 'deleted', 'moved'
    timestamp: float = field(default_factory=time.time)
    
    def __hash__(self):
        return hash((str(self.path), self.event_type))


class FileWatcher:
    """
    Watches directories for file changes.
    
    Simple polling-based watcher that works across platforms.
    """
    
    def __init__(
        self,
        paths: List[Path],
        callback: Callable[[List[FileChange]], None],
        ignore_patterns: Optional[List[str]] = None,
        poll_interval: float = 0.5,
    ):
        """
        Initialize file watcher.
        
        Args:
            paths: Directories to watch
            callback: Function called with list of changes
            ignore_patterns: Glob patterns to ignore
            poll_interval: Polling interval in seconds
        """
        self.paths = [Path(p) for p in paths]
        self.callback = callback
        self.ignore_patterns = ignore_patterns or [
            '**/.*', '**/__pycache__/**', '**/node_modules/**',
            '**/_build/**', '**/.git/**', '**/*.pyc',
        ]
        self.poll_interval = poll_interval
        
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._file_hashes: Dict[str, str] = {}
        self._file_mtimes: Dict[str, float] = {}
    
    def start(self):
        """Start watching for changes."""
        if self._running:
            return
        
        self._running = True
        self._scan_files()  # Initial scan
        
        self._thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._thread.start()
        
        logger.info(f"Started file watcher for {len(self.paths)} paths")
    
    def stop(self):
        """Stop watching for changes."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
        logger.info("Stopped file watcher")
    
    def _watch_loop(self):
        """Main watching loop."""
        while self._running:
            changes = self._check_changes()
            if changes:
                try:
                    self.callback(changes)
                except Exception as e:
                    logger.error(f"Error in file watcher callback: {e}")
            
            time.sleep(self.poll_interval)
    
    def _scan_files(self) -> Dict[str, str]:
        """Scan all files and compute hashes."""
        files = {}
        
        for base_path in self.paths:
            if not base_path.exists():
                continue
            
            for path in base_path.rglob('*'):
                if not path.is_file():
                    continue
                
                if self._should_ignore(path):
                    continue
                
                try:
                    stat = path.stat()
                    self._file_mtimes[str(path)] = stat.st_mtime
                    files[str(path)] = self._get_file_hash(path)
                except Exception:
                    pass
        
        self._file_hashes = files
        return files
    
    def _check_changes(self) -> List[FileChange]:
        """Check for file changes."""
        changes = []
        current_files: Set[str] = set()
        
        for base_path in self.paths:
            if not base_path.exists():
                continue
            
            for path in base_path.rglob('*'):
                if not path.is_file():
                    continue
                
                if self._should_ignore(path):
                    continue
                
                path_str = str(path)
                current_files.add(path_str)
                
                try:
                    stat = path.stat()
                    mtime = stat.st_mtime
                    
                    # Check if file is new
                    if path_str not in self._file_hashes:
                        self._file_hashes[path_str] = self._get_file_hash(path)
                        self._file_mtimes[path_str] = mtime
                        changes.append(FileChange(path, 'created'))
                        continue
                    
                    # Check if file was modified (using mtime first for speed)
                    old_mtime = self._file_mtimes.get(path_str, 0)
                    if mtime > old_mtime:
                        new_hash = self._get_file_hash(path)
                        if new_hash != self._file_hashes.get(path_str):
                            self._file_hashes[path_str] = new_hash
                            self._file_mtimes[path_str] = mtime
                            changes.append(FileChange(path, 'modified'))
                
                except Exception:
                    pass
        
        # Check for deleted files
        for path_str in list(self._file_hashes.keys()):
            if path_str not in current_files:
                del self._file_hashes[path_str]
                if path_str in self._file_mtimes:
                    del self._file_mtimes[path_str]
                changes.append(FileChange(Path(path_str), 'deleted'))
        
        return changes
    
    def _should_ignore(self, path: Path) -> bool:
        """Check if path should be ignored."""
        path_str = str(path)
        
        for pattern in self.ignore_patterns:
            if self._matches_pattern(path_str, pattern):
                return True
        
        return False
    
    def _matches_pattern(self, path: str, pattern: str) -> bool:
        """Simple glob pattern matching."""
        import fnmatch
        return fnmatch.fnmatch(path, pattern)
    
    def _get_file_hash(self, path: Path) -> str:
        """Get MD5 hash of file content."""
        try:
            content = path.read_bytes()
            return hashlib.md5(content).hexdigest()
        except Exception:
            return ''


# ============================================================================
# WebSocket Server for Live Reload
# ============================================================================

class WebSocketConnection:
    """Simple WebSocket connection handler."""
    
    def __init__(self, reader, writer):
        self.reader = reader
        self.writer = writer
        self.closed = False
    
    async def send(self, message: str):
        """Send a message to the client."""
        if self.closed:
            return
        
        try:
            # Simple WebSocket frame (text frame)
            data = message.encode('utf-8')
            length = len(data)
            
            if length <= 125:
                header = bytes([0x81, length])
            elif length <= 65535:
                header = bytes([0x81, 126, (length >> 8) & 0xff, length & 0xff])
            else:
                header = bytes([0x81, 127]) + length.to_bytes(8, 'big')
            
            self.writer.write(header + data)
            await self.writer.drain()
        except Exception:
            self.closed = True
    
    async def close(self):
        """Close the connection."""
        self.closed = True
        try:
            self.writer.close()
            await self.writer.wait_closed()
        except Exception:
            pass


class LiveReloadServer:
    """
    WebSocket server for live reload notifications.
    """
    
    def __init__(self, host: str = "localhost", port: int = 35729):
        self.host = host
        self.port = port
        self.connections: List[WebSocketConnection] = []
        self._server = None
    
    async def start(self):
        """Start the WebSocket server."""
        self._server = await asyncio.start_server(
            self._handle_connection,
            self.host,
            self.port,
        )
        logger.info(f"Live reload server started at ws://{self.host}:{self.port}")
    
    async def stop(self):
        """Stop the WebSocket server."""
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        
        for conn in self.connections:
            await conn.close()
        
        self.connections.clear()
    
    async def _handle_connection(self, reader, writer):
        """Handle incoming WebSocket connection."""
        try:
            # Read HTTP upgrade request
            request = await reader.readuntil(b'\r\n\r\n')
            
            # Parse WebSocket key
            key = None
            for line in request.decode().split('\r\n'):
                if line.lower().startswith('sec-websocket-key:'):
                    key = line.split(':', 1)[1].strip()
                    break
            
            if not key:
                writer.close()
                return
            
            # Calculate accept key
            import hashlib
            import base64
            accept = base64.b64encode(
                hashlib.sha1(
                    (key + '258EAFA5-E914-47DA-95CA-C5AB0DC85B11').encode()
                ).digest()
            ).decode()
            
            # Send upgrade response
            response = (
                'HTTP/1.1 101 Switching Protocols\r\n'
                'Upgrade: websocket\r\n'
                'Connection: Upgrade\r\n'
                f'Sec-WebSocket-Accept: {accept}\r\n'
                '\r\n'
            )
            writer.write(response.encode())
            await writer.drain()
            
            # Create connection
            conn = WebSocketConnection(reader, writer)
            self.connections.append(conn)
            
            # Send hello message
            await conn.send(json.dumps({
                'command': 'hello',
                'protocols': ['http://livereload.com/protocols/official-7'],
                'serverName': 'CXFlow Live Reload',
            }))
            
            # Keep connection alive
            while not conn.closed:
                try:
                    data = await asyncio.wait_for(reader.read(1024), timeout=30)
                    if not data:
                        break
                except asyncio.TimeoutError:
                    # Send ping
                    await conn.send(json.dumps({'command': 'ping'}))
                except Exception:
                    break
            
        except Exception as e:
            logger.debug(f"WebSocket error: {e}")
        finally:
            if conn in self.connections:
                self.connections.remove(conn)
            try:
                writer.close()
            except Exception:
                pass
    
    async def notify_reload(self, path: Optional[str] = None):
        """Notify all clients to reload."""
        message = json.dumps({
            'command': 'reload',
            'path': path or '',
            'liveCSS': True,
            'liveImg': True,
        })
        
        for conn in list(self.connections):
            await conn.send(message)
        
        logger.debug(f"Sent reload notification to {len(self.connections)} clients")


# ============================================================================
# Development Server
# ============================================================================

class DevServer:
    """
    Development server with live reload.
    """
    
    def __init__(
        self,
        project_dir: Path,
        port: int = 3000,
        host: str = "localhost",
        livereload_port: int = 35729,
        auto_build: bool = True,
        open_browser: bool = True,
    ):
        """
        Initialize development server.
        
        Args:
            project_dir: Project directory
            port: HTTP server port
            host: Server host
            livereload_port: Live reload WebSocket port
            auto_build: Automatically rebuild on changes
            open_browser: Open browser on start
        """
        self.project_dir = Path(project_dir)
        self.port = port
        self.host = host
        self.livereload_port = livereload_port
        self.auto_build = auto_build
        self.open_browser = open_browser
        
        self.build_dir = self.project_dir / "_build" / "site"
        
        self._http_server = None
        self._livereload = None
        self._watcher = None
        self._loop = None
        self._build_lock = asyncio.Lock()
        self._last_build = 0
    
    async def start(self):
        """Start the development server."""
        self._loop = asyncio.get_event_loop()
        
        # Initial build
        await self._build()
        
        # Start live reload server
        self._livereload = LiveReloadServer(self.host, self.livereload_port)
        await self._livereload.start()
        
        # Start file watcher
        if self.auto_build:
            self._start_watcher()
        
        # Start HTTP server
        await self._start_http_server()
        
        print(f"\n🚀 Development server started!")
        print(f"   Local:       http://{self.host}:{self.port}")
        print(f"   Live Reload: ws://{self.host}:{self.livereload_port}")
        print(f"\n   Press Ctrl+C to stop\n")
        
        # Open browser
        if self.open_browser:
            import webbrowser
            webbrowser.open(f"http://{self.host}:{self.port}")
        
        # Keep running
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            await self.stop()
    
    async def stop(self):
        """Stop the development server."""
        if self._watcher:
            self._watcher.stop()
        
        if self._livereload:
            await self._livereload.stop()
        
        if self._http_server:
            self._http_server.close()
            await self._http_server.wait_closed()
        
        print("\n👋 Server stopped")
    
    async def _start_http_server(self):
        """Start HTTP server."""
        self._http_server = await asyncio.start_server(
            self._handle_http_request,
            self.host,
            self.port,
        )
    
    async def _handle_http_request(self, reader, writer):
        """Handle HTTP request."""
        try:
            request_line = await reader.readline()
            if not request_line:
                writer.close()
                return
            
            # Parse request
            parts = request_line.decode().strip().split()
            if len(parts) < 2:
                writer.close()
                return
            
            method, path = parts[0], parts[1]
            
            # Read headers
            headers = {}
            while True:
                line = await reader.readline()
                if line == b'\r\n':
                    break
                if b':' in line:
                    key, value = line.decode().split(':', 1)
                    headers[key.strip().lower()] = value.strip()
            
            # Handle request
            if method == 'GET':
                await self._serve_file(writer, path)
            else:
                await self._send_response(writer, 405, 'Method Not Allowed')
        
        except Exception as e:
            logger.debug(f"HTTP error: {e}")
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass
    
    async def _serve_file(self, writer, path: str):
        """Serve a static file."""
        # Clean path
        if path == '/':
            path = '/index.html'
        
        path = path.split('?')[0]  # Remove query string
        
        # Map to file
        file_path = self.build_dir / path.lstrip('/')
        
        # Check for directory
        if file_path.is_dir():
            file_path = file_path / 'index.html'
        
        # Check if file exists
        if not file_path.exists() or not file_path.is_file():
            await self._send_response(writer, 404, 'Not Found', f'File not found: {path}')
            return
        
        # Check if file is within build directory (security)
        try:
            file_path.resolve().relative_to(self.build_dir.resolve())
        except ValueError:
            await self._send_response(writer, 403, 'Forbidden')
            return
        
        # Get content type
        content_type, _ = mimetypes.guess_type(str(file_path))
        content_type = content_type or 'application/octet-stream'
        
        # Read file
        content = file_path.read_bytes()
        
        # Inject live reload script for HTML files
        if content_type == 'text/html':
            content = self._inject_livereload(content)
        
        # Send response
        response = (
            f'HTTP/1.1 200 OK\r\n'
            f'Content-Type: {content_type}\r\n'
            f'Content-Length: {len(content)}\r\n'
            f'Cache-Control: no-cache\r\n'
            f'Connection: close\r\n'
            f'\r\n'
        )
        
        writer.write(response.encode() + content)
        await writer.drain()
    
    async def _send_response(
        self,
        writer,
        status: int,
        status_text: str,
        body: str = '',
    ):
        """Send HTTP response."""
        body_bytes = body.encode('utf-8')
        response = (
            f'HTTP/1.1 {status} {status_text}\r\n'
            f'Content-Type: text/plain\r\n'
            f'Content-Length: {len(body_bytes)}\r\n'
            f'Connection: close\r\n'
            f'\r\n'
        )
        writer.write(response.encode() + body_bytes)
        await writer.drain()
    
    def _inject_livereload(self, content: bytes) -> bytes:
        """Inject live reload script into HTML."""
        script = f'''
<script>
(function() {{
    var ws = new WebSocket('ws://{self.host}:{self.livereload_port}');
    ws.onmessage = function(e) {{
        var data = JSON.parse(e.data);
        if (data.command === 'reload') {{
            if (data.liveCSS && data.path.endsWith('.css')) {{
                // Reload CSS only
                var links = document.querySelectorAll('link[rel="stylesheet"]');
                links.forEach(function(link) {{
                    var href = link.getAttribute('href');
                    link.setAttribute('href', href.split('?')[0] + '?t=' + Date.now());
                }});
            }} else {{
                location.reload();
            }}
        }}
    }};
    ws.onclose = function() {{
        console.log('Live reload disconnected. Reconnecting...');
        setTimeout(function() {{ location.reload(); }}, 1000);
    }};
}})();
</script>
'''
        
        # Insert before </body>
        content_str = content.decode('utf-8')
        if '</body>' in content_str:
            content_str = content_str.replace('</body>', script + '</body>')
        else:
            content_str += script
        
        return content_str.encode('utf-8')
    
    def _start_watcher(self):
        """Start file watcher."""
        watch_paths = [
            self.project_dir,
        ]
        
        self._watcher = FileWatcher(
            paths=watch_paths,
            callback=self._on_file_change,
            ignore_patterns=[
                '**/_build/**',
                '**/.*',
                '**/__pycache__/**',
                '**/*.pyc',
            ],
        )
        self._watcher.start()
    
    def _on_file_change(self, changes: List[FileChange]):
        """Handle file changes."""
        # Debounce - wait for changes to settle
        now = time.time()
        if now - self._last_build < 0.5:
            return
        
        self._last_build = now
        
        # Log changes
        for change in changes:
            logger.info(f"File {change.event_type}: {change.path.name}")
        
        # Schedule rebuild
        if self._loop:
            asyncio.run_coroutine_threadsafe(
                self._rebuild_and_reload(changes),
                self._loop
            )
    
    async def _rebuild_and_reload(self, changes: List[FileChange]):
        """Rebuild and notify clients."""
        async with self._build_lock:
            # Check if only CSS changed
            css_only = all(
                c.path.suffix == '.css' for c in changes
            )
            
            # Rebuild
            success = await self._build()
            
            if success and self._livereload:
                # Notify reload
                if css_only:
                    await self._livereload.notify_reload(str(changes[0].path))
                else:
                    await self._livereload.notify_reload()
    
    async def _build(self) -> bool:
        """Build the project."""
        from .book_builder import BookBuilder
        
        try:
            print("📦 Building...", end=' ', flush=True)
            start = time.time()
            
            builder = BookBuilder(self.project_dir)
            result = builder.build_html(output_dir=self.build_dir)
            
            duration = time.time() - start
            
            if result.success:
                print(f"done in {duration:.2f}s")
                return True
            else:
                print(f"failed: {result.errors}")
                return False
        
        except Exception as e:
            print(f"error: {e}")
            logger.exception("Build failed")
            return False


# ============================================================================
# CLI Entry Point
# ============================================================================

def run_dev_server(
    project_dir: str = ".",
    port: int = 3000,
    host: str = "localhost",
    open_browser: bool = True,
):
    """
    Run the development server.
    
    Args:
        project_dir: Project directory path
        port: HTTP server port
        host: Server host
        open_browser: Open browser on start
    """
    server = DevServer(
        project_dir=Path(project_dir),
        port=port,
        host=host,
        open_browser=open_browser,
    )
    
    # Handle shutdown gracefully
    def signal_handler(sig, frame):
        print("\nShutting down...")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Run server
    asyncio.run(server.start())


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="CXFlow Book Development Server")
    parser.add_argument("path", nargs="?", default=".", help="Project directory")
    parser.add_argument("--port", "-p", type=int, default=3000, help="HTTP port")
    parser.add_argument("--host", "-H", default="localhost", help="Host")
    parser.add_argument("--no-browser", action="store_true", help="Don't open browser")
    
    args = parser.parse_args()
    
    run_dev_server(
        project_dir=args.path,
        port=args.port,
        host=args.host,
        open_browser=not args.no_browser,
    )
