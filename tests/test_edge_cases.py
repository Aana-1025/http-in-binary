"""Boundary and error cases using hand-built frames and socket peers."""

import io
import re
import socket
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src import protocol as p
from src import server
from test_project import PROJECT, exact, wire_frame


class ChunkSocket:
    """Return at most step bytes per recv, even when frames arrive together."""
    def __init__(self, data, step, reset=False):
        self.data = data
        self.step = step
        self.reset = reset

    def recv(self, count):
        if not self.data and self.reset:
            raise ConnectionResetError('connection reset')
        size = min(count, self.step)
        chunk, self.data = self.data[:size], self.data[size:]
        return chunk


class BoundaryTests(unittest.TestCase):
    def test_fragmented_and_coalesced_frames_preserve_boundaries_and_dumps(self):
        frames = [wire_frame(1, b'\x01\x00\x01/\x00\x00'),
                  wire_frame(91, b'unknown'), wire_frame(2, b'\x00\xc8\x00\x00\x00\xff')]
        for step in (1, 3, 7, 8, 65536):
            with self.subTest(step=step):
                output = io.StringIO()
                trace = p.Hexdump(output)
                sock = ChunkSocket(b''.join(frames), step)
                self.assertEqual(p.receive_frame(sock, trace), (1, frames[0][8:]))
                self.assertEqual(p.receive_frame(sock, trace), (91, b''))
                self.assertEqual(p.receive_frame(sock, trace), (2, frames[2][8:]))
                self.assertIsNone(p.receive_frame(sock, trace))
                sections = output.getvalue().split('RECEIVED frame\n')[1:]
                self.assertEqual(len(sections), 3)
                for expected, section in zip(frames, sections):
                    reconstructed = bytearray()
                    for line in section.splitlines():
                        offset, data = line.split('  ', 1)
                        self.assertEqual(int(offset, 16), len(reconstructed))
                        reconstructed.extend(bytes.fromhex(data))
                    self.assertEqual(bytes(reconstructed), expected)

    def test_eof_and_reset_label_incomplete_verbose_captures(self):
        complete = wire_frame(1, b'abc')
        for length in (2, 10):
            for reset in (False, True):
                with self.subTest(length=length, reset=reset):
                    output = io.StringIO()
                    error = ConnectionResetError if reset else p.ProtocolError
                    with self.assertRaises(error):
                        p.receive_frame(ChunkSocket(complete[:length], 1, reset), p.Hexdump(output))
                    self.assertEqual(output.getvalue().count('partial frame (incomplete capture)'), 1)
                    captured = b''.join(bytes.fromhex(data) for data in
                                       re.findall(r'^\w{8}  (.+)$', output.getvalue(), re.MULTILINE))
                    self.assertEqual(captured, complete[:length])

    def test_server_reports_startup_filesystem_error_without_traceback(self):
        output = io.StringIO()
        with patch.object(Path, 'resolve', side_effect=PermissionError('folder inaccessible')):
            with patch('sys.stderr', output):
                self.assertEqual(server.main(['www', '9000']), 1)
        self.assertIn('bserve:', output.getvalue())
        self.assertNotIn('Traceback', output.getvalue())

    def test_ctrl_c_closes_active_connection_and_listener(self):
        listener, conn = MagicMock(), MagicMock()
        listener.__enter__.return_value = listener
        listener.accept.return_value = (conn, ('127.0.0.1', 1234))
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(socket, 'socket', return_value=listener):
                with patch.object(server, 'handle_connection', side_effect=KeyboardInterrupt):
                    with patch('sys.stderr', io.StringIO()):
                        self.assertEqual(server.main([folder, '9000']), 0)
        conn.__exit__.assert_called_once()
        listener.__exit__.assert_called_once()

    def test_server_port_in_use_returns_failure(self):
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            listener.listen()
            result = subprocess.run([sys.executable, str(PROJECT / 'bserve'), str(PROJECT / 'www'),
                                     str(listener.getsockname()[1])], capture_output=True, timeout=5)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn(b'bserve:', result.stderr)
        self.assertNotIn(b'Traceback', result.stderr)

    def test_client_checks_envelopes_status_and_metadata_against_socket_peer(self):
        # Metadata deliberately disagrees with the body and repeats content-length.
        headers = b'\x07\x00\x019\x07\x00\x045000'
        body = bytes(range(256))
        valid = wire_frame(2, b'\x00\xc8\x00\x02' + headers + body)
        cases = [(valid, 0, body), (wire_frame(2, b'\x01\x2b\x00\x00ok'), 0, b'ok'),
                 (wire_frame(2, b'\x01\x91\x00\x00error'), 1, b'error'),
                 (wire_frame(2, b'\x02\x57\x00\x00error'), 1, b'error'),
                 (wire_frame(2, b'\x00\x64\x00\x00final'), 1, b'final'),
                 (wire_frame(1, b'wrong direction'), 1, b''),
                 (wire_frame(2, b'\x00\xc8\x00\x00', version=2), 1, b''),
                 (wire_frame(2, b'\x00\xc8\x00\x00', reserved=1), 1, b''),
                 ((p.MAX_PAYLOAD + 1).to_bytes(4, 'big') + b'\x02\x01\x00\x00', 1, b''),
                 (wire_frame(2, b'\x02\x58\x00\x00'), 1, b''),
                 (wire_frame(2, b'\x00\xc8\x00\x01\x0b'), 1, b''),
                 (wire_frame(2, b'\x00\xc8\x00\x01\x06\x00\x03x'), 1, b''),
                 (valid[:2], 1, b''), (valid[:-1], 1, b'')]
        for reply, code, expected_body in cases:
            with self.subTest(reply=reply[:12], size=len(reply)), socket.socket() as listener:
                listener.bind(('127.0.0.1', 0))
                listener.listen()
                listener.settimeout(3)
                errors = []

                def peer():
                    try:
                        with listener.accept()[0] as conn:
                            conn.settimeout(3)
                            header = exact(conn, 8)
                            exact(conn, int.from_bytes(header[:4], 'big'))
                            conn.sendall(wire_frame(77, b'first') + wire_frame(78, b'') + reply)
                            conn.shutdown(socket.SHUT_WR)
                    except Exception as exc:
                        errors.append(exc)

                worker = threading.Thread(target=peer)
                worker.start()
                result = subprocess.run([sys.executable, str(PROJECT / 'bcurl'), '-v',
                                         f'127.0.0.1:{listener.getsockname()[1]}/file'],
                                        capture_output=True, timeout=5)
                worker.join(timeout=4)
                self.assertFalse(worker.is_alive())
                self.assertEqual(errors, [])
                self.assertEqual(result.returncode, code, result.stderr)
                self.assertEqual(result.stdout, expected_body)
                self.assertEqual(result.stderr.count(b'RECEIVED frame'), 3)
                if reply in (valid[:2], valid[:-1]):
                    self.assertIn(b'partial frame (incomplete capture)', result.stderr)


if __name__ == '__main__':
    unittest.main()
