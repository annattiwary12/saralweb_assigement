"""
Persistent Priority Queue
==========================

Implements a double-ended priority queue (supports extract_min AND
extract_max efficiently) backed by a Min-Max Heap, with state persisted
to a JSON file on disk so it survives process restarts.

Why a Min-Max Heap?
--------------------
A regular binary heap only gives you fast access to ONE end (either the
min or the max). Since this assignment needs both extract_min and
extract_max, the two common options are:
  1. Maintain two separate heaps (a min-heap and a max-heap) in sync -
     doubles memory and bookkeeping, and cross-referencing entries
     between them for update/delete is fiddly.
  2. Use a single Min-Max Heap (Atkinson, Sack, Santoro, Strong, 1986) -
     one array, alternating "min levels" and "max levels":
        - Level 0 (root), level 2, level 4, ... are MIN levels:
          every node's value <= all its descendants.
        - Level 1, level 3, ... are MAX levels:
          every node's value >= all its descendants.
     This gives O(1) peek_min, O(1) peek_max, and O(log n)
     insert / extract_min / extract_max.

On top of the heap array, an `id -> index` hash map is maintained so
arbitrary elements can be found in O(1) and then update()'d or delete()'d
in O(log n), instead of the O(n) linear scan a plain heap would need.

Real-world use cases for priority queues:
  - OS task/process scheduling (run the highest-priority job next)
  - Dijkstra's / A* shortest path algorithms (always expand the
    lowest-cost frontier node next)
  - Event-driven simulations (process the next event in time order)
  - Bandwidth/QoS management in networking (serve highest-priority
    packets first)
  - Load balancers picking the least-loaded server (extract_min on load)
  - Hospital ER triage systems (most critical patient served first -
    conceptually an extract_max on severity)

This particular assignment needing BOTH extract_min and extract_max is a
natural fit for something like a job scheduler that must occasionally
also evict/serve the LOWEST priority item (e.g. to make room, or to
expire stale low-priority work) while normally serving the highest
priority item first.
"""

import json
import os
import threading


