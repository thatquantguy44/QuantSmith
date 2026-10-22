"""Strict YAML-subset reader for SFMeridian configuration and query front-matter.

Spec ``0114`` REQ-002. One reader turns text into data for both the plugin
configuration and the front-matter of every query, and it fails closed: any
construct outside the documented subset raises :class:`YamlSubsetError` with
the source and line instead of being guessed at.

Supported:

* block mappings (``key: value``) and block sequences (``- item``), including
  sequences of mappings and a sequence directly under its key at the same
  indent;
* flow lists ``[a, b]`` and flow maps ``{k: v}`` of scalars, nested, on one line;
* plain scalars (``null``/``~``, ``true``/``false``, integers, floats, strings)
  and single- or double-quoted strings;
* folded (``>``) and literal (``|``) block scalars, with optional ``-`` chomping;
* ``#`` comments outside quotes.

Rejected: anchors, aliases, tags, directives, document markers, complex keys,
tabs in indentation, duplicate keys, and multi-line flow collections. Dates
stay strings; callers that need a date validate the string.
"""

from __future__ import annotations

import re
from typing import Any

__all__ = ["YamlSubsetError", "parse", "parse_scalar"]


class YamlSubsetError(ValueError):
    """Raised when text falls outside the supported subset."""

    def __init__(self, source: str, line: int, message: str) -> None:
        super().__init__(f"{source}:{line}: {message}")
        self.source = source
        self.line = line
        self.message = message


_INT_RE = re.compile(r"[-+]?(0|[1-9][0-9]*)")
_FLOAT_RE = re.compile(r"[-+]?([0-9]+\.[0-9]*|\.[0-9]+|[0-9]+)([eE][-+]?[0-9]+)?")
_KEY_RE = re.compile(r"^([^\s'\"\[\]{},#&*!|>%@`][^:#]*?|'[^']*'|\"[^\"]*\")\s*:(\s|$)")
_FORBIDDEN_START = ("&", "*", "!", "%", "@", "`", "?")


def _strip_comment(text: str) -> str:
    """Drop a ``#`` comment that is outside quotes and starts a token."""
    out: list[str] = []
    quote: str | None = None
    prev = " "
    for ch in text:
        if quote:
            out.append(ch)
            if ch == quote:
                quote = None
        elif ch in ("'", '"') and (prev in " \t[{,:" or not out):
            quote = ch
            out.append(ch)
        elif ch == "#" and prev in " \t":
            break
        else:
            out.append(ch)
        prev = ch
    return "".join(out).rstrip()


def _unquote(text: str, source: str, line: int) -> str:
    if text[0] == "'":
        if len(text) < 2 or text[-1] != "'":
            raise YamlSubsetError(source, line, f"unterminated quoted string {text!r}")
        return text[1:-1].replace("''", "'")
    if len(text) < 2 or text[-1] != '"':
        raise YamlSubsetError(source, line, f"unterminated quoted string {text!r}")
    body = text[1:-1]
    out: list[str] = []
    i = 0
    escapes = {"n": "\n", "t": "\t", '"': '"', "\\": "\\", "/": "/"}
    while i < len(body):
        ch = body[i]
        if ch == "\\":
            if i + 1 >= len(body) or body[i + 1] not in escapes:
                raise YamlSubsetError(source, line, f"unsupported escape in {text!r}")
            out.append(escapes[body[i + 1]])
            i += 2
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def parse_scalar(text: str, source: str = "<text>", line: int = 0) -> Any:
    """Convert one scalar token to a Python value."""
    text = text.strip()
    if text == "":
        return None
    if text[0] in ("'", '"'):
        return _unquote(text, source, line)
    if text.startswith(_FORBIDDEN_START):
        raise YamlSubsetError(source, line, f"unsupported YAML construct {text[0]!r}")
    if text in ("null", "~", "Null", "NULL"):
        return None
    if text in ("true", "True", "TRUE"):
        return True
    if text in ("false", "False", "FALSE"):
        return False
    if _INT_RE.fullmatch(text):
        return int(text)
    if _FLOAT_RE.fullmatch(text) and any(c in text for c in ".eE"):
        return float(text)
    return text


# --------------------------------------------------------------------------
# Flow collections
# --------------------------------------------------------------------------

