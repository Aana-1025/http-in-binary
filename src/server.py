"""Sequential file server. Ctrl+C closes the active socket and listener."""

import argparse
import mimetypes
import socket
import sys
from pathlib import Path

from .protocol import (MAX_PAYLOAD, REQUEST, RESPONSE, ProtocolError,
                       decode_request, encode_response, receive_frame, send_frame)


def response_payload(status, body, content_type='text/plain'):
    headers = [('content-type', content_type), ('content-length', str(len(body))),
               ('server', 'bserve/1'), ('cache-control', 'no-store'),
               ('x-protocol-version', '1')]
    return encode_response(status, headers, body)


def file_response(root, path):
    if (not path.startswith('/') or any(c in path for c in '\x00\\:')
            or '..' in path.split('/')):
        return response_payload(400, b'Invalid path\n')
    parts = ['index.html'] if path == '/' else [p for p in path.split('/') if p not in ('', '.')]
    try:
        target = root.joinpath(*parts).resolve()
        if not target.is_relative_to(root):
            return response_payload(400, b'Path outside root\n')
        if not target.is_file():
            return response_payload(404, b'File not found\n')
        content_type = mimetypes.guess_type(str(target))[0] or 'application/octet-stream'
        # Limit the read even if the file grows between size checks and reading.
        with target.open('rb') as source:
            body = source.read(MAX_PAYLOAD + 1)
        payload = response_payload(200, body, content_type)
        if len(payload) > MAX_PAYLOAD:
            return response_payload(500, b'File response exceeds 16 MiB\n')
        return payload
    except (OSError, ValueError, RuntimeError):
        return response_payload(500, b'Unable to read file\n')


def handle_connection(conn, root):
    while True:
        try:
            try:
                frame = receive_frame(conn)
                if frame is None:
                    return
                frame_type, payload = frame
                if frame_type not in (REQUEST, RESPONSE):
                    continue
                if frame_type != REQUEST:
                    raise ProtocolError('expected REQUEST')
                path, _ = decode_request(payload)
                reply = file_response(root, path)
            except ProtocolError as exc:
                send_frame(conn, RESPONSE, response_payload(400, b'Malformed request\n'))
                if exc.fatal:
                    return
                continue
            send_frame(conn, RESPONSE, reply)
        except OSError:
            return  # The peer has disconnected; accept another client.


def main(argv=None):
    parser = argparse.ArgumentParser(description='Serve files using SPEC.md binary protocol')
    parser.add_argument('root')
    parser.add_argument('port', type=int)
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    if not root.is_dir() or not 1 <= args.port <= 65535:
        print('bserve: supply an existing folder and port 1-65535', file=sys.stderr)
        return 1
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind(('127.0.0.1', args.port))
            listener.listen()
            print(f'Serving {root} on 127.0.0.1:{args.port}', file=sys.stderr, flush=True)
            while True:
                conn, _ = listener.accept()
                with conn:
                    handle_connection(conn, root)
    except KeyboardInterrupt:
        print('Server stopped', file=sys.stderr)
        return 0
    except OSError as exc:
        print(f'bserve: {exc}', file=sys.stderr)
        return 1
