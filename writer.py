from collections import Counter
from io import TextIOWrapper
from os import PathLike
from logic_blocks import Gate, Line, Network
import logic_blocks
from multi_logic import FiveValue


_idType = int

_DOCUMENT_FORMAT = """
\\documentclass{{{doc_class}}}
\\usepackage{{tikz}}
\\usepackage{{circuitikz}}
\\begin{{document}}
\\ctikzset{{ieee ports, logic ports draw leads=false}}
\\tikzset{{every picture/.style={{scale={scale}, font=\\small\\ttfamily}}}}
{content}
\\end{{document}}
"""

_CONTENT_FORMAT = """
\\begin{circuitikz}
{content}
\\end{circuitikz}
"""

_BEAMER_CONTENT_FORMAT = "\\begin{frame}\n\\resizebox{\\textwidth}{!}{" + _CONTENT_FORMAT + "}\n\\end{frame}\n"

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
    def __init__(
        self,
        net: Network,
        file_name: str | PathLike | None = None,
        single_track_width: float = 0.2,
        pin_width: float = 0.6,
        component_width: float = 1.4,
        scale: float = 1.0,
        verbose: bool = False,
    ):
        self.net = net

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
        self.incremental = False
        self.file_name = file_name
        self._compute_positions()

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
            layer_width = (self.tracks_per_layer[layer] + 1) * self.single_track_width + self.pin_width * 2
            accumulated_depths.append(accumulated_depths[-1] + layer_width)
        for gate, (x, y) in self.gate_coordinates.items():
            self.tikz_gate_positions[gate] = (-(x + accumulated_depths[x]), y * self.component_width)

        if self.verbose:
            print("Tracks per layer: ", self.tracks_per_layer)
            print("Track order in each layer: ")
            for x, lines in sorted(lines_in_layer.items(), key=lambda x: x[0]):
                print(f"    {x:>2}: [{', '.join(map(lambda line: line.name, lines))}]")

    def document_format(self, content="{content}") -> str:
        partial = _DOCUMENT_FORMAT.format(
            content=content,
            doc_class="beamer" if self.incremental else "standalone",
            scale=self.scale,
        )
        return partial

    def _pre_postamble(self, fmt_string: str) -> tuple[str, str]:
        pre, post = fmt_string.split("{content}")
        return pre, post

    def __enter__(self):
        self.incremental = True
        self._compute_positions()
        self.file_handle = open(self.file_name, "w")
        pre, _ = self._pre_postamble(self.document_format())
        self.file_handle.write(pre)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        _, post = self._pre_postamble(self.document_format())
        self.file_handle.write(post)
        self.file_handle.close()
        self.incremental = False

    def write_increment(self):
        if not self.file_handle:
            raise RuntimeError("Can only write incrementally when using a context manager.")
        pre, post = self._pre_postamble(_BEAMER_CONTENT_FORMAT)
        self.file_handle.write(pre)
        for gate in self.net.gates:
            self._write_gate(self.file_handle, gate)
        for line in self.net.lines:
            self._write_line(self.file_handle, line)
        self.file_handle.write(post)

    def write_full(self, filename: str | PathLike):
        with open(filename, "w") as f:
            partial = self.document_format(_CONTENT_FORMAT)
            pre, post = self._pre_postamble(partial)
            f.write(pre)
            for gate in self.net.gates:
                self._write_gate(f, gate)
            for line in self.net.lines:
                self._write_line(f, line)
            f.write(post)

    def _escape(self, text: str) -> str:
        return text.replace("_", "\\_").replace("&", "\\&")

    def _write_gate(self, file: TextIOWrapper, gate: Gate):
        input_count = len(gate.inputs)
        file.write(
            "\\node [{} port, number inputs={}] ({}) at ({:.1f}, {:.1f}) {{{}}};\n".format(
                _GATE_NAMES[type(gate)],
                input_count,
                self._node_name(gate),
                self.tikz_gate_positions[gate][0],
                self.tikz_gate_positions[gate][1],
                self._escape(gate.name),
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
            in_pin = earliest_gate.inputs.index(line)
            layer = self.gate_coordinates[earliest_gate][0]
            layer_width = (self.tracks_per_layer[layer] + 1) * self.single_track_width
            track_offset = (self.line_tracks[line] + 1) * self.single_track_width
            position = f"({self._node_name(earliest_gate)}.in {in_pin + 1}) ++(-{layer_width:.1f}, 0)"
            file.write(f"\\draw {position}{modifier_str} node[left] ({line_id}) {{{self._escape(line.name)}}};\n")
            file.write(f"\\draw{modifier_str}")
            fmt = (
                " ({line_id}.east) -- ++({track_offset:.2f}, 0)"
                " |- ({in_id}.in {in_pin}) {node} -- ({in_id}.bin {in_pin})"
            )
            for child in line.children:
                in_id = self._node_name(child)
                in_pin = child.inputs.index(line) + 1
                node = ""
                file.write(
                    fmt.format(
                        line_id=line_id,
                        track_offset=track_offset,
                        in_id=in_id,
                        in_pin=in_pin,
                        node=node,
                    )
                )
            file.write(";\n")

        elif line.parent is not None and not line.children:
            fmt = "\\draw{modifier_str} ({out_id}.bout) -- ({out_id}.out) node[right] {{{line_name}}};\n"
            file.write(
                fmt.format(
                    out_id=self._node_name(line.parent),
                    line_name=self._escape(line.name),
                    modifier_str=modifier_str,
                )
            )

        elif line.parent is not None and line.children:
            file.write(f"\\draw{modifier_str}")
            fmt = (
                " ({out_id}.bout) -- ({out_id}.out) -- ++({track_offset:.2f}, 0)"
                " |- ({in_id}.in {in_pin}) {node} -- ({in_id}.bin {in_pin})"
            )
            out_id = self._node_name(line.parent)
            track_offset = (self.line_tracks[line] + 1) * self.single_track_width
            for child in line.children:
                in_id = self._node_name(child)
                in_pin = child.inputs.index(line) + 1
                node = f"node[above] {{{self._escape(line.name)}}}"
                file.write(
                    fmt.format(
                        out_id=out_id,
                        pin_length=self.pin_width,
                        track_offset=track_offset,
                        in_id=in_id,
                        in_pin=in_pin,
                        node=node,
                    )
                )
            file.write(";\n")

        else:
            assert False, "Unreachable"