class _Flow:
    def __init__(self, text: str, source: str, line: int) -> None:
        self.text = text
        self.pos = 0
        self.source = source
        self.line = line

    def error(self, message: str) -> YamlSubsetError:
        return YamlSubsetError(self.source, self.line, f"{message} in flow {self.text!r}")

    def ws(self) -> None:
        while self.pos < len(self.text) and self.text[self.pos] in " \t":
            self.pos += 1

    def value(self) -> Any:
        self.ws()
        if self.pos >= len(self.text):
            raise self.error("unexpected end")
        ch = self.text[self.pos]
        if ch == "[":
            return self.seq()
        if ch == "{":
            return self.mapping()
        return self.scalar(stops=",]}")

    def scalar(self, stops: str) -> Any:
        self.ws()
        start = self.pos
        if self.pos < len(self.text) and self.text[self.pos] in ("'", '"'):
            quote = self.text[self.pos]
            self.pos += 1
            while self.pos < len(self.text):
                if self.text[self.pos] == quote:
                    if quote == "'" and self.text[self.pos + 1:self.pos + 2] == "'":
                        self.pos += 2
                        continue
                    break
                if quote == '"' and self.text[self.pos] == "\\":
                    self.pos += 1
                self.pos += 1
            if self.pos >= len(self.text):
                raise self.error("unterminated string")
            self.pos += 1
            return _unquote(self.text[start:self.pos], self.source, self.line)
        while self.pos < len(self.text) and self.text[self.pos] not in stops:
            if self.text[self.pos] in "[{":
                raise self.error("nested collection without separator")
            self.pos += 1
        return parse_scalar(self.text[start:self.pos], self.source, self.line)

    def seq(self) -> list[Any]:
        self.pos += 1
        items: list[Any] = []
        self.ws()
        if self.text[self.pos:self.pos + 1] == "]":
            self.pos += 1
            return items
        while True:
            items.append(self.value())
            self.ws()
            ch = self.text[self.pos:self.pos + 1]
            if ch == ",":
                self.pos += 1
                continue
            if ch == "]":
                self.pos += 1
                return items
            raise self.error("expected ',' or ']'")

    def mapping(self) -> dict:
        self.pos += 1
        out: dict = {}
        self.ws()
        if self.text[self.pos:self.pos + 1] == "}":
            self.pos += 1
            return out
        while True:
            key = self.scalar(stops=":,}")
            self.ws()
            if self.text[self.pos:self.pos + 1] != ":":
                raise self.error("expected ':' after key")
            self.pos += 1
            if not isinstance(key, str):
                key = str(key)
            if key in out:
                raise self.error(f"duplicate key {key!r}")
            out[key] = self.value()
            self.ws()
            ch = self.text[self.pos:self.pos + 1]
            if ch == ",":
                self.pos += 1
                continue
            if ch == "}":
                self.pos += 1
                return out
            raise self.error("expected ',' or '}'")


def _flow(text: str, source: str, line: int) -> Any:
    parser = _Flow(text, source, line)
    value = parser.value()
    parser.ws()
    if parser.pos != len(text):
        raise YamlSubsetError(source, line, f"trailing text after flow collection {text!r} "
                              "(multi-line flow collections are not supported)")
    return value


# --------------------------------------------------------------------------
# Block structure
# --------------------------------------------------------------------------

_Line = tuple[int, str, int]  # indent, content, line number


def _lines(text: str, source: str) -> tuple[list[_Line], list[str]]:
    out: list[_Line] = []
    raw_lines = text.splitlines()
    for number, raw in enumerate(raw_lines, start=1):
        leading = raw[: len(raw) - len(raw.lstrip(" \t"))]
        if "\t" in leading:
            raise YamlSubsetError(source, number, "tab in indentation; use spaces")
        content = _strip_comment(raw)
        if not content.strip():
            continue
        stripped = content.strip()
        if stripped in ("---", "...") or stripped.startswith("%"):
            raise YamlSubsetError(source, number, "document markers and directives are not supported")
        out.append((len(content) - len(content.lstrip(" ")), stripped, number))
    return out, raw_lines


