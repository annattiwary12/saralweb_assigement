"""
Tests for module.py

Includes:
  - Basic operation tests (insert/extract_min/extract_max/peek/update/delete/is_empty)
  - Persistence test (data survives reload from a fresh instance)
  - A randomized stress test that cross-checks every operation against a
    plain brute-force reference implementation (a dict), to validate the
    min-max heap invariants hold under arbitrary sequences of ops.

Run with:  python test_module.py
"""

import os
import random
import unittest

from module import PersistentPriorityQueue


TEST_FILE = "test_pq_data.json"


class TestBasicOperations(unittest.TestCase):
    def setUp(self):
        if os.path.exists(TEST_FILE):
            os.remove(TEST_FILE)
        self.pq = PersistentPriorityQueue(TEST_FILE)

    def tearDown(self):
        if os.path.exists(TEST_FILE):
            os.remove(TEST_FILE)
        tmp = TEST_FILE + ".tmp"
        if os.path.exists(tmp):
            os.remove(tmp)

    def test_is_empty_initially(self):
        self.assertTrue(self.pq.is_empty())

    def test_insert_and_peek(self):
        self.pq.insert("a", 5)
        self.pq.insert("b", 1)
        self.pq.insert("c", 9)
        self.assertEqual(self.pq.peek_min()["id"], "b")
        self.assertEqual(self.pq.peek_max()["id"], "c")

    def test_extract_min_and_max(self):
        for _id, prio in [("a", 5), ("b", 1), ("c", 9), ("d", 3)]:
            self.pq.insert(_id, prio)
        self.assertEqual(self.pq.extract_min()["id"], "b")
        self.assertEqual(self.pq.extract_max()["id"], "c")
        self.assertFalse(self.pq.is_empty())

    def test_update_changes_position(self):
        for _id, prio in [("a", 5), ("b", 1), ("c", 9)]:
            self.pq.insert(_id, prio)
        self.pq.update("c", 0)  # was max, now should be min
        self.assertEqual(self.pq.peek_min()["id"], "c")

    def test_delete_arbitrary(self):
        for _id, prio in [("a", 5), ("b", 1), ("c", 9), ("d", 3)]:
            self.pq.insert(_id, prio)
        self.pq.delete("a")
        remaining_ids = {item[1] for item in self.pq.heap}
        self.assertEqual(remaining_ids, {"b", "c", "d"})

    def test_duplicate_insert_raises(self):
        self.pq.insert("a", 1)
        with self.assertRaises(KeyError):
            self.pq.insert("a", 2)

    def test_missing_update_delete_raise(self):
        with self.assertRaises(KeyError):
            self.pq.update("nope", 1)
        with self.assertRaises(KeyError):
            self.pq.delete("nope")

    def test_extract_from_empty_returns_none(self):
        self.assertIsNone(self.pq.extract_min())
        self.assertIsNone(self.pq.extract_max())
        self.assertIsNone(self.pq.peek())


class TestPersistence(unittest.TestCase):
    def setUp(self):
        if os.path.exists(TEST_FILE):
            os.remove(TEST_FILE)

    def tearDown(self):
        if os.path.exists(TEST_FILE):
            os.remove(TEST_FILE)
        tmp = TEST_FILE + ".tmp"
        if os.path.exists(tmp):
            os.remove(tmp)

    def test_state_survives_reload(self):
        pq1 = PersistentPriorityQueue(TEST_FILE)
        pq1.insert("x", 10, value="payload")
        pq1.insert("y", 2)

        # Simulate a process restart: brand new instance, same file.
        pq2 = PersistentPriorityQueue(TEST_FILE)
        self.assertFalse(pq2.is_empty())
        self.assertEqual(pq2.peek_min()["id"], "y")
        self.assertEqual(pq2.peek_max()["id"], "x")
        self.assertEqual(pq2.peek_max()["value"], "payload")


class TestRandomizedAgainstBruteForce(unittest.TestCase):
    """
    Cross-checks the heap against a brute-force dict-based reference over
    many random operations, to validate heap-order invariants hold under
    arbitrary insert/update/delete/extract sequences.
    """

    def setUp(self):
        if os.path.exists(TEST_FILE):
            os.remove(TEST_FILE)
        self.pq = PersistentPriorityQueue(TEST_FILE)
        self.reference = {}  # id -> priority
        self.next_id = 0

    def tearDown(self):
        if os.path.exists(TEST_FILE):
            os.remove(TEST_FILE)
        tmp = TEST_FILE + ".tmp"
        if os.path.exists(tmp):
            os.remove(tmp)

    def _new_id(self):
        self.next_id += 1
        return f"item{self.next_id}"

    def test_randomized_operations(self):
        random.seed(42)
        for _ in range(2000):
            op = random.choice(
                ["insert", "extract_min", "extract_max", "update", "delete", "peek"]
            )

            if op == "insert":
                _id = self._new_id()
                prio = random.randint(-100, 100)
                self.pq.insert(_id, prio)
                self.reference[_id] = prio

            elif op == "extract_min":
                result = self.pq.extract_min()
                if not self.reference:
                    self.assertIsNone(result)
                else:
                    expected_prio = min(self.reference.values())
                    self.assertEqual(result["priority"], expected_prio)
                    del self.reference[result["id"]]

            elif op == "extract_max":
                result = self.pq.extract_max()
                if not self.reference:
                    self.assertIsNone(result)
                else:
                    expected_prio = max(self.reference.values())
                    self.assertEqual(result["priority"], expected_prio)
                    del self.reference[result["id"]]

            elif op == "update" and self.reference:
                _id = random.choice(list(self.reference.keys()))
                new_prio = random.randint(-100, 100)
                self.pq.update(_id, new_prio)
                self.reference[_id] = new_prio

            elif op == "delete" and self.reference:
                _id = random.choice(list(self.reference.keys()))
                self.pq.delete(_id)
                del self.reference[_id]

            elif op == "peek":
                if not self.reference:
                    self.assertIsNone(self.pq.peek("min"))
                    self.assertIsNone(self.pq.peek("max"))
                else:
                    self.assertEqual(
                        self.pq.peek("min")["priority"], min(self.reference.values())
                    )
                    self.assertEqual(
                        self.pq.peek("max")["priority"], max(self.reference.values())
                    )

            # Size and emptiness must always agree with the reference.
            self.assertEqual(len(self.pq.heap), len(self.reference))
            self.assertEqual(self.pq.is_empty(), len(self.reference) == 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
