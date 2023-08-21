from pathlib import Path
from logic_blocks import Line, AND, OR, XOR, XNOR, Network
from d_alg import D_Algorithm
from itertools import chain
from multi_logic import FiveValue
from writer import TikZWriter


def main():
    # Create the input / output lines
    a, b, c, d, e, f, o = [Line(name=name) for name in "abcdefo"]
    # Intermediate lines with names like in exercise:
    g, h, i, j, k, l, m, n = [Line(name=name) for name in "ghijklmn"]

    # Define the network
    with Network() as net:
        and1 = AND([e, f], k)
        xor1 = XOR([a, b], g)
        xor2 = XOR([c, d], h)
        xor = XOR([xor1.output, xor2.output], l)
        xnor1 = XNOR([a, b], i)
        xnor2 = XNOR([c, d], j)
        xnor = XNOR([xnor1.output, xnor2.output], m)
        or1 = OR([and1.output, xor.output], n)
        or2 = OR([xnor.output, or1.output], o)

    out_path = Path(__file__).parent / "out"
    out_path.mkdir(exist_ok=True, parents=True)
    with TikZWriter(net, out_path / "output.tex") as writer:
        writer.write()

    print(or2.equation_str())
    print("Gates in net:", len(net.gates))
    print("Lines in net:", len(net.lines))

    format_str = "{{:>{}}} - {{}}: ".format(max(len(line.name) for line in net.lines))
    sep_str = "\n" + " " * len(format_str.format("", " " * 5))

    for line in net.lines:
        for stuck_at in (False, True):
            sa_name = "s.a.1" if stuck_at else "s.a.0"
            if D_Algorithm(net, line, stuck_at):
                print(
                    format_str.format(line.name, sa_name)
                    + sep_str.join(
                        f"{'IO'[line.is_output()]}: {line.name}, {line.value}"
                        for line in chain(net.outputs(), net.inputs())
                        if line.value != FiveValue.UNKNOWN
                    )
                )
                writer.write()
            else:
                print(format_str.format(line.name, sa_name) + "No D-algorithm assignment found.")


if __name__ == "__main__":
    main()
