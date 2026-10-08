# HTTP in Binary

**Author:** Antara Utane

**Email:** [antarautane11@gmail.com](mailto:antarautane11@gmail.com)

## Overview

This is a TCP client-server project for my Network Architecture course. The server, `bserve`, and the client, `bcurl`, use a custom binary protocol to transfer files. Common header names use numbered IDs to save space compared with repeatedly sending their full text names.

## Main features

- GET-like file requests and binary REQUEST and RESPONSE frames.
- An eight-byte frame header with big-endian integers.
- Ten numbered header names, with a length-prefixed fallback for other names.
- Exact file bytes returned for text, binary, and empty files.
- Persistent server connections and clean skipping of unknown frame types.
- Path protection and error responses for malformed requests, missing files, and file-reading failures.
- Verbose hexdumps and automated tests.

## Protocol at a glance

Each frame begins with this header:

| Field | Size | Purpose |
| --- | --- | --- |
| Payload length | 4 bytes | Number of bytes after the header |
| Type | 1 byte | `1` REQUEST or `2` RESPONSE |
| Version | 1 byte | `1` |
| Reserved | 2 bytes | `0` |

A request contains method `1` (GET), a UTF-8 path, and headers. A response contains a numeric status, headers, and the returned body. All bytes remaining after the response headers belong to the body; there is no separate body-length field.

Lengths and status codes are binary integers. For example, `user-agent` is sent as ID `2`. Header names outside the dictionary are sent as text with a length prefix.

The payload limit is 16 MiB, including metadata. The frame length controls parsing; header values do not change it. Unknown frame types are skipped using their payload length.

The server can handle multiple requests on one connection. The command-line client sends one request, reads its response, and closes. The full encoding and connection rules are in [SPEC.pdf](SPEC.pdf).

## Repository structure

```text
.
├── bserve                     # Server entry point
├── bcurl                      # Client entry point
├── src/                       # Protocol, server, and client modules
├── tests/                     # Protocol, TCP, and error-handling tests
├── www/                       # Text, HTML, and binary sample files
├── SPEC.md
├── SPEC.pdf                   # Two-page protocol specification
├── evidence/
│   ├── annotated-hexdump.md    # Raw bytes and field explanations
│   └── request-response.hex    # Raw request/response capture
├── Makefile                   # Optional check/test shortcuts
├── .gitattributes
└── .gitignore
```

## Requirements

- Python 3.9 or newer.
- No external packages or compilation; the project uses Python's standard library.
- Two terminal windows for running the server and client.

In PowerShell, clone the repository and enter its folder:

```powershell
git clone https://github.com/Aana-1025/http-in-binary.git
cd http-in-binary
python --version
```

You can also download and extract the ZIP from GitHub, then open PowerShell in the extracted folder. Git is only needed for cloning. If Windows uses the Python launcher, replace `python` with `py -3` below.

## Run the server

In the first terminal:

```powershell
python bserve ./www 9000
```

The server listens on `127.0.0.1:9000` and serves files from `www`, one client at a time. Stop it with **Ctrl+C**. If port 9000 is busy, choose another port in both the server and client commands.

On Unix with Python 3 installed:

```sh
./bserve ./www 9000
```

If an extracted ZIP loses executable permissions, run `chmod +x bserve bcurl` once.

## Run the client

In the second terminal, from the same project folder:

```powershell
python bcurl localhost:9000/hello.txt
python bcurl localhost:9000/
```

The first command prints `hello.txt`. The second requests `/index.html`, which is the file mapped to `/`. The client writes the returned body bytes to stdout.

### Save a binary response

Use this command in PowerShell to save the bytes directly:

```powershell
python -c "import subprocess,sys,pathlib; r=subprocess.run([sys.executable,'bcurl','localhost:9000/sample.bin'],capture_output=True); pathlib.Path('download.bin').write_bytes(r.stdout); sys.exit(r.returncode)"
python -c "from pathlib import Path; assert Path('download.bin').read_bytes()==Path('www/sample.bin').read_bytes(); print('Exact binary match')"
```

`sample.bin` contains the byte values 0-255. The downloaded file is ignored by Git.

## Verbose mode

Add `-v` to show the complete sent and received frames, with byte offsets and hexadecimal bytes:

```powershell
python bcurl -v localhost:9000/index.html
```

On Unix:

```sh
./bcurl -v localhost:9000/index.html
```

Hexdumps and diagnostics go to stderr; stdout contains only the response body. TCP can split a frame across reads, so the dump's line breaks may vary while its bytes stay the same.

## Error handling

| Status | Meaning |
| --- | --- |
| 200 | File returned successfully |
| 400 | Malformed request or unsafe path |
| 404 | File is missing or the path is not a regular file |
| 500 | File-reading error or response exceeds the payload limit |

The client exits with **0** for a 2xx response and **1** for failures, including 4xx/5xx responses and connection or protocol errors. These examples return 404 and 400 respectively, both with exit code `1`:

```powershell
python bcurl localhost:9000/missing.txt
$LASTEXITCODE

python bcurl localhost:9000/../secret.txt
$LASTEXITCODE
```

The server keeps connections open after normal responses and recoverable errors. A complete malformed request within the payload limit receives a 400 without closing the connection. Oversized or incomplete frames close it, as described in the specification.

## Tests

```powershell
python -m unittest discover -s tests -v
```

The tests cover exact frame bytes, numbered and literal headers, file downloads, root mapping, malformed requests, path protection, persistent connections, unknown frames, verbose dumps, and interrupted connections. They also check split and combined reads, folder-link escapes, large files, and every annotated byte in the capture.

The tests start their own local server and client processes and clean up temporary files. You do not need a separate demonstration server. If Make is installed, `make test` and `make check` are optional shortcuts.

## Specification and evidence

- [Two-page protocol specification](SPEC.pdf)
- [Specification in Markdown](SPEC.md)
- [Annotated request and response](evidence/annotated-hexdump.md), including raw bytes and field explanations
- [Raw request/response capture](evidence/request-response.hex)
