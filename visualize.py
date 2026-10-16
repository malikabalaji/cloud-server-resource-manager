"""
visualize.py
Draws the graphs used in the report and presentation (matplotlib).

Each function takes plain numbers, so the graphs can be redrawn from the
CSV files without rerunning the simulation.
"""

import matplotlib
matplotlib.use("Agg")            # draw to files, no window needed
import matplotlib.pyplot as plt

COLORS = ["#1B7F79", "#E07A2E", "#5B6C8F", "#8A5CC2"]


def _finish(ax, title, ylabel, path):
    ax.set_title(title, fontsize=12, loc="left")
    ax.set_ylabel(ylabel)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", alpha=0.3)
    plt.tight_layout()
    plt.savefig(path, dpi=160)
    plt.close()


def plot_policy_comparison(rows, path):
    """Grouped bars: waiting, turnaround and response time per local policy."""
    labels = [r["label"] for r in rows]
    metrics = [("avg_waiting", "Waiting"), ("avg_turnaround", "Turnaround"),
               ("avg_response", "Response")]
    width = 0.25
    fig, ax = plt.subplots(figsize=(7, 4))
    for i, (key, name) in enumerate(metrics):
        xs = [x + (i - 1) * width for x in range(len(rows))]
        vals = [r[key] for r in rows]
        bars = ax.bar(xs, vals, width, label=name, color=COLORS[i])
        ax.bar_label(bars, fmt="%.1f", fontsize=7)
    ax.set_xticks(range(len(rows)))
    ax.set_xticklabels(labels)
    ax.legend(frameon=False)
    _finish(ax, "Local scheduling policy vs average times", "Ticks", path)


def plot_utilisation(util_by_dispatch, path):
    """Bars of CPU utilisation per server for each dispatch policy."""
    names = list(util_by_dispatch.keys())
    n_servers = len(next(iter(util_by_dispatch.values())))
    width = 0.8 / len(names)
    fig, ax = plt.subplots(figsize=(7, 4))
    for i, name in enumerate(names):
        xs = [s + (i - (len(names) - 1) / 2) * width for s in range(n_servers)]
        bars = ax.bar(xs, [u * 100 for u in util_by_dispatch[name]], width,
                      label=name, color=COLORS[i])
        ax.bar_label(bars, fmt="%.0f%%", fontsize=7)
    ax.set_xticks(range(n_servers))
    ax.set_xticklabels([f"Server {s}" for s in range(n_servers)])
    ax.set_ylim(0, 110)
    ax.legend(frameon=False)
    _finish(ax, "CPU utilisation per server by dispatch policy", "Utilisation (%)", path)


def plot_quantum_sweep(quanta, waiting, response, path):
    """Line chart: how the Round Robin time slice changes waiting and response."""
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(quanta, waiting, marker="o", color=COLORS[0], label="Avg waiting")
    ax.plot(quanta, response, marker="s", color=COLORS[1], label="Avg response")
    ax.set_xlabel("Round Robin quantum (ticks)")
    ax.legend(frameon=False)
    _finish(ax, "Effect of the Round Robin quantum", "Ticks", path)


def plot_gantt(server, title, path):
    """Gantt chart of one server: which job ran on which core at each tick."""
    fig, ax = plt.subplots(figsize=(8, 1.2 + 0.5 * server.cores))
    # Merge consecutive ticks of the same job on the same core into one bar.
    segments = []
    for core, t, jid in sorted(server.timeline):
        if segments and segments[-1][0] == core and segments[-1][2] == jid \
                and segments[-1][1] + segments[-1][3] == t:
            segments[-1][3] += 1
        else:
            segments.append([core, t, jid, 1])
    for core, start, jid, length in segments:
        ax.barh(core, length, left=start, color=COLORS[(jid - 1) % len(COLORS)],
                edgecolor="white")
        ax.text(start + length / 2, core, f"J{jid}", ha="center", va="center",
                color="white", fontsize=9)
    # Put an axis tick at every start and end point, like a textbook Gantt chart.
    marks = sorted({s[1] for s in segments} | {s[1] + s[3] for s in segments})
    ax.set_xticks(marks)
    ax.set_yticks(range(server.cores))
    ax.set_yticklabels([f"Core {c}" for c in range(server.cores)])
    ax.set_xlabel("Tick")
    ax.set_title(title, fontsize=11, loc="left")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    plt.tight_layout()
    plt.savefig(path, dpi=160)
    plt.close()


# ---------------------------------------------------------------------------
# Review 2 graphs: memory, VM and disk
# ---------------------------------------------------------------------------
def plot_bars(labels, values, title, ylabel, path, errors=None, fmt="%.1f"):
    """Simple bar chart, optionally with 95% confidence-interval error bars."""
    fig, ax = plt.subplots(figsize=(7, 4))
    bars = ax.bar(labels, values, color=COLORS[0], yerr=errors, capsize=4 if errors else 0)
    ax.bar_label(bars, fmt=fmt, fontsize=8, padding=2)
    _finish(ax, title, ylabel, path)


def plot_faults_vs_frames(frames, faults_by_policy, title, path, ylabel="Page faults"):
    """Line per replacement policy: page faults as the number of frames grows."""
    fig, ax = plt.subplots(figsize=(7, 4))
    markers = ["o", "s", "^", "D"]
    for i, (name, faults) in enumerate(faults_by_policy.items()):
        ax.plot(frames, faults, marker=markers[i % 4], color=COLORS[i % len(COLORS)], label=name)
    ax.set_xlabel("Frames")
    ax.set_xticks(frames)
    ax.legend(frameon=False)
    _finish(ax, title, ylabel, path)


def plot_disk_path(order, head, title, path):
    """Head position over the served requests, the classic disk scheduling diagram."""
    fig, ax = plt.subplots(figsize=(7, 3.6))
    ys = list(range(len(order) + 1))
    xs = [head] + list(order)
    ax.plot(xs, ys, marker="o", color=COLORS[0])
    for x, y in zip(xs, ys):
        ax.annotate(str(x), (x, y), textcoords="offset points", xytext=(6, -3), fontsize=8)
    ax.invert_yaxis()
    ax.set_xlim(0, 199)
    ax.set_xlabel("Cylinder")
    ax.set_yticks([])
    _finish(ax, title, "Order served", path)
