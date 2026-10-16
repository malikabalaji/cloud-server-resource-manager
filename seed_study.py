"""
seed_study.py
Checks that the scheduling results are not a lucky accident of one seed.

Runs every (dispatch, local policy) pair on 10 different random workloads
(seeds 1 to 10) and reports the mean and standard deviation of each metric.

Run:  python seed_study.py
Output: results/exp4_seeds.csv
"""

import copy
import os
import statistics

from workload import random_workload
from scheduler import simulate, LOCAL_POLICIES, DISPATCH_POLICIES
from metrics import scheduling_summary, write_csv

SEEDS = range(1, 11)
CORES = [4, 2, 2]


def main():
    os.makedirs("results", exist_ok=True)
    rows = []
    for dispatch in DISPATCH_POLICIES:
        for local in LOCAL_POLICIES:
            waits, resps, stds = [], [], []
            for seed in SEEDS:
                jobs = random_workload(200, seed=seed)
                finished, servers, makespan = simulate(copy.deepcopy(jobs), CORES, local, dispatch, 4)
                s = scheduling_summary(finished, servers, makespan)
                waits.append(s["avg_waiting"])
                resps.append(s["avg_response"])
                stds.append(s["util_std"])
            rows.append({
                "dispatch": dispatch, "local": local,
                "wait_mean": round(statistics.mean(waits), 2),
                "wait_sd": round(statistics.stdev(waits), 2),
                "resp_mean": round(statistics.mean(resps), 2),
                "resp_sd": round(statistics.stdev(resps), 2),
                "util_std_mean": round(statistics.mean(stds), 3),
            })
    write_csv(rows, os.path.join("results", "exp4_seeds.csv"))
    print(f"{'dispatch':8} {'local':5} {'wait (mean, sd)':>18} {'resp (mean, sd)':>18} {'util spread':>12}")
    for r in rows:
        print(f"{r['dispatch']:8} {r['local']:5} {r['wait_mean']:9.2f} {r['wait_sd']:7.2f} "
              f"{r['resp_mean']:9.2f} {r['resp_sd']:7.2f} {r['util_std_mean']:12.3f}")


if __name__ == "__main__":
    main()
