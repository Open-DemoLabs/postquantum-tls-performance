#!/usr/bin/env python3
"""Repeatable mTLS full-handshake vs HTTP keep-alive comparison.

Requires the previously validated wrk-mtls-verify executable, server-side
Apache mTLS vhosts, and SSH to the server for observer and CPU status.
This runner never changes httpd, exporter, crypto configuration or certificates.

Examples:
  python3 pqc_mtls_connection_reuse_campaign.py --runs 1 --duration 20
  python3 pqc_mtls_connection_reuse_campaign.py --runs 5 --duration 120
  python3 pqc_mtls_connection_reuse_campaign.py --profiles all --runs 5 --duration 120

Raw logs remain private. The CSV is structured and contains no hostname.
"""
import argparse
import csv
import datetime as dt
import json
import os
import random
import re
import shlex
import statistics
import subprocess
import sys
import time
from pathlib import Path

PROFILES = {
    "x25519": (16443, "x25519", "client-ecdsa.crt", "client-ecdsa.key", "regular-A2.chain.pem"),
    "hybrid": (15443, "X25519MLKEM768", "client-ecdsa.crt", "client-ecdsa.key", "regular-A2.chain.pem"),
    "classic": (13443, "secp384r1", "client-ecdsa.crt", "client-ecdsa.key", "regular-A2.chain.pem"),
    "pqc-auth": (14443, "X25519MLKEM768", "client-mldsa.crt", "client-mldsa.key", "regular-A1.chain.pem"),
}
FIELDS = [
    "round", "sequence", "profile", "connection_mode", "port", "duration_seconds",
    "threads", "connections", "requests", "rps", "mean_http_latency_ms",
    "tls_full", "tls_resumed", "requests_per_full_handshake", "server_cpu_busy_pct",
    "client_cpu_busy_pct", "exit_code", "timestamp_utc",
]


def ssh_command(args, command):
    cmd = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", "-o", "StrictHostKeyChecking=yes",
           f"{args.ssh_user}@{args.web_host}", command]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if p.returncode:
        raise RuntimeError("Remote preflight/CPU read failed: " + p.stderr.strip()[-400:])
    return p.stdout.strip()


def preflight(args):
    # The exporter may spawn bpftrace in a separate process; both must be off.
    command = ("test \"$(systemctl is-active httpd)\" = active && "
               "test \"$(systemctl is-active pqc-tls-exporter.service || true)\" != active && "
               "! pgrep -f '[b]pftrace' >/dev/null && echo READY")
    if ssh_command(args, command) != "READY":
        raise RuntimeError("Server must have httpd ON and exporter/bpftrace OFF")


def proc_stat_local():
    with open("/proc/stat", encoding="ascii") as f:
        fields = f.readline().split()[1:]
    values = [int(x) for x in fields]
    return sum(values), values[3] + values[4]


def proc_stat_remote(args):
    output = ssh_command(args, "awk '/^cpu / { t=0; for (i=2; i<=NF; i++) t+=$i; print t, $5+$6; exit }' /proc/stat")
    total, idle = map(int, output.split())
    return total, idle


def cpu_busy(before, after):
    total = after[0] - before[0]
    idle = after[1] - before[1]
    if total <= 0:
        raise ValueError("Invalid CPU measurement interval")
    return round(100 * (1 - idle / total), 3)


