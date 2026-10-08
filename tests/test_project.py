"""Independent wire fixtures plus real server/client process tests."""

import io
import ast
import queue
import re
import socket
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from src import protocol as p
from src import server

PROJECT = Path(__file__).resolve().parents[1]


def wire_frame(kind, payload, version=1, reserved=0):
    # Deliberately do not use the production encoder.
    return (len(payload).to_bytes(4, 'big') + bytes([kind, version])
            + reserved.to_bytes(2, 'big') + payload)


def wire_request(path, suffix=b'', method=1):
    data = path.encode('utf-8')
    return wire_frame(1, bytes([method]) + len(data).to_bytes(2, 'big')
                      + data + b'\x00\x00' + suffix)


def exact(sock, count):
    result = b''
    while len(result) < count:
        chunk = sock.recv(count - len(result))
        if not chunk:
            raise AssertionError('unexpected EOF')
        result += chunk
    return result


def wire_response(sock):
    header = exact(sock, 8)
    if header[4:] != b'\x02\x01\x00\x00':
        raise AssertionError(f'wrong response envelope: {header.hex()}')
    payload = exact(sock, int.from_bytes(header[:4], 'big'))
    status = int.from_bytes(payload[:2], 'big')
    count = int.from_bytes(payload[2:4], 'big')
    offset = 4
    entries = []
    for _ in range(count):
        name_id = payload[offset]
        offset += 1
        if name_id == 0:
            length = int.from_bytes(payload[offset:offset + 2], 'big')
            offset += 2 + length
        length = int.from_bytes(payload[offset:offset + 2], 'big')
        offset += 2
        value = payload[offset:offset + length]
        offset += length
        entries.append((name_id, value))
    return status, entries, payload[offset:]


class ProtocolTests(unittest.TestCase):
    def test_exact_eight_byte_big_endian_reference(self):
        payload = bytes.fromhex('01 00 02 2f 78 00 00')
        expected = bytes.fromhex('00 00 00 07 01 01 00 00 01 00 02 2f 78 00 00')
        self.assertEqual(p.FRAME_HEADER.size, 8)
        self.assertEqual(p.encode_request('/x'), payload)
        self.assertEqual(p.make_frame(1, payload), expected)
        self.assertEqual(p.decode_request(payload), ('/x', []))

    def test_ten_numbered_headers_exact_encoding(self):
        expected = b''.join(bytes([i, 0, 1, 118]) for i in range(1, 11))
        entries = [(name, 'v') for name in p.HEADER_NAMES]
        self.assertEqual(p.encode_headers(entries), expected)
        self.assertEqual(p.decode_headers(p.Reader(expected), 10), entries)

    def test_literal_headers_duplicates_empty_unicode(self):
        literal = bytes.fromhex('00 00 06 78 2d 74 65 73 74 00 02 c3 a9')
        self.assertEqual(p.encode_headers([('x-test', 'é')]), literal)
        self.assertEqual(p.decode_headers(p.Reader(literal), 1), [('x-test', 'é')])
        # A dictionary name may be literal; duplicates remain valid.
        raw = b'\x00\x00\x04host\x00\x00\x01\x00\x00'
        self.assertEqual(p.decode_headers(p.Reader(raw), 2), [('host', ''), ('host', '')])

    def test_response_body_uses_remaining_payload(self):
        raw = bytes.fromhex('00 c8 00 00') + b'\x00\xffhello'
        self.assertEqual(p.encode_response(200, [], b'\x00\xffhello'), raw)
        self.assertEqual(p.decode_response(raw), (200, [], b'\x00\xffhello'))

    def test_bad_headers_and_responses_rejected(self):
        for raw in (b'\x0b', b'\x01\x00\x02x', b'\x00\x00\x00\x00\x00',
                    b'\x01\x00\x01\xff'):
            with self.subTest(raw=raw), self.assertRaises(p.ProtocolError):
                p.decode_headers(p.Reader(raw), 1)
        for raw in (b'', b'\x00\x63\x00\x00', b'\x02\x58\x00\x00'):
            with self.subTest(raw=raw), self.assertRaises(p.ProtocolError):
                p.decode_response(raw)

    def test_encoder_rejects_fields_exceeding_wire_widths(self):
        for entries in ([('x', 'v' * 65536)], [('x' * 65536, '')], [('host', '')] * 65536):
            with self.assertRaises(p.ProtocolError):
                p.encode_request('/x', entries)
        with self.assertRaises(p.ProtocolError):
            p.encode_request('/' + 'x' * 65535)

    def test_unknown_payload_discarded_without_retaining_it(self):
        class ChunkSocket:
            def __init__(self):
                self.remaining = 200000
                self.header = self.remaining.to_bytes(4, 'big') + b'\x63\x01\x00\x00'
                self.sizes = []

            def recv(self, count):
                self.sizes.append(count)
                if self.header:
                    data, self.header = self.header[:count], self.header[count:]
                    return data
                amount = min(count, self.remaining)
                self.remaining -= amount
                return b'x' * amount

        sock = ChunkSocket()
        self.assertEqual(p.receive_frame(sock), (99, b''))
        self.assertEqual(sock.remaining, 0)
        self.assertLessEqual(max(sock.sizes), 65536)


class LiveProjectTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        cls.text = b'Hello\r\nExact text bytes\n'
        cls.binary = bytes(range(256)) * 4
        (cls.root / 'hello.txt').write_bytes(cls.text)
        (cls.root / 'sample.bin').write_bytes(cls.binary)
        (cls.root / 'index.html').write_bytes(b'<h1>Index</h1>\n')
        (cls.root / 'empty').write_bytes(b'')
        (cls.root / 'folder').mkdir()
        (cls.root / '%2e%2e.txt').write_bytes(b'Literal percent filename')
        with socket.socket() as reservation:
            reservation.bind(('127.0.0.1', 0))
            cls.port = reservation.getsockname()[1]
        cls.process = subprocess.Popen(
            [sys.executable, str(PROJECT / 'bserve'), str(cls.root), str(cls.port)],
            cwd=PROJECT, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        ready = queue.Queue()
        threading.Thread(target=lambda: ready.put(cls.process.stderr.readline()), daemon=True).start()
        try:
            line = ready.get(timeout=5)
            if not line.startswith(b'Serving '):
                raise AssertionError(f'server startup failed: {line!r}')
        except Exception:
            cls.process.terminate()
            cls.process.wait(timeout=5)
            cls.process.stderr.close()
            cls.temp.cleanup()
            raise

    @classmethod
    def tearDownClass(cls):
        cls.process.terminate()
        cls.process.wait(timeout=5)
        cls.process.stderr.close()
        cls.temp.cleanup()

    def connect(self):
        return socket.create_connection(('127.0.0.1', self.port), timeout=3)

    def request(self, path):
        with self.connect() as conn:
            conn.sendall(wire_request(path))
            return wire_response(conn)

    def client(self, path, verbose=False):
        args = [sys.executable, str(PROJECT / 'bcurl')]
        if verbose:
            args.append('-v')
        args.append(f'localhost:{self.port}{path}')
        return subprocess.run(args, cwd=PROJECT, capture_output=True, timeout=8)

    def test_01_existing_text_exact_bytes_and_all_server_headers(self):
        status, headers, body = self.request('/hello.txt')
        self.assertEqual(status, 200)
        self.assertEqual(body, self.text)
        self.assertEqual([item[0] for item in headers], [6, 7, 8, 9, 10])
        self.assertEqual(headers[1][1], str(len(body)).encode())

    def test_02_binary_download_exact_bytes(self):
        self.assertEqual(self.request('/sample.bin')[2], self.binary)
        result = self.client('/sample.bin')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, self.binary)
        self.assertEqual(result.stderr, b'')

    def test_03_root_maps_to_index(self):
        self.assertEqual(self.request('/')[2], (self.root / 'index.html').read_bytes())

    def test_04_missing_directory_and_empty(self):
        self.assertEqual(self.request('/absent')[0], 404)
        self.assertEqual(self.request('/folder')[0], 404)
        self.assertEqual(self.request('/empty')[::2], (200, b''))

    def test_05_malformed_requests_then_valid_on_same_socket(self):
        malformed = [wire_request('/hello.txt', method=2),
                     wire_request('/hello.txt', suffix=b'extra'),
                     wire_frame(1, b''), wire_frame(2, b'ignored'),
                     wire_frame(1, b'\x01\x00\x00\x00\x00'),
                     wire_frame(1, b'\x01\x00\x01\xff\x00\x00'),
                     wire_frame(1, b'\x01\x00\x01/\x00\x01\x0b'),
                     wire_frame(1, b'', version=2), wire_frame(1, b'', reserved=1)]
        with self.connect() as conn:
            for frame in malformed:
                conn.sendall(frame)
                self.assertEqual(wire_response(conn)[0], 400)
            conn.sendall(wire_request('/hello.txt'))
            self.assertEqual(wire_response(conn)[2], self.text)

    def test_06_unsafe_paths_rejected_literal_percent_preserved(self):
        for path in ('/../secret', '/a/../../secret', '/a\\b', '/C:secret', '/a\x00b', 'relative'):
            with self.subTest(path=path):
                self.assertEqual(self.request(path)[0], 400)
        self.assertEqual(self.request('/%2e%2e.txt')[2], b'Literal percent filename')

    def test_07_unknown_frame_skipped_and_fragmented_reads(self):
        with self.connect() as conn:
            frames = wire_frame(99, b'not a request' * 10000) + wire_frame(0, b'')
            conn.sendall(frames)
            request = wire_request('/hello.txt')
            for byte in request:
                conn.sendall(bytes([byte]))
            self.assertEqual(wire_response(conn)[2], self.text)

    def test_08_multiple_requests_persist_after_404(self):
        with self.connect() as conn:
            for path, expected in (('/hello.txt', 200), ('/missing', 404), ('/sample.bin', 200)):
                conn.sendall(wire_request(path))
                self.assertEqual(wire_response(conn)[0], expected)

    def test_09_verbose_dumps_reconstruct_every_frame_byte(self):
        result = self.client('/hello.txt', verbose=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, self.text)
        sections = re.split(r'(?:SENT|RECEIVED) frame\r?\n', result.stderr.decode())[1:]
        self.assertEqual(len(sections), 2)
        frames = []
        for section in sections:
            data = bytearray()
            for line in section.splitlines():
                offset, hex_bytes = line.split('  ', 1)
                self.assertEqual(int(offset, 16), len(data))
                data.extend(bytes.fromhex(hex_bytes))
            self.assertEqual(len(data), 8 + int.from_bytes(data[:4], 'big'))
            frames.append(bytes(data))
        self.assertEqual(frames[0][4:8], b'\x01\x01\x00\x00')
        self.assertEqual(p.decode_request(frames[0][8:])[1], [
            ('host', f'localhost:{self.port}'), ('user-agent', 'bcurl/1'),
            ('accept', '*/*'), ('accept-encoding', 'identity'), ('connection', 'keep-alive')])
        self.assertEqual(p.decode_response(frames[1][8:])[2], self.text)

    def test_10_client_404_exit_one(self):
        result = self.client('/missing')
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, b'File not found\n')

    def test_11_clean_eof_and_partial_frame_shutdown(self):
        with self.connect() as conn:
            conn.shutdown(socket.SHUT_WR)
            self.assertEqual(conn.recv(1), b'')
        for partial in (b'\x00\x00', wire_frame(1, b'abc')[:-1]):
            with self.connect() as conn:
                conn.sendall(partial)
                conn.shutdown(socket.SHUT_WR)
                self.assertEqual(wire_response(conn)[0], 400)
                self.assertEqual(conn.recv(1), b'')
        self.assertEqual(self.request('/hello.txt')[0], 200)

    def test_12_oversized_frame_400_then_eof(self):
        with self.connect() as conn:
            conn.sendall((p.MAX_PAYLOAD + 1).to_bytes(4, 'big') + b'\x01\x01\x00\x00')
            self.assertEqual(wire_response(conn)[0], 400)
            self.assertEqual(conn.recv(1), b'')

    def test_13_unknown_literal_header_accepted(self):
        payload = b'\x01\x00\x0a/hello.txt\x00\x01\x00\x00\x06x-test\x00\x03yes'
        with self.connect() as conn:
            conn.sendall(wire_frame(1, payload))
            self.assertEqual(wire_response(conn)[2], self.text)

    def test_14_connection_persists_after_500(self):
        large = self.root / 'large.bin'
        with large.open('wb') as output:
            output.truncate(p.MAX_PAYLOAD)
        try:
            with self.connect() as conn:
                conn.sendall(wire_request('/large.bin'))
                self.assertEqual(wire_response(conn)[0], 500)
                conn.sendall(wire_request('/hello.txt'))
                self.assertEqual(wire_response(conn)[2], self.text)
        finally:
            large.unlink()


