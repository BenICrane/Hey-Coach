#!/usr/bin/env python3
"""
Fill a Hey Coach email template from a JSON file.

The JSON names the template and supplies the words (text slots) and the
numbers for the charts. Text is HTML-escaped; the charts are built here so
their colours and sizes stay the same every week.

Run:
  python3 email_templates/render_email.py email_templates/examples/02-standout-run.json

Writes <name>.html (send as htmlBody) and <name>.txt (send as body) to
email_templates/out/ and prints the subject. Standard library only.
"""

import argparse
import html
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

# --------------------------------------------------------------------------
# Palette: dataviz reference palette, dark mode. The templates use the same
# values inline. Dark by design so Gmail's dark mode leaves it alone.
# --------------------------------------------------------------------------
BG = "#1a1a19"        # surface
TEXT = "#f0efec"      # primary ink
TEXT_2 = "#c3c2b7"    # secondary ink
MUTED = "#898781"     # axis / labels
TRACK = "#2c2c2a"     # unfilled track, rest days
DONE = "#3987e5"      # blue, slot 1 (dark): done
PLANNED = "#184f95"   # blue step 600: planned
OTHER = "#5b5a56"     # de-emphasised comparison bars
WARNING = "#fab219"   # status: warning (always with icon + label)
GOOD = "#0ca30c"      # status: good (always with icon + label)

# Copy limits that keep one email on one phone screen (about 280 x 370 CSS px).
LIMITS = {
    "subject": 32, "kicker": 32, "hero_value": 6, "hero_unit": 16,
    "caption": 80, "focus": 72, "goal": 52,
    "stat1_value": 9, "stat2_value": 9, "stat1_label": 22, "stat2_label": 22,
    "strip_start": 14, "strip_end": 14,
}
MAX_WORDS, MIN_LINES, MAX_LINES = 60, 3, 5


def esc(s):
    return html.escape(str(s), quote=True)


def km(x):
    """24.97 -> '25', 16.86 -> '16.9'."""
    return f"{x:.0f}" if abs(x - round(x)) < 0.05 or x >= 20 else f"{x:.1f}"


# --------------------------------------------------------------------------
# Bars. Gmail drops empty elements, so every segment is a table cell with a
# bgcolor and a 1px non-breaking space.
# --------------------------------------------------------------------------
def _cell(width, color, height, radius="0"):
    return (
        f'<td width="{width}" height="{height}" bgcolor="{color}" '
        f'style="width:{width};height:{height}px;background-color:{color};'
        f'border-radius:{radius};font-size:1px;line-height:1px;mso-line-height-rule:exactly;">&nbsp;</td>'
    )


def _row_table(cells):
    return (
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
        f'style="border-collapse:separate;"><tr>{"".join(cells)}</tr></table>'
    )


def _bar(segments, height, rest):
    """segments: [(percent, colour)]. rest: colour of the remainder.

    A meter (rest = TRACK) is rounded at both ends. A data bar (rest = BG)
    is square at the baseline and rounded at the data end. Touching
    segments are split by a 2px surface gap.
    """
    meter = rest != BG
    segs = [(p, c) for p, c in segments if p >= 0.5]
    used = sum(p for p, _ in segs)
    data_count = len(segs)
    if 100 - used >= 0.5:
        segs.append((100 - used, rest))
    cells = []
    for i, (p, c) in enumerate(segs):
        is_rest = i >= data_count
        if i and not (is_rest and not meter):
            cells.append(_cell("2", BG, height))
        if meter:
            left = "4px" if i == 0 else "0"
            right = "4px" if i == len(segs) - 1 else "0"
        else:
            left = "0"
            right = "4px" if i == data_count - 1 else "0"
        cells.append(_cell(f"{p:.0f}%", c, height, f"{left} {right} {right} {left}"))
    return _row_table(cells)


def _key(color, label):
    return f'<span style="color:{color};">&#9632;</span>&nbsp;{label}'


