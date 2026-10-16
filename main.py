"""
main.py
Command-line entry point for the Cloud Server Resource Manager.

Examples
    python main.py                                   # one full-cloud run with defaults
    python main.py --local sjf --dispatch least      # pick CPU algorithms by flag
    python main.py --replace clock --frames 5        # page replacement and frames per job
    python main.py --fit best --disk look            # VM placement and disk scheduling
    python main.py --verify                          # every textbook check, PASS or FAIL
    python main.py --demo                            # CPU textbook example with Gantt charts
    python main.py --compare                         # all experiments, CSV + graphs

Scope (Review 2): workload, multiprocessor scheduling and dispatch, paging,
VM allocation, disk scheduling, metrics and graphs, all in one simulation.
"""

import argparse
import copy
import os

from workload import random_workload, textbook_workload
from scheduler import simulate, LOCAL_POLICIES, DISPATCH_POLICIES
from metrics import scheduling_summary, write_csv
from memory import count_faults, POLICIES as REPLACE_POLICIES
from vm_manager import MemoryPool, FITS
from disk import total_movement, POLICIES as DISK_POLICIES
from cloud import Config, run_cloud
import experiments
import visualize

RESULTS = "results"


def parse_args():
    p = argparse.ArgumentParser(description="Cloud Server Resource Manager simulator")
    p.add_argument("--local", choices=LOCAL_POLICIES, default="fcfs",
                   help="scheduling policy on each server")
    p.add_argument("--dispatch", choices=DISPATCH_POLICIES, default="rr",
                   help="how arriving jobs are sent to servers")
    p.add_argument("--quantum", type=int, default=4, help="Round Robin time slice")
    p.add_argument("--servers", default="4,2,2",
                   help="cores per server, comma separated (default 4,2,2)")
    p.add_argument("--jobs", type=int, default=200, help="number of random jobs")
    p.add_argument("--seed", type=int, default=42, help="random seed")
    p.add_argument("--gap", type=float, default=1.0, help="mean ticks between arrivals")
    p.add_argument("--memory", default="4096,2048,2048",
                   help="memory units per server, comma separated (default 4096,2048,2048)")
    p.add_argument("--replace", choices=REPLACE_POLICIES, default="lru",
                   help="page replacement policy")
    p.add_argument("--frames", type=int, default=4, help="page frames per job")
    p.add_argument("--fit", choices=FITS, default="first", help="VM placement policy")
    p.add_argument("--disk", choices=DISK_POLICIES, default="fcfs", help="disk scheduling policy")
    p.add_argument("--head", type=int, default=53, help="starting disk head cylinder (0 to 199)")
    p.add_argument("--demo", action="store_true", help="run the CPU textbook example")
    p.add_argument("--verify", action="store_true", help="check every module against textbook answers")
    p.add_argument("--compare", action="store_true", help="run all experiments")
    return p.parse_args()


def run_once(jobs, cores, local, dispatch, quantum):
    """Run on a fresh copy of the jobs so one run never affects another."""
    finished, servers, makespan = simulate(copy.deepcopy(jobs), cores, local, dispatch, quantum)
    return scheduling_summary(finished, servers, makespan), servers


def demo():
    print("Textbook example: jobs (burst) J1=24, J2=3, J3=3, all arrive at 0, one core\n")
    for local in LOCAL_POLICIES:
        summary, servers = run_once(textbook_workload(), [1], local, "rr", 4)
        print(f"{local.upper():5} avg waiting = {summary['avg_waiting']:6.2f}   "
              f"avg turnaround = {summary['avg_turnaround']:6.2f}")
        visualize.plot_gantt(servers[0], f"Gantt chart: {local.upper()} (quantum 4)",
                             os.path.join(RESULTS, f"gantt_{local}.png"))
    print("\nExpected by hand: FCFS 17.00, SJF 3.00, RR 5.67")


def verify():
    """Print every hand-calculated reference value next to what the code produces."""
    checks = []

    def check(name, got, expected):
        checks.append(got == expected)
        print(f"  {'PASS' if got == expected else 'FAIL'}  {name:42} got {got!s:>10}   expected {expected}")

    print("CPU scheduling, bursts 24, 3, 3 (average waiting time)")
    for local, exp in (("fcfs", 17.0), ("sjf", 3.0), ("rr", 5.67)):
        s, _ = run_once(textbook_workload(), [1], local, "rr", 4)
        check(local.upper() + (" (quantum 4)" if local == "rr" else ""), s["avg_waiting"], exp)

    refs = experiments.TEXTBOOK_REFS
    print("\nPage replacement, 20-reference string, 3 frames (faults)")
    for pol, exp in (("fifo", 15), ("lru", 12), ("opt", 9)):
        check(pol.upper(), count_faults(refs, 3, pol), exp)
    belady = [1, 2, 3, 4, 1, 2, 5, 1, 2, 3, 4, 5]
    print("\nBelady's anomaly, FIFO (faults)")
    check("3 frames", count_faults(belady, 3, "fifo"), 9)
    check("4 frames", count_faults(belady, 4, "fifo"), 10)

    print("\nVM placement, holes of 100, 500, 200, 300, 600 units; request 212")
    print("  (holes start at addresses 0, 110, 620, 830, 1140)")
    for fit, exp in (("first", 110), ("best", 830), ("worst", 1140)):
        pool = MemoryPool(1740)
        # Build the textbook hole layout: allocate blocks with 10-unit fillers between them,
        # then release blocks 0, 2, 4, 6, 8 so only the fillers stay allocated.
        for owner, size in enumerate([100, 10, 500, 10, 200, 10, 300, 10, 600]):
            pool.allocate(owner, size, "first")
        for owner in (0, 2, 4, 6, 8):
            pool.release(owner)
        check(f"{fit} fit start address", pool.allocate(99, 212, fit), exp)

    print("\nDisk queue 98, 183, 37, 122, 14, 124, 65, 67, head 53 (cylinders)")
    print("  (SCAN, LOOK and C-SCAN all start moving upward, toward cylinder 199)")
    for pol, exp in (("fcfs", 640), ("sstf", 236), ("scan", 331), ("cscan", 382), ("look", 299)):
        check(pol.upper(), total_movement(experiments.DISK_QUEUE, 53, pol)[0], exp)

    print(f"\n{sum(checks)} of {len(checks)} checks passed")


