#!/usr/bin/env python3
"""Reproduce figures and descriptive/paired statistics from the two original CSVs.

Required: numpy, pandas, scipy, matplotlib.
Run from anywhere: python scripts/analyze.py
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
FIGURES = ROOT / 'figures'
TABLES = ROOT / 'tables'
FIGURES.mkdir(exist_ok=True)
TABLES.mkdir(exist_ok=True)

REQUIRED = {'round', 'sequence', 'profile', 'connection_mode', 'threads',
            'connections', 'duration_seconds', 'rps', 'tls_full', 'tls_resumed',
            'exit_code', 'requests', 'requests_per_full_handshake',
            'server_cpu_busy_pct', 'client_cpu_busy_pct',
            'mean_http_latency_ms'}

parts = []
checksums = set()
for label, expected_threads, expected_connections in [('low', 2, 10), ('high', 8, 50)]:
    meta = json.loads((DATA / f'{label}-experiment.json').read_text())
    checksums.add(meta['wrk_sha256'])
    if (meta['runs'], meta['duration'], meta['threads'], meta['connections']) != (5, 120, expected_threads, expected_connections):
        raise ValueError(f'Unexpected campaign metadata in {label}')
    df = pd.read_csv(DATA / f'{label}-results.csv')
    if not REQUIRED.issubset(set(df.columns)):
        raise ValueError(f'Missing columns from {label}: {REQUIRED-set(df.columns)}')
    if len(df) != 20 or df[list(REQUIRED)].isnull().any().any():
        raise ValueError(f'Incomplete dataset: {label}')
    if not ((df.exit_code == 0).all() and (df.tls_resumed == 0).all() and (df.tls_full > 0).all()):
        raise ValueError(f'Failed or resumed tests: {label}')
    if not ((df.threads == expected_threads).all() and (df.connections == expected_connections).all() and (df.duration_seconds == 120).all()):
        raise ValueError(f'Inconsistent test settings: {label}')
    expected = {(round_, profile, mode) for round_ in range(1, 6)
                for profile in ('x25519', 'hybrid') for mode in ('fresh', 'keepalive')}
    observed = set(map(tuple, df[['round','profile','connection_mode']].itertuples(index=False, name=None)))
    if observed != expected or df.duplicated(['round','profile','connection_mode']).any():
        raise ValueError(f'Unexpected condition/round matrix: {label}')
    df['load'] = label
    parts.append(df)
if len(checksums) != 1:
    raise ValueError('Different wrk binaries across campaigns')

all_data = pd.concat(parts, ignore_index=True)
means = (all_data.groupby(['load','connection_mode','profile'], as_index=False)
         .agg(mean_rps=('rps','mean'), sd_rps=('rps','std'),
              mean_requests_per_tls=('requests_per_full_handshake','mean'),
              mean_server_cpu_pct=('server_cpu_busy_pct','mean'),
              mean_client_cpu_pct=('client_cpu_busy_pct','mean'),
              mean_http_latency_ms=('mean_http_latency_ms','mean')))
means.to_csv(TABLES / 'scenario_summary.csv', index=False, float_format='%.6f')

roundwise = []
effects = []
for load in ('low', 'high'):
    subset = all_data[all_data.load == load]
    ratios_by_mode = {}
    for mode in ('fresh', 'keepalive'):
        p = subset[subset.connection_mode == mode].pivot(index='round', columns='profile', values='rps')
        x = p['x25519'].to_numpy()
        h = p['hybrid'].to_numpy()
        rel = 100 * (h / x - 1)
        ratios_by_mode[mode] = rel
        for r, xv, hv, diff in zip(p.index, x, h, rel):
            roundwise.append({'load':load,'round':int(r),'connection_mode':mode,
                              'x25519_rps':xv,'hybrid_rps':hv,'relative_diff_pct':diff})
        mean = rel.mean()
        ci = stats.t.interval(0.95, len(rel)-1, loc=mean, scale=stats.sem(rel))
        effects.append({'load':load, 'contrast':mode, 'paired_mean_diff_pct_or_pp':mean,
                        'ci95_low':ci[0], 'ci95_high':ci[1],
                        'ratio_of_mean_throughput_pct':100*(h.mean()/x.mean()-1),
                        'n_rounds':len(rel), 'two_sided_p_value_exploratory':stats.ttest_1samp(rel, 0).pvalue})
    interaction = ratios_by_mode['keepalive']-ratios_by_mode['fresh']
    ci = stats.t.interval(0.95, len(interaction)-1, loc=interaction.mean(), scale=stats.sem(interaction))
    effects.append({'load':load, 'contrast':'keepalive_minus_fresh',
                    'paired_mean_diff_pct_or_pp':interaction.mean(),
                    'ci95_low':ci[0], 'ci95_high':ci[1],
                    'ratio_of_mean_throughput_pct':float('nan'),
                    'n_rounds':len(interaction),
                    'two_sided_p_value_exploratory':stats.ttest_1samp(interaction, 0).pvalue})
    for r, diff in enumerate(interaction, 1):
        for row in roundwise:
            if row['load']==load and row['round']==r and row['connection_mode']=='keepalive':
                row['interaction_pp'] = diff

roundwise_df = pd.DataFrame(roundwise)
effects_df = pd.DataFrame(effects)
roundwise_df.to_csv(TABLES/'roundwise_pairs.csv',index=False,float_format='%.6f')
effects_df.to_csv(TABLES/'paired_effects_ci.csv',index=False,float_format='%.6f')

# Visual system is deliberately identical to the November 2026 mTLS plots:
# Open-DemoLabs/postquantum-tls-performance/mtls/scripts/plot-mtls-campaign-dark.py
# Dark background, profile colors, 16:9, typography, axes, grid, 300 dpi, PNG/SVG/PDF.
from matplotlib.patches import Patch

BG = "#0B111A"
FG = "#F5F7FA"
MUTED = "#A0AEC0"
GRID = "#293746"
CLASSIC = "#249BFA"
HYBRID = "#B58CFF"
PQC = "#FF624D"
X25519 = "#45D6C4"
DARK = FIGURES / "dark"
DARK.mkdir(exist_ok=True, parents=True)

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 12,
    "text.color": FG,
    "axes.labelcolor": FG,
    "xtick.color": FG,
    "ytick.color": MUTED,
    "axes.edgecolor": GRID,
    "axes.facecolor": BG,
    "figure.facecolor": BG,
    "savefig.facecolor": BG,
    "axes.titleweight": "bold",
    "axes.titlesize": 21,
    "grid.color": GRID,
    "grid.alpha": .65,
    "pdf.fonttype": 42,
    "svg.fonttype": "none",
})

def make_figure(title, subtitle, ylabel):
    fig, ax = plt.subplots(figsize=(16, 9))
    fig.subplots_adjust(left=.09, right=.96, top=.73, bottom=.20)
    fig.text(.09, .92, title, fontsize=25, fontweight="bold", color=FG)
    fig.text(.09, .865, subtitle, fontsize=13, color=MUTED)
    ax.set_ylabel(ylabel, fontsize=13, labelpad=15)
    ax.grid(axis="y", linestyle="--")
    ax.set_axisbelow(True)
    for side in ["top", "right", "left"]:
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(axis="both", length=0, pad=9)
    return fig, ax

def footer(fig, message):
    fig.text(.09, .095, message, fontsize=10.5, color=MUTED)

def save(fig, basename):
    for ext in ("png", "svg", "pdf"):
        fig.savefig(DARK / f"{basename}.{ext}", dpi=300, facecolor=BG)
    plt.close(fig)
    print(f"  Created {basename}.png / .svg / .pdf")

def get_measure(load, mode, profile, metric):
    return all_data[(all_data.load == load) &
                    (all_data.connection_mode == mode) &
                    (all_data.profile == profile)][metric].to_numpy(dtype=float)

load_labels = ["2 threads / 10 conn", "8 threads / 50 conn"]
load_codes = ["low", "high"]
x_load = np.arange(2)

# FIGURES 1 & 2: standalone throughput plots on linear scales, as in mTLS reference.
for figure_no, mode, title, filename, limit in [
    (1, 'fresh', 'mTLS throughput: fresh TLS connections', '01-fresh-throughput-dark', 1450),
    (2, 'keepalive', 'mTLS throughput: HTTP keep-alive', '02-keepalive-throughput-dark', 25000),
]:
    fig, ax = make_figure(title,
        'X25519 vs X25519MLKEM768 | Same ECDSA P-384 authentication | eBPF OFF',
        'Mean HTTP requests / second')
    width = .28
    for profile, color, offset, marker in [
        ('x25519', X25519, -width/2, 'X25519'),
        ('hybrid', HYBRID, width/2, 'Hybrid X25519MLKEM768'),
    ]:
        vals = np.array([get_measure(load, mode, profile, 'rps').mean() for load in load_codes])
        sd = np.array([get_measure(load, mode, profile, 'rps').std(ddof=1) for load in load_codes])
        bars = ax.bar(x_load + offset, vals, width, color=color, edgecolor='none',
                      yerr=sd, capsize=5,
                      error_kw={'ecolor': FG, 'elinewidth':1.7, 'capthick':1.7},
                      label=marker)
        for b, v, s in zip(bars, vals, sd):
            ax.text(b.get_x()+b.get_width()/2, v+s+limit*.018, f'{v:,.0f}',
                    color=color, ha='center', va='bottom',fontsize=16,fontweight='bold')
    ax.set_xticks(x_load, load_labels)
    ax.set_xlim(-.6,1.6)
    ax.set_ylim(0,limit)
    ax.legend(loc='upper right', bbox_to_anchor=(1,1.24), frameon=False,
              labelcolor=FG, ncol=2, fontsize=13)
    if mode=='fresh':
        foot='5 x 120 s runs/profile/load  |  Connection: close  |  eBPF OFF  |  Error bars: +/- 1 SD'
    else:
        foot='5 x 120 s runs/profile/load  |  HTTP/1.1 keep-alive  |  TLS resumed=0  |  Error bars: +/- 1 SD'
    footer(fig, foot)
    save(fig, filename)

# FIGURE 3: 95% t intervals for relative paired comparisons. The experimental
# contrast is not "statistical equivalence"; these are unadjusted, exploratory CIs.
plot_df = effects_df[effects_df.contrast.isin(['fresh','keepalive'])].copy()
plot_df['order'] = plot_df['load'].map({'low':0,'high':2}) + plot_df['contrast'].map({'fresh':0,'keepalive':1})
plot_df = plot_df.sort_values('order')
xx = np.arange(len(plot_df))
y = plot_df.paired_mean_diff_pct_or_pp.to_numpy()
lo = plot_df.ci95_low.to_numpy()
hi = plot_df.ci95_high.to_numpy()
fig, ax = make_figure('Hybrid vs X25519: throughput difference',
    'Paired by benchmark round | 5 rounds per condition | eBPF OFF',
    'Hybrid minus X25519 throughput (%)')
colors = [HYBRID, HYBRID, HYBRID, HYBRID]
alphas = [1.0, .58, 1.0, .58]
bars = ax.bar(xx, y, width=.58, color=colors, edgecolor='none')
for bar, opacity in zip(bars, alphas):
    bar.set_alpha(opacity)
ax.errorbar(xx, y, yerr=np.vstack([y-lo,hi-y]), color=FG,
            fmt='none', capsize=8, elinewidth=2, capthick=2.0, zorder=7)
ax.axhline(0, color=FG, linewidth=1.2, alpha=.75)
ax.set_xticks(xx, ["2t / 10c\nFRESH", "2t / 10c\nKEEP-ALIVE",
                  "8t / 50c\nFRESH", "8t / 50c\nKEEP-ALIVE"])
ax.set_xlim(-.65,3.65)
ax.set_ylim(-6.8,2.2)
for b, val, lower in zip(bars, y, lo):
    ax.text(b.get_x()+b.get_width()/2, min(lower-.30, -1.8),
            f'{val:+.2f}%', ha='center', va='top', color=FG,fontsize=17,fontweight='bold')
ax.legend(handles=[Patch(color=HYBRID, label='Fresh'),
                   Patch(color=HYBRID, alpha=.58, label='Keep-alive')],
          loc='upper right', bbox_to_anchor=(1,1.22), ncol=2, frameon=False, labelcolor=FG)
footer(fig, 'Mean of paired round-relative differences  |  Error bars: exploratory 95% Student-t CI (n=5)  |  Not an equivalence test')
save(fig, '03-relative-difference-95ci-dark')

# FIGURES 4 & 5: round-to-round differences. Same line weights, 16:9 layout,
# marker edge and typography as the preceding mTLS reproducibility plots.
for num, load, display, name in [
    (4,'low','2 threads / 10 connections','04-reproducibility-low-dark'),
    (5,'high','8 threads / 50 connections','05-reproducibility-high-dark'),
]:
    fig, ax = make_figure('Hybrid vs X25519 across benchmark rounds',
        f'{display} | Same ECDSA P-384 authentication | eBPF OFF',
        'Paired throughput difference (%)')
    for mode, color, style, marker, label in [
        ('fresh',HYBRID,'-','o','Fresh connections'),
        ('keepalive',X25519,'--','D','HTTP keep-alive'),
    ]:
        d = roundwise_df[(roundwise_df.load==load) &
                         (roundwise_df.connection_mode==mode)].sort_values('round')
        ax.plot(d['round'], d['relative_diff_pct'],marker=marker,markersize=10,
                markeredgecolor=BG,markeredgewidth=1.2,linestyle=style,
                linewidth=2.5,color=color,label=label)
    ax.axhline(0, color=FG, linewidth=1.2, alpha=.65)
    ax.set_xticks(np.arange(1,6))
    ax.set_xlim(.75,5.25)
    ax.set_ylim(-6.8,4)
    ax.set_xlabel('Benchmark round',fontsize=13,labelpad=12)
    ax.legend(loc='upper right',bbox_to_anchor=(1,1.23),ncol=2,frameon=False,
              labelcolor=FG,fontsize=12)
    footer(fig, '5 independent paired rounds  |  120 s per run  |  Negative values: Hybrid lower RPS  |  Observer OFF')
    save(fig,name)

# FIGURE 6: host-wide utilization - does not attribute CPU to cryptography.
# Vertical bars retain the original mTLS CPU-figure style.
fig, ax = make_figure('Overall CPU utilization by connection policy',
    'System-level CPU busy | Both TLS profiles pooled within each workload condition',
    'Overall CPU busy (%)')
inds=np.arange(4)
conds=[('low','fresh'),('low','keepalive'),('high','fresh'),('high','keepalive')]
labels=['2t / 10c\nFRESH','2t / 10c\nKEEP-ALIVE','8t / 50c\nFRESH','8t / 50c\nKEEP-ALIVE']
width=.31
for cpu_metric, title, col, off in [
    ('server_cpu_busy_pct','Apache server host',CLASSIC,-width/2),
    ('client_cpu_busy_pct','wrk client host',PQC,width/2),
]:
    means_cpu=[all_data[(all_data.load==load)&(all_data.connection_mode==mode)][cpu_metric].mean()
               for load,mode in conds]
    bars=ax.bar(inds+off,means_cpu,width,color=col,edgecolor='none',label=title)
    for bar,v in zip(bars,means_cpu):
        ax.text(bar.get_x()+bar.get_width()/2,v+1.6, f'{v:.1f}%',color=col,
                ha='center',fontsize=14,fontweight='bold')
ax.set_xticks(inds,labels)
ax.set_xlim(-.65,3.65)
ax.set_ylim(0,115)
ax.legend(loc='upper right',bbox_to_anchor=(1,1.24),ncol=2,frameon=False,labelcolor=FG)
footer(fig, 'Mean host-wide CPU busy across 10 runs/condition  |  NOT isolated crypto CPU cost  |  eBPF OFF')
save(fig,'06-overall-cpu-dark')

# FIGURE 7: connection reuse dynamics. This is a rate ratio observed at the
# end of the workload, not a benchmark of isolated TLS handshake latency.
fig,ax=make_figure('HTTP requests per completed TLS handshake',
    'Measured from wrk TLS counters | Session resumption absent throughout both campaigns',
    'HTTP requests / full TLS handshake')
inds=np.arange(4); width=.29
for profile, col, off, name in [
    ('x25519',X25519,-width/2,'X25519'),('hybrid',HYBRID,width/2,'Hybrid X25519MLKEM768')
]:
    vals=[get_measure(load,mode,profile,'requests_per_full_handshake').mean() for load,mode in conds]
    bars=ax.bar(inds+off,vals,width,color=col,edgecolor='none',label=name)
    for bar,v in zip(bars,vals):
        ax.text(bar.get_x()+bar.get_width()/2,v+2.0,f'{v:.1f}',color=col,
                ha='center',fontsize=14,fontweight='bold')
ax.set_xticks(inds,labels)
ax.set_xlim(-.65,3.65)
ax.set_ylim(0,118)
ax.legend(loc='upper right',bbox_to_anchor=(1,1.24),ncol=2,frameon=False,labelcolor=FG)
footer(fig,'Mean run-level requests/full-handshake  |  eBPF OFF  |  Apache effective keep-alive policy pending verification')
save(fig,'07-requests-per-handshake-dark')

print('Rows:',len(all_data),'unique wrk hashes:',len(checksums))
print('\nPaired comparisons:')
print(effects_df.to_string(index=False,float_format=lambda n:f'{n:.4f}'))
print('\nDark figures saved in:', DARK)
print('Tables saved in:', TABLES)
