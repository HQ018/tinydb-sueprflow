from __future__ import annotations

from dataclasses import replace

import pytest

import tinydb.index.btree as btree_module
from tinydb.index import BTreeIndex, IndexLookup, assert_btree_invariants
from tinydb.storage import RecordPointer, StorageManager


def pointer(page_id: int, table: str = "users") -> RecordPointer:
    return RecordPointer(table, page_id, 0)


def test_unsorted_inserts_traverse_in_key_order(tmp_path):
    storage = StorageManager(tmp_path / "index.db")
    index = BTreeIndex(storage, "users_id", order=4)

    for key in (5, 1, 3, 2, 4):
        index.insert(key, pointer(key))

    assert index.traverse() == tuple((key, pointer(key)) for key in (1, 2, 3, 4, 5))
    assert_btree_invariants(index)

    storage.close()


def test_equality_lookup_returns_matching_pointers_only(tmp_path):
    storage = StorageManager(tmp_path / "index.db")
    index = BTreeIndex(storage, "users_id", order=4)

    index.insert(2, pointer(20))
    index.insert(1, pointer(10))
    index.insert(3, pointer(30))

    assert index.equal(2) == (pointer(20),)
    assert index.equal(99) == ()
    assert IndexLookup.equal(2).matches(index) == (pointer(20),)

    storage.close()


def test_range_lookup_supports_inclusive_and_exclusive_bounds(tmp_path):
    storage = StorageManager(tmp_path / "index.db")
    index = BTreeIndex(storage, "users_id", order=4)

    for key in range(1, 7):
        index.insert(key, pointer(key))

    assert index.range(2, 5) == tuple(pointer(key) for key in (2, 3, 4, 5))
    assert index.range(2, 5, include_start=False) == tuple(pointer(key) for key in (3, 4, 5))
    assert index.range(2, 5, include_end=False) == tuple(pointer(key) for key in (2, 3, 4))
    assert index.range(2, 5, include_start=False, include_end=False) == (
        pointer(3),
        pointer(4),
    )
    assert index.range(end=3) == tuple(pointer(key) for key in (1, 2, 3))
    assert index.range(start=4) == tuple(pointer(key) for key in (4, 5, 6))
    assert IndexLookup.range(2, 3).matches(index) == (pointer(2), pointer(3))

    storage.close()


def test_duplicate_keys_return_multiple_pointers_in_insertion_order(tmp_path):
    storage = StorageManager(tmp_path / "index.db")
    index = BTreeIndex(storage, "users_name", order=4)

    first = pointer(1)
    second = pointer(2)
    other = pointer(3)
    index.insert("Ada", first)
    index.insert("Grace", other)
    index.insert("Ada", second)

    assert index.equal("Ada") == (first, second)
    assert index.traverse() == (("Ada", first), ("Ada", second), ("Grace", other))
    assert_btree_invariants(index)

    storage.close()


def test_delete_removes_key_pointer_pairs_and_preserves_remaining_search(tmp_path):
    storage = StorageManager(tmp_path / "index.db")
    index = BTreeIndex(storage, "users_id", order=4)

    for key in range(1, 8):
        index.insert(key, pointer(key))
    duplicate = pointer(70)
    index.insert(7, duplicate)

    index.delete(4, pointer(4))
    index.delete(7, duplicate)

    assert index.equal(4) == ()
    assert index.equal(7) == (pointer(7),)
    assert index.traverse() == tuple((key, pointer(key)) for key in (1, 2, 3, 5, 6, 7))
    assert_btree_invariants(index)

    storage.close()


def test_many_inserts_force_multi_node_shape_and_preserve_invariants(tmp_path):
    storage = StorageManager(tmp_path / "index.db")
    index = BTreeIndex(storage, "users_id", order=4)
    keys = [17, 3, 25, 1, 9, 12, 30, 5, 7, 19, 21, 23, 2, 4, 6, 8, 10, 11, 13]

    for key in keys:
        index.insert(key, pointer(key))

    assert index.traverse() == tuple((key, pointer(key)) for key in sorted(keys))
    assert index.height >= 2
    assert_btree_invariants(index)

    storage.close()