def compare(args, cores):
    jobs = random_workload(args.jobs, args.seed, args.gap)

    # Experiment 1: every local policy with every dispatch policy.
    rows = []
    for dispatch in DISPATCH_POLICIES:
        for local in LOCAL_POLICIES:
            s, _ = run_once(jobs, cores, local, dispatch, args.quantum)
            rows.append({"dispatch": dispatch, "local": local, **s})
    write_csv(rows, os.path.join(RESULTS, "exp1_policies.csv"))

    # Graph: local policies under least-loaded dispatch.
    least_rows = [dict(r, label=r["local"].upper()) for r in rows if r["dispatch"] == "least"]
    visualize.plot_policy_comparison(least_rows, os.path.join(RESULTS, "exp1_policies.png"))

    # Experiment 2: dispatch policies, utilisation per server (FCFS local).
    util = {}
    for dispatch in DISPATCH_POLICIES:
        s, _ = run_once(jobs, cores, "fcfs", dispatch, args.quantum)
        name = "Round-robin dispatch" if dispatch == "rr" else "Least-loaded dispatch"
        util[name] = s["utilisation"]
    visualize.plot_utilisation(util, os.path.join(RESULTS, "exp2_utilisation.png"))

    # Experiment 3: Round Robin quantum sweep (least-loaded dispatch).
    quanta = [1, 2, 4, 6, 8, 12, 16, 24]
    sweep = []
    for q in quanta:
        s, _ = run_once(jobs, cores, "rr", "least", q)
        sweep.append({"quantum": q, **s})
    write_csv(sweep, os.path.join(RESULTS, "exp3_quantum.csv"))
    visualize.plot_quantum_sweep(quanta, [r["avg_waiting"] for r in sweep],
                                 [r["avg_response"] for r in sweep],
                                 os.path.join(RESULTS, "exp3_quantum.png"))

    print("Experiment 1: CPU scheduling only (no VM admission, so every job is admitted)")
    print(f"{'dispatch':8} {'local':5} {'wait':>7} {'turn':>7} {'resp':>7} "
          f"{'thru':>7} {'util_std':>8}")
    for r in rows:
        print(f"{r['dispatch']:8} {r['local']:5} {r['avg_waiting']:7.2f} "
              f"{r['avg_turnaround']:7.2f} {r['avg_response']:7.2f} "
              f"{r['throughput']:7.3f} {r['util_std']:8.4f}")
    print("\nQuantum sweep (RR, least-loaded):")
    for r in sweep:
        print(f"  q={r['quantum']:2}  wait={r['avg_waiting']:7.2f}  resp={r['avg_response']:6.2f}")
    print(f"\nCSV and PNG files written to ./{RESULTS}/")
    print("\n" + "=" * 60)
    experiments.main()


def main():
    args = parse_args()
    os.makedirs(RESULTS, exist_ok=True)
    cores = [int(c) for c in args.servers.split(",")]

    if args.demo:
        demo()
    elif args.verify:
        verify()
    elif args.compare:
        compare(args, cores)
    else:
        cfg = Config(cores=cores, memory=[int(m) for m in args.memory.split(",")],
                     local=args.local, dispatch=args.dispatch, quantum=args.quantum,
                     replace=args.replace, frames=args.frames, fit=args.fit,
                     disk=args.disk, head=args.head)
        jobs = random_workload(args.jobs, args.seed, args.gap)
        s, _, _ = run_cloud(jobs, cfg)
        print("Cloud Server Resource Manager: one full run")
        print(f"  servers (cores)   : {cfg.cores}    memory: {cfg.memory}")
        print(f"  CPU               : local={cfg.local} dispatch={cfg.dispatch} quantum={cfg.quantum}")
        print(f"  memory            : replace={cfg.replace} frames/job={cfg.frames}")
        print(f"  VM / disk         : fit={cfg.fit} disk={cfg.disk} head={cfg.head}")
        print(f"  workload          : jobs={args.jobs} seed={args.seed} gap={args.gap}\n")
        for k, v in s.items():
            print(f"  {k:18}: {v}")


if __name__ == "__main__":
    main()
