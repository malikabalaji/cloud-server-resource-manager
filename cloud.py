"""
cloud.py
Builds the whole cloud from one configuration and runs it.

Every experiment, the command line and the integration tests go through
run_cloud(), so all of them use exactly the same wiring:

    jobs -> dispatcher -> server (VM placed in that server's memory)
         -> CPU scheduler on the server's cores
         -> each tick: page reference (local frames) and maybe a disk log request
         -> shared disk serves one request per tick
"""

import copy
from dataclasses import dataclass, field
from typing import List

from scheduler import simulate
from memory import MemoryManager
from vm_manager import VMManager
from disk import Disk
from metrics import scheduling_summary, resource_summary


@dataclass
class Config:
    cores: List[int] = field(default_factory=lambda: [4, 2, 2])
    memory: List[int] = field(default_factory=lambda: [4096, 2048, 2048])
    local: str = "fcfs"        # fcfs | sjf | rr
    dispatch: str = "rr"       # rr | least
    quantum: int = 4
    replace: str = "lru"       # fifo | lru | opt | clock
    frames: int = 4            # frames per job (3 to 8 in the experiments)
    fit: str = "first"         # first | best | worst
    disk: str = "fcfs"         # fcfs | sstf | scan | cscan | look
    head: int = 53             # starting head position on a 0..199 disk

    def __post_init__(self):
        if len(self.memory) != len(self.cores):
            raise ValueError("Give one memory size per server")


def run_cloud(jobs, cfg: Config):
    """Run on a deep copy of the jobs (so the caller's list is never changed).
    Returns (summary dict, servers, managers dict)."""
    jobs = copy.deepcopy(jobs)
    memory = MemoryManager(cfg.replace, cfg.frames)
    vms = VMManager(cfg.memory, cfg.fit)
    disk = Disk(cfg.disk, head=cfg.head)
    finished, servers, makespan = simulate(jobs, cfg.cores, cfg.local, cfg.dispatch,
                                           cfg.quantum, memory, vms, disk)
    rejected = [j for j in jobs if j.rejected]
    summary = scheduling_summary(finished, servers, makespan)
    summary.update(resource_summary(memory, vms, disk, len(rejected)))
    return summary, servers, {"memory": memory, "vms": vms, "disk": disk, "jobs": jobs}