class PersistentPriorityQueue:
    """A persistent double-ended priority queue (Min-Max Heap)."""

    def __init__(self, filepath="pq_data.json"):
        self.filepath = filepath
        self._lock = threading.Lock()
        self.heap = []          # list of [priority, id, value]
        self.index_of = {}      # id -> current index in self.heap
        self._load()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self):
        if os.path.exists(self.filepath):
            with open(self.filepath, "r") as f:
                data = json.load(f)
            self.heap = data.get("heap", [])
            self.index_of = {item[1]: i for i, item in enumerate(self.heap)}
        else:
            self.heap = []
            self.index_of = {}

    def _save(self):
        tmp_path = self.filepath + ".tmp"
        with open(tmp_path, "w") as f:
            json.dump({"heap": self.heap}, f)
        os.replace(tmp_path, self.filepath)  # atomic on POSIX filesystems

    # ------------------------------------------------------------------
    # Low-level heap helpers
    # ------------------------------------------------------------------

    def _swap(self, i, j):
        self.heap[i], self.heap[j] = self.heap[j], self.heap[i]
        self.index_of[self.heap[i][1]] = i
        self.index_of[self.heap[j][1]] = j

    @staticmethod
    def _level(i):
        level = 0
        while (1 << (level + 1)) - 1 <= i:
            level += 1
        return level

    @classmethod
    def _is_min_level(cls, i):
        return cls._level(i) % 2 == 0

    def _parent(self, i):
        return (i - 1) // 2 if i > 0 else None

    def _grandparent(self, i):
        p = self._parent(i)
        return self._parent(p) if p is not None else None

    def _children(self, i):
        n = len(self.heap)
        return [c for c in (2 * i + 1, 2 * i + 2) if c < n]

    def _grandchildren(self, i):
        n = len(self.heap)
        return [c for c in (4 * i + 3, 4 * i + 4, 4 * i + 5, 4 * i + 6) if c < n]

    def _is_grandchild(self, i, m):
        return m in (4 * i + 3, 4 * i + 4, 4 * i + 5, 4 * i + 6)

    # ------------------------------------------------------------------
    # Bubble up (used after insert, and after in-place value increase)
    # ------------------------------------------------------------------

    def _bubble_up(self, i):
        if self._is_min_level(i):
            p = self._parent(i)
            if p is not None and self.heap[i][0] > self.heap[p][0]:
                self._swap(i, p)
                self._bubble_up_max(p)
            else:
                self._bubble_up_min(i)
        else:
            p = self._parent(i)
            if p is not None and self.heap[i][0] < self.heap[p][0]:
                self._swap(i, p)
                self._bubble_up_min(p)
            else:
                self._bubble_up_max(i)

    def _bubble_up_min(self, i):
        gp = self._grandparent(i)
        while gp is not None and self.heap[i][0] < self.heap[gp][0]:
            self._swap(i, gp)
            i = gp
            gp = self._grandparent(i)

    def _bubble_up_max(self, i):
        gp = self._grandparent(i)
        while gp is not None and self.heap[i][0] > self.heap[gp][0]:
            self._swap(i, gp)
            i = gp
            gp = self._grandparent(i)

    # ------------------------------------------------------------------
    # Trickle down (used after extract, and after in-place value decrease)
    # ------------------------------------------------------------------

    def _trickle_down(self, i):
        if self._is_min_level(i):
            self._trickle_down_min(i)
        else:
            self._trickle_down_max(i)

    def _trickle_down_min(self, i):
        while True:
            candidates = self._children(i) + self._grandchildren(i)
            if not candidates:
                break
            m = min(candidates, key=lambda c: self.heap[c][0])
            if self.heap[m][0] >= self.heap[i][0]:
                break
            self._swap(i, m)
            if self._is_grandchild(i, m):
                p = self._parent(m)
                if self.heap[m][0] > self.heap[p][0]:
                    self._swap(m, p)
                i = m
            else:
                break

    def _trickle_down_max(self, i):
        while True:
            candidates = self._children(i) + self._grandchildren(i)
            if not candidates:
                break
            m = max(candidates, key=lambda c: self.heap[c][0])
            if self.heap[m][0] <= self.heap[i][0]:
                break
            self._swap(i, m)
            if self._is_grandchild(i, m):
                p = self._parent(m)
                if self.heap[m][0] < self.heap[p][0]:
                    self._swap(m, p)
                i = m
            else:
                break

    def _fix_at(self, i):
        # After an in-place priority change, or after a tail element is
        # swapped into position i (during delete), node i may violate the
        # heap property in either direction. Try both directions; only
        # one can ever actually move anything.
        self._trickle_down(i)
        self._bubble_up(i)

    # ------------------------------------------------------------------
    # Public API (matches the assignment spec)
    # ------------------------------------------------------------------

    def is_empty(self):
        return len(self.heap) == 0

    def insert(self, item_id, priority, value=None):
        """Insert a new item. item_id must be unique."""
        with self._lock:
            if item_id in self.index_of:
                raise KeyError(f"id '{item_id}' already exists; use update() instead")
            self.heap.append([priority, item_id, value])
            i = len(self.heap) - 1
            self.index_of[item_id] = i
            self._bubble_up(i)
            self._save()

    def peek_min(self):
        if self.is_empty():
            return None
        p, i, v = self.heap[0]
        return {"id": i, "priority": p, "value": v}

    def _max_index(self):
        n = len(self.heap)
        if n == 1:
            return 0
        if n == 2:
            return 1
        return 1 if self.heap[1][0] >= self.heap[2][0] else 2

    def peek_max(self):
        if self.is_empty():
            return None
        idx = self._max_index()
        p, i, v = self.heap[idx]
        return {"id": i, "priority": p, "value": v}

    def peek(self, mode="min"):
        """mode: 'min' (default) or 'max'."""
        return self.peek_min() if mode == "min" else self.peek_max()

    def _extract_at(self, idx):
        last = len(self.heap) - 1
        item = self.heap[idx]
        del self.index_of[item[1]]
        if idx == last:
            self.heap.pop()
        else:
            self.heap[idx] = self.heap[last]
            self.heap.pop()
            self.index_of[self.heap[idx][1]] = idx
            if self.heap:
                self._fix_at(idx)
        self._save()
        return {"id": item[1], "priority": item[0], "value": item[2]}

    def extract_min(self):
        with self._lock:
            if self.is_empty():
                return None
            return self._extract_at(0)

    def extract_max(self):
        with self._lock:
            if self.is_empty():
                return None
            return self._extract_at(self._max_index())

    def update(self, item_id, new_priority):
        """Change the priority of an existing item, id stays the same."""
        with self._lock:
            if item_id not in self.index_of:
                raise KeyError(f"id '{item_id}' not found")
            i = self.index_of[item_id]
            self.heap[i][0] = new_priority
            self._fix_at(i)
            self._save()

    def delete(self, item_id):
        """Remove an arbitrary item by id (not necessarily min or max)."""
        with self._lock:
            if item_id not in self.index_of:
                raise KeyError(f"id '{item_id}' not found")
            idx = self.index_of[item_id]
            return self._extract_at(idx)


# ---------------------------------------------------------------------------
# Module-level convenience wrappers around one default persistent instance,
# so the required operations are also directly callable as:
#   import module
#   module.insert("job1", 5)
# ---------------------------------------------------------------------------

_default_queue = None


def _get_default():
    global _default_queue
    if _default_queue is None:
        _default_queue = PersistentPriorityQueue("pq_data.json")
    return _default_queue


def insert(item_id, priority, value=None):
    return _get_default().insert(item_id, priority, value)


def extract_min():
    return _get_default().extract_min()


def extract_max():
    return _get_default().extract_max()


def peek(mode="min"):
    return _get_default().peek(mode)


def update(item_id, new_priority):
    return _get_default().update(item_id, new_priority)


def delete(item_id):
    return _get_default().delete(item_id)


def is_empty():
    return _get_default().is_empty()


if __name__ == "__main__":
    # Small demo when run directly: `python module.py`
    demo = PersistentPriorityQueue("pq_demo.json")
    print("is_empty:", demo.is_empty())
    for _id, prio in [("t1", 5), ("t2", 1), ("t3", 9), ("t4", 3), ("t5", 7)]:
        demo.insert(_id, prio)
    print("min:", demo.peek_min(), "  max:", demo.peek_max())
    demo.update("t3", 0)
    print("after update t3 -> priority 0, min is now:", demo.peek_min())
    demo.delete("t2")
    print("after delete t2, is_empty:", demo.is_empty())
    print("extract_min:", demo.extract_min())
    print("extract_max:", demo.extract_max())
    print("is_empty:", demo.is_empty())
