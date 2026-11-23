# plot-stability.py

Generates the seven figures of the TLS stability campaign (classical vs post-quantum
TLS 1.3, 5 profiles × 5 rounds) from the benchmark CSV files.

## Figures

| File name (`<bg>` = `dark` or `white`) | Content |
|----------------------------------------|---------|
| `01-throughput-<bg>`                   | Mean HTTP requests/s per profile, ±1 SD, PQC delta vs. P-384 |
| `02-ebpf-latency-<bg>`                 | eBPF `SSL_do_handshake()` duration, p50 / p95 / p99 |
| `03-cpu-<bg>`                          | Server CPU utilization per profile |
| `04-throughput-vs-p99-<bg>`            | Throughput vs. p99 latency |
| `05-reproducibility-<bg>`              | Per-round throughput (reproducibility across the 5 rounds) |
| `06-relative-throughput-<bg>`          | Throughput reduction vs. the CLASSIC A.2 baseline |
| `07-wrk-latency-<bg>`                  | Client-observed HTTP latency (wrk p50 / p99) |

Every figure is always written as **PNG** (300 dpi) and **SVG**; **PDF** is added with `--pdf`.

Classical TLS bars are drawn with diagonal stripes so the two families can be told apart
without relying on color (colorblind readers, grayscale print). The stripes are drawn as
real lines, so they appear in every PDF viewer.

## Requirements

- Python 3.8 or later
- matplotlib and numpy

```bash
sudo dnf install python3-matplotlib python3-numpy
# or, in a virtual environment:
python3 -m venv venv && source venv/bin/activate
pip install matplotlib numpy
```

## Usage

```bash
python3 plot-dark-stability.py --results RESULTS_CSV --cpu CPU_CSV --bucket BUCKET_CSV
                               [--background {dark,white}] [--output DIR] [--pdf]
```

| Argument            | Required | Default | Description |
|---------------------|----------|---------|-------------|
| `--results RESULTS_CSV` | yes  | —       | Path to `pqc_results_stability.csv` (wrk throughput and latency per round and profile). |
| `--cpu CPU_CSV`     | yes      | —       | Path to `pqc_cpu_stability.csv` (server CPU per run). |
| `--bucket BUCKET_CSV` | yes    | —       | Path to `pqc_histogram_buckets_stability.csv` (eBPF handshake histogram buckets). |
| `--background`      | no       | `dark`  | Figure background: `dark` or `white`. Also the name of the output subdirectory and the file name suffix. |
| `--output DIR`      | no       | current working directory | Base directory. Figures are written to `DIR/dark/` or `DIR/white/`, created if they do not exist. |
| `--pdf`             | no       | off     | Also write a PDF of each figure. |
| `-h`, `--help`      | no       | —       | Show help. |

The script exits with an error if any of `--results`, `--cpu` or `--bucket` is missing
or points to a file that does not exist, or if
`--background` gets a value other than `dark` or `white`.

### Output layout

```
<output>/            (current directory if --output is not used)
├── dark/            --background dark (default)
│   ├── 01-throughput-dark.png
│   ├── 01-throughput-dark.svg
│   ├── 01-throughput-dark.pdf      (only with --pdf)
│   └── ...
└── white/           --background white
    ├── 01-throughput-white.png
    └── ...
```

### Examples

```bash
DATA=benchmarks/2026-11-04-stability

# Dark figures (PNG + SVG) in ./dark/
python3 scripts/plot-dark-stability.py \
    --results $DATA/pqc_results_stability.csv \
    --cpu $DATA/pqc_cpu_stability.csv \
    --bucket $DATA/pqc_histogram_buckets_stability.csv

# White figures with PDF in scripts/figures/white/
python3 scripts/plot-dark-stability.py \
    --results $DATA/pqc_results_stability.csv \
    --cpu $DATA/pqc_cpu_stability.csv \
    --bucket $DATA/pqc_histogram_buckets_stability.csv \
    --background white --output scripts/figures --pdf
```

## Input files

| File | Columns used |
|------|--------------|
| `pqc_results_stability.csv` | `round`, `profile`, `wrk_req_s`, `wrk_p50_ms`, `wrk_p99_ms` (and the other per-run metrics) |
| `pqc_cpu_stability.csv` | `round`, `profile`, `web_cpu_busy_pct` |
| `pqc_histogram_buckets_stability.csv` | `round`, `profile`, `le`, `bucket_increase` |

The script checks the expected campaign shape: 5 rounds × 5 profiles (25 runs) and
21 histogram buckets per run (525 rows). Other shapes stop the script with an assertion error.

## Colors

| Element | Dark | White |
|---------|------|-------|
| Background | `#0B111A` | `#FFFFFF` |
| Main text | `#F5F7FA` | `#0B111A` |
| Secondary text | `#A0AEC0` | `#4A5568` |
| Grid | `#293746` | `#D5DCE4` |
| Classical TLS | `#249BFA` + stripes | `#249BFA` + stripes |
| Post-quantum TLS | `#FF624D` | `#FF624D` |

Stripe spacing and width are set by `HATCH_SPACING_IN` and `HATCH_LINEWIDTH` near the
top of the script.
