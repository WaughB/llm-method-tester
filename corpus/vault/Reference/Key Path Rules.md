---
tags: [aurora-mesh, reference]
---
Key path rules in Aurora Mesh: slash-delimited UTF-8, at most 12 segments,
at most 256 bytes total. Trailing slash means prefix operation (used by
[[Watch Streams]]).

Paths live inside a namespace (default `prism`). Every write returns a
revision; history is readable inside the 1000-revision horizon kept by
[[Moonpress Compaction]]. Oversized values are a different failure — that's
E-1408 in [[Error Codes]], the 768 KB entry cap.
