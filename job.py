"""
job.py
Data model for one user job submitted to the cloud.

A Job is a plain record. It holds what the user asked for (arrival time,
CPU burst, memory) and what the simulator fills in while the job runs
(which server ran it, when it first got a core, when it finished).

Why a dataclass: it gives us a clean constructor and readable printing
for free, so the code stays short and easy to explain.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class Job:
    # ---- Inputs (set when the job is created) ----
    job_id: int            # unique number, e.g. 1, 2, 3
    arrival: int           # tick at which the job reaches the cloud
    burst: int             # total CPU ticks the job needs
    vm_size: int = 64      # memory units the job's VM needs on its server (the ONLY memory size used)
    pages: List[int] = field(default_factory=list)          # page reference string, one per CPU tick
    disk_requests: Dict[int, int] = field(default_factory=dict)  # CPU step -> cylinder to log

    # ---- Filled in by the simulator ----
    remaining: int = field(init=False)        # CPU ticks still needed
    server_id: Optional[int] = None           # server chosen by the dispatcher
    first_start: Optional[int] = None         # first tick the job got a core
    completion: Optional[int] = None          # tick at which the job finished
    quantum_used: int = 0                     # ticks used in the current Round Robin slice
    rejected: bool = False                    # True if no server memory could hold its VM
    page_faults: int = 0                      # filled in when the job releases its frames

    def __post_init__(self):
        # At creation the job still needs its full burst.
        self.remaining = self.burst

    # ---- Metrics, computed from the times above ----
    @property
    def turnaround(self) -> int:
        """Total time in the system: finish time minus arrival time."""
        return self.completion - self.arrival

    @property
    def waiting(self) -> int:
        """Time spent ready but not running: turnaround minus CPU time."""
        return self.turnaround - self.burst

    @property
    def response(self) -> int:
        """Time until the job first got a core."""
        return self.first_start - self.arrival

    def is_done(self) -> bool:
        return self.remaining == 0
