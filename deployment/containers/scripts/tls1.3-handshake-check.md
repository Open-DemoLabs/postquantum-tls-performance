# TLS 1.3 handshake check scripts

This directory contains the scripts that check the TLS 1.3 handshake of every
PQC/classical scenario served by Apache, plus the helper files used by the
`wrk-pqc` container image (`close.lua`, `openssl/*.cnf`).

| File                         | Purpose                                                                 |
|------------------------------|-------------------------------------------------------------------------|
| `tls1.3-handshake-check.sh`  | Runs one strict TLS 1.3 handshake per scenario and verifies KEX group, certificate signature algorithm and cipher suite. |
| `tls1.3-handshake-env.sh`    | Exports the environment variables that `tls1.3-handshake-check.sh` needs. **Must be sourced.** |
| `close.lua`                  | wrk script that sends `Connection: close` (one full handshake per request). |
| `openssl/openssl-XX.cnf`     | Per-scenario OpenSSL client configs used with wrk.                      |

---

## 1. Requirements

- Bash 4+ (uses arrays, `${!var}` indirect expansion and `${var,,}`).
- OpenSSL 3.5+ (RHEL 10.2 / CentOS Stream 9 with OpenSSL 3.5) for ML-KEM,
  ML-DSA and SLH-DSA.
- `timeout` (coreutils).
- The Apache server configured with one VirtualHost per scenario, each listening
  on its own port.

---

## 2. Environment variables

`tls1.3-handshake-check.sh` no longer has the server address or ports hardcoded.
It reads them from the bash environment. **All of them are required**:

| Variable        | Scenario | Key exchange      | Certificate signature | Default in `tls1.3-handshake-env.sh` |
|-----------------|----------|-------------------|-----------------------|--------------------------------------|
| `APACHE_SERVER` | —        | —                 | —                     | `192.0.2.10`                         |
| `PORT_A1`       | A1       | X25519MLKEM768    | ML-DSA-65             | `10443`                              |
| `PORT_A2`       | A2       | NIST P-384        | ECDSA + SHA-384       | `8443`                               |
| `PORT_B1`       | B1       | X25519MLKEM768    | SLH-DSA-SHA2-192s     | `11443`                              |
| `PORT_C1`       | C1       | ML-KEM-1024       | ML-DSA-87             | `12443`                              |
| `PORT_C2`       | C2       | NIST P-521        | ECDSA + SHA-512       | `9443`                               |

Validation done by the check script before any connection is attempted:

1. Every variable above must be set **and non-empty**. Otherwise the script
   lists the missing ones, shows how to configure them, and exits with code `2`.
2. Every `PORT_XX` must be an integer between `1` and `65535`. Otherwise the
   script lists the invalid values and exits with code `2`.

Example of the error when nothing is configured:

```text
$ ./tls1.3-handshake-check.sh
ERROR: the following required environment variable(s) are not set or empty:
         - APACHE_SERVER
         - PORT_A1
         - PORT_A2
         - PORT_B1
         - PORT_C1
         - PORT_C2
       Required: APACHE_SERVER PORT_A1 PORT_A2 PORT_B1 PORT_C1 PORT_C2
       Configure them before running this script, for example:
         source ./tls1.3-handshake-env.sh
       or export them manually:
         export APACHE_SERVER=192.0.2.10 PORT_A1=10443 PORT_A2=8443 \
                PORT_B1=11443 PORT_C1=12443 PORT_C2=9443
```

Other optional variables:

| Variable   | Description                                                  |
|------------|--------------------------------------------------------------|
| `NO_COLOR` | If set (any value), disables colored output.                 |

---

## 3. Configuring the variables with `tls1.3-handshake-env.sh`

1. Edit `tls1.3-handshake-env.sh` and set `APACHE_SERVER` and the `PORT_XX`
   values for your environment.
