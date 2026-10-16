"""
Tests for memory.py (paging and page replacement).
Expected values are the standard textbook answers or traced by hand below.
Run with:  python -m pytest -v
"""

import pytest
from memory import FrameSet, MemoryManager, count_faults
from job import Job

REFS = [7, 0, 1, 2, 0, 3, 0, 4, 2, 3, 0, 3, 2, 1, 2, 0, 1, 7, 0, 1]
BELADY = [1, 2, 3, 4, 1, 2, 5, 1, 2, 3, 4, 5]


@pytest.mark.parametrize("policy, expected", [("fifo", 15), ("lru", 12), ("opt", 9)])
def test_textbook_string_three_frames(policy, expected):
    assert count_faults(REFS, 3, policy) == expected


def test_belady_anomaly_fifo():
    # More frames, more faults: the anomaly that only FIFO-like policies show.
    assert count_faults(BELADY, 3, "fifo") == 9
    assert count_faults(BELADY, 4, "fifo") == 10


def test_lru_and_opt_never_get_worse_with_more_frames():
    # LRU and Optimal are stack algorithms, so they cannot show Belady's anomaly.
    for policy in ("lru", "opt"):
        faults = [count_faults(BELADY, f, policy) for f in range(1, 7)]
        assert faults == sorted(faults, reverse=True)


def test_clock_second_chance_by_hand():
    # Frames 3, string 1 2 3 2 4 1.
    # 1, 2, 3 fill the frames (3 faults, all bits 1). 2 is a hit (bit stays 1).
    # 4: hand clears the bits of 1, 2, 3, comes back to frame 0 and evicts 1 (fault 4).
    # 1: hand at frame 1, bit 0, evicts 2 (fault 5). Frames now 4, 1, 3.
    fs = FrameSet(3, "clock")
    for p in [1, 2, 3, 2, 4, 1]:
        fs.access(p)
    assert fs.faults == 5
    assert fs.frames == [4, 1, 3]


def test_optimal_is_a_lower_bound():
    for frames in range(1, 6):
        opt = count_faults(REFS, frames, "opt")
        for policy in ("fifo", "lru", "clock"):
            assert opt <= count_faults(REFS, frames, policy)


def test_replacement_is_local_to_each_job():
    # Two jobs with 2 frames each. Job A's faults must never evict job B's pages.
    mm = MemoryManager("lru", 2)
    a = Job(1, 0, 4, pages=[1, 2, 3, 4])
    b = Job(2, 0, 2, pages=[9, 8])
    mm.assign(a)
    mm.assign(b)
    mm.reference(b)
    mm.reference(b)                      # B holds pages 9 and 8
    for _ in range(4):
        mm.reference(a)                  # A faults 4 times inside its own 2 frames
    assert sorted(mm.tables[2].resident()) == [8, 9]
    assert mm.total_faults == 6


def test_release_keeps_counts():
    mm = MemoryManager("fifo", 3)
    j = Job(1, 0, 3, pages=[1, 1, 2])
    mm.assign(j)
    for _ in range(3):
        mm.reference(j)
    mm.release(j)
    assert j.page_faults == 2 and 1 not in mm.tables and mm.total_references == 3
