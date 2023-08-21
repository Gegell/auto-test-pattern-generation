from logic_blocks import Line, AND, OR, XOR, XNOR, Network
from multi_logic import FiveValue


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

    print(or2.equation_str())
    print("Gates in net:", len(net.gates))
    print("Lines in net:", len(net.lines))


if __name__ == "__main__":
    main()
