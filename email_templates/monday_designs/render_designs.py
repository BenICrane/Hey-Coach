#!/usr/bin/env python3
"""
Design experiment: the Monday email (06-monday) in 10 design schemes.

Each theme is a set of colours, fonts and a few layout switches. The chart
and table come from render_email.py with its palette swapped for the
theme's, so the content and sizes match the real template exactly.

Run:
  python3 email_templates/monday_designs/render_designs.py [data.json]

Writes one filled HTML file per theme into this folder. Defaults to
examples/06-monday.json. Standard library only.
"""

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import render_email as R  # noqa: E402

SANS = "Roboto,'Google Sans',system-ui,-apple-system,'Segoe UI',Helvetica,Arial,sans-serif"

# Colour roles (same as render_email.py):
#   bg surface, text primary ink, text2 secondary, muted labels, track rest/rules,
#   accent this week + long run, planned upcoming weeks, other done weeks.
THEMES = [
    dict(slug="01-midnight", name="Midnight", note="The current design: dark, calm, blue",
         bg="#1a1a19", text="#f0efec", text2="#c3c2b7", muted="#898781", track="#2c2c2a",
         accent="#3987e5", planned="#184f95", other="#5b5a56", font=SANS, scheme="dark"),
    dict(slug="02-paper", name="Paper", note="Editorial: warm off-white, serif, brick red",
         bg="#f7f3ea", text="#1d1b17", text2="#4a463e", muted="#857f73", track="#e2dacb",
         accent="#b8432f", planned="#e3b5a8", other="#b5ad9d", font="Georgia,'Times New Roman',serif",
         hero_style="italic", hero_weight=400, hero_size=38, scheme="light", rule="#1d1b17"),
    dict(slug="03-track", name="Track", note="Athletic: black, loud orange, heavy caps",
         bg="#0b0b0b", text="#ffffff", text2="#d0d0d0", muted="#8c8c8c", track="#222222",
         accent="#ff5a1f", planned="#6e2b12", other="#4a4a4a",
         font="'Arial Narrow','Helvetica Neue',Arial,sans-serif", hero_weight=900, hero_size=42,
         upper=True, square=True, scheme="dark"),
    dict(slug="04-trail", name="Trail", note="Outdoors: forest green, ochre, humanist sans",
         bg="#1f2a22", text="#eef0e6", text2="#c4cbb8", muted="#8f9a86", track="#2f3d32",
         accent="#e0b84a", planned="#6b5a24", other="#59665a", font="Verdana,Geneva,sans-serif",
         hero_size=36, scheme="dark"),
    dict(slug="05-nordic", name="Nordic", note="Minimal: white, light weights, cool blue",
         bg="#ffffff", text="#0f1b2d", text2="#46566e", muted="#8491a5", track="#e9eef5",
         accent="#2f6fde", planned="#c2d5f7", other="#c7cfdb",
         font="'Helvetica Neue',Helvetica,Arial,sans-serif", hero_weight=300, hero_size=40, scheme="light"),
    dict(slug="06-sunrise", name="Sunrise", note="Warm: orange header band, peach chart",
         bg="#fff6ef", text="#2b1a12", text2="#6a4a3a", muted="#9c7b6a", track="#f4dfd0",
         accent="#e8590c", planned="#f6c29c", other="#d6bfae", font=SANS, hero_size=38,
         band="#e8590c", band_text="#ffffff", band_text2="#ffe3d1", scheme="light"),
    dict(slug="07-swiss", name="Swiss", note="Grid: black and white, red, thick rules",
         bg="#ffffff", text="#000000", text2="#222222", muted="#666666", track="#e6e6e6",
         accent="#e3000f", planned="#f2b0b4", other="#b8b8b8", font="Helvetica,Arial,sans-serif",
         hero_weight=800, hero_size=40, upper=True, square=True, rule="#000000", rule_px=4, scheme="light"),
    dict(slug="08-terminal", name="Terminal", note="Mono: green on black, prompt-style labels",
         bg="#0c100c", text="#d6f5d6", text2="#9fd49f", muted="#628c62", track="#182318",
         accent="#39ff88", planned="#1f6b3f", other="#3b4f3b",
         font="Menlo,Consolas,'DejaVu Sans Mono','Courier New',monospace", hero_size=36, prompt=True, square=True, small=True, scheme="dark"),
    dict(slug="09-lavender", name="Lavender", note="Soft: pastel violet, rounded white card",
         bg="#f1edfa", text="#2a2340", text2="#5b5275", muted="#8b84a3", track="#e7e2f3",
         accent="#7c5cff", planned="#cdc1ff", other="#c6c0d6",
         font="'Trebuchet MS',Helvetica,Arial,sans-serif", card="#ffffff", scheme="light"),
    dict(slug="10-night-run", name="Night run", note="Neon: deep indigo, hot pink accent",
         bg="#0e0b20", text="#f5f3ff", text2="#c9c3e6", muted="#8a84ad", track="#1e1a3a",
         accent="#ff3d8b", planned="#5c1f48", other="#3e3a5c", font=SANS, hero_weight=800, hero_size=38,
         scheme="dark", rule="#ff3d8b", rule_px=3),
]

