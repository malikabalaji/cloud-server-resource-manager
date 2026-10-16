"""
experiments.py
Review 2 experiments for paging, VM allocation and disk scheduling, plus
dispatch in the full cloud, each over 10 seeds with 95% confidence intervals.

Design: one factor at a time. Each experiment changes ONE algorithm and keeps
the workload and every other setting fixed, so any difference is caused by
that algorithm alone.

Run:  python experiments.py          (writes CSV and PNG files to results/)
"""

import os

from workload import random_workload
from cloud import Config, run_cloud
from memory import count_faults, POLICIES as REPLACE
from vm_manager import FITS
from disk import total_movement, POLICIES as DISKS
from metrics import write_csv, mean_ci95, improvement
from scheduler import LOCAL_POLICIES, DISPATCH_POLICIES
import visualize

RESULTS = "results"
SEEDS = range(1, 11)
TEXTBOOK_REFS = [7, 0, 1, 2, 0, 3, 0, 4, 2, 3, 0, 3, 2, 1, 2, 0, 1, 7, 0, 1]
DISK_QUEUE = [98, 183, 37, 122, 14, 124, 65, 67]


def exp5_paging():
    """Faults versus frames: textbook string, then the seeded workload (10 seeds)."""
    frames = list(range(3, 9))
    textbook = {p.upper(): [count_faults(TEXTBOOK_REFS, f, p) for f in frames] for p in REPLACE}
    visualize.plot_faults_vs_frames(frames, textbook, "Textbook reference string: faults vs frames",
                                    os.path.join(RESULTS, "exp5_paging_textbook.png"))
    rows, by_policy = [], {}
    for p in REPLACE:
        by_policy[p.upper()] = []
        for f in frames:
            rates = [run_cloud(random_workload(200, s), Config(replace=p, frames=f))[0]["fault_rate"]
                     for s in SEEDS]
            m, ci = mean_ci95(rates)
            rows.append({"policy": p, "frames": f, "fault_rate_mean": round(m, 4), "ci95": round(ci, 4)})
            by_policy[p.upper()].append(round(m * 100, 2))
    write_csv(rows, os.path.join(RESULTS, "exp5_paging.csv"))
    visualize.plot_faults_vs_frames(frames, by_policy, "Seeded workload: fault rate vs frames (mean of 10 seeds)",
                                    os.path.join(RESULTS, "exp5_paging_workload.png"), "Fault rate (%)")
    return rows


def exp6_vm():
    """First, best and worst fit: success rate and fragmentation over 10 seeds."""
    rows = []
    for fit in FITS:
        succ = [run_cloud(random_workload(200, s), Config(fit=fit))[0]["vm_success_rate"] for s in SEEDS]
        frag = [run_cloud(random_workload(200, s), Config(fit=fit))[0]["avg_fragmentation"] for s in SEEDS]
        (sm, sci), (fm, fci) = mean_ci95(succ), mean_ci95(frag)
        rows.append({"fit": fit, "success_mean": round(sm, 4), "success_ci95": round(sci, 4),
                     "frag_mean": round(fm, 4), "frag_ci95": round(fci, 4)})
    base = rows[0]
    for r in rows:
        r["success_improvement"] = improvement(base["success_mean"], r["success_mean"], True)[0]
    write_csv(rows, os.path.join(RESULTS, "exp6_vm.csv"))
    visualize.plot_bars([r["fit"].title() + " fit" for r in rows], [r["success_mean"] * 100 for r in rows],
                        "VM allocation success rate (mean of 10 seeds, 95% CI)", "Success (%)",
                        os.path.join(RESULTS, "exp6_vm_success.png"),
                        errors=[r["success_ci95"] * 100 for r in rows])
    return rows


