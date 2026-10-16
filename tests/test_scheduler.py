"""
Tests for the scheduling module. Every expected value below was worked out
by hand first (the working is in the comments), then checked by the code.
Run with:  python -m pytest -v
"""

from job import Job
from workload import textbook_workload, random_workload
from scheduler import simulate


def run(jobs, cores, local, dispatch="rr", quantum=4):
    finished, servers, makespan = simulate(jobs, cores, local, dispatch, quantum)
    by_id = {j.job_id: j for j in finished}
    return by_id, servers, makespan


# ---------------------------------------------------------------------------
# Textbook example: J1=24, J2=3, J3=3, all arrive at 0, one core
# ---------------------------------------------------------------------------
def test_fcfs_textbook():
    # Order J1 J2 J3. Waits: J1 0, J2 24, J3 27. Average 51/3 = 17.
    jobs, _, _ = run(textbook_workload(), [1], "fcfs")
    assert [jobs[i].waiting for i in (1, 2, 3)] == [0, 24, 27]


def test_sjf_textbook():
    # Order J2 J3 J1. Waits: J2 0, J3 3, J1 6. Average 9/3 = 3.
    jobs, _, _ = run(textbook_workload(), [1], "sjf")
    assert [jobs[i].waiting for i in (1, 2, 3)] == [6, 0, 3]


def test_rr_textbook_quantum_4():
    # J1 0-4, J2 4-7, J3 7-10, J1 10-30.
    # Waits: J1 30-24 = 6, J2 4, J3 7. Average 17/3, about 5.67.
    jobs, _, makespan = run(textbook_workload(), [1], "rr", quantum=4)
    assert [jobs[i].waiting for i in (1, 2, 3)] == [6, 4, 7]
    assert makespan == 30


# ---------------------------------------------------------------------------
# Round Robin with a late arrival: J1 (arrive 0, burst 5), J2 (arrive 1, burst 3), q = 2
# ---------------------------------------------------------------------------
def test_rr_late_arrival():
    # J1 0-2, J2 2-4, J1 4-6, J2 6-7 (done at 7), J1 7-8 (done at 8).
    # J1: turnaround 8, waiting 3, response 0.
    # J2: turnaround 6, waiting 3, response 1.
    jobs, _, _ = run([Job(1, 0, 5), Job(2, 1, 3)], [1], "rr", quantum=2)
    assert (jobs[1].completion, jobs[1].waiting, jobs[1].response) == (8, 3, 0)
    assert (jobs[2].completion, jobs[2].waiting, jobs[2].response) == (7, 3, 1)


# ---------------------------------------------------------------------------
# Multiprocessor: one server with 2 cores, FCFS
# ---------------------------------------------------------------------------
def test_two_cores_fcfs():
    # Core 0: J1 0-4. Core 1: J2 0-2, then J3 2-5.
    # Waits: J1 0, J2 0, J3 2.
    jobs, _, makespan = run([Job(1, 0, 4), Job(2, 0, 2), Job(3, 0, 3)], [2], "fcfs")
    assert [jobs[i].waiting for i in (1, 2, 3)] == [0, 0, 2]
    assert makespan == 5


# ---------------------------------------------------------------------------
# Dispatch policies: two 1-core servers
# ---------------------------------------------------------------------------
def test_round_robin_dispatch_alternates():
    # Four jobs at time 0 go to servers 0, 1, 0, 1 in turn.
    jobs, _, _ = run([Job(i, 0, 2) for i in range(1, 5)], [1, 1], "fcfs", "rr")
    assert [jobs[i].server_id for i in (1, 2, 3, 4)] == [0, 1, 0, 1]


def test_least_loaded_dispatch():
    # J1 (burst 10): both servers empty, tie goes to server 0.
    # J2 (burst 1): server 0 has 10 ticks of work, server 1 has 0, so server 1.
    # J3 (burst 1): server 0 has 10, server 1 has 1, so server 1 again.
    # Round-robin dispatch would have put J3 behind the long job on server 0.
    jobs, _, _ = run([Job(1, 0, 10), Job(2, 0, 1), Job(3, 0, 1)], [1, 1], "fcfs", "least")
    assert [jobs[i].server_id for i in (1, 2, 3)] == [0, 1, 1]
    assert jobs[3].waiting == 1


# ---------------------------------------------------------------------------
# Sanity checks on random workloads
# ---------------------------------------------------------------------------
def test_same_seed_same_workload():
    a = random_workload(50, seed=7)
    b = random_workload(50, seed=7)
    assert [(j.arrival, j.burst) for j in a] == [(j.arrival, j.burst) for j in b]


def test_work_is_conserved():
    # Every CPU tick a job needs is done exactly once, under every policy.
    for local in ("fcfs", "sjf", "rr"):
        for dispatch in ("rr", "least"):
            jobs = random_workload(100, seed=3)
            need = sum(j.burst for j in jobs)
            _, servers, _ = simulate(jobs, [4, 2, 2], local, dispatch, 4)
            assert sum(s.busy_ticks for s in servers) == need
