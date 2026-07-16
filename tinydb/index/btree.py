from __future__ import annotations

import json
from dataclasses import dataclass
from functools import cmp_to_key
from typing import Any, Literal

from tinydb.errors import StorageError
from tinydb.storage import RecordPointer, StorageManager
from tinydb.storage.page import pack_payload, unpack_payload


_INDEX_MARKER = "tinydb.btree.v1"
_Scalar = bool | int | float | str


@dataclass(frozen=True)
class _Entry:
    key: _Scalar
    pointer: RecordPointer
    sequence: int


@dataclass(frozen=True)
class _Node:
    keys: tuple[_Scalar, ...]
    entries: tuple[_Entry, ...] = ()
    children: tuple["_Node", ...] = ()

    @property
    def is_leaf(self) -> bool:
        return not self.children


@dataclass(frozen=True)
class IndexLookup:
    kind: Literal["equal", "range"]
    key: object | None = None
    start: object | None = None
    end: object | None = None
    include_start: bool = True
    include_end: bool = True

    @classmethod
    def equal(cls, key: object) -> "IndexLookup":
        return cls("equal", key=key)

    @classmethod
    def range(
        cls,
        start: object | None = None,
        end: object | None = None,
        include_start: bool = True,
        include_end: bool = True,
    ) -> "IndexLookup":
        return cls(
            "range",
            start=start,
            end=end,
            include_start=include_start,
            include_end=include_end,
        )

    def matches(self, index: "BTreeIndex") -> tuple[RecordPointer, ...]:
        if self.kind == "equal":
            return index.equal(self.key)
        return index.range(
            self.start,
            self.end,
            include_start=self.include_start,
            include_end=self.include_end,
        )


