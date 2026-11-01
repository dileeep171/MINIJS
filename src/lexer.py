
"""Tokenizer for the MiniJS 1.0 language."""
from dataclasses import dataclass


class MiniJSError(Exception):
    """Base class for MiniJS errors."""


@dataclass(frozen=True)
class Token:
    kind: str
    value: object
    position: int


KEYWORDS = {
    "let", "if", "else", "while",
    "true", "false", "print"
}

OPERATORS = (
    "===", "!==", "&&", "||",
    "<=", ">=",
    "+", "-", "*", "/", "%",
    "!", "<", ">", "=",
    ";", "(", ")", "{", "}"
)


class Lexer:
    def __init__(self, source: str):
        self.source = source.lstrip("\ufeff")
        self.i = 0
        self.tokens = []

    def tokenize(self):
        s = self.source
        n = len(s)

        while self.i < n:
            c = s[self.i]

            if c in " \t\r\n":
                self.i += 1
                continue

            # Single-line comments
            if s.startswith("//", self.i):
                end = s.find("\n", self.i + 2)
                self.i = n if end == -1 else end + 1
                continue

            # Block comments
            if s.startswith("/*", self.i):
                start = self.i
                end = s.find("*/", self.i + 2)

                if end == -1:
                    raise MiniJSError(
                        f"Lexical error: unterminated block comment at position {start}"
                    )

                self.i = end + 2
                continue

            # Number literals
            if c.isascii() and c.isdigit():
                start = self.i

                while self.i < n and s[self.i].isascii() and s[self.i].isdigit():
                    self.i += 1

                if self.i < n and s[self.i] == ".":
                    self.i += 1
                    frac_start = self.i

                    while self.i < n and s[self.i].isascii() and s[self.i].isdigit():
                        self.i += 1

                    if frac_start == self.i:
                        raise MiniJSError(
                            f"Lexical error: malformed number at position {start}"
                        )

                number = float(s[start:self.i])
                self.tokens.append(Token("NUMBER", number, start))
                continue

            # Identifiers and keywords
            if c.isascii() and (c.isalpha() or c in "_$"):
                start = self.i
                self.i += 1

                while self.i < n:
                    ch = s[self.i]

                    if ch.isascii() and (ch.isalnum() or ch in "_$"):
                        self.i += 1
                    else:
                        break

                word = s[start:self.i]

                if word in KEYWORDS:
                    self.tokens.append(
                        Token(word.upper(), word, start)
                    )
                else:
                    self.tokens.append(
                        Token("IDENT", word, start)
                    )

                continue

            # Operators
            matched = None

            for op in OPERATORS:
                if s.startswith(op, self.i):
                    matched = op
                    break

            if matched is not None:
                self.tokens.append(
                    Token(matched, matched, self.i)
                )
                self.i += len(matched)
                continue

            raise MiniJSError(
                f"Lexical error: unexpected character {c!r} at position {self.i}"
            )

        self.tokens.append(Token("EOF", None, n))
        return self.tokens
