"""
memory.py
Paging and page replacement.

Each admitted job owns a fixed set of F page frames inside its VM.
Replacement is LOCAL: when a job faults and all its frames are full, it
evicts one of ITS OWN pages, never another job's page.

Four replacement policies:
    fifo  : evict the page that has been in memory the longest
    lru   : evict the page that was used least recently
    opt   : evict the page whose next use is furthest in the future
            (Belady's optimal policy; needs to know the future, so it is a benchmark)
    clock : second-chance FIFO. Each frame has a reference bit. The hand skips
            (and clears) frames whose bit is 1 and evicts the first frame whose bit is 0.

A page fault does NOT block the job in this first version: the fault is
counted, and the job keeps running on its core.
"""

from collections import OrderedDict
from typing import Dict, List, Optional

POLICIES = ("fifo", "lru", "opt", "clock")
FRAME_SIZE = 8          # memory units per frame (a VM of 64 units holds 8 frames)


class FrameSet:
    """The frames owned by one job, plus the state its policy needs."""

    def __init__(self, n_frames: int, policy: str, refs: Optional[List[int]] = None):
        if policy not in POLICIES:
            raise ValueError(f"Unknown replacement policy: {policy}")
        if n_frames < 1:
            raise ValueError("A job needs at least one frame")
        self.n_frames = n_frames
        self.policy = policy
        self.refs = refs or []            # full reference string (only Optimal looks ahead)
        self.pos = 0                      # index of the next reference in self.refs
        self.faults = 0
        self.references = 0
        # One structure per policy keeps each algorithm easy to read:
        self.fifo_queue: List[int] = []            # fifo: oldest page at the front
        self.lru = OrderedDict()                   # lru: least recent page first
        self.frames: List[Optional[int]] = []      # opt and clock: page in each frame
        self.ref_bit: List[int] = []               # clock: reference bit per frame
        self.hand = 0                              # clock: index of the clock hand

    # ------------------------------------------------------------------
    def resident(self) -> List[int]:
        """Pages currently in this job's frames (used by tests and printing)."""
        if self.policy == "fifo":
            return list(self.fifo_queue)
        if self.policy == "lru":
            return list(self.lru.keys())
        return [p for p in self.frames if p is not None]

    def access(self, page: int) -> bool:
        """Reference one page. Returns True if it caused a page fault."""
        self.references += 1
        fault = getattr(self, "_" + self.policy)(page)
        self.pos += 1
        if fault:
            self.faults += 1
        return fault

    # ------------------------------------------------------------------
    def _fifo(self, page):
        if page in self.fifo_queue:
            return False                              # hit: FIFO order does not change
        if len(self.fifo_queue) == self.n_frames:
            self.fifo_queue.pop(0)                    # evict the oldest page
        self.fifo_queue.append(page)
        return True

    def _lru(self, page):
        if page in self.lru:
            self.lru.move_to_end(page)                # hit: now the most recently used
            return False
        if len(self.lru) == self.n_frames:
            self.lru.popitem(last=False)              # evict the least recently used
        self.lru[page] = True
        return True

    def _opt(self, page):
        if page in self.frames:
            return False
        if len(self.frames) < self.n_frames:
            self.frames.append(page)                  # a free frame is available
            return True
        future = self.refs[self.pos + 1:]

        def next_use(p):
            # Distance to the next use; pages never used again count as infinitely far.
            return future.index(p) if p in future else float("inf")

        # Evict the page used furthest in the future (ties: lowest frame index).
        victim = max(range(len(self.frames)), key=lambda i: (next_use(self.frames[i]), -i))
        self.frames[victim] = page
        return True

    def _clock(self, page):
        if page in self.frames:
            self.ref_bit[self.frames.index(page)] = 1  # hit: give it a second chance
            return False
        if len(self.frames) < self.n_frames:
            self.frames.append(page)
            self.ref_bit.append(1)
            return True
        while self.ref_bit[self.hand] == 1:           # skip pages that were used recently
            self.ref_bit[self.hand] = 0
            self.hand = (self.hand + 1) % self.n_frames
        self.frames[self.hand] = page                 # replace the first page with bit 0
        self.ref_bit[self.hand] = 1
        self.hand = (self.hand + 1) % self.n_frames
        return True


def count_faults(refs: List[int], n_frames: int, policy: str) -> int:
    """Run a whole reference string through one policy and count the faults.
    Used for the textbook checks and the faults-versus-frames experiment."""
    fs = FrameSet(n_frames, policy, refs)
    for p in refs:
        fs.access(p)
    return fs.faults


class MemoryManager:
    """One component, one policy, but a separate FrameSet for every job."""

    def __init__(self, policy: str, frames_per_job: int):
        if policy not in POLICIES:
            raise ValueError(f"Unknown replacement policy: {policy}")
        self.policy = policy
        self.frames_per_job = frames_per_job
        self.tables: Dict[int, FrameSet] = {}     # job_id -> its frames
        self.total_faults = 0
        self.total_references = 0

    def assign(self, job):
        """Give an admitted job its own frames."""
        self.tables[job.job_id] = FrameSet(self.frames_per_job, self.policy, job.pages)

    def reference(self, job) -> bool:
        """The job touches its next page. Returns True on a fault."""
        fs = self.tables[job.job_id]
        if fs.pos >= len(job.pages):
            return False                              # no more references for this job
        fault = fs.access(job.pages[fs.pos])
        self.total_references += 1
        self.total_faults += fault
        return fault

    def release(self, job):
        """Free the job's frames when it finishes; its counts stay in the totals."""
        fs = self.tables.pop(job.job_id, None)
        if fs:
            job.page_faults = fs.faults

    def fault_rate(self) -> float:
        return self.total_faults / self.total_references if self.total_references else 0.0
