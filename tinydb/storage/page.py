from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import TypeAlias

from tinydb.errors import StorageError


PAGE_SIZE = 4096
PageId: TypeAlias = int
_PAYLOAD_PREFIX_SIZE = 4


@dataclass(frozen=True)
class Page:
    page_id: PageId
    data: bytes

    def __post_init__(self) -> None:
        if self.page_id < 0:
            raise StorageError(f"invalid page id: {self.page_id}")
        if len(self.data) > PAGE_SIZE:
            raise StorageError("page data exceeds fixed page size")


def normalize_page_data(data: bytes) -> bytes:
    if len(data) > PAGE_SIZE:
        raise StorageError("page data exceeds fixed page size")
    return data.ljust(PAGE_SIZE, b"\0")


def pack_payload(payload: bytes) -> bytes:
    if len(payload) > PAGE_SIZE - _PAYLOAD_PREFIX_SIZE:
        raise StorageError("page payload exceeds fixed page size")
    return normalize_page_data(struct.pack(">I", len(payload)) + payload)


def unpack_payload(data: bytes) -> bytes:
    if len(data) < _PAYLOAD_PREFIX_SIZE:
        raise StorageError("page payload is truncated")
    payload_size = struct.unpack(">I", data[:_PAYLOAD_PREFIX_SIZE])[0]
    if payload_size > PAGE_SIZE - _PAYLOAD_PREFIX_SIZE:
        raise StorageError("page payload length is invalid")
    end = _PAYLOAD_PREFIX_SIZE + payload_size
    if len(data) < end:
        raise StorageError("page payload is truncated")
    return data[_PAYLOAD_PREFIX_SIZE:end]