class BTreeIndex:
    def __init__(self, storage: StorageManager, name: str, order: int = 4):
        if order < 3:
            raise ValueError("B-tree order must be at least 3")
        if not name:
            raise ValueError("index name must not be empty")

        self.storage = storage
        self.name = name
        self.order = order
        self._generation = 0
        self._next_sequence_value = 0
        self._root = _Node(())

        self._load()

    @property
    def height(self) -> int:
        def node_height(node: _Node) -> int:
            if node.is_leaf:
                return 1
            return 1 + node_height(node.children[0])

        return node_height(self._root)

    def insert(self, key: object, pointer: RecordPointer) -> None:
        entry = _Entry(_normalize_key(key), pointer, self._next_sequence())
        root, split = self._insert_into_node(self._root, entry)
        if split is None:
            self._root = root
        else:
            self._root = _make_internal((root, split))
        self._persist()

    def build(self, entries: object) -> None:
        built: list[_Entry] = []
        for key, pointer in entries:
            built.append(_Entry(_normalize_key(key), pointer, self._next_sequence()))
        self._root = _bulk_load_entries(tuple(sorted(built, key=cmp_to_key(_compare_entries))), self.order)
        self._persist()

    def delete(self, key: object, pointer: RecordPointer | None = None) -> None:
        scalar = _normalize_key(key)
        root, removed = self._delete_from_node(self._root, scalar, pointer)
        if not removed:
            return
        self._root = _bulk_load_entries(_walk(root), self.order)
        self._persist()

    def equal(self, key: object) -> tuple[RecordPointer, ...]:
        scalar = _normalize_key(key)
        return tuple(entry.pointer for entry in _walk(self._root) if _compare_keys(entry.key, scalar) == 0)

    def range(
        self,
        start: object | None = None,
        end: object | None = None,
        include_start: bool = True,
        include_end: bool = True,
    ) -> tuple[RecordPointer, ...]:
        return tuple(
            entry.pointer
            for entry in _walk(self._root)
            if _in_range(entry.key, start, end, include_start, include_end)
        )

    def traverse(self) -> tuple[tuple[object, RecordPointer], ...]:
        return tuple((entry.key, entry.pointer) for entry in _walk(self._root))

    def _insert_into_node(self, node: _Node, entry: _Entry) -> tuple[_Node, _Node | None]:
        if node.is_leaf:
            entries = list(node.entries)
            entries.insert(_entry_insert_position(entries, entry), entry)
            leaf = _make_leaf(tuple(entries))
            if len(leaf.entries) <= _max_leaf_entries(self.order):
                return leaf, None
            return _split_leaf(leaf)

        children = list(node.children)
        child_index = _child_index_for_key(node.keys, entry.key)
        child, split = self._insert_into_node(children[child_index], entry)
        children[child_index] = child
        if split is not None:
            children.insert(child_index + 1, split)

        internal = _make_internal(tuple(children))
        if len(internal.children) <= self.order:
            return internal, None
        return _split_internal(internal)

    def _delete_from_node(
        self,
        node: _Node,
        key: _Scalar,
        pointer: RecordPointer | None,
    ) -> tuple[_Node, bool]:
        if node.is_leaf:
            remaining: list[_Entry] = []
            removed = False
            for entry in node.entries:
                key_matches = _compare_keys(entry.key, key) == 0
                pointer_matches = pointer is None or entry.pointer == pointer
                if key_matches and pointer_matches:
                    removed = True
                    continue
                remaining.append(entry)
            return _make_leaf(tuple(remaining)), removed

        removed = False
        children: list[_Node] = []
        for child in node.children:
            new_child, child_removed = self._delete_from_node(child, key, pointer)
            removed = removed or child_removed
            if not _is_empty_node(new_child):
                children.append(new_child)
        if not children:
            return _Node(()), removed
        if len(children) == 1:
            return children[0], removed
        return _make_internal(tuple(children)), removed

    def _load(self) -> None:
        latest: dict[str, Any] | None = None
        for page_id in range(self.storage.page_count()):
            try:
                raw_payload = unpack_payload(self.storage.read_page(page_id).data)
                payload = json.loads(raw_payload.decode("utf-8"))
            except (StorageError, UnicodeDecodeError, json.JSONDecodeError):
                continue
            if (
                isinstance(payload, dict)
                and payload.get("kind") == _INDEX_MARKER
                and payload.get("name") == self.name
                and int(payload.get("generation", 0)) >= self._generation
            ):
                latest = payload
                self._generation = int(payload.get("generation", 0))

        if latest is None:
            return

        self.order = int(latest.get("order", self.order))
        if "root" in latest:
            self._root = _deserialize_node(latest["root"])
        else:
            legacy_entries = tuple(_deserialize_entry(raw) for raw in latest.get("entries", []))
            self._root = _bulk_load_entries(
                tuple(sorted(legacy_entries, key=cmp_to_key(_compare_entries))),
                self.order,
            )
        entries = _walk(self._root)
        persisted_next = latest.get("next_sequence")
        if persisted_next is None:
            self._next_sequence_value = (max((entry.sequence for entry in entries), default=-1) + 1)
        else:
            self._next_sequence_value = int(persisted_next)

    def _persist(self) -> None:
        self._generation += 1
        payload = {
            "kind": _INDEX_MARKER,
            "name": self.name,
            "order": self.order,
            "generation": self._generation,
            "next_sequence": self._next_sequence_value,
            "root": _serialize_node(self._root),
        }
        raw_payload = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        self.storage.allocate_page(pack_payload(raw_payload))

    def _next_sequence(self) -> int:
        sequence = self._next_sequence_value
        self._next_sequence_value += 1
        return sequence


def assert_btree_invariants(index: BTreeIndex) -> None:
    if not isinstance(index, BTreeIndex):
        raise AssertionError("expected BTreeIndex")
    if index.order < 3:
        raise AssertionError("B-tree order must be at least 3")

    entries = _walk(index._root)
    for previous, current in zip(entries, entries[1:]):
        if _compare_entries(previous, current) > 0:
            raise AssertionError("B-tree entries are not sorted")

    leaf_depths: set[int] = set()
    _assert_node(index._root, index.order, None, None, 1, leaf_depths, is_root=True)
    if len(leaf_depths) != 1:
        raise AssertionError("B-tree leaves are not balanced")


