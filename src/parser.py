
"""Recursive-descent parser for MiniJS 1.0."""

from dataclasses import dataclass
from lexer import MiniJSError, Lexer


@dataclass
class Node:
    kind: str
    value: object = None
    children: tuple = ()


class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.i = 0

    @classmethod
    def from_source(cls, source):
        return cls(Lexer(source).tokenize())

    def peek(self, kind=None):
        token = self.tokens[self.i]
        return token if kind is None else token.kind == kind

    def take(self, kind=None):
        token = self.tokens[self.i]

        if kind is not None and token.kind != kind:
            raise MiniJSError(
                f"Syntax error at position {token.position}: "
                f"expected {kind}, got {token.kind}"
            )

        self.i += 1
        return token

    def parse(self):
        statements = []

        while not self.peek("EOF"):
            statements.append(self.statement())

        self.take("EOF")
        return Node("program", children=tuple(statements))

    def statement(self):

        if self.peek("LET"):
            self.take("LET")
            name = self.take("IDENT").value
            self.take("=")
            expression = self.expression()
            self.take(";")

            return Node("declare", name, (expression,))

        if self.peek("IDENT"):
            name = self.take("IDENT").value
            self.take("=")
            expression = self.expression()
            self.take(";")

            return Node("assign", name, (expression,))

        if self.peek("PRINT"):
            self.take("PRINT")
            self.take("(")
            expression = self.expression()
            self.take(")")
            self.take(";")

            return Node("print", children=(expression,))

        if self.peek("IF"):
            self.take("IF")
            self.take("(")
            condition = self.expression()
            self.take(")")

            then_block = self.block()
            else_block = None

            if self.peek("ELSE"):
                self.take("ELSE")
                else_block = self.block()

            return Node(
                "if",
                children=(condition, then_block, else_block)
            )

        if self.peek("WHILE"):
            self.take("WHILE")
            self.take("(")
            condition = self.expression()
            self.take(")")
            body = self.block()

            return Node("while", children=(condition, body))

        if self.peek("{"):
            return self.block()

        token = self.peek()

        raise MiniJSError(
            f"Syntax error at position {token.position}: "
            f"unexpected token {token.kind}"
        )

    def block(self):
        self.take("{")
        statements = []

        while not self.peek("}"):
            if self.peek("EOF"):
                token = self.peek()
                raise MiniJSError(
                    f"Syntax error at position {token.position}: unclosed block"
                )

            statements.append(self.statement())

        self.take("}")
        return Node("block", children=tuple(statements))

    def expression(self):
        return self.logical_or()

    def logical_or(self):
        node = self.logical_and()

        while self.peek("||"):
            op = self.take().kind
            node = Node("binary", op, (node, self.logical_and()))

        return node

    def logical_and(self):
        node = self.equality()

        while self.peek("&&"):
            op = self.take().kind
            node = Node("binary", op, (node, self.equality()))

        return node

    def equality(self):
        node = self.comparison()

        while self.peek("===") or self.peek("!=="):
            op = self.take().kind
            node = Node("binary", op, (node, self.comparison()))

        return node

    def comparison(self):
        node = self.addition()

        while self.peek("<") or self.peek("<=") or self.peek(">") or self.peek(">="):
            op = self.take().kind
            node = Node("binary", op, (node, self.addition()))

        return node

    def addition(self):
        node = self.multiplication()

        while self.peek("+") or self.peek("-"):
            op = self.take().kind
            node = Node("binary", op, (node, self.multiplication()))

        return node

    def multiplication(self):
        node = self.unary()

        while self.peek("*") or self.peek("/") or self.peek("%"):
            op = self.take().kind
            node = Node("binary", op, (node, self.unary()))

        return node

    def unary(self):
        if self.peek("!") or self.peek("+") or self.peek("-"):
            op = self.take().kind
            return Node("unary", op, (self.unary(),))

        return self.primary()

    def primary(self):
        if self.peek("NUMBER"):
            return Node("number", self.take("NUMBER").value)

        if self.peek("TRUE"):
            self.take("TRUE")
            return Node("boolean", True)

        if self.peek("FALSE"):
            self.take("FALSE")
            return Node("boolean", False)

        if self.peek("IDENT"):
            return Node("variable", self.take("IDENT").value)

        if self.peek("("):
            self.take("(")
            node = self.expression()
            self.take(")")
            return node

        token = self.peek()

        raise MiniJSError(
            f"Syntax error at position {token.position}: "
            f"expected expression, got {token.kind}"
        )