def parse_result(raw, expected_group):
    def match(pattern):
        m = re.search(pattern, raw, re.I | re.M)
        if not m:
            raise ValueError("Missing wrk result field " + pattern)
        return m.group(1)
    group = match(r"^Negotiated group:\s*(\S+)")
    if group.casefold() != expected_group.casefold():
        raise ValueError(f"Unexpected negotiated group: {group} != {expected_group}")
    if match(r"^Protocol:\s*(\S+)") != "TLSv1.3":
        raise ValueError("TLS version is not 1.3")
    if match(r"^Cipher:\s*(\S+)") != "TLS_AES_256_GCM_SHA384":
        raise ValueError("Unexpected TLS cipher suite")
    if re.search(r"Non-2xx or 3xx responses:\s*[1-9]", raw):
        raise ValueError("Unexpected non-success HTTP responses")
    socket_line = re.search(r"^Socket errors:\s*(.+)$", raw, re.M)
    if socket_line and any(int(n) for n in re.findall(r"\b\d+\b", socket_line.group(1))):
        raise ValueError("wrk reported socket errors")
    lat = re.search(r"^\s*Latency\s+([\d.]+)(us|ms|s)\b", raw, re.M)
    latency = None if not lat else round(float(lat.group(1)) * {"us": .001, "ms": 1, "s": 1000}[lat.group(2)], 4)
    full = int(match(r"TLS handshake summary:\s*full=(\d+)"))
    resumed = int(match(r"TLS handshake summary:\s*full=\d+\s+resumed=(\d+)"))
    requests = int(match(r"^\s*(\d+) requests in "))
    rps = float(match(r"^Requests/sec:\s*([\d.]+)"))
    if resumed != 0 or full <= 0 or requests <= 0 or rps <= 0:
        raise ValueError(f"Unexpected handshake/request counts: full={full} resumed={resumed} requests={requests}")
    return dict(requests=requests, rps=rps, mean_http_latency_ms=latency,
                tls_full=full, tls_resumed=resumed,
                requests_per_full_handshake=round(requests / full, 4))


def save_csv(path, rows):
    # Atomic replacement keeps the dataset valid after each successful test.
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    os.chmod(tmp, 0o600)
    tmp.replace(path)


