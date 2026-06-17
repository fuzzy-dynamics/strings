#!/usr/bin/env python3
"""Tiny terminal-UI kit for witsoc (presentation only).

Gives witsoc's text output a consistent visual language — status symbols, a
progress bar, boxed banners, checklists, tables — so it reads like an instrument
panel in a terminal and degrades to clean ASCII when piped, redirected, or when
NO_COLOR is set. It renders strings: it computes nothing about a run and never
changes a claim.

Safe by default: color and Unicode are used only on an interactive TTY with a
UTF capable encoding. Overrides:
  NO_COLOR / WITSOC_NO_UI=1   -> never color
  WITSOC_FORCE_UI=1           -> force color (e.g. when the orchestrator renders ANSI)
  WITSOC_ASCII=1              -> never use Unicode glyphs/box-drawing
"""

from __future__ import annotations

import os
import sys
from typing import Sequence

RESET = "\033[0m"
_STYLES = {
    "red": "31", "green": "32", "yellow": "33", "blue": "34",
    "magenta": "35", "cyan": "36", "grey": "90", "bold": "1", "dim": "2",
}

# name -> (unicode glyph, ascii fallback)
_SYM = {
    "ok": ("✓", "[ok]"),
    "fail": ("✗", "[x]"),
    "pause": ("⏸", "[..]"),
    "pending": ("•", "-"),
    "partial": ("◐", "~"),
    "run": ("◷", "[*]"),
    "arrow": ("▶", ">"),
}
_BAR_FILL = ("▰", "#")
_BAR_EMPTY = ("▱", "-")
_BOX = {
    True: dict(tl="┌", tr="┐", bl="└", br="┘", h="─", v="│", ml="├", mr="┤"),
    False: dict(tl="+", tr="+", bl="+", br="+", h="-", v="|", ml="+", mr="+"),
}

# status word -> (symbol name, style)
_STATUS_LOOK = {
    "OK": ("ok", "green"), "PASS": ("ok", "green"), "TRUE": ("ok", "green"),
    "FAIL": ("fail", "red"), "FAILED": ("fail", "red"), "FALSE": ("fail", "red"),
    "PAUSE": ("pause", "yellow"), "PAUSED": ("pause", "yellow"),
    "PENDING": ("pending", "grey"), "SKIP": ("pending", "grey"),
    "PARTIAL": ("partial", "yellow"), "RUN": ("run", "cyan"), "RUNNING": ("run", "cyan"),
}


def color_enabled(stream=None) -> bool:
    if os.environ.get("WITSOC_NO_UI", "").strip() == "1":
        return False
    if os.environ.get("NO_COLOR") is not None:
        return False
    if os.environ.get("WITSOC_FORCE_UI", "").strip() == "1":
        return True
    s = stream if stream is not None else sys.stdout
    try:
        if not s.isatty():
            return False
    except Exception:
        return False
    return os.environ.get("TERM", "") != "dumb"


def unicode_enabled(stream=None) -> bool:
    if os.environ.get("WITSOC_ASCII", "").strip() == "1":
        return False
    s = stream if stream is not None else sys.stdout
    enc = (getattr(s, "encoding", None) or "").lower()
    return "utf" in enc


def _visible_len(text: str) -> int:
    """Length of text ignoring ANSI escape sequences."""
    out, i = 0, 0
    while i < len(text):
        if text[i] == "\033":
            j = text.find("m", i)
            if j != -1:
                i = j + 1
                continue
        out += 1
        i += 1
    return out


class UI:
    """A renderer bound to a (color, unicode) decision. Primitives return
    strings so callers route them to stdout or stderr freely."""

    def __init__(self, color: bool, uni: bool):
        self.color = bool(color)
        self.uni = bool(uni)

    @classmethod
    def for_stream(cls, stream=None) -> "UI":
        return cls(color_enabled(stream), unicode_enabled(stream))

    # --- atoms ----------------------------------------------------------------
    def paint(self, text: str, *styles: str) -> str:
        if not self.color or not styles:
            return text
        codes = ";".join(_STYLES[s] for s in styles if s in _STYLES)
        return f"\033[{codes}m{text}{RESET}" if codes else text

    def glyph(self, name: str) -> str:
        u, a = _SYM.get(name, ("?", "?"))
        return u if self.uni else a

    def status(self, word: str) -> str:
        """A colored symbol for a status/bool word (e.g. 'ok', 'FAILED')."""
        name, style = _STATUS_LOOK.get(str(word).strip().upper(), ("pending", "grey"))
        return self.paint(self.glyph(name), style)

    def bar(self, done: int, total: int, width: int = 12) -> str:
        total = max(int(total or 0), 0)
        done = min(max(int(done or 0), 0), total) if total else 0
        filled = round(width * (done / total)) if total else 0
        fill = _BAR_FILL[0] if self.uni else _BAR_FILL[1]
        empty = _BAR_EMPTY[0] if self.uni else _BAR_EMPTY[1]
        style = "green" if total and done == total else ("yellow" if done else "grey")
        return self.paint(fill * filled + empty * (width - filled), style)

    # --- blocks ---------------------------------------------------------------
    def box(self, title: str, lines: Sequence[str], width: int | None = None) -> str:
        b = _BOX[self.uni]
        body = [str(x) for x in lines]
        inner = max([_visible_len(title) + 2] + [_visible_len(x) for x in body] + [40])
        if width:
            inner = max(inner, width - 4)
        inner = min(inner, 100)
        top = f"{b['tl']}{b['h']} {self.paint(title, 'bold')} {b['h'] * max(inner - _visible_len(title) - 2, 0)}{b['tr']}"
        out = [top]
        for x in body:
            if x == "__rule__":
                out.append(f"{b['ml']}{b['h'] * (inner + 2)}{b['mr']}")
                continue
            pad = inner - _visible_len(x)
            out.append(f"{b['v']} {x}{' ' * max(pad, 0)} {b['v']}")
        out.append(f"{b['bl']}{b['h'] * (inner + 2)}{b['br']}")
        return "\n".join(out)

    def checklist(self, items: Sequence[tuple[str, str]]) -> str:
        """items = [(label, status_word)] rendered as 'SYM label'."""
        return "  ".join(f"{self.status(st)} {label}" for label, st in items)


def for_stream(stream=None) -> UI:
    return UI.for_stream(stream)
