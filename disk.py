"""
disk.py
Disk logging and disk scheduling on ONE disk shared by all servers.

Running jobs issue log requests (cylinder numbers). They join a single queue.
The disk serves ONE request per tick, chosen by the disk policy:

    fcfs  : oldest request first
    sstf  : request nearest the current head position
    scan  : move in one direction serving requests, go all the way to the
            edge of the disk, then reverse (the "elevator")
    cscan : move in one direction only; at the edge jump back to the other
            edge (the return seek is counted) and continue in the same direction
    look  : like SCAN, but reverse at the last request instead of the edge

Fair comparison: SCAN, LOOK and C-SCAN all start in the SAME direction
(default +1, toward the highest cylinder), so differences in head movement
come from the algorithm and not from a different starting direction.

Metric: total head movement (cylinders), and average seek per request.

The disk does not block jobs in this first version: a job issues its
request and keeps running; the request waits in the disk queue.
"""

from typing import List, Tuple

POLICIES = ("fcfs", "sstf", "scan", "cscan", "look")


class Disk:
    def __init__(self, policy: str, head: int = 53, lo: int = 0, hi: int = 199,
                 direction: int = +1):
        """direction: +1 means the head starts moving toward hi (cylinder 199),
        -1 toward lo (cylinder 0). The same value is used by SCAN, LOOK and C-SCAN."""
        if policy not in POLICIES:
            raise ValueError(f"Unknown disk policy: {policy}")
        self.policy = policy
        self.head = head
        self.lo, self.hi = lo, hi
        self.direction = direction
        self.queue: List[Tuple[int, int]] = []    # (cylinder, tick issued), oldest first
        self.movement = 0                          # total cylinders travelled
        self.served = 0
        self.order: List[int] = []                 # cylinders in the order served

    def enqueue(self, cylinder: int, tick: int = 0):
        if not self.lo <= cylinder <= self.hi:
            raise ValueError(f"Cylinder {cylinder} outside {self.lo}..{self.hi}")
        self.queue.append((cylinder, tick))

    def pending(self) -> bool:
        return bool(self.queue)

    # ------------------------------------------------------------------
    def _move_to(self, cylinder: int):
        self.movement += abs(cylinder - self.head)
        self.head = cylinder

    def _ahead(self):
        """Requests at or beyond the head in the current direction."""
        if self.direction > 0:
            return [i for i, (c, _) in enumerate(self.queue) if c >= self.head]
        return [i for i, (c, _) in enumerate(self.queue) if c <= self.head]

    def _pick(self) -> int:
        """Index in the queue of the request to serve next."""
        if self.policy == "fcfs":
            return 0
        if self.policy == "sstf":
            return min(range(len(self.queue)),
                       key=lambda i: (abs(self.queue[i][0] - self.head), self.queue[i][1]))
        ahead = self._ahead()
        if not ahead:
            if self.policy == "scan":
                self._move_to(self.lo if self.direction < 0 else self.hi)   # travel to the edge
                self.direction = -self.direction
            elif self.policy == "look":
                self.direction = -self.direction                           # turn at last request
            else:  # cscan: finish the sweep, then jump to the other edge (counted)
                if self.direction > 0:
                    self._move_to(self.hi)
                    self._move_to(self.lo)
                else:
                    self._move_to(self.lo)
                    self._move_to(self.hi)
            ahead = self._ahead()
        return min(ahead, key=lambda i: (abs(self.queue[i][0] - self.head), self.queue[i][1]))

    def serve_one(self) -> bool:
        """Serve one request (one per tick). Returns False if the queue is empty."""
        if not self.queue:
            return False
        cylinder, _ = self.queue.pop(self._pick())
        self._move_to(cylinder)
        self.served += 1
        self.order.append(cylinder)
        return True

    def avg_seek(self) -> float:
        return self.movement / self.served if self.served else 0.0


def total_movement(requests: List[int], head: int, policy: str,
                   lo: int = 0, hi: int = 199, direction: int = +1) -> Tuple[int, List[int]]:
    """Serve a fixed queue completely (the textbook setting).
    Uses exactly the same Disk.serve_one logic as the simulation."""
    d = Disk(policy, head, lo, hi, direction)
    for c in requests:
        d.enqueue(c)
    while d.serve_one():
        pass
    return d.movement, d.order