class _Block:
    def __init__(self, lines: list[_Line], raw: list[str], source: str) -> None:
        self.lines = lines
        self.raw = raw
        self.source = source
        self.i = 0

    def error(self, line: int, message: str) -> YamlSubsetError:
        return YamlSubsetError(self.source, line, message)

    def node(self, indent: int) -> Any:
        _, content, _ = self.lines[self.i]
        if content == "-" or content.startswith("- "):
            return self.sequence(indent)
        return self.mapping(indent)

    def _value(self, text: str, indent: int, line: int, allow_same_indent_seq: bool) -> Any:
        if text in (">", "|", ">-", "|-", ">+", "|+"):
            return self.block_scalar(text, indent, line)
        if text.startswith(("[", "{")):
            return _flow(text, self.source, line)
        if text:
            return parse_scalar(text, self.source, line)
        # Empty value: a nested block, a same-indent sequence, or null.
        if self.i < len(self.lines):
            nxt_indent, nxt, _ = self.lines[self.i]
            if nxt_indent > indent:
                return self.node(nxt_indent)
            if allow_same_indent_seq and nxt_indent == indent and (nxt == "-" or nxt.startswith("- ")):
                return self.sequence(indent)
        return None

    def mapping(self, indent: int) -> dict:
        out: dict = {}
        while self.i < len(self.lines):
            line_indent, content, number = self.lines[self.i]
            if line_indent < indent:
                break
            if line_indent > indent:
                raise self.error(number, "unexpected indentation")
            if content == "-" or content.startswith("- "):
                break
            match = _KEY_RE.match(content)
            if not match:
                raise self.error(number, f"expected 'key: value', got {content!r}")
            key_text = match.group(1).strip()
            key = _unquote(key_text, self.source, number) if key_text[0] in "'\"" else key_text
            if key in out:
                raise self.error(number, f"duplicate key {key!r}")
            value_text = content[match.end():].strip()
            self.i += 1
            out[key] = self._value(value_text, indent, number, allow_same_indent_seq=True)
        return out

    def sequence(self, indent: int) -> list:
        out: list = []
        while self.i < len(self.lines):
            line_indent, content, number = self.lines[self.i]
            if line_indent < indent:
                break
            if line_indent > indent:
                raise self.error(number, "unexpected indentation")
            if not (content == "-" or content.startswith("- ")):
                break
            body = content[1:].strip()
            if body and body[0] not in "'\"[{" and _KEY_RE.match(body):
                # A mapping item: re-read the body as the first key at indent + 2.
                item_indent = indent + 2
                self.lines[self.i] = (item_indent, body, number)
                out.append(self.mapping(item_indent))
                continue
            self.i += 1
            out.append(self._value(body, indent, number, allow_same_indent_seq=False))
        return out

    def block_scalar(self, style: str, indent: int, line: int) -> str:
        parts: list[str] = []
        first = line  # raw line numbers are 1-based; the header is ``line``
        number = first + 1
        block_indent: int | None = None
        while number <= len(self.raw):
            raw = self.raw[number - 1]
            if raw.strip() == "":
                parts.append("")
                number += 1
                continue
            this_indent = len(raw) - len(raw.lstrip(" "))
            if this_indent <= indent:
                break
            if block_indent is None:
                block_indent = this_indent
            if this_indent < block_indent:
                break
            parts.append(raw[block_indent:].rstrip())
            number += 1
        while self.i < len(self.lines) and self.lines[self.i][2] < number:
            self.i += 1
        while parts and parts[-1] == "":
            parts.pop()
        if style.startswith("|"):
            text = "\n".join(parts)
        else:
            text = " ".join(p for p in parts if p != "")
        keep_newline = not style.endswith("-")
        return text + ("\n" if keep_newline and text else "")


def parse(text: str, source: str = "<text>") -> Any:
    """Parse ``text`` in the supported subset; an empty document is ``{}``."""
    lines, raw = _lines(text, source)
    if not lines:
        return {}
    block = _Block(lines, raw, source)
    root_indent = lines[0][0]
    if root_indent != 0:
        raise YamlSubsetError(source, lines[0][2], "document must start at column 0")
    value = block.node(0)
    if block.i < len(block.lines):
        _, content, number = block.lines[block.i]
        raise YamlSubsetError(source, number, f"unexpected content {content!r}")
    return value