def _assert_node(
    node: _Node,
    order: int,
    lower: _Scalar | None,
    upper: _Scalar | None,
    depth: int,
    leaf_depths: set[int],
    *,
    is_root: bool,
) -> None:
    if tuple(sorted(node.keys, key=cmp_to_key(_compare_keys))) != node.keys:
        raise AssertionError("B-tree node keys are not sorted")

    if node.is_leaf:
        leaf_depths.add(depth)
        if len(node.entries) > _max_leaf_entries(order):
            raise AssertionError("leaf node has too many entries")
        if not is_root and len(node.entries) < _min_leaf_entries(order):
            raise AssertionError("leaf node has too few entries")
        if tuple(entry.key for entry in node.entries) != node.keys:
            raise AssertionError("leaf keys do not match leaf entries")
        for previous, current in zip(node.entries, node.entries[1:]):
            if _compare_entries(previous, current) > 0:
                raise AssertionError("leaf entries are not sorted")
        for entry in node.entries:
            if lower is not None and _compare_keys(entry.key, lower) < 0:
                raise AssertionError("leaf entry violates lower bound")
            if upper is not None and _compare_keys(entry.key, upper) > 0:
                raise AssertionError("leaf entry violates upper bound")
        return

    if node.entries:
        raise AssertionError("internal node must not contain leaf entries")
    if len(node.children) != len(node.keys) + 1:
        raise AssertionError("internal node child count is invalid")
    if len(node.children) > order:
        raise AssertionError("internal node has too many children")
    if not is_root and len(node.children) < _min_children(order):
        raise AssertionError("internal node has too few children")
    if is_root and len(node.children) < 2:
        raise AssertionError("root internal node must have at least two children")
    if node.keys != _separator_keys(node.children):
        raise AssertionError("internal separators do not match child maximums")

    for position, child in enumerate(node.children):
        child_lower = lower if position == 0 else node.keys[position - 1]
        child_upper = upper if position == len(node.children) - 1 else node.keys[position]
        _assert_node(
            child,
            order,
            child_lower,
            child_upper,
            depth + 1,
            leaf_depths,
            is_root=False,
        )


def _make_leaf(entries: tuple[_Entry, ...]) -> _Node:
    return _Node(tuple(entry.key for entry in entries), entries=entries)


def _make_internal(children: tuple[_Node, ...]) -> _Node:
    return _Node(_separator_keys(children), children=children)


def _separator_keys(children: tuple[_Node, ...]) -> tuple[_Scalar, ...]:
    return tuple(_max_key(child) for child in children[:-1])


def _split_leaf(node: _Node) -> tuple[_Node, _Node]:
    split_at = len(node.entries) // 2
    return _make_leaf(node.entries[:split_at]), _make_leaf(node.entries[split_at:])


def _split_internal(node: _Node) -> tuple[_Node, _Node]:
    split_at = len(node.children) // 2
    return _make_internal(node.children[:split_at]), _make_internal(node.children[split_at:])


def _bulk_load_entries(entries: tuple[_Entry, ...], order: int) -> _Node:
    if not entries:
        return _Node(())

    level = [
        _make_leaf(entries[offset : offset + size])
        for offset, size in _sized_offsets(
            _balanced_sizes(len(entries), _max_leaf_entries(order), _min_leaf_entries(order))
        )
    ]
    while len(level) > 1:
        level = [
            _make_internal(tuple(level[offset : offset + size]))
            for offset, size in _sized_offsets(
                _balanced_sizes(len(level), order, _min_children(order))
            )
        ]
    return level[0]


def _balanced_sizes(total: int, max_size: int, min_size: int) -> tuple[int, ...]:
    if total <= max_size:
        return (total,)

    count = (total + max_size - 1) // max_size
    while count > 1 and total // count < min_size:
        count -= 1

    base = total // count
    remainder = total % count
    return tuple(base + (1 if position < remainder else 0) for position in range(count))


def _sized_offsets(sizes: tuple[int, ...]) -> tuple[tuple[int, int], ...]:
    offsets: list[tuple[int, int]] = []
    offset = 0
    for size in sizes:
        offsets.append((offset, size))
        offset += size
    return tuple(offsets)