# --------------------------------------------------------------------------
# Components: JSON key -> HTML. Templates reference them as {{KEY}}.
# --------------------------------------------------------------------------
def progress(d):
    """{"done": 24.97, "planned": 27, "target": 52}"""
    done, planned, target = d["done"], d.get("planned", 0), d["target"]
    done_pct = min(done / target, 1) * 100
    plan_pct = max(min(planned, target - done), 0) / target * 100
    bar = _bar([(done_pct, DONE), (plan_pct, PLANNED)], 12, TRACK)
    keys = _key(DONE, f"{km(done)} km done")
    if plan_pct:
        keys += "&nbsp;&nbsp; " + _key(PLANNED, f"{km(planned)} planned")
    return (
        bar
        + '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr>'
        f'<td style="padding-top:5px;font-size:11px;line-height:14px;color:{TEXT_2};">{keys}</td>'
        f'<td align="right" style="padding-top:5px;font-size:11px;line-height:14px;color:{MUTED};white-space:nowrap;">'
        f'{km(target)} km target</td></tr></table>'
    )


DAY_STYLE = {  # state -> (fill, text colour)
    "done": (DONE, "#ffffff"),
    "planned": (PLANNED, TEXT),
    "rest": (TRACK, MUTED),
    "missed": (TRACK, MUTED),
}


def days(items):
    """[{"label": "M", "km": "17", "state": "done|planned|rest|missed", "today": true}]

    7 items for a week strip (with km), 14 for a streak strip (km optional).
    Today gets a light ring.
    """
    letters, boxes = [], []
    for it in items:
        today = it.get("today", False)
        fill, ink = DAY_STYLE[it["state"]]
        letters.append(
            f'<td align="center" style="padding-bottom:3px;font-size:11px;line-height:13px;'
            f'font-weight:{700 if today else 400};color:{TEXT if today else MUTED};">{esc(it["label"])}</td>'
        )
        text = esc(it["km"]) if it.get("km") else "&nbsp;"
        boxes.append(
            f'<td align="center" height="22" bgcolor="{fill}" style="height:22px;background-color:{fill};'
            f'border:2px solid {TEXT if today else fill};border-radius:5px;'
            f'font-size:11px;line-height:13px;font-weight:600;color:{ink};">{text}</td>'
        )
    return (
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="2" border="0" '
        'style="border-collapse:separate;table-layout:fixed;">'
        f'<tr>{"".join(letters)}</tr><tr>{"".join(boxes)}</tr></table>'
    )


def compare(rows):
    """[{"label": "This run", "value": 16.86, "display": "16.9 km", "highlight": true}]

    Highlight one bar; the others stay grey (emphasis, not a palette).
    """
    top = max(r["value"] for r in rows)
    out = []
    for r in rows:
        hi = r.get("highlight", False)
        bar = _bar([(r["value"] / top * 100, DONE if hi else OTHER)], 8, BG)
        out.append(
            f'<tr><td style="padding-top:5px;font-size:12px;line-height:15px;color:{TEXT if hi else TEXT_2};">{esc(r["label"])}</td>'
            f'<td align="right" style="padding-top:5px;font-size:12px;line-height:15px;white-space:nowrap;'
            f'font-weight:{700 if hi else 400};color:{TEXT if hi else TEXT_2};">{esc(r["display"])}</td></tr>'
            f'<tr><td colspan="2" style="padding-top:3px;">{bar}</td></tr>'
        )
    return (
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">'
        + "".join(out) + "</table>"
    )


def meter(d):
    """{"value": 64, "target": 80, "label": "now"} - percent with a target tick."""
    v, t, h = d["value"], d["target"], 12
    now_key = _key(DONE, f"{v:.0f}% " + esc(d.get("label", "now")))
    if v < t:
        cells = [
            _cell(f"{v:.0f}%", DONE, h, "4px 0 0 4px"), _cell("2", BG, h),
            _cell(f"{t - v:.0f}%", TRACK, h), _cell("3", TEXT, h),
            _cell(f"{100 - t:.0f}%", TRACK, h, "0 4px 4px 0"),
        ]
    else:
        cells = [
            _cell(f"{t:.0f}%", DONE, h, "4px 0 0 4px"), _cell("3", TEXT, h),
            _cell(f"{v - t:.0f}%", DONE, h),
        ]
        if v < 100:
            cells += [_cell("2", BG, h), _cell(f"{100 - v:.0f}%", TRACK, h, "0 4px 4px 0")]
    return (
        _row_table(cells)
        + '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr>'
        f'<td style="padding-top:5px;font-size:11px;line-height:14px;color:{TEXT_2};">'
        f'{now_key}</td>'
        f'<td align="right" style="padding-top:5px;font-size:11px;line-height:14px;color:{TEXT_2};white-space:nowrap;">'
        f'<span style="color:{TEXT};font-weight:700;">|</span>&nbsp;{t:.0f}% target</td></tr></table>'
    )


