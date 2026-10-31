"""Just enough SQL lexing for the console: split a script into statements and
say what kind each is. It only skips what can hide a semicolon (quotes, dollar
quotes, comments); it parses nothing, and it is not a security boundary: the
workspace role is (5.3)."""

import re
from dataclasses import dataclass

DDL_WORDS = frozenset(
    [
        "create",
        "alter",
        "drop",
        "truncate",
        "comment",
        "grant",
        "revoke",
        "reindex",
        "cluster",
        "vacuum",
        "analyze",
    ]
)
# Transaction control would end or split the one transaction a request runs in.
TRANSACTION_WORDS = frozenset(
    [
        "begin",
        "start",
        "commit",
        "end",
        "rollback",
        "abort",
        "savepoint",
        "release",
        "prepare",
    ]
)

_DOLLAR = re.compile(r"\$([A-Za-z_][A-Za-z_0-9]*)?\$")


@dataclass(frozen=True)
class Statement:
    text: str
    keyword: str

    @property
    def is_ddl(self) -> bool:
        return self.keyword in DDL_WORDS

    @property
    def is_transaction_control(self) -> bool:
        return self.keyword in TRANSACTION_WORDS


def _first_word(text: str) -> str:
    cleaned = re.sub(r"--[^\n]*|/\*.*?\*/", " ", text, flags=re.S)
    match = re.search(r"[A-Za-z_]+", cleaned)
    return match.group(0).lower() if match else ""


def split(script: str) -> list[Statement]:
    """The statements of a script, without empty ones."""
    statements: list[str] = []
    start = 0
    i = 0
    n = len(script)
    while i < n:
        ch = script[i]
        if ch in "'\"":
            i = script.find(ch, i + 1)
            while i != -1 and i + 1 < n and script[i + 1] == ch:  # doubled quote
                i = script.find(ch, i + 2)
            i = n if i == -1 else i + 1
        elif script.startswith("--", i):
            end = script.find("\n", i)
            i = n if end == -1 else end + 1
        elif script.startswith("/*", i):
            depth, i = 1, i + 2
            while i < n and depth:
                if script.startswith("/*", i):
                    depth, i = depth + 1, i + 2
                elif script.startswith("*/", i):
                    depth, i = depth - 1, i + 2
                else:
                    i += 1
        elif ch == "$" and (tag := _DOLLAR.match(script, i)):
            end = script.find(tag.group(0), tag.end())
            i = n if end == -1 else end + len(tag.group(0))
        elif ch == ";":
            statements.append(script[start:i])
            i += 1
            start = i
        else:
            i += 1
    statements.append(script[start:])
    return [
        Statement(text=text.strip(), keyword=_first_word(text))
        for text in statements
        if _first_word(text)
    ]
