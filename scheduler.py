"""
scheduler.py
Multiprocessor scheduling for the cloud: two levels of decision.

Level 1, DISPATCH (which server gets a new job?)
    rr     : round-robin dispatch. Send jobs to servers in turn: 0, 1, 2, 0, 1, 2 ...
             Simple and fair in count, but blind to how busy each server is.
    least  : least-loaded dispatch. Send the job to the server with the least
             outstanding work per core. Smarter, but needs load information.

Level 2, LOCAL SCHEDULING (on a server, which waiting job gets a free core?)
    fcfs   : First Come First Served. Oldest job first. Non-preemptive.
    sjf    : Shortest Job First. Smallest CPU need first. Non-preemptive.
    rr     : Round Robin. Oldest job first, but a job may run only `quantum`
             ticks before it is sent to the back of the queue. Preemptive.

How time works: the simulation moves in whole ticks (t = 0, 1, 2, ...).
On each tick:
    1. Jobs arriving at this tick are dispatched to a server.
    2. Jobs whose Round Robin slice ended last tick rejoin the back of their
       queue (after new arrivals, a common textbook convention).
    3. Every free core picks a job using the local policy.
    4. Every busy core does one tick of work.
A tick-based design is easy to trace by hand, which matters for the viva.

Full cloud mode (Review 2): when memory, VM and disk managers are passed in,
    1a. an arriving job's VM must fit in the memory of the server it is sent
        to, otherwise the job is rejected and never runs;
    1b. an admitted job receives its own F page frames;
    4a. every tick of work also references the job's next page and may issue
        one disk log request (neither blocks the job);
    4b. a finished job frees its frames and its VM;
    5.  the shared disk serves one request per tick.
The loop stops only when no job is left to arrive, no admitted job is
unfinished and the disk queue is empty.
"""

from typing import List
from job import Job
from server import Server

LOCAL_POLICIES = ("fcfs", "sjf", "rr")
DISPATCH_POLICIES = ("rr", "least")


# ---------------------------------------------------------------------------
# Level 2: choosing a job from a server's ready queue
# ---------------------------------------------------------------------------
def pick_next(queue: List[Job], policy: str) -> Job:
    """Remove and return the job that should get the next free core."""
    if policy in ("fcfs", "rr"):
        # The queue is kept in arrival order, so the front is the oldest job.
        return queue.pop(0)
    if policy == "sjf":
        # Smallest remaining CPU need wins; ties go to the earlier arrival.
        best = min(queue, key=lambda j: (j.remaining, j.arrival, j.job_id))
        queue.remove(best)
        return best
    raise ValueError(f"Unknown local policy: {policy}")


# ---------------------------------------------------------------------------
# Level 1: choosing a server for an arriving job
# ---------------------------------------------------------------------------
class Dispatcher:
    def __init__(self, servers: List[Server], policy: str):
        if policy not in DISPATCH_POLICIES:
            raise ValueError(f"Unknown dispatch policy: {policy}")
        self.servers = servers
        self.policy = policy
        self.next_index = 0        # used by round-robin dispatch

    def choose(self) -> Server:
        if self.policy == "rr":
            server = self.servers[self.next_index % len(self.servers)]
            self.next_index += 1
            return server
        # least: lowest load per core; ties go to the lower server id.
        return min(self.servers, key=lambda s: (s.load_per_core(), s.server_id))


# ---------------------------------------------------------------------------
# One tick of work on one server
# ---------------------------------------------------------------------------
def step_server(server: Server, t: int, policy: str, quantum: int, requeue: List[Job],
                memory=None, vms=None, disk=None):
    """Advance one server by one tick.

    requeue holds jobs preempted at the end of the previous tick; they join
    the back of the queue now, after this tick's new arrivals.
    """
    server.ready_queue.extend(requeue)
    requeue.clear()

    # Fill every free core.
    for c in range(server.cores):
        if server.running[c] is None and server.ready_queue:
            job = pick_next(server.ready_queue, policy)
            if job.first_start is None:
                job.first_start = t           # first time on a core: response time is fixed
            job.quantum_used = 0
            server.running[c] = job

    # Do one tick of work on every busy core.
    for c in range(server.cores):
        job = server.running[c]
        if job is None:
            continue
        step = job.burst - job.remaining          # which CPU tick of this job is running
        if memory is not None:
            memory.reference(job)                 # touch the next page; a fault does not block
        if disk is not None and step in job.disk_requests:
            disk.enqueue(job.disk_requests[step], t)   # log request joins the shared disk queue
        job.remaining -= 1
        job.quantum_used += 1
        server.busy_ticks += 1
        server.timeline.append((c, t, job.job_id))
        if job.is_done():
            job.completion = t + 1            # work done during tick t ends at time t + 1
            server.finished.append(job)
            server.running[c] = None
            if memory is not None:
                memory.release(job)           # free the job's frames
            if vms is not None:
                vms.release(server.server_id, job)   # free the VM's memory block
        elif policy == "rr" and job.quantum_used >= quantum:
            requeue.append(job)               # slice used up: back of the queue next tick
            server.running[c] = None


# ---------------------------------------------------------------------------
# Full simulation
# ---------------------------------------------------------------------------
def simulate(jobs: List[Job], core_counts: List[int],
             local: str = "fcfs", dispatch: str = "rr", quantum: int = 4,
             memory=None, vms=None, disk=None):
    """Run the cloud and return (finished_jobs, servers, makespan).

    jobs        : list of Job objects (they are modified in place)
    core_counts : e.g. [4, 2, 2] means three servers with 4, 2 and 2 cores
    local       : fcfs | sjf | rr
    dispatch    : rr | least
    quantum     : Round Robin time slice in ticks
    memory, vms, disk : optional managers; pass all three for the full cloud,
                        or none of them for scheduling only (Review 1 mode)
    Rejected jobs are marked job.rejected = True and are not in finished_jobs.
    """
    if local not in LOCAL_POLICIES:
        raise ValueError(f"Unknown local policy: {local}")

    servers = [Server(i, c) for i, c in enumerate(core_counts)]
    dispatcher = Dispatcher(servers, dispatch)
    requeues = {s.server_id: [] for s in servers}

    pending = sorted(jobs, key=lambda j: (j.arrival, j.job_id))
    idx = 0
    t = 0
    total = len(pending)

    def work_left():
        # Continue while a job is still to arrive, an admitted job is unfinished,
        # a preempted job is waiting to rejoin a queue, or the disk has requests.
        return (idx < total
                or any(not s.is_idle() for s in servers)
                or any(requeues.values())
                or (disk is not None and disk.pending()))

    while work_left():
        # 1. Dispatch every job that arrives at this tick.
        while idx < total and pending[idx].arrival <= t:
            job = pending[idx]
            idx += 1
            server = dispatcher.choose()
            job.server_id = server.server_id
            if vms is not None and not vms.allocate(server.server_id, job):
                job.rejected = True               # no hole large enough on this server
                continue
            if memory is not None:
                memory.assign(job)                # the job's own F frames
            server.ready_queue.append(job)

        # 2 to 4. Each server does one tick.
        for server in servers:
            step_server(server, t, local, quantum, requeues[server.server_id], memory, vms, disk)

        # 5. The shared disk serves one request; fragmentation is sampled.
        if disk is not None:
            disk.serve_one()
        if vms is not None:
            vms.sample()
        t += 1

    finished = [j for s in servers for j in s.finished]
    makespan = max(j.completion for j in finished) if finished else 0
    return finished, servers, makespan
