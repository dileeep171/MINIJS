#!/usr/bin/env python3
"""MiniJS 1.0 public correctness checker (Python 3, standard library only).

Usage:
    python3 correctness_test.py -- ./minijs
    python3 correctness_test.py -- node interpreter.js
    python3 correctness_test.py -- python3 interpreter.py

The student's launch command receives an extra final argument: source-file path.
This program supplies positive and negative tests, compares stdout, and enforces exit status.
It is intentionally NOT a performance benchmark and does not implement MiniJS.
"""

import argparse
import math
import os
from pathlib import Path
import random
import subprocess
import sys
import tempfile
from dataclasses import dataclass


@dataclass
class Test:
    name: str
    source: str
    expected: tuple[str, ...] = ()
    error: bool = False


def program_tests(seed: int, extra_random: int) -> list[Test]:
    tests: list[Test] = []

    def ok(name: str, code: str, *output: object) -> None:
        tests.append(Test(name, code, tuple(str(item) for item in output)))

    def bad(name: str, code: str) -> None:
        tests.append(Test(name, code, error=True))

    ok("empty program", "/* empty program */")
    ok("integer literals", "print(0);print(25);print(0002);", 0, 25, 2)
    ok("decimal literals", "print(1.25);print(0.5);", "1.25", "0.5")
    ok("operator precedence", "print(2+3*4);print((2+3)*4);print(20/2/2);", 14, 20, 5)
    ok("unary and parentheses", "print(-(-7));print(+(-3));print(-(2+3));", 7, -3, -5)
    ok("remainder sign", "print(17%5);print(-17%5);print(17%-5);", 2, -2, 2)
    ok("floating operations", "print(1/2);print(0.1+0.2);print(2.5*4);", "0.5", "0.30000000000000004", 10)
    ok("special IEEE values", "print(1/0);print(-1/0);print(0/0);print(1%0);", "Infinity", "-Infinity", "NaN", "NaN")
    ok("signed zero", "print(-0);print(0===-0);", 0, "true")
    ok("relational operations", "print(2<3);print(3<=3);print(4>5);print(5>=5);", "true", "true", "false", "true")
    ok("strict equality types", "print(true===1);print(false!==0);print(2===2);print(2!==3);", "false", "true", "true", "true")
    ok("NaN comparisons", "print(0/0===0/0);print(0/0!==0/0);print(0/0<2);", "false", "true", "false")
    ok("logical precedence", "print(true||false&&false);print(!false===true);", "true", "true")
    ok("logical operand results", "print(0||7);print(3&&9);print(5&&0);print(false||8);", 7, 9, 0, 8)
    ok("truthiness", "print(!0);print(!(-1));print(!!3);print(!(0/0));", "true", "false", "true", "true")
    ok("short circuit avoids error", "print(false&&unknown);print(true||other);print(0&&missing);print(2||missing);", "false", "true", 0, 2)
    ok("comments and whitespace", "// comment\n let\tx = 7; /* ignored\n block */ print ( x ); // end", 7)
    ok("arithmetic associativity", "print(40-10-5);print(100/5/2);print(2*3+4*5);", 25, 10, 26)
    ok("mutable variable", "let x=4;x=x*2;print(x);", 8)
    ok("lexical shadowing", "let x=3;{let x=9;print(x);}print(x);", 9, 3)
    ok("write outer binding", "let x=1;{x=x+2;{let x=5;x=x+7;print(x);}print(x);}print(x);", 12, 3, 3)
    ok("while loop sum", "let sum=0;let i=1;while(i<=100){sum=sum+i;i=i+1;}print(sum);", 5050)
    ok("new scope per iteration", "let i=0;while(i<3){let x=i*2;print(x);i=i+1;}", 0, 2, 4)
    ok("if true else", "if(1){print(11);}else{print(12);}if(0){print(21);}else{print(22);}", 11, 22)
    ok("if without else", "if(false){print(100);}print(1);", 1)
    ok("nested control flow", "let i=0;let sum=0;while(i<10){if(i%2===0){sum=sum+i;}else{sum=sum+1;}i=i+1;}print(sum);", 25)
    ok("skip unreachable branch", "if(false){print(unknown);}else{print(3);}", 3)
    ok("mixed logical condition", "let v=0;while(v<4&&!(v===3)){v=v+1;}print(v);", 3)
    ok("nested blocks", "let a=2;{{let b=4;{print(a+b);}}}print(a);", 6, 2)
    ok("large integer exactly represented", "print(9007199254740992+1);", "9007199254740992")
    ok("nested single expression", "print((((2+3)*4-(6/2))%9)===8);", "true")

    # These check that malformed programs are rejected rather than partially executed.
    bad("syntax: missing semicolon", "let x=1 print(x);")
    bad("syntax: unclosed block", "if(true){print(1);")
    bad("syntax: missing expression", "let x=;")
    bad("syntax: unclosed parenthesis", "print((1+2);")
    bad("syntax: missing braces", "if(true)print(1);")
    bad("syntax: unknown operator", "print(1**2);")
    bad("syntax: parse all before executing", "print(10);let y=;")
    bad("lexical: unexpected character", "print(@);")
    bad("lexical: unterminated comment", "/* no closing comment")
    bad("runtime: undefined read", "print(missing);")
    bad("runtime: undefined assignment", "missing=10;")
    bad("runtime: redeclaration", "let a=1;let a=2;")
    bad("runtime: block-local variable unavailable", "{let x=2;}print(x);")
    bad("runtime: shadowed TDZ", "let x=5;{let x=x+1;}")
    bad("runtime: arithmetic type", "print(1+true);")
    bad("runtime: compare type", "print(true<1);")
    bad("runtime: unary type", "print(-true);")
    bad("runtime: non-boolean equality still valid, but illegal assigned literal", "true=3;")

    rng = random.Random(seed)
    for idx in range(extra_random):
        steps = rng.randint(5, 200)
        mod = rng.randint(2, 11)
        factor = rng.randint(-8, 8)
        extra = rng.randint(-13, 13)
        accum = 0
        for i in range(steps):
            if i % mod == 0:
                accum += i * factor + extra
            else:
                accum -= i
        source = (
            f"let sum=0;let i=0;while(i<{steps}){{"
            f"if(i%{mod}===0){{sum=sum+i*({factor})+({extra});}}"
            "else{sum=sum-i;}i=i+1;}print(sum);"
        )
        ok(f"generated loop #{idx+1}", source, accum)

    return tests


