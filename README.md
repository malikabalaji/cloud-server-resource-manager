# Cloud Server Resource Manager

A reproducible simulator of a small cloud. Jobs arrive over time, are dispatched to
servers with unequal core counts, run under a CPU scheduling policy, place a VM in
their server's memory, use their own page frames, and log requests to one shared
disk. Every algorithm is chosen by a command-line flag and compared against a simple
baseline on the same seeded workload.

Operating Systems project, VIT Vellore. Team: Nehaa Prabhu (24BAI0130),
Sanhit Muthuswamy (24BCE0173), Malika Balaji (24BAI0114).

## What is implemented

| Decision | Algorithms | Baseline | File |
| --- | --- | --- | --- |
| Dispatch to servers | Round-robin, least-loaded per core | Round-robin | `scheduler.py` |
| CPU scheduling per server | FCFS, SJF, Round Robin | FCFS | `scheduler.py` |
| Page replacement | FIFO, LRU, Optimal, Clock | FIFO | `memory.py` |
| VM placement | First fit, best fit, worst fit | First fit | `vm_manager.py` |
| Disk scheduling | FCFS, SSTF, SCAN, C-SCAN, LOOK | FCFS | `disk.py` |

## Resource model

| Resource | Owner | Notes |
| --- | --- | --- |
| CPU cores | Each server (4, 2, 2) | One ready queue and scheduler per server |
| Physical memory | Each server (4096, 2048, 2048 units) | A job's VM must fit on the server it is sent to, otherwise the job is rejected |
| Page frames | Each job (F frames, frame size 8) | Replacement is local to the job |
| Disk | Shared by all servers (cylinders 0 to 199) | One queue, one request served per tick |

## Limitations of the current version

- **Paging and disk do not delay jobs.** Page faults and disk requests are recorded, but they
  do not block CPU execution or delay job completion. Paging and disk policies are therefore
  evaluated with page-fault statistics and disk head movement, not by their effect on job
  waiting or completion time.
- **No retry after VM rejection.** If a job's VM does not fit on the server chosen by the
  dispatcher, the job is rejected and is not retried on another server. Dispatch policies can
  therefore admit different numbers of jobs, so rejection rates are reported separately
  (`results/exp8_dispatch_full.csv`) whenever dispatch policies are compared.
- **Fragmentation is averaged over active servers.** `avg_fragmentation` is the average
  fragmentation among active server pools (servers holding at least one VM), sampled once per
  tick; it is not a system-wide average.

## Project structure

```
cloud_sim/
├── job.py            Job record: arrival, burst, VM size, pages, disk requests, results
├── server.py         Server: cores, ready queue, utilisation
├── workload.py       Textbook jobs and seeded random workloads
├── scheduler.py      Dispatcher, CPU scheduling and the tick-driven main loop
├── memory.py         Page frames and FIFO, LRU, Optimal, Clock replacement
├── vm_manager.py     Per-server memory pools and first, best, worst fit
├── disk.py           Shared disk and FCFS, SSTF, SCAN, C-SCAN, LOOK
├── cloud.py          Builds every manager from one Config and runs the cloud
├── metrics.py        Summaries, improvement formulas, 95% confidence intervals
├── visualize.py      Gantt charts and comparison graphs (matplotlib)
├── experiments.py    Paging, VM and disk experiments over 10 seeds
├── seed_study.py     CPU scheduling repeated over 10 seeds
├── main.py           Command-line entry point
├── tests/            45 pytest tests (textbook answers and integration checks)
└── results/          CSV tables and PNG graphs written by the experiments
```

## Setup

Requires Python 3.9 or later.

```bash
git clone <repository-url>
cd cloud-server-resource-manager
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## How to run

```bash
python main.py --verify                       # every textbook check, PASS or FAIL
python main.py --demo                         # CPU textbook example and Gantt charts
python main.py                                # one full-cloud run with default settings
python main.py --local sjf --dispatch least   # choose CPU algorithms
python main.py --replace clock --frames 5     # choose paging policy and frames per job
python main.py --fit best --disk look         # choose VM placement and disk policy
python main.py --compare                      # all experiments, CSV and PNG in results/
python seed_study.py                          # CPU scheduling over 10 seeds
python experiments.py                         # paging, VM, disk over 10 seeds
python -m pytest -v                           # run all tests
```

## Command-line options

| Flag | Values | Default | Meaning |
| --- | --- | --- | --- |
| `--local` | fcfs, sjf, rr | fcfs | CPU scheduling policy on each server |
| `--dispatch` | rr, least | rr | Round-robin or least-loaded dispatch |
| `--quantum` | integer | 4 | Round Robin time slice (ticks) |
| `--servers` | e.g. 4,2,2 | 4,2,2 | Cores per server |
| `--memory` | e.g. 4096,2048,2048 | 4096,2048,2048 | Memory units per server |
| `--replace` | fifo, lru, opt, clock | lru | Page replacement policy |
| `--frames` | integer | 4 | Page frames per job |
| `--fit` | first, best, worst | first | VM placement policy |
| `--disk` | fcfs, sstf, scan, cscan, look | fcfs | Disk scheduling policy |
| `--head` | 0 to 199 | 53 | Starting disk head cylinder |
| `--jobs` | integer | 200 | Number of random jobs |
| `--seed` | integer | 42 | Random seed (same seed, same results) |
| `--gap` | number | 1.0 | Mean ticks between arrivals |

## Verification

`python main.py --verify` checks every module against hand-calculated answers:

| Input | Algorithm | Expected |
| --- | --- | --- |
| Bursts 24, 3, 3 | FCFS / SJF / RR (q = 4) | Average waiting 17 / 3 / 5.67 |
| 7,0,1,2,0,3,0,4,2,3,0,3,2,1,2,0,1,7,0,1, 3 frames | FIFO / LRU / Optimal | 15 / 12 / 9 faults |
| 1,2,3,4,1,2,5,1,2,3,4,5 | FIFO, 3 / 4 frames | 9 / 10 faults (Belady's anomaly) |
| Holes 100, 500, 200, 300, 600; request 212 | First / best / worst fit | Holes of 500 / 300 / 600 |
| 98,183,37,122,14,124,65,67, head 53 | FCFS / SSTF / SCAN / C-SCAN / LOOK | 640 / 236 / 331 / 382 / 299 cylinders |

For a fair comparison SCAN, LOOK and C-SCAN all start moving in the same direction (upward, toward
cylinder 199). C-SCAN counts the return seek.
