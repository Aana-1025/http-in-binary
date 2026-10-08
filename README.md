# HTTP in Binary

*Network Architecture course project*

**Author:** Antara Utane

**Email:** [antarautane11@gmail.com](mailto:antarautane11@gmail.com)

`bserve` is a file server and `bcurl` is its client. They communicate over TCP using a binary message format. Common header names, such as `user-agent`, use one-byte IDs instead of long text names to save bytes.

The client requests a file from the server's root folder and writes the returned bytes to stdout. The same format works for text, binary, and empty files. [SPEC.pdf](SPEC.pdf) describes the complete protocol.

## Main features

- Binary REQUEST and RESPONSE frames over TCP.
- An eight-byte frame header with big-endian integers.
- Ten numbered header names and a length-prefixed literal-name fallback.
- Exact text, binary, and empty-file responses.
- Persistent server connections, including after recoverable malformed requests.
- Unknown frame types skipped using their payload length.
- Status codes for successful requests, malformed requests, and missing files.
- Verbose hexdumps and tests for framing, file handling, and error recovery.

## Protocol overview

Each frame begins with this header:

| Field | Size | Purpose |
| --- | --- | --- |
| Payload length | 4 bytes | Number of bytes after the header |
| Type | 1 byte | `1` REQUEST or `2` RESPONSE |
| Version | 1 byte | `1` |
| Reserved | 2 bytes | `0` |

A request contains method `1` (GET), a UTF-8 path, and headers. A response contains a numeric status, headers, and the file body. Everything remaining after the response headers is the body; there is no separate body-length field.

Lengths and status codes are binary integers. For example, `user-agent` is sent as ID `2`, rather than repeating its ten-character name. Other header names use the literal form defined in the specification.

The payload limit is 16 MiB, including metadata. Header values are descriptive and do not override framing. See [SPEC.pdf](SPEC.pdf) for the full encoding and connection rules.

The server keeps the connection open after normal responses and recoverable errors. The command-line client uses one connection, sends one request, reads its response, and then closes.

## Project structure

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
- Python's standard library only; no packages or compilation are needed.
- Two terminal windows for running the server and client.

Clone the repository, or extract a downloaded copy, and open PowerShell in the project folder:

```powershell
git clone https://github.com/Aana-1025/http-in-binary.git
cd http-in-binary
python --version
```

Git is only needed for cloning. If Windows uses the Python launcher, replace `python` with `py -3` in the commands below.

## Run the server

In the first terminal:

```powershell
python bserve ./www 9000
```

The server listens on `127.0.0.1:9000` and serves files from `www`, one client at a time. Stop it with **Ctrl+C**. If port 9000 is busy, choose another port in both the server and client commands.

On Unix with Python 3 installed, the assignment's command is:

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

The first command prints the contents of `hello.txt`. The second requests `/index.html`, which is the file mapped to `/`.

### Verbose hexdump

```powershell
python bcurl -v localhost:9000/index.html
```

On Unix:

```sh
./bcurl -v localhost:9000/index.html
```

`-v` prints the complete sent and received frames, with byte offsets and hexadecimal bytes. Hexdumps and diagnostics go to stderr; stdout contains only the response body. TCP may split a frame across reads, so the dump's line breaks can vary without changing the bytes.

For a field-by-field explanation of a recorded exchange, see the [annotated hexdump](evidence/annotated-hexdump.md).

### Save a binary response

Use this command in PowerShell to save the bytes directly:

```powershell
python -c "import subprocess,sys,pathlib; r=subprocess.run([sys.executable,'bcurl','localhost:9000/sample.bin'],capture_output=True); pathlib.Path('download.bin').write_bytes(r.stdout); sys.exit(r.returncode)"
python -c "from pathlib import Path; assert Path('download.bin').read_bytes()==Path('www/sample.bin').read_bytes(); print('Exact binary match')"
```

`sample.bin` contains the byte values 0-255. The downloaded file is ignored by Git.

## Status codes and error examples

| Status | Meaning |
| --- | --- |
| 200 | File returned successfully |
| 400 | Malformed request or unsafe path |
| 404 | File is missing or the path is not a regular file |
| 500 | File-reading error or response exceeds the payload limit |

The client exits with **0** for a 2xx response and **1** for failures, including 4xx/5xx responses and connection or protocol errors.

```powershell
python bcurl localhost:9000/missing.txt
$LASTEXITCODE
```

This returns a 404 error body and exit code `1`.

An unsafe path also fails:

```powershell
python bcurl localhost:9000/../secret.txt
$LASTEXITCODE
```

This returns a 400 response and exit code `1`. Complete malformed requests within the payload limit receive a 400 without closing the connection. Oversized or incomplete frames close it as described in the specification.

## Run the tests

```powershell
python -m unittest discover -s tests -v
```

The tests cover exact wire bytes, numbered and literal headers, text and binary downloads, root mapping, malformed requests, path protection, persistent connections, unknown frames, verbose dumps, and interrupted connections. They also check split and combined reads, folder-link escapes, large files, and every annotated byte in the capture.

Tests launch their own local server and client processes and clean up temporary files. A separately running demonstration server is not needed. If Make is installed, `make test` and `make check` are optional shortcuts.

## Specification and evidence

- [Two-page protocol specification](SPEC.pdf)
- [Specification in Markdown](SPEC.md)
- [Annotated request and response](evidence/annotated-hexdump.md), including raw bytes and field explanations
- [Raw request/response capture](evidence/request-response.hex)
