"""
vm_manager.py
Virtual machine allocation with contiguous placement.

Each server has its own physical memory (for example 4096 units). When a job
is dispatched to a server, its VM must be placed in one free block (hole) of
THAT server's memory. Three placement policies:

    first : the first hole, in address order, that is large enough
    best  : the smallest hole that is large enough (least leftover)
    worst : the largest hole (keeps the leftover piece usable)

If no hole is large enough the request is REJECTED and counted; the job is
not admitted. When a VM is released, its block is returned and merged with
neighbouring holes, so free space does not stay split into tiny pieces.

External fragmentation of one server:
    EF = 1 - (largest free hole / total free memory)
EF is 0 when all free memory is one block, and close to 1 when it is
scattered into many small holes.
"""

from typing import Dict, List, Optional, Tuple

FITS = ("first", "best", "worst")


class MemoryPool:
    """The memory of one server, kept as a sorted list of (start, size) holes."""

    def __init__(self, capacity: int):
        self.capacity = capacity
        self.holes: List[Tuple[int, int]] = [(0, capacity)]   # all memory free at start
        self.allocated: Dict[int, Tuple[int, int]] = {}       # owner id -> (start, size)

    def free_total(self) -> int:
        return sum(size for _, size in self.holes)

    def largest_hole(self) -> int:
        return max((size for _, size in self.holes), default=0)

    def fragmentation(self) -> float:
        free = self.free_total()
        return 0.0 if free == 0 else 1.0 - self.largest_hole() / free

    def allocate(self, owner: int, size: int, fit: str) -> Optional[int]:
        """Place a block of `size` for `owner`. Returns its start address, or None."""
        if fit not in FITS:
            raise ValueError(f"Unknown fit policy: {fit}")
        candidates = [i for i, (_, s) in enumerate(self.holes) if s >= size]
        if not candidates:
            return None                                       # rejected: nothing fits
        if fit == "first":
            i = candidates[0]                                 # holes are in address order
        elif fit == "best":
            i = min(candidates, key=lambda k: (self.holes[k][1], self.holes[k][0]))
        else:
            i = max(candidates, key=lambda k: (self.holes[k][1], -self.holes[k][0]))
        start, hole_size = self.holes[i]
        if hole_size == size:
            self.holes.pop(i)                                 # hole used up exactly
        else:
            self.holes[i] = (start + size, hole_size - size)  # shrink the hole from the front
        self.allocated[owner] = (start, size)
        return start

    def release(self, owner: int):
        """Return the owner's block and merge it with adjacent holes."""
        start, size = self.allocated.pop(owner)
        self.holes.append((start, size))
        self.holes.sort()
        merged = [self.holes[0]]
        for s, sz in self.holes[1:]:
            ps, psz = merged[-1]
            if ps + psz == s:                                 # touching: join them
                merged[-1] = (ps, psz + sz)
            else:
                merged.append((s, sz))
        self.holes = merged


class VMManager:
    """One component, one fit policy, but a separate MemoryPool per server."""

    def __init__(self, capacities: List[int], fit: str):
        if fit not in FITS:
            raise ValueError(f"Unknown fit policy: {fit}")
        self.fit = fit
        self.pools = [MemoryPool(c) for c in capacities]
        self.requests = 0
        self.admitted = 0
        self.ef_samples: List[float] = []     # fragmentation sampled once per tick per server

    def allocate(self, server_id: int, job) -> bool:
        self.requests += 1
        ok = self.pools[server_id].allocate(job.job_id, job.vm_size, self.fit) is not None
        self.admitted += ok
        return ok

    def release(self, server_id: int, job):
        self.pools[server_id].release(job.job_id)

    def sample(self):
        """Record the current fragmentation of every server that holds at least one VM."""
        for pool in self.pools:
            if pool.allocated:
                self.ef_samples.append(pool.fragmentation())

    def success_rate(self) -> float:
        return self.admitted / self.requests if self.requests else 1.0

    def avg_fragmentation(self) -> float:
        """Average fragmentation among active server pools (pools holding at least one VM)."""
        return sum(self.ef_samples) / len(self.ef_samples) if self.ef_samples else 0.0
