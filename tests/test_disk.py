"""
Tests for disk.py (disk scheduling on one shared disk).
Queue 98, 183, 37, 122, 14, 124, 65, 67; head at 53; cylinders 0 to 199.
For a fair comparison SCAN, LOOK and C-SCAN all start moving in the SAME direction
(upward, toward 199, unless another direction is given). C-SCAN counts the return seek.
Run with:  python -m pytest -v
"""

import pytest
from disk import Disk, total_movement

Q = [98, 183, 37, 122, 14, 124, 65, 67]


@pytest.mark.parametrize("policy, expected", [
    ("fcfs", 640),    # 45+85+146+85+108+110+59+2
    ("sstf", 236),    # 53->65->67->37->14->98->122->124->183
    ("scan", 331),    # 53 up to 183 (130), on to 199 (16), back down to 14 (185)
    ("cscan", 382),   # 53 up to 199 (146), return to 0 (199), up to 37 (37)
    ("look", 299),    # 53 up to 183 (130), back down to 14 (169)
])
def test_textbook_head_movement(policy, expected):
    assert total_movement(Q, 53, policy)[0] == expected


@pytest.mark.parametrize("policy, expected", [
    ("scan", 236),    # 53 down to 0 (53), then up to 183 (183)
    ("cscan", 386),   # 53 down to 0 (53), return to 199 (199), down to 65 (134)
    ("look", 208),    # 53 down to 14 (39), then up to 183 (169)
])
def test_same_rule_when_all_start_downward(policy, expected):
    assert total_movement(Q, 53, policy, direction=-1)[0] == expected


def test_scan_look_cscan_share_the_starting_direction():
    # All three serve 65 first when moving upward, and 37 first when moving downward.
    for policy in ("scan", "look", "cscan"):
        assert total_movement(Q, 53, policy)[1][0] == 65
        assert total_movement(Q, 53, policy, direction=-1)[1][0] == 37


def test_service_orders():
    assert total_movement(Q, 53, "sstf")[1] == [65, 67, 37, 14, 98, 122, 124, 183]
    assert total_movement(Q, 53, "cscan")[1] == [65, 67, 98, 122, 124, 183, 14, 37]


def test_one_request_per_tick():
    d = Disk("fcfs", head=0)
    d.enqueue(10)
    d.enqueue(20)
    assert d.serve_one() and d.served == 1 and d.pending()
    assert d.serve_one() and not d.pending()
    assert not d.serve_one()                     # nothing left: no movement
    assert d.movement == 20 and d.avg_seek() == 10


def test_out_of_range_cylinder_rejected():
    with pytest.raises(ValueError):
        Disk("sstf").enqueue(250)
