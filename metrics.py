"""
metrics.py
Turns a finished simulation into numbers we can compare.

Scheduling metrics (all in ticks unless noted):
    avg_waiting     : average time jobs sat ready but not running
    avg_turnaround  : average time from arrival to finish
    avg_response    : average time from arrival to first run
    throughput      : jobs finished per tick (jobs / makespan)
    utilisation     : per server, share of core-time spent working
    util_std        : spread of utilisation across servers (lower = better balanced)

Resource metrics (full cloud mode):
    page_faults, fault_rate : total faults and faults / references (memory manager)
    vm_success_rate         : admitted VMs / VM requests
    rejected                : jobs whose VM did not fit on their server
    avg_fragmentation       : average fragmentation among active server pools, i.e. the
                              mean of 1 - largest hole / free memory, sampled once per
                              tick on each server that holds at least one VM (servers
                              with no VMs are not counted, so this is not a system-wide
                              average)
    head_movement, avg_seek : total cylinders travelled and per request (disk)

Why both average and spread: an average can hide one overloaded server.
The standard deviation shows whether the load is shared evenly.

Improvement over a baseline (paper, equations 8 and 9):
    lower is better  : (base - alg) / base * 100
    higher is better : (alg - base) / base * 100
Both need a nonzero baseline; otherwise the plain difference is reported.
"""

import csv
import statistics
from typing import Dict, List


def scheduling_summary(finished, servers, makespan) -> Dict:
    n = len(finished)
    if n == 0:
        return {"jobs": 0, "makespan": 0, "avg_waiting": 0.0, "avg_turnaround": 0.0,
                "avg_response": 0.0, "throughput": 0.0,
                "utilisation": [0.0] * len(servers), "util_std": 0.0}
    utils = [s.utilisation(makespan) for s in servers]
    return {
        "jobs": n,
        "makespan": makespan,
        "avg_waiting": round(sum(j.waiting for j in finished) / n, 2),
        "avg_turnaround": round(sum(j.turnaround for j in finished) / n, 2),
        "avg_response": round(sum(j.response for j in finished) / n, 2),
        "throughput": round(n / makespan, 4) if makespan else 0.0,
        "utilisation": [round(u, 3) for u in utils],
        "util_std": round(statistics.pstdev(utils), 4) if len(utils) > 1 else 0.0,
    }


def resource_summary(memory, vms, disk, rejected: int) -> Dict:
    return {
        "page_faults": memory.total_faults,
        "fault_rate": round(memory.fault_rate(), 4),
        "vm_requests": vms.requests,
        "rejected": rejected,
        "rejection_rate": round(rejected / vms.requests, 4) if vms.requests else 0.0,
        "vm_success_rate": round(vms.success_rate(), 4),
        "avg_fragmentation": round(vms.avg_fragmentation(), 4),
        "disk_served": disk.served,
        "head_movement": disk.movement,
        "avg_seek": round(disk.avg_seek(), 2),
    }


def improvement(base: float, alg: float, higher_is_better: bool = False):
    """Percentage improvement of alg over base. Returns (value, unit):
    unit is '%' normally, or 'abs' when the baseline is zero."""
    if base == 0:
        return (alg - base if higher_is_better else base - alg), "abs"
    pct = (alg - base) / base * 100 if higher_is_better else (base - alg) / base * 100
    return round(pct, 2), "%"


def mean_ci95(values: List[float]):
    """Mean and half-width of a 95% confidence interval (t distribution)."""
    n = len(values)
    m = statistics.mean(values)
    if n < 2:
        return m, 0.0
    t_crit = {2: 12.706, 3: 4.303, 4: 3.182, 5: 2.776, 6: 2.571, 7: 2.447,
              8: 2.365, 9: 2.306, 10: 2.262}.get(n, 1.96)   # critical t for n - 1 degrees
    return m, t_crit * statistics.stdev(values) / n ** 0.5


def write_csv(rows: List[Dict], path: str):
    """Save a list of result dictionaries as a CSV table for the report."""
    if not rows:
        return
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        for row in rows:
            out = dict(row)
            # Lists (per-server utilisation) are stored as "0.91|0.88|0.90".
            for k, v in out.items():
                if isinstance(v, list):
                    out[k] = "|".join(str(x) for x in v)
            writer.writerow(out)
