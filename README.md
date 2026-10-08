# Binary File Protocol

*Network Architecture course project*

**Author:** Antara Utane

**Email:** [antarautane11@gmail.com](mailto:antarautane11@gmail.com)

This project transfers files over TCP using a small binary protocol. The server, `bserve`, reads a request and returns a file from its root folder. The client, `bcurl`, sends one GET-like request and writes the response body without changing its bytes.

The protocol specification defines the message format so another client or server can implement the same rules. This is a course protocol rather than standard HTTP; browsers and ordinary curl cannot use it directly.

The submission documents are the [two-page specification](SPEC.pdf) and the [annotated request/response hexdump](evidence/annotated-hexdump.md). The specification is also available as [Markdown](SPEC.md), alongside the [raw capture](evidence/request-response.hex).

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

A request contains the GET-like method, a path, and headers. A response contains a numeric status, headers, and the file body. Everything remaining after the response headers is the body; there is no separate body-length field.

The payload limit is 16 MiB, including metadata. Header values are descriptive and do not override framing. See [SPEC.pdf](SPEC.pdf) for the full encoding and connection rules.

## Repository structure

```text
.
├── bserve                     # Server entry point
├── bcurl                      # Client entry point
├── src/                       # Protocol, server, and client modules
├── tests/test_project.py      # Protocol and local TCP tests
├── www/                       # Text, HTML, and binary sample files
├── SPEC.md
├── SPEC.pdf                   # Two-page protocol specification
├── evidence/
│   ├── annotated-hexdump.md
│   └── request-response.hex
├── Makefile                   # Optional check/test shortcuts
├── .gitattributes
└── .gitignore
```

## Requirements

- Python 3.9 or newer. Tested on Windows with Python 3.11.9.
- Python's standard library only; no packages or compilation are needed.
- Two terminal windows for running the server and client.

Clone the repository, or extract a downloaded copy, and open PowerShell in the project folder:

```powershell
git clone https://github.com/Aana-1025/network-architecture-project.git
cd network-architecture-project
python --version
```

Git is only needed for cloning. If Windows uses the Python launcher, replace `python` with `py -3` in the commands below.

## Run the server

In the first terminal:

```powershell
python bserve ./www 9000
```

The server listens on `127.0.0.1:9000` and handles one client at a time. Files are served from `www`. Stop it with **Ctrl+C**.

## Run the client

In the second terminal, from the same project folder:

```powershell
python bcurl localhost:9000/hello.txt
python bcurl localhost:9000/
```

The first command prints the contents of `hello.txt`. The second requests `/index.html`, which is the file mapped to `/`.

### Verbose hexdump

```powershell
python bcurl -v localhost:9000/hello.txt
```

`-v` prints the complete sent and received frames, with byte offsets and hexadecimal bytes. Hexdumps and diagnostics go to stderr; stdout contains only the response body. TCP may split a frame across reads, so the dump's line breaks can vary without changing the bytes.

For a field-by-field explanation of a recorded exchange, see the [annotated hexdump](evidence/annotated-hexdump.md).

### Save a binary response

This command avoids differences in how PowerShell versions redirect binary output:

```powershell
python -c "import subprocess,sys,pathlib; r=subprocess.run([sys.executable,'bcurl','localhost:9000/sample.bin'],capture_output=True); pathlib.Path('download.bin').write_bytes(r.stdout); sys.exit(r.returncode)"
python -c "from pathlib import Path; assert Path('download.bin').read_bytes()==Path('www/sample.bin').read_bytes(); print('Exact binary match')"
```

`sample.bin` contains the byte values 0-255. The downloaded file is ignored by Git.

## Status codes and expected results

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

## Run the tests

```powershell
python -m unittest discover -s tests -v
```

The 28 tests cover exact wire bytes, numbered and literal headers, text and binary downloads, root mapping, malformed requests, path protection, persistent connections, unknown frames, verbose dumps, and EOF handling. They also check that the annotated ranges explain every captured byte.

Tests launch their own local server and client processes and clean up temporary files. A separately running demonstration server is not needed. If Make is installed, `make test` and `make check` are optional shortcuts.

## Notes and limitations

- If port 9000 is occupied, choose another port in both commands.
- Paths are literal filenames; percent escapes are not decoded. Requests cannot escape the server root.
- The server keeps connections open after normal responses and recoverable errors. Oversized or incomplete frames close the connection as specified.
- The client uses one connection and does not retry. Compression, TLS, and multiplexing are outside this project's scope.
- Unix-style entry points can be enabled with `chmod +x bserve bcurl`. Testing was performed on Windows.
- The included client and server have been tested together and against test peers. Interoperability with a separately authored partner endpoint has not been demonstrated.
