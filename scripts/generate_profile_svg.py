#!/usr/bin/env python3
"""Generate assets/profile-terminal.svg — a terminal-style GitHub profile
card with the ASCII portrait on the left and system-style info on the
right, including a live "Uptime" field computed from BIRTH_DATE.

This script is the single source of truth for the SVG: do not hand-edit
the generated file, edit this script (and its constants below) instead.

Usage:
    python scripts/generate_profile_svg.py

Requires Python 3.9+ (stdlib `zoneinfo`). On Windows, install the
`tzdata` package (see scripts/requirements.txt) so the IANA time zone
database is available; Linux CI runners ship it already.
"""

from __future__ import annotations

import calendar
import sys
import textwrap
from datetime import date, datetime
from pathlib import Path
from xml.dom import minidom
from xml.sax.saxutils import escape as xml_escape

try:
    from zoneinfo import ZoneInfo
except ImportError as exc:  # pragma: no cover
    raise SystemExit("Python 3.9+ with the zoneinfo module is required") from exc

ROOT = Path(__file__).resolve().parent.parent
ASCII_PATH = ROOT / "ascii_portrait.txt"
SVG_OUT = ROOT / "assets" / "profile-terminal.svg"

# Change the birth date used for the Uptime field here.
BIRTH_DATE = date(2005, 1, 23)
TIMEZONE = "Europe/Oslo"

# --- Canvas ----------------------------------------------------------------
WIDTH, HEIGHT = 1800, 900
CENTER_Y = HEIGHT / 2
BG_COLOR = "#0a0b10"
FONT_FAMILY = "'Cascadia Code','Cascadia Mono',Consolas,'Courier New',monospace"
CHAR_ASPECT = 0.6  # monospace glyph advance width, as a fraction of font-size

# --- Palette (terminal-inspired) -------------------------------------------
COLOR_PORTRAIT = "#ffffff"
COLOR_NAME = "#ffffff"
COLOR_ROLE = "#e5b567"      # amber / orange
COLOR_LABEL = "#e06c75"     # muted terminal red
COLOR_VALUE = "#c9ccd6"     # light gray
COLOR_PROMPT = "#6ee7b7"    # green
COLOR_CMD = "#e8e9ee"       # near-white command text
COLOR_LINK = "#7aa2f7"      # terminal blue
COLOR_MUTED = "#565a6e"
COLOR_DOT_LEADER = "#565a6e"  # dim separator dots between label and value
COLOR_DIVIDER = "#ffffff"

# --- Layout ------------------------------------------------------------------
STAGE_PAD_X = 80
COL_GAP = 46

PORTRAIT_FONT = 15
PORTRAIT_LINE_H = 15

PROMPT_FONT = 17
NAME_FONT = 46
ROLE_FONT = 21
SYSINFO_FONT = 18
GHROW_FONT = 18

DOT_LEADER_CHAR = "."
DOT_LEADER_GAP = 9  # dot columns reserved after the longest label
SYSINFO_ROW_GAP = 8
SYSINFO_LINE_H = SYSINFO_FONT * 1.3
SYSINFO_CHAR_W = SYSINFO_FONT * CHAR_ASPECT
BLOCK_GAP = 26

NAME_TEXT = "Olav Leek"
ROLE_TEXT = "Aspiring Finance & Business Analytics"
GH_AT = "github.com/"
GH_HANDLE = "OlavKL"


def compute_uptime(birth: date, today: date) -> tuple[int, int, int]:
    """Complete calendar years / months / remaining days between two dates.

    Pure calendar-field subtraction (not day-count division), so a
    birthday on the 31st into a 30-day month still borrows correctly.
    """
    if today < birth:
        raise ValueError("birth date is in the future relative to today")

    years = today.year - birth.year
    months = today.month - birth.month
    days = today.day - birth.day

    if days < 0:
        months -= 1
        prev_month = today.month - 1 or 12
        prev_year = today.year if today.month > 1 else today.year - 1
        days += calendar.monthrange(prev_year, prev_month)[1]

    if months < 0:
        years -= 1
        months += 12

    return years, months, days


def load_ascii_portrait() -> list[str]:
    if not ASCII_PATH.exists():
        raise SystemExit(f"ASCII portrait not found: {ASCII_PATH}")
    text = ASCII_PATH.read_text(encoding="utf-8")
    lines = text.split("\n")
    while lines and lines[-1] == "":
        lines.pop()
    if not lines:
        raise SystemExit(f"ASCII portrait is empty: {ASCII_PATH}")
    return lines


# --- Layout events -----------------------------------------------------------
# Each event describes one visual row; render() turns the list into SVG
# markup while accumulating a y-cursor, so the exact same increments are
# used both to measure the block's total height and to place it.

