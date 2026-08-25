# Persistent Priority Queue — SDE Assignment

## Requirements
- Python 3.8+
- No external packages (standard library only: `json`, `os`, `threading`, `unittest`)

## Run the demo
```bash
python module.py
```
This runs a small end-to-end demo (insert, peek, update, delete, extract_min,
extract_max) and writes its state to `pq_demo.json` in the same folder.

## Run the tests
```bash
python test_module.py
```
Runs 10 tests, including a 2000-operation randomized stress test that
cross-checks every insert/extract_min/extract_max/update/delete/peek call
against a brute-force reference implementation.

## Usage
```python
from module import PersistentPriorityQueue

pq = PersistentPriorityQueue("pq_data.json")   # loads existing state if present

pq.insert("job1", priority=5)
pq.insert("job2", priority=1, value={"desc": "cleanup task"})

pq.peek_min()        # -> lowest priority item, without removing it
pq.peek_max()         # -> highest priority item, without removing it
pq.extract_min()      # -> removes and returns lowest priority item
pq.extract_max()      # -> removes and returns highest priority item
pq.update("job1", 10) # change job1's priority
pq.delete("job1")     # remove job1 outright, wherever it is in the queue
pq.is_empty()          # -> bool
```

State is written to the JSON file after every mutating call, so creating a
new `PersistentPriorityQueue` pointed at the same file — even in a fresh
process — picks up right where the previous one left off.

There's also a module-level API using a shared default instance, in case
the module is expected to expose the operations directly rather than
through a class:
```python
import module
module.insert("job1", 5)
module.extract_min()
```

## Implementation notes

The queue supports **both** `extract_min` and `extract_max` efficiently,
which a plain binary heap can't do on its own — a min-heap gives you fast
access to the smallest element but finding the largest means scanning all
the leaves, and vice versa for a max-heap.

Instead, this is a **Min-Max Heap** (Atkinson, Sack, Santoro & Strong,
1986): a single array where levels alternate roles —
- Level 0 (the root), level 2, level 4, ... are **min levels**: every
  node's value is ≤ all of its descendants.
- Level 1, level 3, ... are **max levels**: every node's value is ≥ all
  of its descendants.

That gives:
- `peek_min` / `peek_max`: O(1)
- `insert` / `extract_min` / `extract_max`: O(log n)

Insert uses a "bubble up" that checks the node against its **parent**
first to decide whether it belongs on the min side or max side of the
tree, then continues bubbling against **grandparents** (skipping a level,
since grandparents sit on the same level-type). Extraction and update
use a "trickle down" that compares a node against its children *and*
grandchildren to decide where it needs to sink to.

On top of the heap array, an `id -> array index` hash map is maintained
and kept in sync on every swap. That's what makes `update(id, ...)` and
`delete(id)` possible in O(log n) instead of an O(n) linear scan to find
the item first — arbitrary elements (not just the current min/max) can be
located in O(1) and then repaired in place.

Persistence is plain JSON, written atomically (write to a `.tmp` file,
then `os.replace` — atomic on POSIX filesystems) after every mutation, so
a crash mid-write can't corrupt the on-disk state.

### Real-world use cases for priority queues
- **OS scheduling** — always run the highest-priority ready process next.
- **Dijkstra's / A\* shortest path** — repeatedly expand the frontier
  node with the lowest tentative cost.
- **Event-driven simulation** — process the next event in timestamp
  order.
- **Network QoS** — serve highest-priority packets first, lowest-priority
  ones only when there's spare capacity.
- **Job/task queues with expiry** — normally serve the highest-priority
  job (`extract_max`), but also periodically evict the stale
  lowest-priority job to free up space (`extract_min`) — a natural fit
  for a queue that needs both ends, like this one.