def exp7_disk():
    """Disk policies: textbook queue, then the seeded workload (10 seeds)."""
    for p in DISKS:
        moved, order = total_movement(DISK_QUEUE, 53, p)
        visualize.plot_disk_path(order, 53, f"{p.upper()} on the textbook queue: {moved} cylinders",
                                 os.path.join(RESULTS, f"exp7_disk_{p}.png"))
    rows = []
    for p in DISKS:
        moves = [run_cloud(random_workload(200, s), Config(disk=p))[0]["head_movement"] for s in SEEDS]
        m, ci = mean_ci95(moves)
        rows.append({"disk": p, "head_movement_mean": round(m, 1), "ci95": round(ci, 1)})
    base = rows[0]["head_movement_mean"]
    for r in rows:
        r["improvement_pct"] = improvement(base, r["head_movement_mean"])[0]
    write_csv(rows, os.path.join(RESULTS, "exp7_disk.csv"))
    visualize.plot_bars([r["disk"].upper() for r in rows], [r["head_movement_mean"] for r in rows],
                        "Total head movement (mean of 10 seeds, 95% CI)", "Cylinders",
                        os.path.join(RESULTS, "exp7_disk_workload.png"),
                        errors=[r["ci95"] for r in rows], fmt="%.0f")
    return rows


def exp8_dispatch_full():
    """Dispatch and CPU policies in the FULL cloud (VM admission switched on), 10 seeds.

    A VM that does not fit on the server chosen by the dispatcher is rejected and is
    NOT retried on another server, so two dispatch policies can admit different numbers
    of jobs. The rejection rate is therefore reported next to every waiting time, and
    waiting times should only be compared together with it.
    """
    rows = []
    for dispatch in DISPATCH_POLICIES:
        for local in LOCAL_POLICIES:
            runs = [run_cloud(random_workload(200, s), Config(dispatch=dispatch, local=local))[0] for s in SEEDS]
            (wm, wci) = mean_ci95([r["avg_waiting"] for r in runs])
            (rm, rci) = mean_ci95([r["rejection_rate"] for r in runs])
            rows.append({"dispatch": dispatch, "local": local,
                         "admitted_mean": round(sum(r["jobs"] for r in runs) / len(runs), 1),
                         "rejection_rate_mean": round(rm, 4), "rejection_ci95": round(rci, 4),
                         "wait_mean": round(wm, 2), "wait_ci95": round(wci, 2)})
    write_csv(rows, os.path.join(RESULTS, "exp8_dispatch_full.csv"))
    return rows


def main():
    os.makedirs(RESULTS, exist_ok=True)
    print("Experiment 5: paging (fault rate, mean over 10 seeds)")
    for r in exp5_paging():
        print(f"  {r['policy']:5} frames={r['frames']}  {r['fault_rate_mean']:.4f} +/- {r['ci95']:.4f}")
    print("\nExperiment 6: VM allocation (mean over 10 seeds)")
    for r in exp6_vm():
        print(f"  {r['fit']:5}  success={r['success_mean']:.4f} +/- {r['success_ci95']:.4f}  "
              f"fragmentation={r['frag_mean']:.4f}  vs first fit={r['success_improvement']:+.2f}%")
    print("\nExperiment 7: disk scheduling (head movement, mean over 10 seeds)")
    for r in exp7_disk():
        print(f"  {r['disk']:5}  {r['head_movement_mean']:9.1f} +/- {r['ci95']:7.1f}  "
              f"vs FCFS={r['improvement_pct']:+.2f}%")
    print("\nExperiment 8: dispatch in the full cloud (VMs that do not fit are rejected, not retried)")
    print(f"  {'dispatch':8} {'local':5} {'admitted':>9} {'rejection rate':>16} {'avg waiting':>14}")
    for r in exp8_dispatch_full():
        print(f"  {r['dispatch']:8} {r['local']:5} {r['admitted_mean']:9.1f} "
              f"{r['rejection_rate_mean']:9.4f} +/- {r['rejection_ci95']:.4f} {r['wait_mean']:8.2f} +/- {r['wait_ci95']:.2f}")
    print(f"\nCSV and PNG files written to ./{RESULTS}/")


if __name__ == "__main__":
    main()
