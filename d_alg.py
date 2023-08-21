# Prerequisites
# - **D-Frontier**: contains all gates with current output `x` and at least one input `D` or `!D`
#   - Select 1 gate from this and assign non-controlling values to unspecified inputs.
#   - *backtrack* if empty & terminate (FAIL) if all choices are exhausted (*undetectable*).
# - **J-Frontier**: gates whose output is known, but inputs are unknowable (at this point in time).
# - **Imply**: computes all values determined by implication.


from typing import NamedTuple
from logic_blocks import Gate, Line, Network
from multi_logic import FiveValue
from enum import Enum


class Direction(Enum):
    BACKWARDS = "←"
    FORWARDS = "→"
    BOTH = "↔"


class ImplicationError(Exception):
    """Raised when an implication is found to be contradictory."""


class AssignmentQueueItem(NamedTuple):
    line: Line
    value: FiveValue
    direction: Direction

    def __repr__(self):
        return f"({self.line.name}, {self.value}, {self.direction.value})"


class AssignmentContext:
    def __init__(self):
        self.original_values = []

    def revert(self):
        # print(f"Backtracking assignments on {[line.name for line, _ in self.original_values]}")
        for line, value in self.original_values:
            line.value = value

    def assign(self, line, value):
        # print(f"Assigning {value} to {line.name}")
        self.original_values.append((line, line.value))
        line.value = value


def imply(
    d_front: set[Gate],
    j_front: set[Gate],
    assignment_queue: list[AssignmentQueueItem],
    visited_outputs: set[Line],
):
    """Performs all implications, maintaining d/j_front and assignment_queue."""

    def deduce_gate(gate: Gate | None) -> None:
        if gate is None:
            return
        # Deduce the output
        deduction = gate.forward()
        if deduction != FiveValue.UNKNOWN:
            assignment_queue.append(AssignmentQueueItem(gate.output, deduction, Direction.FORWARDS))

        # If it has a D input and a X output, add it to the D frontier
        if gate.has_sensitized_input() and gate.output.value == FiveValue.UNKNOWN:
            d_front.add(gate)
        else:  # Remove if it was in the D frontier
            d_front.discard(gate)

        # If it has a non-X output, but cannot imply it based on its inputs, add it to the J frontier
        if not gate.can_imply_output() and gate.output.value != FiveValue.UNKNOWN:
            j_front.add(gate)
        else:  # Remove if it was in the J frontier
            j_front.discard(gate)

    assignments = AssignmentContext()
    while assignment_queue:
        line, value, direction = assignment_queue.pop()
        if line.is_output():
            visited_outputs.add(line)

        if line.value == FiveValue.UNKNOWN:
            assignments.assign(line, value)
        elif line.value == value:
            continue  # Already assigned, no change needed
        else:
            # If not at the fault location and we have different values, we have a contradiction
            assignments.revert()
            return False
            # raise ImplicationError(f"Cannot assign {value} to {line.name} (current value: {line.value})")

        # Propagate the assignment
        if direction == Direction.BACKWARDS or direction == Direction.BOTH:
            deduce_gate(line.parent)
        if direction == Direction.FORWARDS or direction == Direction.BOTH:
            for gate in line.children:
                deduce_gate(gate)
    return True


def error_at_primary_out(visited_outputs: set[Line]):
    """Returns whether there is an error at the primary output."""

    def is_sensitized(line):
        return line.value == FiveValue.ON_IS_OFF or line.value == FiveValue.OFF_IS_ON

    return any(map(is_sensitized, visited_outputs))


def D_Algorithm_Recurse(
    d_front: set[Gate],
    j_front: set[Gate],
    assignment_queue: list[AssignmentQueueItem],
    visited_outputs: set[Line],
):
    # Resolve all assignments which can be propagated
    # Raises exception on FAIL: implication found contradiction
    if not imply(d_front, j_front, assignment_queue, visited_outputs):
        return False

    # Try to propagate the error to the primary output
    if not error_at_primary_out(visited_outputs):
        while d_front:
            gate = d_front.pop()
            controlling_value = gate.controlling
            for line in gate.inputs:
                if line.value == FiveValue.UNKNOWN:
                    assignment_queue.append(AssignmentQueueItem(line, ~controlling_value, Direction.BOTH))
            if D_Algorithm_Recurse(d_front.copy(), j_front.copy(), assignment_queue.copy(), visited_outputs.copy()):
                return True
            # backtrack by restoring d/j_front and assignment_queue
        return False  # FAIL: all possible choices to propagate the error are exhausted

    # Now we have an error at the primary output
    # Resolve all remaining choices to generate the signals
    while j_front:
        gate = j_front.pop()
        controlling_value = gate.controlling
        for line in gate.inputs:
            if line.value == FiveValue.UNKNOWN:
                assignment_queue.append(AssignmentQueueItem(line, controlling_value, Direction.BOTH))
                if D_Algorithm_Recurse(
                    d_front.copy(), j_front.copy(), assignment_queue.copy(), visited_outputs.copy()
                ):
                    return True
                assignment_queue[-1] = AssignmentQueueItem(line, ~controlling_value, Direction.BOTH)
        if D_Algorithm_Recurse(d_front.copy(), j_front.copy(), assignment_queue.copy(), visited_outputs.copy()):
            return True
        return False  # FAIL: all remaining choices to generate the signal yield errors
    return True  # SUCCESS


def D_Algorithm(net: Network, fault_loc: Line, is_stuck_at_1: bool):
    """Initializes the D-Algorithm."""
    net.reset()
    source_gate = fault_loc.parent
    incoming_line = Line(name=fault_loc.name + "_in", parent=source_gate)
    if source_gate is not None:
        source_gate.output = incoming_line
    fault_loc.parent = None

    # Initialize
    d_front: set[Gate] = set()
    j_front: set[Gate] = set()
    if is_stuck_at_1:
        assignment_queue = [
            AssignmentQueueItem(incoming_line, FiveValue.OFF, Direction.BACKWARDS),
            AssignmentQueueItem(fault_loc, FiveValue.OFF_IS_ON, Direction.FORWARDS),
        ]
    else:
        assignment_queue = [
            AssignmentQueueItem(incoming_line, FiveValue.ON, Direction.BACKWARDS),
            AssignmentQueueItem(fault_loc, FiveValue.ON_IS_OFF, Direction.FORWARDS),
        ]

    # Start
    try:
        result = D_Algorithm_Recurse(d_front, j_front, assignment_queue, set())
    except ImplicationError:
        raise
    finally:
        fault_loc.parent = source_gate
        if source_gate is not None:
            source_gate.output = fault_loc
        del incoming_line
    return result