def number_equal(actual: str, expected: str) -> bool:
    if expected in ("true", "false"):
        return actual == expected
    if expected in ("NaN", "Infinity", "-Infinity"):
        return actual == expected
    try:
        got = float(actual)
        want = float(expected)
    except ValueError:
        return False
    if not math.isfinite(got):
        return False
    # Integer-valued expected output must be exact when its magnitude can
    # be represented as a contiguous range of IEEE-754 binary64 integers.
    if want.is_integer() and abs(want) <= 2**53:
        return got == want
    return math.isclose(got, want, rel_tol=1e-12, abs_tol=1e-12)


def check_output(actual_stdout: str, expected: tuple[str, ...]) -> tuple[bool, str]:
    normalized = actual_stdout.replace("\r\n", "\n")
    if normalized.endswith("\n"):
        normalized = normalized[:-1]
    lines = normalized.split("\n") if normalized else []
    if len(lines) != len(expected):
        return False, f"expected {len(expected)} output line(s), got {len(lines)}: {lines!r}"
    for index, (actual, want) in enumerate(zip(lines, expected), 1):
        if actual != actual.strip() or not number_equal(actual, want):
            return False, f"line {index}: expected {want!r}, got {actual!r}"
    return True, ""


def main() -> int:
    parser = argparse.ArgumentParser(description="MiniJS 1.0 correctness checker")
    parser.add_argument("--seed", type=int, default=20261016)
    parser.add_argument("--random-cases", type=int, default=20)
    parser.add_argument("--timeout", type=float, default=3.0, help="seconds per test")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("command", nargs=argparse.REMAINDER,
                        help="use -- followed by interpreter command")
    args = parser.parse_args()
    command = args.command
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        parser.error("provide command after --, e.g. -- ./minijs")
    if args.random_cases < 0 or args.random_cases > 1000:
        parser.error("--random-cases must be in [0, 1000]")
    if args.timeout <= 0:
        parser.error("--timeout must be positive")

    suite = program_tests(args.seed, args.random_cases)
    passed = 0
    failed = []

    with tempfile.TemporaryDirectory(prefix="minijs-test-") as temp:
        for i, test in enumerate(suite):
            source_path = Path(temp) / f"test_{i:03}.mjs"
            source_path.write_text(test.source + "\n", encoding="utf-8")
            try:
                run = subprocess.run(
                    [*command, str(source_path)],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=args.timeout,
                    stdin=subprocess.DEVNULL,
                )
                if test.error:
                    good = run.returncode != 0 and not run.stdout.strip()
                    why = "expected nonzero exit and empty stdout" if not good else ""
                else:
                    good_out, why = check_output(run.stdout, test.expected)
                    good = run.returncode == 0 and good_out
                    if run.returncode != 0:
                        why = f"exit {run.returncode}, stderr: {run.stderr[:180]!r}; {why}"
            except subprocess.TimeoutExpired:
                good = False
                why = f"timed out after {args.timeout}s"
            except OSError as exc:
                print(f"Cannot launch interpreter: {exc}", file=sys.stderr)
                return 2

            if good:
                passed += 1
                if args.verbose:
                    print(f"PASS  {test.name}")
            else:
                failed.append((test, why))
                print(f"FAIL  {test.name}: {why}")
                if args.verbose:
                    print("  source:", test.source)

    print(f"\nMiniJS 1.0 public correctness: {passed}/{len(suite)} passed")
    print("PASS" if passed == len(suite) else "FAIL")
    if failed:
        print("To reproduce generated cases, use --seed and --random-cases with the same values.")
    else:
        print("Public tests passed. Hidden correctness checks may cover additional cases.")
    return 0 if passed == len(suite) else 1


if __name__ == "__main__":
    sys.exit(main())
