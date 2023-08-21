from abc import ABC, abstractmethod
from collections import Counter
from functools import reduce
from typing import Optional, Self
from multi_logic import FiveValue


class Line:
    _name_registry: Counter[str] = Counter(["Line"])

    def __init__(
        self,
        value: FiveValue = FiveValue.UNKNOWN,
        name: str | None = None,
        children: Optional[list["Gate"]] = None,
        parent: Optional["Gate"] = None,
    ):
        self.value: FiveValue = value
        self.children: list[Gate] = children or []
        self.parent: Optional[Gate] = parent

        # Assign a name if none is provided (with deduplication)
        name = name or "Line"
        count = self._name_registry[name]
        self._name_registry[name] += 1
        self.name = f"{name}_{count}" if count else name

    def __hash__(self):
        return id(self)

    def __str__(self):
        return f"{self.name} ({self.value})"

    def __repr__(self):
        return f"Line({self.name}, {self.value}, {self.children}, {self.parent})"

    def is_output(self) -> bool:
        return len(self.children) == 0

    def is_input(self) -> bool:
        return self.parent is None

    def equation_str(self) -> str:
        return self.parent.equation_str() if self.parent else self.name


class Gate(ABC):
    _name_registry: Counter[str] = Counter()

    def __init__(
        self, inputs: list[Line], output: Line | None, inversion: FiveValue, controlling: FiveValue, name: str | None
    ):
        # Register the gate with the associated lines
        for line in inputs:
            line.children = line.children or []
            line.children.append(self)
        if output is None:
            output = Line()
        output.parent = self

        # Assign a name if none is provided (with deduplication)
        name = name or f"{self.__class__.__name__}"
        self._name_registry[name] += 1
        self.name: str = f"{name}_{self._name_registry[name]}"

        self.inputs: list[Line] = inputs
        self.output: Line = output
        self.inversion: FiveValue = inversion
        self.controlling: FiveValue = controlling

        # Register the gate with the active network context
        Network.register_gate(self)

    def get_unknown_input(self) -> Line | None:
        for line in self.inputs:
            if line.value == FiveValue.UNKNOWN:
                return line
        return None

    def has_sensitized_input(self) -> bool:
        return any(line.value in [FiveValue.ON_IS_OFF, FiveValue.OFF_IS_ON] for line in self.inputs)

    def can_imply_output(self) -> bool:
        return self.output.value == self.forward()

    def equation_str(self) -> str:
        operands = []
        for line in self.inputs:
            if line.parent is None:
                operands.append(line.name)
            else:
                operands.append(line.parent.equation_str())
        return f"{self.name}({', '.join(operands)})"

    @abstractmethod
    def forward(self) -> FiveValue:
        pass


class Network:
    """Context manager for a network of gates."""

    _active_network_contexts: list["Network"] = []

    def __init__(self) -> None:
        self.gates: set[Gate] = set()
        self.lines: set[Line] = set()

    def __enter__(self) -> Self:
        assert not self._active_network_contexts, "Nested network contexts are not yet supported."
        self._active_network_contexts.append(self)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self._active_network_contexts.pop()

    def _add_gate(self, gate: Gate):
        """Add a gate to the network."""
        self.gates.add(gate)
        self.lines.update(gate.inputs)
        self.lines.add(gate.output)

    @classmethod
    def active_network(cls) -> "Network":
        """Return the active network context."""
        if not cls._active_network_contexts:
            raise RuntimeError("No active network context.")
        return cls._active_network_contexts[-1]

    @classmethod
    def register_gate(cls, gate: Gate):
        """Register a gate with the active network context."""
        try:
            cls.active_network()._add_gate(gate)
        except RuntimeError:
            raise RuntimeError("Gate created outside of network context, please use a Network context manager.")

    def outputs(self) -> list[Line]:
        return [line for line in self.lines if not line.children]

    def inputs(self) -> list[Line]:
        return [line for line in self.lines if not line.parent]

    def reset(self):
        for line in self.lines:
            line.value = FiveValue.UNKNOWN


class AND(Gate):
    def __init__(self, inputs: list[Line], output: Line | None = None, name: str | None = None):
        super().__init__(inputs, output, FiveValue.OFF, FiveValue.OFF, name)

    def forward(self):
        return reduce(lambda a, b: a & b, [line.value for line in self.inputs])


class NAND(Gate):
    def __init__(self, inputs: list[Line], output: Line | None = None, name: str | None = None):
        super().__init__(inputs, output, FiveValue.ON, FiveValue.OFF, name)

    def forward(self):
        return ~reduce(lambda a, b: a & b, [line.value for line in self.inputs])


class OR(Gate):
    def __init__(self, inputs: list[Line], output: Line | None = None, name: str | None = None):
        super().__init__(inputs, output, FiveValue.OFF, FiveValue.ON, name)

    def forward(self):
        return reduce(lambda a, b: a | b, [line.value for line in self.inputs])


class NOR(Gate):
    def __init__(self, inputs: list[Line], output: Line | None = None, name: str | None = None):
        super().__init__(inputs, output, FiveValue.ON, FiveValue.ON, name)

    def forward(self):
        return ~reduce(lambda a, b: a | b, [line.value for line in self.inputs])


class XOR(Gate):
    def __init__(self, inputs: list[Line], output: Line | None = None, name: str | None = None):
        super().__init__(inputs, output, FiveValue.ON, FiveValue.ON, name)  # Controlling and inversion are arbitrary

    def forward(self):
        return reduce(lambda a, b: a ^ b, [line.value for line in self.inputs])


class XNOR(Gate):
    def __init__(self, inputs: list[Line], output: Line | None = None, name: str | None = None):
        super().__init__(inputs, output, FiveValue.ON, FiveValue.OFF, name)  # Controlling and inversion are arbitrary

    def forward(self):
        return ~reduce(lambda a, b: a ^ b, [line.value for line in self.inputs])


class NOT(Gate):
    def __init__(self, inputs: list[Line], output: Line | None = None, name: str | None = None):
        assert len(inputs) == 1, "NOT gate must have exactly one input."
        super().__init__(inputs, output, FiveValue.ON, FiveValue.OFF, name)

    def forward(self):
        return ~self.inputs[0].value