def _entry_insert_position(entries: list[_Entry], entry: _Entry) -> int:
    position = 0
    while position < len(entries) and _compare_entries(entries[position], entry) <= 0:
        position += 1
    return position


def _child_index_for_key(keys: tuple[_Scalar, ...], key: _Scalar) -> int:
    position = 0
    while position < len(keys) and _compare_keys(key, keys[position]) >= 0:
        position += 1
    return position


def _is_empty_node(node: _Node) -> bool:
    return not node.entries and not node.children


def _max_leaf_entries(order: int) -> int:
    return order - 1


def _min_leaf_entries(order: int) -> int:
    return max(1, _min_children(order) - 1)


def _min_children(order: int) -> int:
    return (order + 1) // 2


def _walk(node: _Node) -> tuple[_Entry, ...]:
    if node.is_leaf:
        return node.entries
    entries: list[_Entry] = []
    for child in node.children:
        entries.extend(_walk(child))
    return tuple(entries)


def _max_key(node: _Node) -> _Scalar:
    if node.is_leaf:
        return node.entries[-1].key
    return _max_key(node.children[-1])


def _in_range(
    key: _Scalar,
    start: object | None,
    end: object | None,
    include_start: bool,
    include_end: bool,
) -> bool:
    if start is not None:
        lower = _compare_keys(key, _normalize_key(start))
        if lower < 0 or (lower == 0 and not include_start):
            return False
    if end is not None:
        upper = _compare_keys(key, _normalize_key(end))
        if upper > 0 or (upper == 0 and not include_end):
            return False
    return True


def _normalize_key(key: object) -> _Scalar:
    if isinstance(key, bool):
        return key
    if isinstance(key, (int, float, str)):
        return key
    raise TypeError(f"unsupported B-tree key type: {type(key).__name__}")


def _compare_entries(left: _Entry, right: _Entry) -> int:
    key_order = _compare_keys(left.key, right.key)
    if key_order != 0:
        return key_order
    return (left.sequence > right.sequence) - (left.sequence < right.sequence)


def _compare_keys(left: _Scalar, right: _Scalar) -> int:
    return (left > right) - (left < right)


def _serialize_entry(entry: _Entry) -> dict[str, Any]:
    return {
        "key": _serialize_key(entry.key),
        "pointer": {
            "table": entry.pointer.table,
            "page_id": entry.pointer.page_id,
            "slot": entry.pointer.slot,
        },
        "sequence": entry.sequence,
    }


def _serialize_node(node: _Node) -> dict[str, Any]:
    return {
        "keys": [_serialize_key(key) for key in node.keys],
        "entries": [_serialize_entry(entry) for entry in node.entries],
        "children": [_serialize_node(child) for child in node.children],
    }


def _deserialize_node(raw: dict[str, Any]) -> _Node:
    return _Node(
        tuple(_deserialize_key(key) for key in raw.get("keys", [])),
        entries=tuple(_deserialize_entry(entry) for entry in raw.get("entries", [])),
        children=tuple(_deserialize_node(child) for child in raw.get("children", [])),
    )


def _deserialize_entry(raw: dict[str, Any]) -> _Entry:
    pointer = raw["pointer"]
    return _Entry(
        _deserialize_key(raw["key"]),
        RecordPointer(str(pointer["table"]), int(pointer["page_id"]), int(pointer.get("slot", 0))),
        int(raw["sequence"]),
    )


def _serialize_key(key: _Scalar) -> list[object]:
    if isinstance(key, bool):
        return ["bool", key]
    if isinstance(key, int):
        return ["int", key]
    if isinstance(key, float):
        return ["float", key]
    return ["str", key]


def _deserialize_key(raw: list[object]) -> _Scalar:
    kind, value = raw
    if kind == "bool":
        return bool(value)
    if kind == "int":
        return int(value)
    if kind == "float":
        return float(value)
    if kind == "str":
        return str(value)
    raise StorageError(f"unsupported B-tree key encoding: {kind}")