def get_sysinfo_entries(uptime_text: str) -> list[tuple[str, str]]:
    return [
        ("Uptime", uptime_text),
        ("Education", "BSc Economics & Business Administration"),
        ("Interests", "Investing, Real Estate, Business Analytics"),
        ("Experience", "Technical Support, Fiber Networks & Wi-Fi"),
        ("Side Quests", "iOS Jailbreaking, Crypto Mining, Web Scraping, Automation"),
        ("Languages", "Python, SQL"),
    ]


def dot_leader_target_col(sysinfo_entries: list[tuple[str, str]]) -> int:
    """Character column every value must start at.

    Automatically derived from the longest label so a fixed number of
    dot columns (DOT_LEADER_GAP) always follows it, and shorter labels
    pick up correspondingly more dots to reach the same column.
    """
    return max(len(label) for label, _ in sysinfo_entries) + DOT_LEADER_GAP


def build_info_events(
    sysinfo_entries: list[tuple[str, str]], target_col: int, value_max_chars: int
) -> list[tuple]:
    events: list[tuple] = [
        ("prompt", [("~", COLOR_LINK), (" $ ", COLOR_PROMPT), ("whoami", COLOR_CMD)], PROMPT_FONT * 1.2, 6),
        ("name", NAME_TEXT, NAME_FONT * 1.15, 6),
        ("role", ROLE_TEXT, ROLE_FONT * 1.2, BLOCK_GAP),
    ]

    for i, (label, value) in enumerate(sysinfo_entries):
        wrapped = textwrap.wrap(value, width=value_max_chars) or [""]
        dots = DOT_LEADER_CHAR * max(1, target_col - len(label))
        gap_after = SYSINFO_ROW_GAP if i < len(sysinfo_entries) - 1 else BLOCK_GAP
        events.append(("sysrow", label, dots, wrapped, gap_after))

    events.append(
        ("prompt", [("~", COLOR_LINK), (" $ ", COLOR_PROMPT), ("gh profile", COLOR_CMD)], PROMPT_FONT * 1.2, 4)
    )
    events.append(("ghrow", None, GHROW_FONT * 1.2, 0))
    return events


def render_info_events(events: list[tuple], start_y: float, x_label: float, x_value: float, emit: bool):
    y = start_y
    parts: list[str] = []

    for ev in events:
        kind = ev[0]

        if kind == "prompt":
            _, spans, line_h, gap_after = ev
            y += line_h
            if emit:
                tspans = "".join(
                    f'<tspan fill="{color}">{xml_escape(text)}</tspan>' for text, color in spans
                )
                parts.append(
                    f'<text x="{x_label:.1f}" y="{y:.1f}" font-family="{FONT_FAMILY}" '
                    f'font-size="{PROMPT_FONT}" font-weight="600">{tspans}</text>'
                )
            y += gap_after

        elif kind == "name":
            _, text, line_h, gap_after = ev
            y += line_h
            if emit:
                parts.append(
                    f'<text x="{x_label:.1f}" y="{y:.1f}" font-family="{FONT_FAMILY}" '
                    f'font-size="{NAME_FONT}" font-weight="600" fill="{COLOR_NAME}">'
                    f'{xml_escape(text)}</text>'
                )
            y += gap_after

        elif kind == "role":
            _, text, line_h, gap_after = ev
            y += line_h
            if emit:
                parts.append(
                    f'<text x="{x_label:.1f}" y="{y:.1f}" font-family="{FONT_FAMILY}" '
                    f'font-size="{ROLE_FONT}" fill="{COLOR_ROLE}">{xml_escape(text)}</text>'
                )
            y += gap_after

        elif kind == "sysrow":
            _, label, dots, wrapped_lines, gap_after = ev
            first_baseline = None
            continuation_tspans = []
            for j, line_text in enumerate(wrapped_lines):
                y += SYSINFO_LINE_H
                if j == 0:
                    first_baseline = y
                else:
                    # Wrapped continuation lines align under the value's
                    # start column, not under the label.
                    continuation_tspans.append(
                        f'<tspan x="{x_value:.1f}" y="{y:.1f}" fill="{COLOR_VALUE}">'
                        f'{xml_escape(line_text)}</tspan>'
                    )
            if emit:
                first_value = wrapped_lines[0] if wrapped_lines else ""
                # Lock the label and dot-leader segments to their exact
                # intended pixel widths via textLength, so the value
                # column starts at the same x on every renderer/font
                # instead of relying on an assumed character-advance
                # ratio (which drifts slightly across fonts).
                label_len = f'{len(label) * SYSINFO_CHAR_W:.2f}'
                dots_len = f'{len(dots) * SYSINFO_CHAR_W:.2f}'
                parts.append(
                    f'<text x="{x_label:.1f}" y="{first_baseline:.1f}" font-family="{FONT_FAMILY}" '
                    f'font-size="{SYSINFO_FONT}">'
                    f'<tspan fill="{COLOR_LABEL}" font-weight="600" '
                    f'textLength="{label_len}" lengthAdjust="spacing">{xml_escape(label)}</tspan>'
                    f'<tspan fill="{COLOR_DOT_LEADER}" '
                    f'textLength="{dots_len}" lengthAdjust="spacing">{xml_escape(dots)}</tspan>'
                    f'<tspan fill="{COLOR_VALUE}">{xml_escape(first_value)}</tspan>'
                    f'{"".join(continuation_tspans)}'
                    f'</text>'
                )
            y += gap_after

        elif kind == "ghrow":
            _, _, line_h, gap_after = ev
            y += line_h
            if emit:
                handle_x = x_label + len(GH_AT) * GHROW_FONT * CHAR_ASPECT
                cursor_x = handle_x + len(GH_HANDLE) * GHROW_FONT * CHAR_ASPECT + 6
                parts.append(
                    f'<text x="{x_label:.1f}" y="{y:.1f}" font-family="{FONT_FAMILY}" '
                    f'font-size="{GHROW_FONT}" fill="{COLOR_MUTED}">{xml_escape(GH_AT)}'
                    f'<tspan fill="{COLOR_LINK}" font-weight="600">{xml_escape(GH_HANDLE)}</tspan></text>'
                )
                parts.append(
                    f'<rect x="{cursor_x:.1f}" y="{y - GHROW_FONT:.1f}" width="11" height="{GHROW_FONT + 4}" '
                    f'fill="{COLOR_LINK}"/>'
                )
            y += gap_after

        else:  # pragma: no cover - defensive
            raise ValueError(f"unknown layout event kind: {kind!r}")

    return y - start_y, parts


