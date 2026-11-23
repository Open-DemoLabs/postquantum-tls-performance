# wrk-pqc — wrk built against OpenSSL 3.5 on CentOS Stream 9

A container image with [wrk](https://github.com/wg/wrk) compiled against the
**system OpenSSL (>= 3.5)** of CentOS Stream 9. It also contains two test scripts
that use it for TLS 1.3 benchmarks with classical and post-quantum (ML-KEM,
ML-DSA, SLH-DSA) algorithms. Each test is configured through environment
variables: server IP, port, scenario and OpenSSL config file path.

The image is built in two stages:

| Stage     | Base image                              | What it does                                                                                   |
|-----------|-----------------------------------------|------------------------------------------------------------------------------------------------|
| `builder` | `quay.io/centos/centos:stream9`         | Installs gcc/make/git/unzip/curl/`openssl-devel`, clones wrk, runs `make WITH_OPENSSL=/usr -j"$(nproc)"`, checks linkage, downloads the GPL-3.0 license, stages wrk + the whole `scripts/` tree in `/staging` |
| runtime   | `quay.io/centos/centos:stream9-minimal` | Installs only the OpenSSL runtime and CLI, copies `/staging/` to `/`, and runs as UID 1001       |

The final image contains no compiler, no sources and no `-devel` packages.

---

## 1. Repository layout

```
wrk-pqc/
├── Containerfile              # Multi-stage build (podman / buildah)
├── README.md                  # This file
└── scripts/                   # Copied entirely to /srv/scripts (see "Copy rules")
    ├── tls-check.sh           # One handshake with openssl s_client + checks
    ├── run-checks.sh          # tls-check.sh, then the wrk test
    ├── close.lua              # "Connection: close" => one full handshake per request
    └── openssl/
        ├── openssl-A1.cnf     # X25519MLKEM768      (server cert ML-DSA-65)
        ├── openssl-A2.cnf     # secp384r1           (server cert ECDSA P-384/SHA-384)
        ├── openssl-B1.cnf     # X25519MLKEM768      (server cert SLH-DSA-SHA2-192s)
        ├── openssl-C1.cnf     # MLKEM1024           (server cert ML-DSA-87)
        └── openssl-C2.cnf     # secp521r1           (server cert ECDSA P-521/SHA-512)
```

### Copy rules for `scripts/`

The **whole** `scripts/` directory is copied recursively to `/srv/scripts`,
whatever it contains. Drop in any extra file or subdirectory and it will be in
the image after the next build. Permissions are set in the image regardless of
the permissions in your checkout:

| Item                                                                 | Mode   |
|----------------------------------------------------------------------|--------|
| Directories                                                          | `0755` |
| Bash scripts: name ends in `.sh`, **or** first line is a `#!` shebang for `bash` or `sh` (`#!/bin/bash`, `#!/usr/bin/env bash`, `#!/bin/sh`, ...) | `0755` |
| Any other file (`.lua`, `.cnf`, `.py`, data files, ...)              | `0644` |

Ownership is reset to `root:root`. The downloaded GPL-3.0 text is copied last
as `/srv/scripts/LICENSE` (`0644`), so it replaces any `scripts/LICENSE` file.
The build log lists the staged tree with its modes ("Staged /srv/scripts:").

What the runtime image contains:

| Path                               | Content                                                                    |
|------------------------------------|----------------------------------------------------------------------------|
| `/usr/local/bin/wrk`               | wrk, linked to `/lib64/libssl.so.3` and `/lib64/libcrypto.so.3` (LuaJIT linked statically) |
| `/srv/scripts/` (**WORKDIR**)      | Everything from `scripts/` (by default `tls-check.sh`, `run-checks.sh`, `close.lua`, `openssl/*.cnf`) + `LICENSE` (GPL-3.0). In `PATH`. |
| `/srv/data/`                       | Empty directory. Mount a volume here with your own scripts or configs.     |
| `/usr/share/licenses/wrk/`         | wrk upstream LICENSE / NOTICE (Apache-2.0, kept as required by that license) |
| `/usr/share/doc/wrk/BUILD-INFO`    | Repo, ref, commit, OpenSSL build version, build date                       |

No default command: the image defines no `ENTRYPOINT` and an empty `CMD`, so it runs nothing unless you pass a command (see section 6).

---

## 2. Requirements

- `podman` and/or `buildah` (rootless works).
- Network access during the build to `quay.io`, the CentOS Stream mirrors and `github.com`.
- CentOS Stream 9 repositories that ship **OpenSSL >= 3.5**. Both stages fail the
  build if `openssl-libs` is older than `MIN_OPENSSL_VERSION` (default `3.5.0`) or
  if ML-KEM / ML-DSA are not available.

---

## 3. Building

```bash
cd wrk-pqc

# podman
podman build -t localhost/wrk-pqc:latest -f Containerfile .

# or buildah
buildah build --layers -t localhost/wrk-pqc:latest -f Containerfile .
```

Pull the base image again first (`podman pull quay.io/centos/centos:stream9`), or
add `--no-cache`, to get the newest OpenSSL 3.5.x from the Stream repos.

### Build arguments

| Argument              | Default                                   | Description                                                 |
|-----------------------|-------------------------------------------|-------------------------------------------------------------|
| `BUILDER_IMAGE`       | `quay.io/centos/centos:stream9`           | Base image for the compile stage                            |
| `RUNTIME_IMAGE`       | `quay.io/centos/centos:stream9-minimal`   | Base image for the final stage                              |
| `WRK_REPO`            | `https://github.com/wg/wrk.git`           | wrk Git repository                                          |
| `WRK_REF`             | `master`                                  | Branch or tag for `git clone --branch` (e.g. `4.2.0`). Not a commit SHA. |
| `MIN_OPENSSL_VERSION` | `3.5.0`                                   | Minimum `openssl-libs` version allowed in both stages       |
| `LICENSE_URL`         | `https://www.gnu.org/licenses/gpl-3.0.txt` | Where the GPL-3.0 text is downloaded from at build time     |

### What the build checks

1. OpenSSL version >= `MIN_OPENSSL_VERSION` and ML-KEM/ML-DSA available (both stages).
2. `ldd wrk` resolves `libssl.so.3` / `libcrypto.so.3` to `/lib64` or `/usr/lib64`.
   This proves the OpenSSL bundled with wrk was **not** used.
3. The downloaded license really is the GPLv3 text (`GNU GENERAL PUBLIC LICENSE`,
   `Version 3, 29 June 2007`). An error page or a different license fails the build.
4. `timeout` is present in the runtime image (needed by `tls-check.sh`).
5. `wrk -v` runs in the runtime image, so all shared libraries are present.

### Checking that the image has no default command

```bash
podman image inspect localhost/wrk-pqc:latest --format 'Entrypoint={{.Config.Entrypoint}} Cmd={{.Config.Cmd}}'
# Expected: Entrypoint=[] Cmd=[]
```

Running the image without a command (`podman run localhost/wrk-pqc:latest`)
fails with an error saying no command was given. That is intentional: every
run must name the command (`run-checks.sh`, `tls-check.sh`, `wrk`, `openssl`,
`bash`, a script in `/srv/data`, ...).

---

## 4. Environment variables

### Test target (used by both scripts)

| Variable            | Required | Default            | Description                                                              |
|---------------------|----------|--------------------|--------------------------------------------------------------------------|
| `SERVER_IP`         | yes      | —                  | Server IP address (IPv4 or IPv6) or hostname                             |
| `SERVER_PORT`       | yes      | —                  | Server TLS port                                                          |
| `SCENARIO`          | yes      | —                  | Scenario ID: `A1`, `A2`, `B1`, `C1`, `C2` or any custom label            |
| `OPENSSL_CONF_PATH` | no       | empty              | OpenSSL client config file. The scripts export it as `OPENSSL_CONF`. Empty means the system default (crypto-policies). |

### `tls-check.sh`

| Variable            | Default                          | Description                                                       |
|---------------------|----------------------------------|-------------------------------------------------------------------|
| `EXPECT_GROUP`      | derived from `SCENARIO` (below)  | Expected key-exchange group (case-insensitive substring match)    |
| `EXPECT_CIPHER`     | `TLS_AES_256_GCM_SHA384`         | Expected TLS 1.3 cipher suite                                     |
| `EXPECT_SIGALG`     | empty (not checked)              | Expected server signature type substring, e.g. `mldsa65`          |
| `TLS_CHECK_TIMEOUT` | `10`                             | Handshake timeout, in seconds                                     |

Default `EXPECT_GROUP` per scenario:

| `SCENARIO` | Expected group   |
|------------|------------------|
| `A1`, `B1` | `X25519MLKEM768` |
| `A2`       | `secp384r1`      |
| `C1`       | `MLKEM1024`      |
| `C2`       | `secp521r1`      |
| other      | not checked unless `EXPECT_GROUP` is set |

### `run-checks.sh`

| Variable          | Default                       | Description                                                     |
|-------------------|-------------------------------|-----------------------------------------------------------------|
| `WRK_THREADS`     | `8`                           | wrk `-t` (one per client vCPU)                                  |
| `WRK_CONNECTIONS` | `200`                         | wrk `-c`                                                        |
| `WRK_DURATION`    | `60s`                         | wrk `-d`                                                        |
| `WRK_SCRIPT`      | `/srv/scripts/close.lua`      | wrk `-s`. Set it **empty** (`-e WRK_SCRIPT=`) for keep-alive.   |
| `WRK_PATH`        | `/`                           | URL path requested                                              |
| `WRK_EXTRA_ARGS`  | empty                         | Extra wrk arguments, space separated (e.g. `--timeout 5s`)      |
| `SKIP_TLS_CHECK`  | `0`                           | `1` = skip `tls-check.sh` before wrk                            |

---

## 5. The scripts

### `tls-check.sh`

Performs one handshake with `openssl s_client -brief` against
`SERVER_IP:SERVER_PORT`, using `OPENSSL_CONF_PATH`, and prints a table:

```
tls-check: scenario=A1 target=10.0.0.10:10443 openssl_conf=/srv/scripts/openssl/openssl-A1.cnf
  protocol   TLSv1.3                                  OK
  cipher     TLS_AES_256_GCM_SHA384                   OK
  group      X25519MLKEM768                           OK
  signature  mldsa65                                  (not checked)
tls-check: PASS
```

| Exit code | Meaning                                                   |
|-----------|-----------------------------------------------------------|
| 0         | All checks passed                                         |
| 1         | Handshake OK, but a parameter does not match the scenario |
| 2         | Handshake failed (the raw `s_client` output is printed)   |
| 3         | Configuration error (missing variable, unreadable file)   |

### `run-checks.sh`

1. Prints a header with the date, scenario, URL, OpenSSL config, OpenSSL
   version and wrk parameters.
2. Runs `tls-check.sh`. If that fails, it exits with the same code and **does not
   start wrk**, so you never benchmark a handshake with the wrong parameters.
3. Runs:
   `wrk -t $WRK_THREADS -c $WRK_CONNECTIONS -d $WRK_DURATION --latency [-s $WRK_SCRIPT] [$WRK_EXTRA_ARGS] https://$SERVER_IP:$SERVER_PORT$WRK_PATH`

### OpenSSL config files (`/srv/scripts/openssl/`)

wrk has no command-line options for TLS groups or cipher suites. Instead, it
uses the `system_default` section of the OpenSSL config that `OPENSSL_CONF`
points to. Each scenario file:

- sets `MinProtocol = MaxProtocol = TLSv1.3` and `Ciphersuites = TLS_AES_256_GCM_SHA384`;
- sets **only** the scenario's group in `Groups`, so the handshake fails instead of
  falling back to another group;
- does **not** include crypto-policies, so results don't depend on the system policy;
- sets `config_diagnostics = 1`, so a typo is an error instead of being ignored;
- has an optional, commented `SignatureAlgorithms` line that makes the client
  accept only the expected certificate type.

To use your own config, put it in the `/srv/data` volume and point
`OPENSSL_CONF_PATH` at it (e.g. `/srv/data/my-openssl.cnf`).

---

## 6. Running tests

### Scenario / port map (current Apache `benchmark.conf`)

| `SCENARIO` | Key exchange     | Server signature    | `SERVER_PORT` | `OPENSSL_CONF_PATH`                     |
|------------|------------------|---------------------|---------------|-----------------------------------------|
| A1         | X25519MLKEM768   | ML-DSA-65           | 10443         | `/srv/scripts/openssl/openssl-A1.cnf`   |
| A2         | NIST P-384       | ECDSA + SHA-384     | 8443          | `/srv/scripts/openssl/openssl-A2.cnf`   |
| B1         | X25519MLKEM768   | SLH-DSA-SHA2-192s   | 11443         | `/srv/scripts/openssl/openssl-B1.cnf`   |
| C1         | ML-KEM-1024      | ML-DSA-87           | 443           | `/srv/scripts/openssl/openssl-C1.cnf`   |
| C2         | NIST P-521       | ECDSA + SHA-512     | 9443          | `/srv/scripts/openssl/openssl-C2.cnf`   |

### Recommended podman flags for benchmarking

| Flag                            | Why                                                                         |
|---------------------------------|-----------------------------------------------------------------------------|
| `--network host`                | Avoids rootless podman's userspace network stack (pasta/slirp4netns). Without it you measure the network stack, not TLS. |
| `--ulimit nofile=65535:65535`   | wrk opens one socket per connection                                         |
| `--cpuset-cpus 0-7`             | Pins wrk to known CPUs (client has 8 vCPUs). Match `WRK_THREADS` to this.   |
| `--rm`                          | Throw-away container per run                                                |

### Example: scenario A1, handshake-bound test

```bash
podman run --rm --network host --ulimit nofile=65535:65535 --cpuset-cpus 0-7 \
  -e SERVER_IP=10.0.0.10 \
  -e SERVER_PORT=10443 \
  -e SCENARIO=A1 \
  -e OPENSSL_CONF_PATH=/srv/scripts/openssl/openssl-A1.cnf \
  localhost/wrk-pqc:latest run-checks.sh
```

`run-checks.sh` checks the handshake, then runs
`wrk -t 8 -c 200 -d 60s --latency -s /srv/scripts/close.lua https://10.0.0.10:10443/`.

### Example: changing wrk parameters and saving the output

```bash
podman run --rm --network host --ulimit nofile=65535:65535 --cpuset-cpus 0-7 \
  -e SERVER_IP=10.0.0.10 -e SERVER_PORT=443 -e SCENARIO=C1 \
  -e OPENSSL_CONF_PATH=/srv/scripts/openssl/openssl-C1.cnf \
  -e WRK_CONNECTIONS=250 -e WRK_DURATION=30s -e WRK_EXTRA_ARGS="--timeout 5s" \
  localhost/wrk-pqc:latest run-checks.sh 2>&1 | tee wrk-C1-$(date +%Y%m%dT%H%M%S).txt
```

### Example: keep-alive throughput test (no per-request handshake)

```bash
podman run --rm --network host --ulimit nofile=65535:65535 \
  -e SERVER_IP=10.0.0.10 -e SERVER_PORT=8443 -e SCENARIO=A2 \
  -e OPENSSL_CONF_PATH=/srv/scripts/openssl/openssl-A2.cnf \
  -e WRK_SCRIPT= \
  localhost/wrk-pqc:latest run-checks.sh
```

### Example: handshake check only

```bash
podman run --rm --network host \
  -e SERVER_IP=10.0.0.10 -e SERVER_PORT=10443 -e SCENARIO=A1 \
  -e OPENSSL_CONF_PATH=/srv/scripts/openssl/openssl-A1.cnf \
  -e EXPECT_SIGALG=mldsa65 \
  localhost/wrk-pqc:latest tls-check.sh
```

### Example: all scenarios in sequence (run on the host)

```bash
#!/bin/bash
set -euo pipefail
SERVER_IP=10.0.0.10
IMAGE=localhost/wrk-pqc:latest
declare -A PORT=( [A1]=10443 [A2]=8443 [B1]=11443 [C1]=443 [C2]=9443 )

mkdir -p results
for s in A1 A2 B1 C1 C2; do
  podman run --rm --network host --ulimit nofile=65535:65535 --cpuset-cpus 0-7 \
    -e SERVER_IP="${SERVER_IP}" -e SERVER_PORT="${PORT[$s]}" -e SCENARIO="${s}" \
    -e OPENSSL_CONF_PATH="/srv/scripts/openssl/openssl-${s}.cnf" \
    "${IMAGE}" run-checks.sh 2>&1 | tee "results/wrk-${s}-$(date +%Y%m%dT%H%M%S).txt"
  sleep 10
done
```

---

## 7. Custom scripts with the `/srv/data` volume

`/srv/data` exists in the image and is declared as a `VOLUME`. Mount a host
directory there to provide your own wrk Lua scripts, OpenSSL configs or shell
scripts. Use `:Z` on SELinux hosts.

```bash
# Custom wrk Lua script with the standard runner
podman run --rm --network host --ulimit nofile=65535:65535 \
  -v "$PWD/mydata:/srv/data:Z" \
  -e SERVER_IP=10.0.0.10 -e SERVER_PORT=10443 -e SCENARIO=A1 \
  -e OPENSSL_CONF_PATH=/srv/scripts/openssl/openssl-A1.cnf \
  -e WRK_SCRIPT=/srv/data/bench.lua \
  localhost/wrk-pqc:latest run-checks.sh

# Custom OpenSSL config
podman run --rm --network host -v "$PWD/mydata:/srv/data:Z" \
  -e SERVER_IP=10.0.0.10 -e SERVER_PORT=10443 -e SCENARIO=A1 \
  -e OPENSSL_CONF_PATH=/srv/data/openssl-custom.cnf \
  localhost/wrk-pqc:latest run-checks.sh

# Custom shell script (must be executable, or call it with bash)
podman run --rm --network host -v "$PWD/mydata:/srv/data:Z" \
  -e SERVER_IP=10.0.0.10 -e SERVER_PORT=10443 -e SCENARIO=A1 \
  localhost/wrk-pqc:latest bash /srv/data/my-test.sh
```

Custom scripts get the same environment variables. `/srv/scripts` is in `PATH`,
so they can call `tls-check.sh`, `run-checks.sh`, `wrk` and `openssl` directly.
`OPENSSL_CONF_PATH` is **not** exported as `OPENSSL_CONF` for custom scripts
(only the two bundled scripts do that). Export it yourself, or pass
`-e OPENSSL_CONF=...`.

The container runs as UID 1001. If your scripts write results into `/srv/data`
under rootless podman, add `--userns=keep-id` or make the directory writable for
the mapped UID.

---

## 8. Other useful commands

```bash
# Shell inside the image (starts in /srv/scripts)
podman run --rm -it localhost/wrk-pqc:latest bash

# wrk version / build metadata / OpenSSL capabilities
podman run --rm localhost/wrk-pqc:latest wrk -v
podman run --rm localhost/wrk-pqc:latest cat /usr/share/doc/wrk/BUILD-INFO
podman run --rm localhost/wrk-pqc:latest openssl version -a
podman run --rm localhost/wrk-pqc:latest openssl list -kem-algorithms
podman run --rm localhost/wrk-pqc:latest openssl list -signature-algorithms
podman run --rm localhost/wrk-pqc:latest openssl list -tls-groups
```

---

## 9. Troubleshooting

| Symptom                                                    | Cause / fix                                                                                     |
|------------------------------------------------------------|-------------------------------------------------------------------------------------------------|
| `run-checks: ERROR: SERVER_IP is not set` (exit 3)         | Missing `-e SERVER_IP/SERVER_PORT/SCENARIO`.                                                    |
| `OPENSSL_CONF_PATH=... is not readable` (exit 3)           | Wrong path, volume not mounted, or SELinux denial (add `:Z`).                                   |
| `tls-check: FAIL - handshake failed` (exit 2)              | Server down/wrong port, or no common group/signature with the server. Read the printed `s_client` output. |
| `group ... MISMATCH` (exit 1)                              | The config doesn't match the scenario, or `OPENSSL_CONF_PATH` is empty and the system default picked another group. |
| `wrk -v` fails at build time / `ldd` check fails           | wrk built the bundled OpenSSL: check that `openssl-devel` installed and `WITH_OPENSSL=/usr` reached `make`. |
| Build fails: `OpenSSL x.y.z is older than the required 3.5.0` | Outdated base image or mirror: `podman pull` again or build with `--no-cache`.               |
| `stream9-minimal` image not found                          | `--build-arg RUNTIME_IMAGE=quay.io/centos/centos:stream9` (bigger image, otherwise identical).  |
| Much lower requests/s than expected                        | Missing `--network host`, `nofile` limit too low, or client CPU saturated.                       |

---

## 10. Notes

- wrk does not verify the server certificate (`SSL_VERIFY_NONE`). The signature
  verification cost is still paid during the handshake.
- `tls-check.sh` reads the fields printed by `openssl s_client -brief`. The
  signature type is only checked when `EXPECT_SIGALG` is set, because its
  wording varies between OpenSSL versions and algorithms.
- Keep `/usr/share/doc/wrk/BUILD-INFO` with your results, because the OpenSSL
  3.5.x version can change between rebuilds.

---

## 11. License

This project (Containerfile, scripts, Lua script and OpenSSL configs) is
licensed under the **GNU General Public License v3.0 or later**
(`SPDX-License-Identifier: GPL-3.0-or-later`). Every file carries that SPDX
header, and the image label `org.opencontainers.image.licenses` is
`GPL-3.0-or-later`.

The license text is not stored in this repository. It is **downloaded at build
time** from `LICENSE_URL` (default `https://www.gnu.org/licenses/gpl-3.0.txt`),
checked, and copied to `/srv/scripts/LICENSE` in the image:

```bash
podman run --rm localhost/wrk-pqc:latest head -n 3 /srv/scripts/LICENSE
```

wrk itself is a third-party component under the **Apache License 2.0**. Its
upstream `LICENSE`/`NOTICE` files are kept in `/usr/share/licenses/wrk/`, as the
Apache license requires. Apache-2.0 code can be combined into a GPLv3 work.
