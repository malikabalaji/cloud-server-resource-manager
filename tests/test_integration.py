"""
Integration tests: all managers running together through cloud.run_cloud.
These check the behaviour promised in the paper's system model.
Run with:  python -m pytest -v
"""

from job import Job
from workload import random_workload
from scheduler import simulate
from memory import MemoryManager
from vm_manager import VMManager
from disk import Disk
from cloud import Config, run_cloud


def managers(capacity=(100,), replace="fifo", frames=2, fit="first", disk="fcfs"):
    return MemoryManager(replace, frames), VMManager(list(capacity), fit), Disk(disk)


def test_loop_waits_for_late_arrivals():
    # J1 runs 0-5, nothing happens 5-10, J2 arrives at 10. The loop must not stop at 5.
    mem, vms, disk = managers()
    jobs = [Job(1, 0, 5, vm_size=10, pages=[1] * 5), Job(2, 10, 2, vm_size=10, pages=[1, 2])]
    finished, _, makespan = simulate(jobs, [1], "fcfs", "rr", 4, mem, vms, disk)
    assert len(finished) == 2 and makespan == 12


def test_loop_drains_disk_queue():
    # One job issues 3 disk requests in its only 3 ticks; the disk serves one per tick,
    # so every request is served before the loop ends.
    mem, vms, disk = managers()
    job = Job(1, 0, 3, vm_size=10, pages=[1, 1, 1], disk_requests={0: 10, 1: 20, 2: 30})
    simulate([job], [1], "fcfs", "rr", 4, mem, vms, disk)
    assert disk.served == 3 and not disk.pending()


def test_vm_that_does_not_fit_is_rejected():
    mem, vms, disk = managers(capacity=(100,))
    jobs = [Job(1, 0, 3, vm_size=80, pages=[1] * 3), Job(2, 0, 3, vm_size=40, pages=[1] * 3)]
    finished, _, _ = simulate(jobs, [1], "fcfs", "rr", 4, mem, vms, disk)
    assert [j.job_id for j in finished] == [1]
    assert jobs[1].rejected and vms.success_rate() == 0.5


def test_memory_is_freed_when_jobs_finish():
    # The second job arrives after the first finishes, so it fits in the freed memory.
    mem, vms, disk = managers(capacity=(100,))
    jobs = [Job(1, 0, 2, vm_size=100, pages=[1, 1]), Job(2, 5, 2, vm_size=100, pages=[1, 1])]
    finished, _, _ = simulate(jobs, [1], "fcfs", "rr", 4, mem, vms, disk)
    assert len(finished) == 2 and vms.pools[0].holes == [(0, 100)]


def test_faults_and_disk_do_not_change_cpu_times():
    # Non-blocking model: CPU results are identical whatever the paging or disk policy.
    jobs = random_workload(100, seed=5)
    base = run_cloud(jobs, Config(replace="fifo", frames=3, disk="fcfs"))[0]
    other = run_cloud(jobs, Config(replace="opt", frames=8, disk="sstf"))[0]
    for key in ("jobs", "avg_waiting", "avg_turnaround", "avg_response", "makespan"):
        assert base[key] == other[key]


def test_same_seed_same_results():
    a = run_cloud(random_workload(80, seed=9), Config(fit="best", disk="look"))[0]
    b = run_cloud(random_workload(80, seed=9), Config(fit="best", disk="look"))[0]
    assert a == b


def test_every_job_is_either_finished_or_rejected():
    jobs = random_workload(150, seed=2)
    summary, _, mgr = run_cloud(jobs, Config())
    assert summary["jobs"] + summary["rejected"] == 150
    assert summary["vm_requests"] == 150
