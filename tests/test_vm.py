"""
Tests for vm_manager.py (VM allocation with first, best and worst fit).
Run with:  python -m pytest -v
"""

import pytest
from vm_manager import MemoryPool, VMManager
from job import Job


def textbook_pool():
    """Holes of 100, 500, 200, 300, 600 at addresses 0, 110, 620, 830, 1140,
    separated by 10-unit blocks that stay allocated (owners 1, 3, 5, 7)."""
    pool = MemoryPool(1740)
    for owner, size in enumerate([100, 10, 500, 10, 200, 10, 300, 10, 600]):
        pool.allocate(owner, size, "first")
    for owner in (0, 2, 4, 6, 8):
        pool.release(owner)
    return pool


def test_hole_layout():
    assert textbook_pool().holes == [(0, 100), (110, 500), (620, 200), (830, 300), (1140, 600)]


@pytest.mark.parametrize("fit, start", [("first", 110), ("best", 830), ("worst", 1140)])
def test_placement_of_212(fit, start):
    # 212 fits in the 500, 300 and 600 holes.
    # First fit: first in address order = 500 hole at 110.
    # Best fit : smallest that fits      = 300 hole at 830.
    # Worst fit: largest                 = 600 hole at 1140.
    assert textbook_pool().allocate(99, 212, fit) == start


def test_reject_when_nothing_fits():
    pool = textbook_pool()
    assert pool.allocate(99, 601, "best") is None      # largest hole is 600


def test_release_merges_neighbours():
    pool = MemoryPool(300)
    for owner in range(3):
        pool.allocate(owner, 100, "first")              # [0][1][2], no free memory
    pool.release(0)
    pool.release(2)
    assert pool.holes == [(0, 100), (200, 100)]
    pool.release(1)                                      # middle block joins both sides
    assert pool.holes == [(0, 300)]


def test_fragmentation_formula():
    pool = textbook_pool()
    # Free 1700, largest hole 600: EF = 1 - 600/1700.
    assert pool.fragmentation() == pytest.approx(1 - 600 / 1700)
    assert MemoryPool(100).fragmentation() == 0.0


def test_each_server_has_its_own_memory():
    vms = VMManager([100, 100], "first")
    assert vms.allocate(0, Job(1, 0, 1, vm_size=100))
    assert not vms.allocate(0, Job(2, 0, 1, vm_size=64))   # server 0 is full
    assert vms.allocate(1, Job(3, 0, 1, vm_size=64))        # server 1 still has room
    assert vms.success_rate() == pytest.approx(2 / 3)
