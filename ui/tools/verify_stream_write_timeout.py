"""A stalled stream reader must not hold the gameplay thread indefinitely."""
import ast
import json
import pathlib
import socket
import threading
import time
from socketserver import _SocketWriter

source = pathlib.Path(__file__).resolve().parents[1] / 'server/ui_server.py'
tree = ast.parse(source.read_text())
handler = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'H')
methods = [n for n in handler.body if isinstance(n, ast.FunctionDef)
           and n.name in {'_stream_start', '_stream_line'}]
ns = {'json': json, 'STREAM_WRITE_TIMEOUT_SECONDS': 0.1}
node = ast.ClassDef(name='H', bases=[], keywords=[], decorator_list=[], body=methods)
exec(compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])),
             '<real stream writer>', 'exec'), ns)

writer, reader = socket.socketpair()
writer.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 4096)
h = ns['H']()
h.connection = writer
h.wfile = _SocketWriter(writer)
h.send_response = lambda *args: None
h.send_header = lambda *args: None
h.end_headers = lambda: None
result = []
errors = []

def publish():
    try:
        h._stream_start()
        result.append(h._stream_line({'event': 'x' * (2 * 1024 * 1024)}))
    except Exception as exc:
        errors.append(exc)

thread = threading.Thread(target=publish, daemon=True)
try:
    thread.start()
    thread.join(0.8)
    assert not thread.is_alive(), 'stalled socket write still blocks gameplay'
    assert not errors, errors
    assert result == [False], result
    assert writer.gettimeout() == 0.1
finally:
    reader.close()
    writer.close()
    thread.join(1)

# Header failure also abandons transport without abandoning engine execution.
h = ns['H']()
h.connection = type('Connection', (), {'settimeout': lambda self, seconds: None})()
h.send_response = lambda *args: None
h.send_header = lambda *args: None
def failed_headers():
    raise TimeoutError('blocked headers')
h.end_headers = failed_headers
assert h._stream_start() is False
print('PASS: stalled stream writes and headers return failure within a bounded time')
