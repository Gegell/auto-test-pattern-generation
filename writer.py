from collections import Counter
from io import TextIOWrapper
from os import PathLike
from logic_blocks import Gate, Line, Network
import logic_blocks
from multi_logic import FiveValue


_idType = int

_BOILERPLATE_FORMAT = """
\\documentclass{{standalone}}
\\usepackage{{tikz}}
\\usepackage{{circuitikz}}
\\begin{{document}}
\\begin{{circuitikz}}[ieee ports, scale={scale}, font=\\small]
{content}\\end{{circuitikz}}
\\end{{document}}
"""

_GATE_NAMES = {
    logic_blocks.AND: "and",
    logic_blocks.NAND: "nand",
    logic_blocks.OR: "or",
    logic_blocks.NOR: "nor",
    logic_blocks.XOR: "xor",
    logic_blocks.XNOR: "xnor",
    logic_blocks.NOT: "not",
}

_LINE_MODIFIERS = {
    FiveValue.ON: "green!50!black, thick",
    FiveValue.OFF: "red, thick",
    FiveValue.ON_IS_OFF: "green!50!black, dashed, thick",
    FiveValue.OFF_IS_ON: "red, dashed, thick",
}


class TikZWriter:
    _active_writers: dict[_idType, "TikZWriter"] = {}

    def __init__(
        self,
        net: Network,
        filename: str | PathLike,
        single_track_width: float = 0.2,
        pin_width: float = 1.2,
        component_width: float = 1.4,
        scale: float = 1.0,
        verbose: bool = False,
    ):
        self.net = net
        self.filename = filename
        self.tikz_node_names: dict[Gate, str] = {}
        self.tikz_line_names: dict[Line, str] = {}
        self.tikz_gate_positions: dict[Gate, tuple[float, float]] = {}
        self.gate_coordinates: dict[Gate, tuple[int, int]] = {}
        self.line_tracks: dict[Line, int] = {}
        self.tracks_per_layer: Counter[int] = Counter()

        self.single_track_width = single_track_width
        self.pin_width = pin_width  # Additional spacing around each track to compensate for pins sticking out
        self.component_width = component_width  # Width of each gate for scale = 1
        self.scale = scale  # Scale factor for the whole diagram

        self.verbose = verbose

    def __enter__(self):
        self._active_writers[id(self)] = self
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self._active_writers.pop(id(self))

    def _node_name(self, gate: Gate) -> str:
        if gate not in self.tikz_node_names:
            self.tikz_node_names[gate] = f"g{len(self.tikz_node_names)}"
        return self.tikz_node_names[gate]

    def _line_name(self, line: Line) -> str:
        if line not in self.tikz_line_names:
            self.tikz_line_names[line] = f"l{len(self.tikz_line_names)}"
        return self.tikz_line_names[line]

    def _compute_positions(self) -> None:
        this_layer = self.net.outputs()
        visited: set[Gate] = set()
        depth = 0
        while this_layer:
            to_visit = []
            for i, line in enumerate(this_layer):
                if line.parent is None:
                    continue
                gate = line.parent
                self.gate_coordinates[gate] = (depth, i)
                visited.add(gate)
                for in_line in gate.inputs:
                    if in_line.parent not in visited and all(child in visited for child in in_line.children):
                        to_visit.append(in_line)
            depth += 1
            this_layer = to_visit
        self.tracks_per_layer = Counter()
        lines_in_layer: dict[int, list[Line]] = {}
        for line in self.net.lines:
            max_x = max((self.gate_coordinates[gate][0] for gate in line.children), default=-1)
            self.line_tracks[line] = self.tracks_per_layer[max_x]
            self.tracks_per_layer[max_x] += 1
            lines_in_layer.setdefault(max_x, []).append(line)
        accumulated_depths = [0.0]
        for layer in range(1, depth):
            layer_width = (self.tracks_per_layer[layer] + 1) * self.single_track_width + self.pin_width
            accumulated_depths.append(accumulated_depths[-1] + layer_width)
        for gate, (x, y) in self.gate_coordinates.items():
            self.tikz_gate_positions[gate] = (-(x + accumulated_depths[x]), y * self.component_width)

        if self.verbose:
            print("Tracks per layer: ", self.tracks_per_layer)
            print("Track order in each layer: ")
            for x, lines in sorted(lines_in_layer.items(), key=lambda x: x[0]):
                print(f"    {x:>2}: [{', '.join(map(lambda line: line.name, lines))}]")

    def write(self):
        self._compute_positions()
        with open(self.filename, "w") as f:
            formatted = _BOILERPLATE_FORMAT.format(scale=self.scale, content="{content}")
            pre, post = formatted.split("{content}")
            f.write(pre)
            for gate in self.net.gates:
                self._write_gate(f, gate)
            for line in self.net.lines:
                self._write_line(f, line)
            f.write(post)

    def _write_gate(self, file: TextIOWrapper, gate: Gate):
        input_count = len(gate.inputs)
        file.write(
            "\\node [{} port, number inputs={}] ({}) at ({:.1f}, {:.1f}) {{\\verb|{}|}};\n".format(
                _GATE_NAMES[type(gate)],
                input_count,
                self._node_name(gate),
                self.tikz_gate_positions[gate][0],
                self.tikz_gate_positions[gate][1],
                gate.name,
            )
        )

    def _write_line(self, file: TextIOWrapper, line: Line):
        if self.verbose:
            file.write(
                "% {}: {} -> [{}]\n".format(
                    line.name,
                    line.parent.name if line.parent else "",
                    ", ".join(g.name for g in line.children),
                )
            )
        modifier = _LINE_MODIFIERS.get(line.value, "")
        modifier_str = f" [{modifier}]" if modifier else ""
        line_id = self._line_name(line)
        if line.parent is None and not line.children:
            file.write(f"\\draw{modifier_str} node {{{line_id}}};\n")

        elif line.parent is None and line.children:
            earliest_gate = max((child for child in line.children), key=lambda gate: self.gate_coordinates[gate][0])
            input_index = earliest_gate.inputs.index(line)
            layer = self.gate_coordinates[earliest_gate][0]
            layer_width = (self.tracks_per_layer[layer] + 1) * self.single_track_width
            track_offset = (self.line_tracks[line] + 1) * self.single_track_width
            position = f"({self._node_name(earliest_gate)}.in {input_index + 1}) ++(-{layer_width:.1f}, 0)"
            file.write(f"\\draw {position}{modifier_str} node[left] ({line_id}) {{\\verb|{line.name}|}};\n")
            file.write(f"\\draw{modifier_str}")
            for child in line.children:
                input_index = child.inputs.index(line)
                input_position = f"({self._node_name(child)}.in {input_index + 1})"
                file.write(f" ({line_id}.east) -- ++({track_offset:.1f}, 0) |- {input_position}")
            file.write(";\n")

        elif line.parent is not None and not line.children:
            file.write(f"\\draw{modifier_str} ({self._node_name(line.parent)}.out) node[right] {{\\verb|{line.name}|}};\n")

        elif line.parent is not None and line.children:
            file.write(f"\\draw{modifier_str}")
            track_offset = (self.line_tracks[line] + 1) * self.single_track_width
            start_path = f"({self._node_name(line.parent)}.out) -- ++({track_offset:.1f}, 0)"
            for child in line.children:
                input_index = child.inputs.index(line)
                input_position = f"({self._node_name(child)}.in {input_index + 1})"
                file.write(f" {start_path} |- {input_position}")
            file.write(f" node[above, pos=1] {{\\verb|{line.name}|}};\n")

        else:
            assert False, "Unreachable"

    @classmethod
    def write_all(cls):
        for writer in cls._active_writers.values():
            writer.write()