def sessions(rows):
    """[{"day": "Wed", "session": "Easy, HR under 150", "km": "11 km"}] - up to 3 rows."""
    out = []
    for i, r in enumerate(rows[:3]):
        line = f"border-top:1px solid {TRACK};" if i else ""
        out.append(
            f'<tr><td width="40" style="{line}padding:6px 0;font-size:13px;line-height:16px;font-weight:700;color:{TEXT};">{esc(r["day"])}</td>'
            f'<td style="{line}padding:6px 8px;font-size:13px;line-height:16px;color:{TEXT_2};">{esc(r["session"])}</td>'
            f'<td align="right" style="{line}padding:6px 0;font-size:13px;line-height:16px;font-weight:700;color:{TEXT};white-space:nowrap;">{esc(r["km"])}</td></tr>'
        )
    return (
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">'
        + "".join(out) + "</table>"
    )


def status(d):
    """{"state": "warning|good", "label": "Below the 80% target"} - icon + label, never colour alone."""
    icon = {"warning": (WARNING, "&#9650;"), "good": (GOOD, "&#10003;")}[d["state"]]
    return (
        f'<span style="color:{icon[0]};font-size:11px;">{icon[1]}</span>'
        f'&nbsp;<span style="color:{TEXT};font-weight:600;">{esc(d["label"])}</span>'
    )


COMPONENTS = {
    "progress": progress, "days": days, "compare": compare,
    "meter": meter, "sessions": sessions, "status": status,
}


# --------------------------------------------------------------------------
# Render
# --------------------------------------------------------------------------
def check_copy(data):
    problems = []
    for key, limit in LIMITS.items():
        if key in data and len(str(data[key])) > limit:
            problems.append(f"'{key}' is {len(str(data[key]))} chars (max {limit}): {data[key]!r}")
    lines = data.get("message", [])
    words = sum(len(line.split()) for line in lines)
    if not MIN_LINES <= len(lines) <= MAX_LINES:
        problems.append(f"'message' has {len(lines)} lines (want {MIN_LINES}-{MAX_LINES})")
    if words >= MAX_WORDS:
        problems.append(f"'message' has {words} words (want under {MAX_WORDS})")
    return problems


def render(data):
    template = (HERE / f"{data['template']}.html").read_text(encoding="utf-8")
    data = dict(data)
    data.setdefault("preheader", data["message"][0] if data.get("message") else "")
    missing = []

    def fill(match):
        key = match.group(1).lower()
        if key in COMPONENTS:
            if key not in data:
                missing.append(key)
                return ""
            return COMPONENTS[key](data[key])
        if key not in data:
            missing.append(key)
            return ""
        return esc(data[key])

    out = re.sub(r"\{\{([A-Z0-9_]+)\}\}", fill, template)
    if missing:
        raise SystemExit(f"Missing values for {data['template']}: {', '.join(sorted(set(missing)))}")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("data", help="JSON file with the template name, text slots and chart data")
    ap.add_argument("--out", default=str(HERE / "out"), help="output folder (default: email_templates/out)")
    ap.add_argument("--strict", action="store_true", help="fail (instead of warn) when copy is too long")
    args = ap.parse_args()

    data = json.loads(Path(args.data).read_text(encoding="utf-8"))
    problems = check_copy(data)
    for p in problems:
        print(f"Warning: {p}", file=sys.stderr)
    if problems and args.strict:
        raise SystemExit("Copy too long for one phone screen; shorten it and re-run.")

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    name = Path(args.data).stem
    (out_dir / f"{name}.html").write_text(render(data), encoding="utf-8")
    (out_dir / f"{name}.txt").write_text("\n\n".join(data["message"]) + "\n", encoding="utf-8")
    print(f"Subject: {data['subject']}")
    print(f"HTML:    {out_dir / (name + '.html')}")
    print(f"Text:    {out_dir / (name + '.txt')}")


if __name__ == "__main__":
    sys.exit(main())
