"""One connection, one GET-like request, raw body output."""

import socket
import sys

from .protocol import (REQUEST, RESPONSE, Hexdump, ProtocolError, decode_response,
                       encode_request, receive_frame, send_frame)


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    verbose = bool(args and args[0] == '-v')
    if verbose:
        args.pop(0)
    if len(args) != 1:
        print('Usage: python bcurl [-v] host:port/path', file=sys.stderr)
        return 1
    trace = Hexdump(sys.stderr) if verbose else None
    try:
        address, separator, tail = args[0].partition('/')
        host, colon, port_text = address.rpartition(':')
        port = int(port_text)
        if not separator or not colon or not host or not 1 <= port <= 65535:
            raise ValueError('expected host:port/path')
        headers = [('host', address), ('user-agent', 'bcurl/1'), ('accept', '*/*'),
                   ('accept-encoding', 'identity'), ('connection', 'keep-alive')]
        payload = encode_request('/' + tail, headers)
        # One address, one socket, one connect call. No fallback or retry.
        address_ip = socket.gethostbyname(host)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as conn:
            conn.connect((address_ip, port))
            send_frame(conn, REQUEST, payload, trace)
            while True:
                frame = receive_frame(conn, trace)
                if frame is None:
                    raise ProtocolError('EOF before response')
                frame_type, response = frame
                if frame_type not in (REQUEST, RESPONSE):
                    continue
                if frame_type != RESPONSE:
                    raise ProtocolError('expected RESPONSE')
                status, _, body = decode_response(response)
                sys.stdout.buffer.write(body)
                sys.stdout.buffer.flush()
                return 0 if 200 <= status <= 299 else 1
    except (OSError, ValueError, ProtocolError, OverflowError) as exc:
        print(f'bcurl: {exc}', file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 1