PAGE = """<!DOCTYPE html>
<!-- Hey Coach Monday email, design experiment: {name}. {note}. -->
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="{scheme}">
<meta name="supported-color-schemes" content="{scheme}">
<title>{subject}</title>
</head>
<body style="margin:0;padding:0;background-color:{bg};">
<div style="display:none;max-height:0;overflow:hidden;opacity:0;font-size:1px;line-height:1px;color:{bg};">{preheader}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="{bg}" style="background-color:{bg};">
<tr><td align="center" style="padding:{outer_pad};">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="{card}" style="max-width:420px;background-color:{card};border-radius:{card_radius};font-family:{font};color:{text};">
{rule_row}<tr><td style="{head_style}">
<div style="font-size:11px;line-height:14px;font-weight:600;letter-spacing:0.06em;text-transform:uppercase;color:{head_muted};">{kicker}</div>
<div style="padding-top:2px;font-size:{hero_size}px;line-height:{hero_lh}px;font-weight:{hero_weight};font-style:{hero_style};color:{head_text};{hero_case}">{hero_value}<span style="font-size:16px;line-height:20px;font-weight:400;font-style:normal;text-transform:none;color:{head_text2};">&nbsp;{hero_unit}</span></div>
<div style="padding-top:2px;font-size:{cap_size}px;line-height:18px;color:{head_text2};">{caption}</div>
</td></tr>
<tr><td style="padding:{block_pad} {inner_x} 0 {inner_x};">{block}</td></tr>
<tr><td style="padding:10px {inner_x} 0 {inner_x};">{plan}</td></tr>
<tr><td style="padding:8px {inner_x} {inner_bottom} {inner_x};font-size:{goal_size}px;line-height:16px;color:{text2};"><span style="color:{accent};">{arrow}</span>&nbsp;{goal}</td></tr>
</table>
</td></tr>
</table>
</body>
</html>
"""


def render(theme, data):
    t = dict(theme)
    # Swap render_email's palette for the theme's so the chart and table match.
    for const, key in [("BG", "bg"), ("TEXT", "text"), ("TEXT_2", "text2"), ("MUTED", "muted"),
                       ("TRACK", "track"), ("DONE", "accent"), ("PLANNED", "planned"), ("OTHER", "other")]:
        setattr(R, const, t[key])
    block, plan = R.block(data["block"]), R.plan(data["plan"])
    if t.get("square"):
        block = block.replace("border-radius:3px 3px 0 0", "border-radius:0")
    if t.get("small"):  # wide (monospace) fonts: one size down so rows stay on one line
        plan = plan.replace("font-size:12px", "font-size:10px").replace('width="34"', 'width="28"')
    if t.get("rule"):  # heavier total rule in themes with a rule colour
        plan = plan.replace(f"border-top:1px solid {t['muted']}", f"border-top:2px solid {t['rule']}")

    card = t.get("card")
    band = t.get("band")
    hero_size = t.get("hero_size", 40)
    kicker = data["kicker"]
    if t.get("prompt"):
        kicker = "&gt; " + R.esc(kicker)
    else:
        kicker = R.esc(kicker)
    rule = t.get("rule") if t.get("rule_px") else None
    return PAGE.format(
        name=t["name"], note=t["note"], scheme=t["scheme"], bg=t["bg"], font=t["font"],
        text=t["text"], text2=t["text2"], accent=t["accent"],
        subject=R.esc(data["subject"]), preheader=R.esc(data["message"][0]),
        card=card or t["bg"], card_radius="14px" if card else "0",
        outer_pad=("4px" if card else "0 0 10px 0" if band
                   else "0 14px 10px 14px" if t.get("rule_px") else "10px 14px"),
        rule_row=(f'<tr><td height="{t["rule_px"]}" bgcolor="{rule}" style="height:{t["rule_px"]}px;background-color:{rule};'
                  'font-size:1px;line-height:1px;">&nbsp;</td></tr>\n<tr><td height="6" style="height:6px;font-size:1px;line-height:1px;">&nbsp;</td></tr>\n') if rule else "",
        head_style=(f"background-color:{band};padding:8px 14px 8px 14px;" if band
                    else f"padding:{'8px 10px 0 10px' if card else '0'};"),
        cap_size=12 if t.get("small") else 14,
        goal_size=10 if t.get("small") else 12,
        head_text=t.get("band_text", t["text"]) if band else t["text"],
        head_text2=t.get("band_text2", t["text2"]) if band else t["text2"],
        head_muted=t.get("band_text2", t["muted"]) if band else t["muted"],
        kicker=kicker, hero_value=R.esc(data["hero_value"]), hero_unit=R.esc(data["hero_unit"]),
        caption=R.esc(data["caption"]), goal=R.esc(data["goal"]),
        hero_size=hero_size, hero_lh=hero_size + 2, hero_weight=t.get("hero_weight", 700),
        hero_style=t.get("hero_style", "normal"),
        hero_case="text-transform:uppercase;letter-spacing:-0.01em;" if t.get("upper") else "",
        inner_x=("10px" if card else "14px" if band else "0"), inner_bottom="8px" if card else "0",
        block_pad="8px" if (band or card) else "10px",
        block=block, plan=plan, arrow="&gt;" if t.get("prompt") else "&#8594;",
    )


def main():
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE.parent / "examples" / "06-monday.json"
    data = json.loads(src.read_text(encoding="utf-8"))
    for theme in THEMES:
        out = HERE / f"{theme['slug']}.html"
        out.write_text(render(theme, data), encoding="utf-8")
        print(out.name)


if __name__ == "__main__":
    main()
