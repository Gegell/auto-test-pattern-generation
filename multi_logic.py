"""Implements various multi-valued logic values and their operations.

In detail it contains 3 valued logic (0, 1, X).
This is then also extended by 5 valued logic (0, 1, X, 1/0 = D, 0/1 = D') for 
fault simulation.
Likewise, 9 valued logic (0, 1, X, D, D', 1/X, 0/X, X/1, X/0) is implemented for
possible future use.
"""


from functools import cache
from typing import Iterator, TypeAlias, Union


def _iter_bit_positions(val: int) -> Iterator[int]:
    """Yields all the active bit positions in a value."""
    pos = 0
    while val != 0:
        if val & 1:
            yield pos
        val >>= 1
        pos += 1


@cache
def _generate_interleave_mask(vector_size: int):
    """Generates a mask for interleaving bits in a vector of the given size."""
    mask = 0
    for i in range(vector_size):
        mask |= 0b01 << (2 * i)
    return mask


class TriValue:
    """Implements 3-valued logic."""

    ON: "TriValue"
    OFF: "TriValue"
    UNKNOWN: "TriValue"

    value: int
    vector_size: int
    CompatibleType: TypeAlias = Union[None, bool, int, "TriValue"]

    def _decompose_bits(self, val: int) -> tuple[int, int]:
        """Decomposes an integer into its interleaved bits."""
        mask = self._interleave_mask()
        return val & mask, (val >> 1) & mask

    def _swap_bits(self, val: int) -> int:
        """Swaps the top and bottom bits of a tri-value vector."""
        bottom, top = self._decompose_bits(val)
        return (bottom << 1) | top

    def _interleave_mask(self):
        """Generates a mask for interleaving bits in a vector of the given size."""
        return _generate_interleave_mask(self.vector_size)

    def _full_mask(self):
        """Generates a mask for all bits in a vector of the given size."""
        return (1 << (2 * self.vector_size)) - 1

    def _check_valid_tri_value_vector(self, val: int) -> bool:
        """Checks that the given value is a valid tri-value vector. Raises ValueError if not.

        In this case a valid tri-value vector is one where no bit pair is 0b10."""
        if val.bit_length() > 2 * self.vector_size:
            raise ValueError(
                f"Invalid tri-value vector: {bin(val)}, too many bits for given vector size {self.vector_size}."
            )
        bottom, top = self._decompose_bits(val)
        check_mask = (~bottom) & top
        if check_mask != 0:
            positions = [bp // 2 for bp in _iter_bit_positions(check_mask)]
            raise ValueError(f"Invalid tri-value vector: {bin(val)}, bits {positions} are 0b10.")
        return (~bottom & top) == 0

    def __new__(cls, value: CompatibleType, vector_size: int = 1) -> "TriValue":
        if isinstance(value, cls):
            return value
        if value is None:
            return cls.UNKNOWN
        if isinstance(value, bool):
            return cls.ON if value else cls.OFF
        if isinstance(value, int):
            obj = super().__new__(cls)
            obj.vector_size = vector_size
            obj.value = value
            if not obj._check_valid_tri_value_vector(value):
                raise ValueError(f"Invalid tri-value vector: {value:b}")
            return obj
        raise TypeError(f"Cannot convert {type(value)} to TriValue")

    def __getitem__(self, index: int) -> "TriValue":
        return TriValue((self.value >> (2 * index)) & 0b11)

    def __repr__(self) -> str:
        return f"TriValue({self.value:b})"

    def __str__(self) -> str:
        return "".join("0X?1"[self[i].value] for i in range(self.vector_size))

    def __invert__(self) -> "TriValue":
        return TriValue(~self._swap_bits(self.value) & self._full_mask(), self.vector_size)

    def __and__(self, other: CompatibleType) -> "TriValue":
        other_tv = TriValue(other)
        # TODO: support combining vectors of different sizes, pad with "UNKNOWN"
        assert self.vector_size == other_tv.vector_size, "combining vectors of different sizes is not yet supported"
        return TriValue(self.value & other_tv.value)

    def __rand__(self, other: CompatibleType) -> "TriValue":
        return self & other

    def __or__(self, other: CompatibleType) -> "TriValue":
        other_tv = TriValue(other)
        assert self.vector_size == other_tv.vector_size, "combining vectors of different sizes is not yet supported"
        return TriValue(self.value | other_tv.value, self.vector_size)

    def __ror__(self, other: CompatibleType) -> "TriValue":
        return self | other

    def __xor__(self, other: CompatibleType) -> "TriValue":
        other_tv = TriValue(other)
        return ((~self) & other_tv) | (self & (~other_tv))

    def __rxor__(self, other: CompatibleType) -> "TriValue":
        return self ^ other

    def __eq__(self, other) -> bool:
        if other is None:
            return self.value == TriValue(None).value
        if not isinstance(other, (TriValue, int, bool)):
            return NotImplemented
        return self.value == TriValue(other).value

    def __hash__(self) -> int:
        return hash(self.value)


setattr(TriValue, "ON", TriValue(0b11))
setattr(TriValue, "OFF", TriValue(0b00))
setattr(TriValue, "UNKNOWN", TriValue(0b01))


class NineValue:
    """Implements 9-valued logic."""

    ON: "NineValue"
    OFF: "NineValue"
    UNKNOWN: "NineValue"
    ON_IS_OFF: "NineValue"
    OFF_IS_ON: "NineValue"
    ON_IS_UNKNOWN: "NineValue"
    OFF_IS_UNKNOWN: "NineValue"
    UNKNOWN_IS_ON: "NineValue"
    UNKNOWN_IS_OFF: "NineValue"

    def __init__(self, value: tuple[TriValue, TriValue]):
        self.value = value

    def __invert__(self) -> "NineValue":
        return NineValue((~self.value[0], ~self.value[1]))

    def __and__(self, other: "NineValue") -> "NineValue":
        return NineValue((self.value[0] & other.value[0], self.value[1] & other.value[1]))

    def __or__(self, other: "NineValue") -> "NineValue":
        return NineValue((self.value[0] | other.value[0], self.value[1] | other.value[1]))

    def __xor__(self, other: "NineValue") -> "NineValue":
        return NineValue((self.value[0] ^ other.value[0], self.value[1] ^ other.value[1]))

    def __repr__(self) -> str:
        return f"NineValue({self.value})"

    def __str__(self) -> str:
        return f"{self.value[0]}/{self.value[1]}"

    def __eq__(self, other) -> bool:
        if not isinstance(other, NineValue):
            return NotImplemented
        return self.value == other.value

    def __hash__(self) -> int:
        return hash(self.value)


setattr(NineValue, "ON", NineValue((TriValue.ON, TriValue.ON)))
setattr(NineValue, "OFF", NineValue((TriValue.OFF, TriValue.OFF)))
setattr(NineValue, "UNKNOWN", NineValue((TriValue.UNKNOWN, TriValue.UNKNOWN)))
setattr(NineValue, "ON_IS_OFF", NineValue((TriValue.ON, TriValue.OFF)))  # D = 1/0
setattr(NineValue, "OFF_IS_ON", NineValue((TriValue.OFF, TriValue.ON)))  # D' = 0/1
setattr(NineValue, "ON_IS_UNKNOWN", NineValue((TriValue.ON, TriValue.UNKNOWN)))  # 1/x
setattr(NineValue, "OFF_IS_UNKNOWN", NineValue((TriValue.OFF, TriValue.UNKNOWN)))  # 0/x
setattr(NineValue, "UNKNOWN_IS_ON", NineValue((TriValue.UNKNOWN, TriValue.ON)))  # x/1
setattr(NineValue, "UNKNOWN_IS_OFF", NineValue((TriValue.UNKNOWN, TriValue.OFF)))  # x/0


class FiveValue:
    """Implements 5-valued logic."""

    ON: "FiveValue"
    OFF: "FiveValue"
    UNKNOWN: "FiveValue"
    ON_IS_OFF: "FiveValue"
    OFF_IS_ON: "FiveValue"

    def _merge_unknowns(self, value: tuple[TriValue, TriValue]) -> tuple[TriValue, TriValue]:
        if value[0] == TriValue.UNKNOWN or value[1] == TriValue.UNKNOWN:
            return (TriValue.UNKNOWN, TriValue.UNKNOWN)
        return value

    def __init__(self, value: tuple[TriValue, TriValue]):
        self.value = self._merge_unknowns(value)

    def __invert__(self) -> "FiveValue":
        return FiveValue((~self.value[0], ~self.value[1]))

    def __and__(self, other: "FiveValue") -> "FiveValue":
        return FiveValue((self.value[0] & other.value[0], self.value[1] & other.value[1]))

    def __or__(self, other: "FiveValue") -> "FiveValue":
        return FiveValue((self.value[0] | other.value[0], self.value[1] | other.value[1]))

    def __xor__(self, other: "FiveValue") -> "FiveValue":
        return FiveValue((self.value[0] ^ other.value[0], self.value[1] ^ other.value[1]))

    def __repr__(self) -> str:
        return f"FiveValue({self.value})"

    def __str__(self) -> str:
        return f"{self.value[0]}/{self.value[1]}"

    def __eq__(self, other) -> bool:
        if not isinstance(other, FiveValue):
            return NotImplemented
        return self.value[0][0] == other.value[0][0] and self.value[1][0] == other.value[1][0]

    def __hash__(self) -> int:
        return hash(self.value)


setattr(FiveValue, "ON", FiveValue((TriValue.ON, TriValue.ON)))
setattr(FiveValue, "OFF", FiveValue((TriValue.OFF, TriValue.OFF)))
setattr(FiveValue, "UNKNOWN", FiveValue((TriValue.UNKNOWN, TriValue.UNKNOWN)))
setattr(FiveValue, "ON_IS_OFF", FiveValue((TriValue.ON, TriValue.OFF)))  # D = 1/0
setattr(FiveValue, "OFF_IS_ON", FiveValue((TriValue.OFF, TriValue.ON)))  # D' = 0/1
