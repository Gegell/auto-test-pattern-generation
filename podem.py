# TODO: Actually transform this pseudo python into executable code.

# Prerequisites
# - **inversion**: property of the gate, 1 if it inverts the controlling value otherwise 0.
# - PODEM has no need for a J-Frontier (un-justified values) as it only does forward implication.


def backtrace(line, value):
    while line.is_gate_output():
        gate = line.gate
        line = gate.any_x_input()
        value = value ^ gate.inversion
    return line, value  # line is now a primary input


def select_objective(d_front, fault):
    """Selects a line to assign."""
    if fault.line == "x":
        return (fault.line, not fault.value)  # e.g. f sa0 yields (f, 1)
    gate = d_front[0]  # select gate from d frontier (better metrics exist)
    line = gate.any_x_input()
    return (line, not gate.controlling)


def PODEM(fault):
    if error_at_primary_out():
        return True
    if test_not_possible():
        return False

    # Select a line to assign
    (line, value) = select_objective(d_front, fault)
    (root, root_value) = backtrace(line, value)

    imply(root, root_value, d_front)
    if PODEM():
        return True

    imply(root, not root_value, d_front)
    if PODEM():
        return True

    # undo assignment
    imply(root, "x", d_front)
    return False
