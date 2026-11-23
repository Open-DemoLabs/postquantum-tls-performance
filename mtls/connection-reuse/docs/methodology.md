# Methodology and reproducibility notes

## Scope

A repeated, verified mutual-TLS (mTLS) performance experiment using Apache httpd (event MPM) with OpenSSL 3.5.8, on RHEL 9.8, compared **X25519** and **X25519MLKEM768** key establishment. The client/server certificate algorithm remained **ECDSA P-384** for both experimental profiles. The negotiated TLS version was TLS 1.3, and the configured cipher suite was `TLS_AES_256_GCM_SHA384`. Full experimental setup and negative certificate-verification tests are documented in the [main mTLS campaign](../../README.md).

## Trial matrix

- Low concurrency: 2 `wrk` threads, 10 connections, seed `20261120`; ran November 20, 2026.
- High concurrency: 8 `wrk` threads, 50 connections, seed `20261121`; ran November 22, 2026.
- Both: five rounds; two TLS key-exchange profiles; two HTTP connection policies; 120 seconds per trial; 10-second pause between trials. **Total: 40 measured trials, 80 minutes timed workload.**
- `fresh`: request header `Connection: close`; intended one newly established TLS connection per HTTP request.
- `keepalive`: no explicit `Connection: close`, allowing HTTP/1.1 persistent connections. This **does not** mean TLS session resumption.
- For each round, the four scenarios were shuffled using a recorded random seed. Runs were not simultaneous.
- eBPF exporter was stopped, and the benchmark runner verified no active bpftrace process before each trial.
- Both campaigns record the same SHA-256 of the verified custom `wrk` binary in the experiment metadata. The executable is not redistributed.

## Validation

The client `wrk` version previously validated peer certificate verification (`SSL_VERIFY_PEER`), hostname validation (`SSL_set1_host`) and provision of a client certificate. The runner additionally parses negotiated TLS version, cipher suite, key exchange group, successful HTTP responses, socket error summaries, completed full handshakes and session resumptions. A run is rejected if fields mismatch, if session resumption is nonzero, if the HTTP/TLS handshake count ratio is implausible, or if `wrk` exits unsuccessfully.

The published CSVs contain no failed runs, missing matrix cells, zero handshakes or resumed TLS sessions, and every experiment records its parameters. **Original raw wrk output was not included in the uploaded archive**, therefore the per-run negotiated-group and detailed error checks cannot be independently verified from this dataset alone. This is a reproducibility limitation, not a reason to assert anything about absent logs.

## Interpretation limits

1. Whole-host CPU deltas (`/proc/stat`) are not per-process CPU time and do not isolate KEX computations.
2. Reported `wrk` HTTP response latency **excludes TLS connection establishment**. Do not use it for KEX timing.
3. High-concurrency fresh runs brought the server near 99.4% and client near 94% host busy. Saturation can conceal or confound algorithmic differences.
4. Five sequential rounds per condition permit exploratory, not definitive, inference; no multiple-testing correction. `t`-based 95% confidence intervals and exact sign-flip tests have differing assumptions and discreteness at n=5.
5. A CI containing zero is **not** evidence of equivalence. No equivalence or non-inferiority margin was specified or tested.
6. HTTP throughput improved sharply in keep-alive mode because the connection-management workload changed; this is **not** an isolated measure of ML-KEM overhead or a pure speed-up factor for TLS handshakes.
7. Some requests-per-handshake counts are slightly above 100. We have not established the server's effective `MaxKeepAliveRequests` or the exact boundary accounting for these values.
8. Because server/client machine characteristics, operating system and application stack affect throughput, these numbers should not be generalized across deployments.

## Publication and privacy

Publish sanitized numeric data, metadata, analysis scripts, source runner, PNG/SVG figures and statistical tables. Keep raw logs private until reviewed for hostnames, PKI configuration and other environment-specific details. Never commit private keys, certificate files, SSH configuration, credentials or internal FQDNs. Preserve the original raw benchmark logs offline for traceability.