class EvidenceTests(unittest.TestCase):
    def test_every_captured_byte_has_an_accurate_annotation(self):
        trace = (PROJECT / 'evidence' / 'request-response.hex').read_text()
        sections = re.split(r'(?:SENT|RECEIVED) frame\n', trace)[1:]
        self.assertEqual(len(sections), 2)
        frames = []
        for section in sections:
            data = bytearray()
            for line in section.splitlines():
                if not line.strip():
                    continue
                offset, hex_bytes = line.split('  ', 1)
                self.assertEqual(int(offset, 16), len(data))
                data.extend(bytes.fromhex(hex_bytes))
            self.assertEqual(len(data), 8 + int.from_bytes(data[:4], 'big'))
            frames.append(bytes(data))
        annotation = (PROJECT / 'evidence' / 'annotated-hexdump.md').read_text()
        tables = re.split(r'## (?:REQUEST|RESPONSE)\n', annotation)[1:]
        self.assertEqual(len(tables), 2)
        for frame, table in zip(frames, tables):
            coverage = []
            for start, end, field, value in re.findall(
                    r'^\| (\d+)-(\d+) \| ([^|]+) \| ([^|]+) \|$', table, re.MULTILINE):
                start, end = int(start), int(end)
                actual = frame[start:end+1]
                coverage.extend(range(start, end+1))
                if field in ('Path', 'Value', 'Body'):
                    expected = ast.literal_eval(value)
                    if isinstance(expected, str):
                        expected = expected.encode('utf-8')
                    self.assertEqual(actual, expected, field)
                else:
                    expected = int(value.split()[0])
                    self.assertEqual(int.from_bytes(actual, 'big'), expected, field)
            self.assertEqual(coverage, list(range(len(frame))))
        self.assertEqual(p.decode_request(frames[0][8:])[0], '/hello.txt')
        status, _, body = p.decode_response(frames[1][8:])
        self.assertEqual(status, 200)
        self.assertEqual(body, (PROJECT / 'www' / 'hello.txt').read_bytes())


