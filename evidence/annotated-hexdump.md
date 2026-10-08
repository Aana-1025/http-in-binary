# Annotated live exchange

This exchange was captured from bserve and bcurl running on Windows with Python 3.11.9.

Command: `python bcurl -v localhost:53702/hello.txt`. A local TCP relay forwarded this request to bserve on port 53701.

The relay captured the socket bytes in both directions, which matched the verbose dumps. The client exited with 0, and the returned body matched `www/hello.txt` byte for byte.

Byte ranges below are decimal, inclusive, and start at zero per frame. request-response.hex uses hexadecimal offsets.

## REQUEST

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
| 26-40 | Value | 'localhost:53702' |
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

The ranges cover every byte of both frames. The test suite checks each annotation value against the capture. The response body occupies the remaining payload, with no separate body-length field.

The capture records an exchange between the client and server included in this repository.
