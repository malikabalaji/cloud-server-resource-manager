"""
workload.py
Creates the list of jobs fed into the simulator.

Two kinds of workload:
1. Fixed workloads: small, hand-written job lists from the textbook.
   We know the correct answers for these, so they prove the code works.
2. Random workloads: many jobs generated from a seed. The same seed
   always produces the same jobs, so every experiment is repeatable.

Why a mix of short and long jobs: real cloud traffic is mostly small
requests with a few heavy batch jobs. This mix is exactly where
FCFS, SJF and Round Robin behave differently, so it makes the
comparison meaningful.
"""

import random
from typing import List
from job import Job

VM_SIZES = (64, 128, 192, 256, 320, 384, 448, 512)   # multiples of the 8-unit frame size


def textbook_workload() -> List[Job]:
    """Classic example (Silberschatz): three jobs arrive at time 0
    with bursts 24, 3 and 3. Hand-calculated average waiting time:
    FCFS 17.0, SJF 3.0, Round Robin with quantum 4 is 17/3 (about 5.67)."""
    return [
        Job(job_id=1, arrival=0, burst=24),
        Job(job_id=2, arrival=0, burst=3),
        Job(job_id=3, arrival=0, burst=3),
    ]


def random_workload(n_jobs: int = 200, seed: int = 42,
                    mean_gap: float = 1.0, long_fraction: float = 0.2,
                    disk_prob: float = 0.25) -> List[Job]:
    """Generate n_jobs jobs with a fixed seed.

    mean_gap      : average ticks between arrivals (smaller means busier)
    long_fraction : share of jobs that are long batch jobs
    disk_prob     : chance that a CPU tick of a job also issues a disk log request
    """
    rng = random.Random(seed)       # private generator, so the seed fully controls output
    jobs = []
    t = 0.0
    for i in range(1, n_jobs + 1):
        # Exponential gaps model independent users arriving at random.
        t += rng.expovariate(1.0 / mean_gap)
        if rng.random() < long_fraction:
            burst = rng.randint(20, 60)      # long batch job
        else:
            burst = rng.randint(1, 10)       # short interactive request
        jobs.append(Job(job_id=i, arrival=int(t), burst=burst))

    # Resource demands come from a SEPARATE generator, so changing them does not
    # change the arrivals and bursts produced by a given seed.
    # vm_size (memory units, multiples of the 8-unit frame) is the only memory
    # demand; it is what vm_manager.py places in the server's memory.
    res = random.Random(seed * 7919 + 1)
    for job in jobs:
        job.vm_size = res.choice(VM_SIZES)
        job.pages = reference_string(res, job.burst)
        job.disk_requests = {step: res.randint(0, 199)
                             for step in range(job.burst) if res.random() < disk_prob}
    return jobs


def reference_string(rng: random.Random, length: int, locality: float = 0.7) -> List[int]:
    """Page references with locality: each job uses 5 to 12 distinct pages and,
    with probability `locality`, re-uses one of its last three pages."""
    n_pages = rng.randint(5, 12)
    refs: List[int] = []
    for _ in range(length):
        if refs and rng.random() < locality:
            refs.append(rng.choice(refs[-3:]))       # recently used page (locality)
        else:
            refs.append(rng.randrange(n_pages))       # any page of the job
    return refs
