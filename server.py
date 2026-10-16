"""
server.py
Data model for one physical server in the cloud.

A server has a number of CPU cores. Jobs sent to it wait in a ready
queue. On every tick, each free core takes a job from the queue
(the scheduler decides which one), and each busy core does one tick
of work on its job.

Why model cores explicitly: this is what makes it multiprocessor
scheduling. A 4-core server can run 4 jobs at the same moment.
"""

from typing import List, Optional
from job import Job


class Server:
    def __init__(self, server_id: int, cores: int):
        self.server_id = server_id
        self.cores = cores
        self.ready_queue: List[Job] = []                  # jobs waiting for a core
        self.running: List[Optional[Job]] = [None] * cores  # one slot per core
        self.finished: List[Job] = []                     # completed jobs
        self.busy_ticks = 0                               # core-ticks spent doing work
        self.timeline = []                                # (core, tick, job_id) for Gantt charts

    def outstanding_work(self) -> int:
        """Total CPU ticks still owed to every job on this server
        (waiting plus running). The dispatcher uses this as 'load'."""
        waiting = sum(j.remaining for j in self.ready_queue)
        running = sum(j.remaining for j in self.running if j is not None)
        return waiting + running

    def load_per_core(self) -> float:
        """Load divided by cores, so a 4-core server with 8 ticks of work
        counts as less loaded than a 1-core server with 4 ticks."""
        return self.outstanding_work() / self.cores

    def is_idle(self) -> bool:
        return not self.ready_queue and all(j is None for j in self.running)

    def utilisation(self, makespan: int) -> float:
        """Fraction of available core-time actually used for work."""
        if makespan == 0:
            return 0.0
        return self.busy_ticks / (self.cores * makespan)