def run_test(args, round_number, index, profile, conn_mode, result_dir):
    port, group, cert, key, ca = PROFILES[profile]
    env = os.environ.copy()
    env.update(WRK_CLIENT_CERT=str(args.cert_dir / cert),
               WRK_CLIENT_KEY=str(args.cert_dir / key), WRK_CA_FILE=str(args.cert_dir / ca))
    cmd = [str(args.wrk), f"-t{args.threads}", f"-c{args.connections}",
           f"-d{args.duration}s", "--latency"]
    if conn_mode == "fresh":
        cmd.extend(["-H", "Connection: close"])
    cmd.append(f"https://{args.server}:{port}/")

    label = f"round{round_number:02d}-{index:02d}-{profile}-{conn_mode}"
    print(f"RUN {label}", flush=True)
    server_before, client_before = proc_stat_remote(args), proc_stat_local()
    stamp = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    proc = subprocess.run(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          text=True, timeout=args.duration + 120)
    client_after, server_after = proc_stat_local(), proc_stat_remote(args)
    logpath = result_dir / f"{label}.log"
    logpath.write_text(proc.stdout, encoding="utf-8")
    os.chmod(logpath, 0o600)
    if proc.returncode:
        raise RuntimeError(f"wrk failed ({proc.returncode}), inspect private {logpath}")
    try:
        metrics = parse_result(proc.stdout, group)
    except ValueError as exc:
        raise RuntimeError(f"Invalid measurement; inspect private {logpath}: {exc}") from exc
    ratio = metrics["requests_per_full_handshake"]
    if conn_mode == "fresh" and not (0.90 <= ratio <= 1.05):
        raise RuntimeError(f"Fresh-mode handshake ratio unexpected: {ratio}")
    if conn_mode == "keepalive" and ratio < 2:
        raise RuntimeError(f"Keep-alive was not demonstrated (requests/handshake={ratio})")
    record = dict(round=round_number, sequence=index, profile=profile,
                  connection_mode=conn_mode, port=port, duration_seconds=args.duration,
                  threads=args.threads, connections=args.connections,
                  server_cpu_busy_pct=cpu_busy(server_before, server_after),
                  client_cpu_busy_pct=cpu_busy(client_before, client_after),
                  exit_code=proc.returncode, timestamp_utc=stamp, **metrics)
    print(f"  RPS={metrics['rps']:.2f} TLS={metrics['tls_full']} "
          f"requests/TLS={ratio:.2f} server_CPU={record['server_cpu_busy_pct']:.2f}% "
          f"client_CPU={record['client_cpu_busy_pct']:.2f}%", flush=True)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profiles", choices=["core", "all"], default="core",
                        help="core: x25519/hybrid; all also includes classic/pqc-auth")
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--duration", type=int, default=120)
    parser.add_argument("--threads", type=int, default=8)
    parser.add_argument("--connections", type=int, default=50)
    parser.add_argument("--pause", type=int, default=10)
    parser.add_argument("--seed", type=int, default=20261120)
    parser.add_argument("--server", required=True,
                        help="mTLS HTTP server hostname (provided by the operator)")
    parser.add_argument("--web-host", default=None,
                        help="SSH monitoring host; defaults to --server")
    parser.add_argument("--ssh-user", default="root")
    parser.add_argument("--wrk", type=Path, default=Path("/usr/local/src/wrk-mtls-verify/wrk"))
    parser.add_argument("--cert-dir", type=Path, default=Path("/root/mtls-certs"))
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()
    if args.web_host is None:
        args.web_host = args.server
    if args.runs < 1 or args.duration < 10 or args.threads < 1 or args.connections < args.threads or args.pause < 0:
        parser.error("Invalid runs/duration/threads/connections/pause")
    profiles = ["x25519", "hybrid"] if args.profiles == "core" else list(PROFILES)
    for file in [args.wrk] + [args.cert_dir / name for p in profiles for name in PROFILES[p][2:]]:
        if not file.is_file():
            parser.error(f"Required local file not found: {file}")
    os.umask(0o077)
    folder = args.output_dir or (Path.home() / ("pqc-connection-reuse-" + dt.datetime.now().strftime("%Y%m%d-%H%M%S")))
    folder.mkdir(mode=0o700, parents=True, exist_ok=False)
    (folder / "experiment.json").write_text(json.dumps({
        "profiles": profiles, "connection_modes": ["fresh", "keepalive"],
        "runs": args.runs, "duration": args.duration, "threads": args.threads,
        "connections": args.connections, "pause": args.pause, "seed": args.seed,
        "observer": "OFF (required)", "wrk_sha256": __import__("hashlib").sha256(args.wrk.read_bytes()).hexdigest(),
    }, indent=2) + "\n", encoding="utf-8")
    print("Results directory:", folder, flush=True)
    rows = []
    rng = random.Random(args.seed)
    tasks = [(name, mode) for name in profiles for mode in ("fresh", "keepalive")]
    try:
        for round_number in range(1, args.runs + 1):
            order = tasks.copy()
            rng.shuffle(order)
            print(f"=== ROUND {round_number}: {order} ===", flush=True)
            for index, (profile, mode) in enumerate(order, 1):
                # Do not proceed if the observer has been reactivated mid-campaign.
                preflight(args)
                row = run_test(args, round_number, index, profile, mode, folder)
                rows.append(row)
                save_csv(folder / "results.csv", rows)
                time.sleep(args.pause)
    except (Exception, KeyboardInterrupt) as exc:
        print("CAMPAIGN INTERRUPTED:", exc, file=sys.stderr, flush=True)
        print("Validated partial results retained:", folder / "results.csv", file=sys.stderr)
        return 1
    print("CAMPAIGN COMPLETE — results:", folder / "results.csv", flush=True)
    for mode in ("fresh", "keepalive"):
        data = {name: [r["rps"] for r in rows if r["connection_mode"] == mode and r["profile"] == name]
                for name in profiles}
        print(mode, " ".join(f"{name}={statistics.mean(a):.2f} RPS (n={len(a)})" for name, a in data.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
