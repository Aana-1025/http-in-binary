# Annotated request and response

This is one complete file request and response between `bcurl` and `bserve`.

Client command:

```powershell
python bcurl -v localhost:55526/hello.txt
```

A local TCP relay on port 55526 recorded the traffic and forwarded it to `bserve` on port 55525, serving `www`.

The bytes below are the recorded socket bytes. They also match the client's verbose output. The response returned `www/hello.txt` unchanged, and the client exited with 0.

Offsets in the dumps are hexadecimal. Table ranges are decimal and inclusive, starting at zero for each frame. The same bytes are saved in [request-response.hex](request-response.hex).

## REQUEST

Client to server:

```text
00000000  00 00 00 49 01 01 00 00 01 00 0a 2f 68 65 6c 6c
00000010  6f 2e 74 78 74 00 05 01 00 0f 6c 6f 63 61 6c 68
00000020  6f 73 74 3a 35 35 35 32 36 02 00 07 62 63 75 72
00000030  6c 2f 31 03 00 03 2a 2f 2a 04 00 08 69 64 65 6e
00000040  74 69 74 79 05 00 0a 6b 65 65 70 2d 61 6c 69 76
00000050  65
```

| Byte range | Field | Value |
| --- | --- | --- |
| 0-3 | Payload length | 73 |
| 4-4 | Type | 1 |
| 5-5 | Version | 1 |
| 6-7 | Reserved | 0 |
| 8-8 | Method | 1 (GET) |
| 9-10 | Path length | 10 |
| 11-20 | Path | '/hello.txt' |
| 21-22 | Header count | 5 |
| 23-23 | Name ID | 1 (host) |
| 24-25 | Value length | 15 |
| 26-40 | Value | 'localhost:55526' |
| 41-41 | Name ID | 2 (user-agent) |
| 42-43 | Value length | 7 |
| 44-50 | Value | 'bcurl/1' |
| 51-51 | Name ID | 3 (accept) |
| 52-53 | Value length | 3 |
| 54-56 | Value | '*/*' |
| 57-57 | Name ID | 4 (accept-encoding) |
| 58-59 | Value length | 8 |
| 60-67 | Value | 'identity' |
| 68-68 | Name ID | 5 (connection) |
| 69-70 | Value length | 10 |
| 71-80 | Value | 'keep-alive' |

Total frame: 81 bytes = 8 header bytes + 73 payload bytes.

## RESPONSE

Server to client:

```text
00000000  00 00 00 55 02 01 00 00 00 c8 00 05 06 00 0a 74
00000010  65 78 74 2f 70 6c 61 69 6e 07 00 02 33 37 08 00
00000020  08 62 73 65 72 76 65 2f 31 09 00 08 6e 6f 2d 73
00000030  74 6f 72 65 0a 00 01 31 48 65 6c 6c 6f 20 66 72
00000040  6f 6d 20 74 68 65 20 62 69 6e 61 72 79 20 66 69
00000050  6c 65 20 70 72 6f 74 6f 63 6f 6c 21 0a
```

| Byte range | Field | Value |
| --- | --- | --- |
| 0-3 | Payload length | 85 |
| 4-4 | Type | 2 |
| 5-5 | Version | 1 |
| 6-7 | Reserved | 0 |
| 8-9 | Status | 200 |
| 10-11 | Header count | 5 |
| 12-12 | Name ID | 6 (content-type) |
| 13-14 | Value length | 10 |
| 15-24 | Value | 'text/plain' |
| 25-25 | Name ID | 7 (content-length) |
| 26-27 | Value length | 2 |
| 28-29 | Value | '37' |
| 30-30 | Name ID | 8 (server) |
| 31-32 | Value length | 8 |
| 33-40 | Value | 'bserve/1' |
| 41-41 | Name ID | 9 (cache-control) |
| 42-43 | Value length | 8 |
| 44-51 | Value | 'no-store' |
| 52-52 | Name ID | 10 (x-protocol-version) |
| 53-54 | Value length | 1 |
| 55-55 | Value | '1' |
| 56-92 | Body | b'Hello from the binary file protocol!\n' |

Total frame: 93 bytes = 8 header bytes + 85 payload bytes.

The first eight bytes of each frame are its fixed header. The request then carries GET, the path, and five numbered headers. The response carries status 200, five numbered headers, and the 37-byte file body.

The ranges explain every byte. The response body is everything left after the headers, with no separate body-length field.