class ErrorAndClientTests(unittest.TestCase):
    def test_file_read_error_returns_500(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            (root / 'file').write_bytes(b'x')
            with patch.object(Path, 'open', side_effect=PermissionError('denied')):
                self.assertEqual(p.decode_response(server.file_response(root, '/file'))[0], 500)

    def test_oversized_file_returns_500(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            with (root / 'large').open('wb') as output:
                output.truncate(p.MAX_PAYLOAD)
            self.assertEqual(p.decode_response(server.file_response(root, '/large'))[0], 500)

    def test_resolved_target_outside_root_returns_400(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            with patch.object(Path, 'resolve', return_value=root.parent / 'outside'):
                self.assertEqual(p.decode_response(server.file_response(root, '/link'))[0], 400)

    def test_ctrl_c_closes_server_listener(self):
        listener = unittest.mock.MagicMock()
        listener.__enter__.return_value = listener
        listener.accept.side_effect = KeyboardInterrupt
        with tempfile.TemporaryDirectory() as folder, patch.object(socket, 'socket', return_value=listener):
            with patch('sys.stderr', io.StringIO()):
                self.assertEqual(server.main([folder, '9000']), 0)
        listener.__exit__.assert_called_once()

    def test_client_against_independent_peer(self):
        # Peer sends unknown + RESPONSE without production encode/decode helpers.
        for payload, expected_exit in ((b'\x00\xc8\x00\x00binary\x00\xff', 0),
                                       (b'\x01\xf4\x00\x00error', 1),
                                       (b'\x00', 1)):
            with self.subTest(payload=payload), socket.socket() as listener:
                listener.bind(('127.0.0.1', 0))
                listener.listen()
                listener.settimeout(3)
                port = listener.getsockname()[1]
                errors = []
                received = []

                def peer():
                    try:
                        with listener.accept()[0] as conn:
                            conn.settimeout(3)
                            header = exact(conn, 8)
                            received.append(header + exact(conn, int.from_bytes(header[:4], 'big')))
                            conn.sendall(wire_frame(77, b'ignore me') + wire_frame(2, payload))
                            self.assertEqual(conn.recv(1), b'')
                        listener.settimeout(0.2)
                        try:
                            second, _ = listener.accept()
                            second.close()
                            errors.append('client opened a second connection')
                        except socket.timeout:
                            pass
                    except Exception as exc:
                        errors.append(exc)

                worker = threading.Thread(target=peer)
                worker.start()
                result = subprocess.run([sys.executable, str(PROJECT / 'bcurl'), '-v',
                                         f'127.0.0.1:{port}/file'], capture_output=True, timeout=5)
                worker.join(timeout=4)
                self.assertFalse(worker.is_alive())
                self.assertEqual(errors, [])
                self.assertEqual(len(received), 1)
                self.assertEqual(result.returncode, expected_exit, result.stderr)
                self.assertEqual(result.stderr.count(b'RECEIVED frame'), 2)
                if expected_exit == 0:
                    self.assertEqual(result.stdout, b'binary\x00\xff')

    def test_client_clean_eof_before_response_and_usage_failure(self):
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            listener.listen()
            listener.settimeout(3)
            port = listener.getsockname()[1]

            def peer():
                with listener.accept()[0] as conn:
                    conn.settimeout(3)
                    header = exact(conn, 8)
                    exact(conn, int.from_bytes(header[:4], 'big'))

            worker = threading.Thread(target=peer)
            worker.start()
            result = subprocess.run([sys.executable, str(PROJECT / 'bcurl'), f'127.0.0.1:{port}/x'],
                                    capture_output=True, timeout=5)
            worker.join(timeout=4)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout, b'')
        result = subprocess.run([sys.executable, str(PROJECT / 'bcurl'), 'bad-input'],
                                capture_output=True, timeout=5)
        self.assertEqual(result.returncode, 1)


if __name__ == '__main__':
    unittest.main()