def build_svg(uptime_text: str) -> str:
    portrait_lines = load_ascii_portrait()
    portrait_char_w = PORTRAIT_FONT * CHAR_ASPECT
    max_line_len = max(len(line) for line in portrait_lines)
    portrait_width = max_line_len * portrait_char_w
    portrait_block_h = len(portrait_lines) * PORTRAIT_LINE_H

    portrait_x = STAGE_PAD_X
    portrait_top_y = CENTER_Y - portrait_block_h / 2

    divider_x = portrait_x + portrait_width + COL_GAP
    divider_y1 = portrait_top_y
    divider_y2 = portrait_top_y + portrait_block_h

    sysinfo_entries = get_sysinfo_entries(uptime_text)
    target_col = dot_leader_target_col(sysinfo_entries)

    info_x = divider_x + 1 + COL_GAP
    label_x = info_x
    value_x = info_x + target_col * SYSINFO_CHAR_W
    info_col_width = WIDTH - STAGE_PAD_X - info_x
    value_col_width = info_col_width - target_col * SYSINFO_CHAR_W
    value_max_chars = max(10, int(value_col_width / SYSINFO_CHAR_W))

    events = build_info_events(sysinfo_entries, target_col, value_max_chars)
    total_h, _ = render_info_events(events, 0, label_x, value_x, emit=False)
    info_top_y = CENTER_Y - total_h / 2
    _, info_parts = render_info_events(events, info_top_y, label_x, value_x, emit=True)

    portrait_parts = []
    for i, line in enumerate(portrait_lines):
        baseline = portrait_top_y + PORTRAIT_LINE_H * (i + 1)
        portrait_parts.append(
            f'<text x="{portrait_x}" y="{baseline:.1f}" xml:space="preserve" '
            f'font-family="{FONT_FAMILY}" font-size="{PORTRAIT_FONT}" '
            f'fill="{COLOR_PORTRAIT}">{xml_escape(line)}</text>'
        )

    svg = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-label="Olav Leek terminal profile">
<title>Olav Leek — terminal profile</title>
<style>
text {{ font-variant-ligatures: none; font-feature-settings: "liga" 0, "clig" 0, "calt" 0, "dlig" 0; }}
</style>
<rect width="{WIDTH}" height="{HEIGHT}" fill="{BG_COLOR}"/>
<g>
{chr(10).join(portrait_parts)}
</g>
<line x1="{divider_x:.1f}" y1="{divider_y1:.1f}" x2="{divider_x:.1f}" y2="{divider_y2:.1f}" stroke="{COLOR_DIVIDER}" stroke-opacity="0.09" stroke-width="1"/>
<g>
{chr(10).join(info_parts)}
</g>
</svg>
"""
    return svg


def main() -> None:
    try:
        today = datetime.now(ZoneInfo(TIMEZONE)).date()
        years, months, days = compute_uptime(BIRTH_DATE, today)
        uptime_text = f"{years}y {months}mo {days}d"

        svg = build_svg(uptime_text)
        minidom.parseString(svg)  # fail loudly on malformed XML before writing

        SVG_OUT.parent.mkdir(parents=True, exist_ok=True)
        SVG_OUT.write_text(svg, encoding="utf-8", newline="\n")

        if not SVG_OUT.exists() or SVG_OUT.stat().st_size == 0:
            raise SystemExit(f"Wrote {SVG_OUT} but the file is missing or empty")

        print(f"Wrote {SVG_OUT} (Uptime: {uptime_text})")
    except Exception as exc:
        print(f"generate_profile_svg failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