2. **Source** it in your current shell (do not execute it):

   ```bash
   source ./tls1.3-handshake-env.sh
   # or the POSIX form
   . ./tls1.3-handshake-env.sh
   ```

   It prints the configured values:

   ```text
   TLS 1.3 handshake check environment configured:
     APACHE_SERVER = 192.0.2.10
     PORT_A1       = 10443
     PORT_A2       = 8443
     PORT_B1       = 11443
     PORT_C1       = 12443
     PORT_C2       = 9443
   ```

3. Verify them at any time with:

   ```bash
   env | grep -E '^(APACHE_SERVER|PORT_(A1|A2|B1|C1|C2))='
   ```

If you run it as a program (`./tls1.3-handshake-env.sh` or
`bash tls1.3-handshake-env.sh`) it refuses with an error and exit code `1`,
because the exported variables would disappear as soon as the child process ends.

Since the variables are exported, they are inherited by every program started
from that shell, including `tls1.3-handshake-check.sh`. They last until the
shell is closed. To remove them:

```bash
unset APACHE_SERVER PORT_A1 PORT_A2 PORT_B1 PORT_C1 PORT_C2
```

---

## 4. Running the handshake check

```bash
source ./tls1.3-handshake-env.sh
./tls1.3-handshake-check.sh
```

### Overriding values for a single run

Variables given on the command line apply only to that run and take precedence
over the exported ones:

```bash
APACHE_SERVER=10.0.0.20 PORT_C1=443 ./tls1.3-handshake-check.sh
```

Without sourcing the env file, all six variables must be given:

```bash
APACHE_SERVER=10.0.0.10 PORT_A1=10443 PORT_A2=8443 PORT_B1=11443 \
PORT_C1=12443 PORT_C2=9443 ./tls1.3-handshake-check.sh
```

### Endpoint positional argument

The optional first argument still overrides the endpoint used for the
connections (for example, to connect by a different IP or hostname).
`APACHE_SERVER` must still be set, because it is validated before the argument
is considered:

```bash
./tls1.3-handshake-check.sh web.example.com
```

### Inside the `wrk-pqc` container

The image's default command is `tls1.3-handshake-check.sh`, so the variables
must be passed with `-e` (or with `--env-file`):

```bash
podman run --rm --network host \
  -e APACHE_SERVER=10.0.0.10 \
  -e PORT_A1=10443 -e PORT_A2=8443 -e PORT_B1=11443 \
  -e PORT_C1=12443 -e PORT_C2=9443 \
  quay.io/repository/rhte_2019/wrk-pqc:latest
```

You can also reuse the env file on the host to forward the values:

```bash
source ./tls1.3-handshake-env.sh
podman run --rm --network host \
  -e APACHE_SERVER -e PORT_A1 -e PORT_A2 -e PORT_B1 -e PORT_C1 -e PORT_C2 \
  quay.io/repository/rhte_2019/wrk-pqc:latest
```

(`-e NAME` without a value copies `NAME` from the host environment.)

---

## 5. What the check verifies

For each scenario the script runs `openssl s_client` against
`<endpoint>:<PORT_XX>` offering **only** the scenario's group and **only** the
`TLS_AES_256_GCM_SHA384` suite, so an unsupported configuration fails the
handshake instead of silently falling back. It then checks:

1. The protocol is `TLSv1.3`.
2. The negotiated key exchange group matches the expected one.
3. The expected signature algorithm appears in the server certificate.
4. The negotiated cipher suite is `TLS_AES_256_GCM_SHA384` (AEAD `AES_256_GCM`,
   hash `SHA384`).

Each scenario prints `RESULT: PASS` or `RESULT: FAIL`, followed by a summary.

---

## 6. Exit codes

| Code | Meaning                                                                       |
|------|-------------------------------------------------------------------------------|
| `0`  | All scenarios passed.                                                         |
| `1`  | At least one scenario failed.                                                 |
| `2`  | Required environment variable missing/empty, invalid port, or `openssl` not found in `PATH`. |

`tls1.3-handshake-env.sh` returns `1` only when it is executed instead of sourced.
