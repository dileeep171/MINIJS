
"""MiniJS 1.0 interpreter."""

import math
import sys
from pathlib import Path

from lexer import Lexer, MiniJSError
from parser import Parser


_UNINITIALIZED = object()


class Environment:
    def __init__(self, parent=None):
        self.parent = parent
        self.values = {}

    def declare(self, name):
        if name in self.values:
            raise MiniJSError(
                f"Runtime error: '{name}' has already been declared in this scope"
            )

        self.values[name] = _UNINITIALIZED

    def get(self, name):
        if name in self.values:
            value = self.values[name]

            if value is _UNINITIALIZED:
                raise MiniJSError(
                    f"Runtime error: cannot access '{name}' before initialization"
                )

            return value

        if self.parent is not None:
            return self.parent.get(name)

        raise MiniJSError(f"Runtime error: '{name}' is not defined")

    def assign(self, name, value):
        if name in self.values:
            if self.values[name] is _UNINITIALIZED:
                raise MiniJSError(
                    f"Runtime error: cannot assign '{name}' before initialization"
                )

            self.values[name] = value
            return

        if self.parent is not None:
            self.parent.assign(name, value)
            return

        raise MiniJSError(f"Runtime error: '{name}' is not defined")


def is_number(value):
    return type(value) is float


def require_number(value, op):
    if not is_number(value):
        raise MiniJSError(
            f"Runtime error: operator '{op}' requires Number operands"
        )


def truthy(value):
    if type(value) is bool:
        return value

    return value != 0.0 and not math.isnan(value)


def strict_equal(a, b):
    if type(a) is not type(b):
        return False

    if is_number(a):
        return not (math.isnan(a) or math.isnan(b)) and a == b

    return a == b


def js_div(a, b):
    if math.isnan(a) or math.isnan(b):
        return math.nan

    if b == 0.0:
        if a == 0.0:
            return math.nan

        sign = math.copysign(1.0, a) * math.copysign(1.0, b)
        return math.copysign(math.inf, sign)

    try:
        return a / b
    except OverflowError:
        sign = math.copysign(1.0, a) * math.copysign(1.0, b)
        return math.copysign(math.inf, sign)


def js_remainder(a, b):
    if math.isnan(a) or math.isnan(b):
        return math.nan

    if math.isinf(a) or b == 0.0:
        return math.nan

    if math.isinf(b):
        return a

    return math.fmod(a, b)


def number_text(value):
    if math.isnan(value):
        return "NaN"

    if math.isinf(value):
        return "Infinity" if value > 0 else "-Infinity"

    if value == 0.0:
        return "0"

    # Python repr gives the shortest round-trip float representation.
    s = repr(value)

    if "e" not in s and "E" not in s:
        if s.endswith(".0"):
            s = s[:-2]
        return s

    # JavaScript uses ordinary decimal notation in this range.
    if 1e-6 <= abs(value) < 1e21:
        from decimal import Decimal

        s = format(Decimal(s), "f")

        if "." in s:
            s = s.rstrip("0").rstrip(".")

        return s

    mantissa, exponent = s.lower().split("e")

    if mantissa.endswith(".0"):
        mantissa = mantissa[:-2]

    exp = int(exponent)

    return f"{mantissa}e{'+' if exp >= 0 else ''}{exp}"


def format_value(value):
    if type(value) is bool:
        return "true" if value else "false"

    return number_text(value)


class Interpreter:
    def __init__(self):
        self.output = []
        self.global_env = Environment()

    def run(self, program):
        self.execute(program, self.global_env)
        return self.output

    def execute(self, node, env):
        kind = node.kind

        if kind == "program":
            for statement in node.children:
                self.execute(statement, env)

        elif kind == "block":
            local = Environment(env)

            for statement in node.children:
                self.execute(statement, local)

        elif kind == "declare":
            name = node.value
            env.declare(name)

            value = self.evaluate(node.children[0], env)
            env.values[name] = value

        elif kind == "assign":
            value = self.evaluate(node.children[0], env)
            env.assign(node.value, value)

        elif kind == "print":
            value = self.evaluate(node.children[0], env)
            self.output.append(format_value(value))

        elif kind == "if":
            condition, yes, no = node.children

            if truthy(self.evaluate(condition, env)):
                self.execute(yes, env)
            elif no is not None:
                self.execute(no, env)

        elif kind == "while":
            condition, body = node.children

            while truthy(self.evaluate(condition, env)):
                self.execute(body, env)

        else:
            raise MiniJSError(
                f"Internal error: unknown statement {kind}"
            )

    def evaluate(self, node, env):
        kind = node.kind

        if kind == "number":
            return float(node.value)

        if kind == "boolean":
            return node.value

        if kind == "variable":
            return env.get(node.value)

        if kind == "unary":
            op = node.value
            value = self.evaluate(node.children[0], env)

            if op == "!":
                return not truthy(value)

            require_number(value, op)

            if op == "+":
                return value

            return -value

        if kind == "binary":
            op = node.value
            left = self.evaluate(node.children[0], env)

            # Short-circuit logical operations.
            if op == "&&":
                if truthy(left):
                    return self.evaluate(node.children[1], env)
                return left

            if op == "||":
                if truthy(left):
                    return left
                return self.evaluate(node.children[1], env)

            right = self.evaluate(node.children[1], env)

            if op in ("===", "!=="):
                result = strict_equal(left, right)
                return result if op == "===" else not result

            require_number(left, op)
            require_number(right, op)

            if op == "+":
                return left + right

            if op == "-":
                return left - right

            if op == "*":
                return left * right

            if op == "/":
                return js_div(left, right)

            if op == "%":
                return js_remainder(left, right)

            if op in ("<", "<=", ">", ">="):
                if math.isnan(left) or math.isnan(right):
                    return False

                if op == "<":
                    return left < right
                if op == "<=":
                    return left <= right
                if op == ">":
                    return left > right
                return left >= right

        raise MiniJSError(
            f"Internal error: unknown expression {kind}"
        )


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv

    if len(argv) != 1:
        print(
            "Usage: python interpreter.py path/to/program.mjs",
            file=sys.stderr
        )
        return 2

    try:
        source = Path(argv[0]).read_text(encoding="utf-8-sig")

        # Parse the complete source before executing anything.
        tokens = Lexer(source).tokenize()
        tree = Parser(tokens).parse()

        interpreter = Interpreter()
        output = interpreter.run(tree)

        # Print output only if execution succeeds.
        if output:
            sys.stdout.write("\n".join(output) + "\n")

        return 0

    except (OSError, UnicodeError, MiniJSError, ArithmeticError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
