# Final submission-readiness audit

Protocol unchanged. SPEC.md, SPEC.pdf, code, README and capture agree. SPEC.pdf is exactly two A4 pages and both rendered pages were visually inspected.

The live evidence was freshly captured through a TCP relay, independently observing socket bytes; these matched verbose output. Annotation tests validate every value and contiguous byte coverage (81-byte request; 93-byte response).

## Original assignment requirements

| Requirement | Result |
| --- | --- |
| bserve TCP listener and binary request | PASS |
| Path mapped to a file inside root | PASS |
| Response status, headers and exact file bytes | PASS |
| 404 for absent file | PASS |
| 400 for malformed request | PASS |
| Persistent connection after normal and recoverable-error responses | PASS |
| bcurl constructs request and reads response | PASS |
| Body to stdout | PASS |
| Verbose dump of every frame | PASS |
| Nonzero exit on 4xx/5xx | PASS |
| Client never opens a second connection | PASS |
| Fixed header with defended widths | PASS |
| Ten numbered header names and length-prefixed literal fallback | PASS |
| Unknown frame types skipped cleanly | PASS |
| Specification sufficient to implement either endpoint | PASS |
| Two-page specification | PASS |
| Program supplied | PASS |
| Actual complete annotated request/response hexdump | PASS |
| Paired authors with only the specification exchanged | FAIL - not demonstrated |
| Actual independently authored partner interoperability | FAIL - not demonstrated |

PASS for persistence applies to recoverable errors. Oversized/incomplete input closes as explicitly documented in the approved specification; a strict instructor interpretation could question this exception.

## Submission contents

The final archive contains only launchers, source, tests, samples, README, Makefile, .gitignore, specification Markdown/PDF, and evidence. Excluded: assignment image, both planning files, older ZIP, temporary PDF tools/renders, submission staging directories, caches, local downloads and Git metadata. Originals remain in the working folder.

## Remaining limits

Real paired/specification-only collaboration remains unfulfilled. Windows python launch commands were executed; Unix executable launch behaviour is not tested. The server binds loopback for local demonstrations. Interactive console Ctrl+C and actual Windows junction/symlink handling are not separately demonstrated; cleanup and containment have controlled tests.

At the time of this submission-readiness audit, no Git initialization or GitHub push had been performed.

## Final clean verification

28 tests passed from a fresh extraction of the intended archive. All tested source, sample, specification and capture files matched the submission copies byte-for-byte. Full output is in test-results.txt.