def test_index_entries_survive_close_and_reopen_with_same_name(tmp_path):
    path = tmp_path / "index.db"
    storage = StorageManager(path)
    index = BTreeIndex(storage, "users_id", order=4)

    index.insert(3, pointer(30))
    index.insert(1, pointer(10))
    index.insert(2, pointer(20))
    storage.close()

    reopened = StorageManager(path)
    restored = BTreeIndex(reopened, "users_id", order=4)

    assert restored.traverse() == ((1, pointer(10)), (2, pointer(20)), (3, pointer(30)))
    assert restored.equal(2) == (pointer(20),)
    assert_btree_invariants(restored)

    reopened.close()


def test_tree_nodes_are_the_operational_source_of_truth(tmp_path):
    storage = StorageManager(tmp_path / "index.db")
    index = BTreeIndex(storage, "users_id", order=4)

    for key in (4, 1, 3, 2, 5):
        index.insert(key, pointer(key))

    assert not hasattr(index, "_entries")
    assert index.traverse() == tuple((key, pointer(key)) for key in (1, 2, 3, 4, 5))
    assert index.equal(3) == (pointer(3),)
    assert_btree_invariants(index)

    storage.close()


def test_invariants_reject_child_moved_to_wrong_range(tmp_path):
    storage = StorageManager(tmp_path / "index.db")
    index = BTreeIndex(storage, "users_id", order=4)

    for key in range(1, 20):
        index.insert(key, pointer(key))

    root = index._root
    assert not root.is_leaf
    index._root = replace(
        root,
        children=(root.children[-1],) + root.children[1:-1] + (root.children[0],),
    )

    with pytest.raises(AssertionError):
        assert_btree_invariants(index)

    storage.close()


def test_invariants_reject_leaf_overflow_even_when_traversal_stays_sorted(tmp_path):
    storage = StorageManager(tmp_path / "index.db")
    index = BTreeIndex(storage, "users_id", order=4)

    for key in range(1, 10):
        index.insert(key, pointer(key))

    leaf = _leftmost_leaf(index._root)
    overflow_entries = leaf.entries + tuple(
        btree_module._Entry(
            leaf.entries[-1].key,
            pointer(200 + offset),
            leaf.entries[-1].sequence + offset + 1,
        )
        for offset in range(index.order - len(leaf.entries))
    )
    overflow_leaf = replace(
        leaf,
        keys=tuple(entry.key for entry in overflow_entries),
        entries=overflow_entries,
    )
    index._root = _replace_leftmost_leaf(index._root, overflow_leaf)

    with pytest.raises(AssertionError):
        assert_btree_invariants(index)

    storage.close()


def test_delete_underflow_compacts_tree_without_losing_remaining_entries(tmp_path):
    storage = StorageManager(tmp_path / "index.db")
    index = BTreeIndex(storage, "users_id", order=4)

    for key in range(1, 30):
        index.insert(key, pointer(key))
    for key in range(1, 24):
        index.delete(key, pointer(key))

    remaining = tuple(range(24, 30))
    assert index.traverse() == tuple((key, pointer(key)) for key in remaining)
    for key in remaining:
        assert index.equal(key) == (pointer(key),)
    assert index.range(25, 28) == tuple(pointer(key) for key in (25, 26, 27, 28))
    assert_btree_invariants(index)

    storage.close()


def test_reopened_index_restores_root_node_snapshot_not_legacy_entries(tmp_path):
    path = tmp_path / "index.db"
    storage = StorageManager(path)
    index = BTreeIndex(storage, "users_id", order=4)

    for key in range(20, 0, -1):
        index.insert(key, pointer(key))
    storage.close()

    reopened = StorageManager(path)
    restored = BTreeIndex(reopened, "users_id", order=4)

    assert not hasattr(restored, "_entries")
    assert not restored._root.is_leaf
    assert restored.traverse() == tuple((key, pointer(key)) for key in range(1, 21))
    assert restored.equal(10) == (pointer(10),)
    assert_btree_invariants(restored)

    reopened.close()


def _leftmost_leaf(node):
    if node.is_leaf:
        return node
    return _leftmost_leaf(node.children[0])


def _replace_leftmost_leaf(node, leaf):
    if node.is_leaf:
        return leaf
    children = (_replace_leftmost_leaf(node.children[0], leaf),) + node.children[1:]
    return replace(node, children=children)
