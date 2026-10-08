"""Wire encoding and exact-byte TCP reads, following SPEC.md."""

import struct

REQUEST, RESPONSE = 1, 2
MAX_PAYLOAD = 16 * 1024 * 1024
FRAME_HEADER = struct.Struct('!IBBH')  # big-endian: length, type, version, reserved
HEADER_NAMES = (
    'host', 'user-agent', 'accept', 'accept-encoding', 'connection',
    'content-type', 'content-length', 'server', 'cache-control', 'x-protocol-version',
)


class ProtocolError(Exception):
    def __init__(self, message, fatal=False):
        super().__init__(message)
        self.fatal = fatal


def valid_name(name):
    return bool(name) and all(c in 'abcdefghijklmnopqrstuvwxyz0123456789-' for c in name)


class Reader:
    """A cursor that never reads beyond a payload."""
    def __init__(self, data):
        self.data = data
        self.offset = 0

    def take(self, length):
        if length > len(self.data) - self.offset:
            raise ProtocolError('field extends beyond payload')
        result = self.data[self.offset:self.offset + length]
        self.offset += length
        return result

    def number(self, width):
        return int.from_bytes(self.take(width), 'big')

    def text(self, length):
        try:
            return self.take(length).decode('utf-8')
        except UnicodeDecodeError as exc:
            raise ProtocolError('invalid UTF-8') from exc


def encode_headers(headers):
    if len(headers) > 65535:
        raise ProtocolError('too many headers')
    result = bytearray()
    for name, value in headers:
        if not valid_name(name):
            raise ProtocolError('invalid header name')
        if name in HEADER_NAMES:
            result.append(HEADER_NAMES.index(name) + 1)
        else:
            name_bytes = name.encode('ascii')
            if len(name_bytes) > 65535:
                raise ProtocolError('header name too long')
            result += b'\x00' + struct.pack('!H', len(name_bytes)) + name_bytes
        value_bytes = value.encode('utf-8')
        if len(value_bytes) > 65535:
            raise ProtocolError('header value too long')
        result += struct.pack('!H', len(value_bytes)) + value_bytes
    return bytes(result)


def decode_headers(reader, count):
    headers = []
    for _ in range(count):
        name_id = reader.number(1)
        if name_id == 0:
            name = reader.text(reader.number(2))
            if not valid_name(name):
                raise ProtocolError('invalid literal name')
        elif 1 <= name_id <= 10:
            name = HEADER_NAMES[name_id - 1]
        else:
            raise ProtocolError('unknown header ID')
        value = reader.text(reader.number(2))
        headers.append((name, value))
    return headers


def encode_request(path, headers=()):
    path_bytes = path.encode('utf-8')
    if not 1 <= len(path_bytes) <= 65535:
        raise ProtocolError('invalid path length')
    encoded_headers = encode_headers(headers)
    return (b'\x01' + struct.pack('!H', len(path_bytes)) + path_bytes
            + struct.pack('!H', len(headers)) + encoded_headers)


def decode_request(payload):
    reader = Reader(payload)
    if reader.number(1) != 1:
        raise ProtocolError('only GET is supported')
    length = reader.number(2)
    if length == 0:
        raise ProtocolError('empty path')
    path = reader.text(length)
    headers = decode_headers(reader, reader.number(2))
    if reader.offset != len(payload):
        raise ProtocolError('extra request bytes')
    return path, headers


def encode_response(status, headers, body):
    if not 100 <= status <= 599:
        raise ProtocolError('invalid status')
    encoded_headers = encode_headers(headers)
    return struct.pack('!HH', status, len(headers)) + encoded_headers + body


def decode_response(payload):
    reader = Reader(payload)
    status = reader.number(2)
    if not 100 <= status <= 599:
        raise ProtocolError('invalid status')
    headers = decode_headers(reader, reader.number(2))
    return status, headers, reader.take(len(payload) - reader.offset)


def make_frame(frame_type, payload):
    if len(payload) > MAX_PAYLOAD:
        raise ProtocolError('payload exceeds 16 MiB')
    return FRAME_HEADER.pack(len(payload), frame_type, 1, 0) + payload


class Hexdump:
    """Stream dumps without storing unknown payloads in memory."""
    def __init__(self, stream):
        self.stream = stream

    def start(self, direction):
        print(f'{direction} frame', file=self.stream)

    def data(self, data, offset):
        for index in range(0, len(data), 16):
            print(f'{offset + index:08x}  {data[index:index + 16].hex(" ")}',
                  file=self.stream)

    def partial(self):
        print('partial frame (incomplete capture)', file=self.stream)


def receive_frame(sock, trace=None):
    """Return (type, payload), None for clean EOF; skip unknown payloads."""
    offset = 0

    def read_exact(length, clean_eof=False, collect=True):
        nonlocal offset
        result = bytearray()
        remaining = length
        while remaining:
            chunk = sock.recv(min(remaining, 65536))
            if not chunk:
                if clean_eof and remaining == length:
                    return None
                if trace:
                    trace.partial()
                raise ProtocolError('EOF inside frame', fatal=True)
            if trace:
                if offset == 0:
                    trace.start('RECEIVED')
                trace.data(chunk, offset)
            offset += len(chunk)
            remaining -= len(chunk)
            if collect:
                result.extend(chunk)
        return bytes(result)

    header = read_exact(8, clean_eof=True)
    if header is None:
        return None
    length, frame_type, version, reserved = FRAME_HEADER.unpack(header)
    if length > MAX_PAYLOAD:
        if trace:
            trace.partial()
        raise ProtocolError('payload exceeds 16 MiB', fatal=True)
    payload = read_exact(length, collect=frame_type in (REQUEST, RESPONSE))
    if version != 1 or reserved != 0:
        raise ProtocolError('invalid version or reserved field')
    return frame_type, payload


def send_frame(sock, frame_type, payload, trace=None):
    frame = make_frame(frame_type, payload)
    sock.sendall(frame)
    if trace:
        trace.start('SENT')
        trace.data(frame, 0)
