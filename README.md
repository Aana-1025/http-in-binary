# Binary TCP file server and client

A small Network Architecture course project, using **Python 3.9 or newer and its standard library only**. Developed and tested on Windows with Python 3.11.9. No packages, paid services, or cloud accounts are needed.

`bserve` reads a binary request and returns a file. `bcurl` sends one GET-like request and writes the exact response body. This is our course protocol, not regular HTTP: a web browser or ordinary curl cannot talk to it.

## Run on Windows

Install Python 3.9 or newer if needed, enabling its PATH option. Open PowerShell in the extracted project folder, or your cloned repository folder, where `bserve`, `bcurl`, and `SPEC.md` are visible. From its parent folder, use `cd network-architecture-project`. Check Python with `python --version`. If your installation uses the Python launcher, replace `python` with `py -3` below. No pip install or build step is needed.

In the first terminal:

```powershell
python bserve ./www 9000
```

In a second terminal, in the same folder:

```powershell
python bcurl localhost:9000/hello.txt
python bcurl localhost:9000/
python bcurl -v localhost:9000/hello.txt
python bcurl localhost:9000/missing.txt
$LASTEXITCODE
```

The last request prints an error body and exits with 1. Successful 2xx responses exit with 0; all failures exit with 1. Verbose hex output goes to stderr, so stdout remains the body. Stop the server with **Ctrl+C**. The server listens on `127.0.0.1` for local demonstrations and handles clients one at a time. No compilation step is required.

To save and verify a binary download without relying on PowerShell redirection behaviour:

```powershell
python -c "import subprocess,sys,pathlib; r=subprocess.run([sys.executable,'bcurl','localhost:9000/sample.bin'],capture_output=True); pathlib.Path('download.bin').write_bytes(r.stdout); sys.exit(r.returncode)"
python -c "from pathlib import Path; assert Path('download.bin').read_bytes()==Path('www/sample.bin').read_bytes(); print('Exact binary match')"
```

`download.bin` is a temporary output, ignored by Git. If port 9000 is occupied, select another port in both commands. Run the second terminal from the same folder; if no response arrives, check that the first terminal is still serving. On Unix-like systems, use `chmod +x bserve bcurl` before the assignment's `./bserve` and `./bcurl` forms. Unix launch behaviour has not been tested here.

## Check and test

```powershell
python -m compileall -q src tests
python -m unittest discover -s tests -v
```

Tests start and stop their own local server and client processes, choose a temporary port, and clean up temporary sample files. You do not need to leave the demonstration server running. Tests also use independently constructed wire bytes and test peers. If Make is already installed, `make check` and `make test` are optional shortcuts.

Full observed test output is in `evidence/test-results.txt`. Tests cover text, binary and empty files; root mapping; 404; malformed requests; traversal protection; persistent connections; unknown-frame skipping; fragmented TCP input; verbose dumps; client failures; clean and partial EOF; oversized input/files; and controlled file errors. Ctrl+C cleanup and resolved-path containment have unit tests; actual Windows junction/symlink behaviour and interactive console Ctrl+C have not been separately demonstrated.

## How to explain it

- TCP delivers a stream of bytes. The eight-byte header tells us where each message ends.
- `src/protocol.py` packs/unpacks fields, checks lengths, reads exact byte counts, and dumps hex.
- `src/server.py` loops over frames on the same connection and serves files confined to the root.
- `src/client.py` opens one connection, sends a request, reads its response, and outputs the body.
- Unknown types are skipped using their payload length, allowing future extensions.
- Response body length comes from the remaining payload, not HTTP headers.

Read **SPEC.md** for the complete wire format and **SPEC.pdf** for its two-page submission rendering. The protocol has not been changed during implementation or audit. Percent sequences are literal filenames; no URL decoding, HTTP caching, compression, automatic retry, or multiplexing is implemented. The 16 MiB payload cap bounds memory use; recoverable malformed requests receive 400 and leave the connection open.

## Files and submission status

`www/index.html`, `www/hello.txt`, and `www/sample.bin` are demonstration files; the binary sample contains every byte value 0–255. The `evidence` folder contains a live request/response dump, its annotation, and test output.

The course requires a **two-page rendered specification** and paired, specification-only collaboration. SPEC.pdf supplies the two-page specification. Our local client/server and independent test peers do not establish actual partner interoperability; that course requirement remains unfulfilled. Git is optional for running the project. The repository contains code, tests, documentation, samples, and evidence; no GitHub publication has been performed.
