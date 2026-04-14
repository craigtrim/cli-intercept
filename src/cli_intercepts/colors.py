"""ANSI color helpers. Honors NO_COLOR and non-TTY stdout."""

from __future__ import annotations

import os
import sys


def _enabled() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    return sys.stdout.isatty()


ENABLED = _enabled()


# SGR codes. 24-bit colors would be nicer but 8/16-color is universal.
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"

FG = {
    "gray":     "\033[90m",
    "red":      "\033[31m",
    "green":    "\033[32m",
    "yellow":   "\033[33m",
    "blue":     "\033[34m",
    "magenta":  "\033[35m",
    "cyan":     "\033[36m",
    "white":    "\033[37m",
    # bright variants for emphasis
    "bred":     "\033[91m",
    "bgreen":   "\033[92m",
    "byellow":  "\033[93m",
    "bcyan":    "\033[96m",
}


def paint(text: str, *styles: str) -> str:
    """Wrap `text` in the given styles. Styles are keys of FG or 'bold'/'dim'."""
    if not ENABLED or not text:
        return text
    prefix = ""
    for s in styles:
        if s == "bold":
            prefix += BOLD
        elif s == "dim":
            prefix += DIM
        elif s in FG:
            prefix += FG[s]
    return f"{prefix}{text}{RESET}" if prefix else text


# -- semantic shorthands ---------------------------------------------------


def pass_(text: str) -> str:   return paint(text, "bgreen", "bold")
def fail_(text: str) -> str:   return paint(text, "bred", "bold")
def warn_(text: str) -> str:   return paint(text, "byellow", "bold")
def err_(text: str) -> str:    return paint(text, "magenta", "bold")
def info_(text: str) -> str:   return paint(text, "bcyan")
def dim_(text: str) -> str:    return paint(text, "gray")
def bold_(text: str) -> str:   return paint(text, "bold")
