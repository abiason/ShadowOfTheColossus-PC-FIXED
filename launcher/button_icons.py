# SPDX-License-Identifier: GPL-2.0-or-later
"""Controller button icons for Shadow of the Colossus launcher.

Drawn with ancient carved stone and faded gold relic aesthetics, matching SotC.
Supports PlayStation, Xbox, and Nintendo button layouts.
"""
import os
import sys

# Launcher palette
BG = '#0d0f10'
PANEL = '#14171a'
CARD = '#1b1f23'
LINE = '#2a3036'
TEXT = '#e6e2da'
MUTED = '#8f9499'
GOLD = '#d7c08a'
ACCENT = '#3e5f73'

# Styles
STYLES = ('playstation', 'xbox', 'nintendo')
STYLE_NAMES = {'playstation': 'PlayStation', 'xbox': 'Xbox', 'nintendo': 'Nintendo'}

# Game buttons (PS4) -> SDL buttons
GAME_BUTTONS = {
    'cross': 'a', 'circle': 'b', 'square': 'x', 'triangle': 'y',
    'l1': 'leftshoulder', 'r1': 'rightshoulder',
    'l2': 'lefttrigger', 'r2': 'righttrigger',
    'l3': 'leftstick', 'r3': 'rightstick',
    'options': 'start', 'touchpad': 'touchpad',
    'touchpad_right': 'touchpad',
    'up': 'dpup', 'down': 'dpdown', 'left': 'dpleft', 'right': 'dpright',
}

# Selectable SDL buttons in logical order
PAD_BUTTONS = [
    'a', 'b', 'x', 'y',
    'leftshoulder', 'rightshoulder',
    'lefttrigger', 'righttrigger',
    'leftstick', 'rightstick',
    'back', 'start', 'guide',
    'touchpad', 'misc1',
    'dpup', 'dpdown', 'dpleft', 'dpright',
    'paddle1', 'paddle2', 'paddle3', 'paddle4',
]

# Ancient stone palette
STONE_BODY = '#2c333b'
STONE_SHADOW = '#16191c'
STONE_HIGHLIGHT = '#434d58'
STONE_BED = '#20252b'
STONE_BORDER = '#38424c'
GOLD_ACCENT = '#8a7a55'

# PlayStation face symbol colors (desaturated)
PS_CROSS = '#7293b8'     # azul grisáceo
PS_CIRCLE = '#b85b56'    # rojo teja apagado
PS_SQUARE = '#b3738d'    # rosa viejo
PS_TRIANGLE = '#6f9d7f'  # verde salvia

# Xbox face letter colors (desaturated)
XB_A = '#6a9358'         # verde musgo
XB_B = '#ba5f5a'         # rojo teja
XB_X = '#5e83a6'         # azul pizarra
XB_Y = '#c6a052'         # ocre

# Nintendo colors: ancient GOLD
NIN_COLOR = GOLD

LABELS = {
    'playstation': {
        'a': 'Cross', 'b': 'Circle', 'x': 'Square', 'y': 'Triangle',
        'leftshoulder': 'L1', 'rightshoulder': 'R1',
        'lefttrigger': 'L2', 'righttrigger': 'R2',
        'leftstick': 'L3', 'rightstick': 'R3',
        'back': 'Share', 'start': 'Options', 'guide': 'PS',
        'touchpad': 'Touchpad', 'misc1': 'Mute',
        'dpup': 'D-pad Up', 'dpdown': 'D-pad Down', 'dpleft': 'D-pad Left', 'dpright': 'D-pad Right',
        'paddle1': 'P1', 'paddle2': 'P2', 'paddle3': 'P3', 'paddle4': 'P4',
    },
    'xbox': {
        'a': 'A', 'b': 'B', 'x': 'X', 'y': 'Y',
        'leftshoulder': 'LB', 'rightshoulder': 'RB',
        'lefttrigger': 'LT', 'righttrigger': 'RT',
        'leftstick': 'LS', 'rightstick': 'RS',
        'back': 'View', 'start': 'Menu', 'guide': 'Xbox',
        'touchpad': '—', 'misc1': 'Share',
        'dpup': 'D-pad Up', 'dpdown': 'D-pad Down', 'dpleft': 'D-pad Left', 'dpright': 'D-pad Right',
        'paddle1': 'P1', 'paddle2': 'P2', 'paddle3': 'P3', 'paddle4': 'P4',
    },
    'nintendo': {
        'a': 'B', 'b': 'A', 'x': 'Y', 'y': 'X',
        'leftshoulder': 'L', 'rightshoulder': 'R',
        'lefttrigger': 'ZL', 'righttrigger': 'ZR',
        'leftstick': 'LS', 'rightstick': 'RS',
        'back': '−', 'start': '+', 'guide': 'HOME',
        'touchpad': '—', 'misc1': 'Capture',
        'dpup': 'D-pad Up', 'dpdown': 'D-pad Down', 'dpleft': 'D-pad Left', 'dpright': 'D-pad Right',
        'paddle1': 'P1', 'paddle2': 'P2', 'paddle3': 'P3', 'paddle4': 'P4',
    },
}


def label(button, style) -> str:
    """Returns only the display name of the button in the given style for dropdowns."""
    btn = GAME_BUTTONS.get(button, button)
    st = LABELS.get(style, LABELS['playstation'])
    return st.get(btn, button.upper() if isinstance(button, str) else str(button))


def _stone_disc():
    return [
        ('oval', (0.06, 0.08, 0.94, 0.96), STONE_SHADOW, None, 0),
        ('oval', (0.06, 0.04, 0.94, 0.92), STONE_HIGHLIGHT, None, 0),
        ('oval', (0.06, 0.06, 0.94, 0.94), STONE_BODY, None, 0),
        ('oval', (0.13, 0.13, 0.87, 0.87), None, GOLD_ACCENT, 0.035),
        ('oval', (0.16, 0.16, 0.84, 0.84), STONE_BED, None, 0),
    ]


def _stone_pill(y0=0.25, y1=0.75, r=0.25):
    h = y1 - y0
    rad = r if r is not None else h / 2
    return [
        ('round_rect', (0.06, y0 + 0.02, 0.94, y1 + 0.02), rad, STONE_SHADOW, None, 0),
        ('round_rect', (0.06, y0 - 0.02, 0.94, y1 - 0.02), rad, STONE_HIGHLIGHT, None, 0),
        ('round_rect', (0.06, y0, 0.94, y1), rad, STONE_BODY, None, 0),
        ('round_rect', (0.11, y0 + 0.05, 0.89, y1 - 0.05), max(0.04, rad - 0.04), None, GOLD_ACCENT, 0.03),
        ('round_rect', (0.13, y0 + 0.07, 0.87, y1 - 0.07), max(0.02, rad - 0.06), STONE_BED, None, 0),
    ]


def primitives(button, style):
    """Defines the button icon primitives in normalized 0..1 coordinates."""
    btn = GAME_BUTTONS.get(button, button)
    items = []

    # 1. Face buttons: a, b, x, y
    if btn in ('a', 'b', 'x', 'y'):
        items.extend(_stone_disc())
        if style == 'playstation':
            if btn == 'a':  # Cross
                items.extend([
                    ('line', (0.34 + 0.015, 0.34 + 0.015, 0.66 + 0.015, 0.66 + 0.015), STONE_SHADOW, 0.08),
                    ('line', (0.34 + 0.015, 0.66 + 0.015, 0.66 + 0.015, 0.34 + 0.015), STONE_SHADOW, 0.08),
                    ('line', (0.34, 0.34, 0.66, 0.66), PS_CROSS, 0.08),
                    ('line', (0.34, 0.66, 0.66, 0.34), PS_CROSS, 0.08),
                ])
            elif btn == 'b':  # Circle
                items.extend([
                    ('oval', (0.33 + 0.015, 0.33 + 0.015, 0.67 + 0.015, 0.67 + 0.015), None, STONE_SHADOW, 0.08),
                    ('oval', (0.33, 0.33, 0.67, 0.67), None, PS_CIRCLE, 0.08),
                ])
            elif btn == 'x':  # Square
                items.extend([
                    ('rect', (0.34 + 0.015, 0.34 + 0.015, 0.66 + 0.015, 0.66 + 0.015), None, STONE_SHADOW, 0.08),
                    ('rect', (0.34, 0.34, 0.66, 0.66), None, PS_SQUARE, 0.08),
                ])
            elif btn == 'y':  # Triangle
                pts = [(0.50, 0.31), (0.68, 0.67), (0.32, 0.67)]
                s_pts = [(p[0] + 0.015, p[1] + 0.015) for p in pts]
                items.extend([
                    ('polygon', s_pts, None, STONE_SHADOW, 0.08),
                    ('polygon', pts, None, PS_TRIANGLE, 0.08),
                ])
        elif style == 'xbox':
            colors = {'a': XB_A, 'b': XB_B, 'x': XB_X, 'y': XB_Y}
            letters = {'a': 'A', 'b': 'B', 'x': 'X', 'y': 'Y'}
            c = colors[btn]
            char = letters[btn]
            items.extend([
                ('text', (0.50 + 0.015, 0.50 + 0.015), char, STONE_SHADOW, 0.44, 'bold'),
                ('text', (0.50, 0.50), char, c, 0.44, 'bold'),
            ])
        else:  # nintendo
            letters = {'a': 'B', 'b': 'A', 'x': 'Y', 'y': 'X'}
            char = letters[btn]
            items.extend([
                ('text', (0.50 + 0.015, 0.50 + 0.015), char, STONE_SHADOW, 0.44, 'bold'),
                ('text', (0.50, 0.50), char, NIN_COLOR, 0.44, 'bold'),
            ])
        return items

    # 2. Bumpers: leftshoulder, rightshoulder
    if btn in ('leftshoulder', 'rightshoulder'):
        items.extend([
            ('round_rect', (0.06, 0.26, 0.94, 0.78), 0.14, STONE_SHADOW, None, 0),
            ('round_rect', (0.06, 0.22, 0.94, 0.74), 0.14, STONE_HIGHLIGHT, None, 0),
            ('round_rect', (0.06, 0.24, 0.94, 0.76), 0.14, STONE_BODY, None, 0),
            ('round_rect', (0.11, 0.29, 0.89, 0.71), 0.09, None, GOLD_ACCENT, 0.03),
            ('round_rect', (0.13, 0.31, 0.87, 0.69), 0.07, STONE_BED, None, 0),
        ])
        txt = {'playstation': ('L1' if btn == 'leftshoulder' else 'R1'),
               'xbox': ('LB' if btn == 'leftshoulder' else 'RB'),
               'nintendo': ('L' if btn == 'leftshoulder' else 'R')}[style]
        items.append(('text', (0.50, 0.50), txt, TEXT, 0.30, 'bold'))
        return items

    # 3. Triggers: lefttrigger, righttrigger
    if btn in ('lefttrigger', 'righttrigger'):
        items.extend([
            ('round_rect', (0.12, 0.16, 0.88, 0.88), 0.18, STONE_SHADOW, None, 0),
            ('round_rect', (0.12, 0.12, 0.88, 0.84), 0.18, STONE_HIGHLIGHT, None, 0),
            ('round_rect', (0.12, 0.14, 0.88, 0.86), 0.18, STONE_BODY, None, 0),
            ('round_rect', (0.17, 0.19, 0.83, 0.81), 0.13, None, GOLD_ACCENT, 0.03),
            ('round_rect', (0.19, 0.21, 0.81, 0.79), 0.11, STONE_BED, None, 0),
        ])
        txt = {'playstation': ('L2' if btn == 'lefttrigger' else 'R2'),
               'xbox': ('LT' if btn == 'lefttrigger' else 'RT'),
               'nintendo': ('ZL' if btn == 'lefttrigger' else 'ZR')}[style]
        items.append(('text', (0.50, 0.50), txt, TEXT, 0.30, 'bold'))
        return items

    # 4. Sticks: leftstick, rightstick
    if btn in ('leftstick', 'rightstick'):
        items.extend([
            ('oval', (0.06, 0.08, 0.94, 0.96), STONE_SHADOW, None, 0),
            ('oval', (0.06, 0.04, 0.94, 0.92), STONE_HIGHLIGHT, None, 0),
            ('oval', (0.06, 0.06, 0.94, 0.94), STONE_BODY, None, 0),
            ('oval', (0.09, 0.09, 0.91, 0.91), None, STONE_BORDER, 0.03),
            ('oval', (0.19, 0.21, 0.81, 0.83), STONE_SHADOW, None, 0),
            ('oval', (0.19, 0.17, 0.81, 0.79), STONE_HIGHLIGHT, None, 0),
            ('oval', (0.19, 0.19, 0.81, 0.81), STONE_BED, None, 0),
            ('oval', (0.20, 0.20, 0.80, 0.80), None, GOLD_ACCENT, 0.03),
        ])
        txt = {'playstation': ('L3' if btn == 'leftstick' else 'R3'),
               'xbox': ('LS' if btn == 'leftstick' else 'RS'),
               'nintendo': ('LS' if btn == 'leftstick' else 'RS')}[style]
        items.append(('text', (0.50, 0.50), txt, TEXT, 0.28, 'bold'))
        return items

    # 5. Start / back / guide
    if btn in ('start', 'back', 'guide'):
        items.extend(_stone_pill(0.26, 0.74, 0.24))
        if style == 'playstation':
            txt = {'start': 'OPTIONS', 'back': 'SHARE', 'guide': 'PS'}[btn]
        elif style == 'xbox':
            txt = {'start': 'MENU', 'back': 'VIEW', 'guide': 'XBOX'}[btn]
        else:
            txt = {'start': '+', 'back': '−', 'guide': 'HOME'}[btn]

        if txt == 'OPTIONS':
            sz = 0.17
        elif len(txt) >= 5:
            sz = 0.20
        elif len(txt) == 4:
            sz = 0.24
        elif txt in ('+', '−'):
            sz = 0.38
        else:
            sz = 0.28
        items.append(('text', (0.50, 0.50), txt, TEXT, sz, 'bold'))
        return items

    # 6. Touchpad & Misc1
    if btn == 'touchpad':
        if style == 'playstation':
            items.extend([
                ('round_rect', (0.05, 0.24, 0.95, 0.76), 0.10, STONE_SHADOW, None, 0),
                ('round_rect', (0.05, 0.20, 0.95, 0.72), 0.10, STONE_HIGHLIGHT, None, 0),
                ('round_rect', (0.05, 0.22, 0.95, 0.74), 0.10, STONE_BODY, None, 0),
                ('round_rect', (0.09, 0.26, 0.91, 0.70), 0.07, None, GOLD_ACCENT, 0.03),
                ('round_rect', (0.11, 0.28, 0.89, 0.68), 0.05, STONE_BED, None, 0),
                ('text', (0.50, 0.50), 'TOUCHPAD', TEXT, 0.16, 'bold'),
            ])
        else:
            items.extend([
                ('round_rect', (0.15, 0.32, 0.85, 0.68), 0.18, '#191d21', '#262d34', 0.03),
                ('line', (0.35, 0.50, 0.65, 0.50), MUTED, 0.06),
            ])
        return items

    if btn == 'misc1':
        items.extend(_stone_pill(0.26, 0.74, 0.24))
        txt = {'playstation': 'MUTE', 'xbox': 'SHARE', 'nintendo': 'CAPTURE'}[style]
        sz = 0.17 if len(txt) >= 7 else (0.22 if len(txt) >= 5 else 0.26)
        items.append(('text', (0.50, 0.50), txt, TEXT, sz, 'bold'))
        return items

    # 7. D-pad: dpup, dpdown, dpleft, dpright
    if btn in ('dpup', 'dpdown', 'dpleft', 'dpright'):
        items.extend([
            ('round_rect', (0.08, 0.36, 0.92, 0.68), 0.04, STONE_SHADOW, None, 0),
            ('round_rect', (0.34, 0.10, 0.66, 0.94), 0.04, STONE_SHADOW, None, 0),
            ('round_rect', (0.08, 0.32, 0.92, 0.64), 0.04, STONE_HIGHLIGHT, None, 0),
            ('round_rect', (0.34, 0.06, 0.66, 0.90), 0.04, STONE_HIGHLIGHT, None, 0),
            ('round_rect', (0.08, 0.34, 0.92, 0.66), 0.04, STONE_BODY, None, 0),
            ('round_rect', (0.34, 0.08, 0.66, 0.92), 0.04, STONE_BODY, None, 0),
            ('oval', (0.38, 0.38, 0.62, 0.62), STONE_BED, STONE_BORDER, 0.02),
        ])
        arrow_muted = '#3c4652'
        if btn != 'dpup':
            items.append(('polygon', [(0.50, 0.18), (0.58, 0.30), (0.42, 0.30)], arrow_muted, None, 0))
        if btn != 'dpdown':
            items.append(('polygon', [(0.50, 0.82), (0.58, 0.70), (0.42, 0.70)], arrow_muted, None, 0))
        if btn != 'dpleft':
            items.append(('polygon', [(0.18, 0.50), (0.30, 0.42), (0.30, 0.58)], arrow_muted, None, 0))
        if btn != 'dpright':
            items.append(('polygon', [(0.82, 0.50), (0.70, 0.42), (0.70, 0.58)], arrow_muted, None, 0))

        if btn == 'dpup':
            items.extend([
                ('round_rect', (0.35, 0.09, 0.65, 0.44), 0.04, GOLD, None, 0),
                ('polygon', [(0.50, 0.17), (0.59, 0.31), (0.41, 0.31)], '#14171a', None, 0),
            ])
        elif btn == 'dpdown':
            items.extend([
                ('round_rect', (0.35, 0.56, 0.65, 0.91), 0.04, GOLD, None, 0),
                ('polygon', [(0.50, 0.83), (0.59, 0.69), (0.41, 0.69)], '#14171a', None, 0),
            ])
        elif btn == 'dpleft':
            items.extend([
                ('round_rect', (0.09, 0.35, 0.44, 0.65), 0.04, GOLD, None, 0),
                ('polygon', [(0.17, 0.50), (0.31, 0.41), (0.31, 0.59)], '#14171a', None, 0),
            ])
        elif btn == 'dpright':
            items.extend([
                ('round_rect', (0.56, 0.35, 0.91, 0.65), 0.04, GOLD, None, 0),
                ('polygon', [(0.83, 0.50), (0.69, 0.41), (0.69, 0.59)], '#14171a', None, 0),
            ])
        return items

    # 8. Paddles: paddle1..paddle4
    if btn in ('paddle1', 'paddle2', 'paddle3', 'paddle4'):
        p_num = btn[-1]
        items.extend([
            ('round_rect', (0.10, 0.18, 0.90, 0.82), 0.18, STONE_SHADOW, None, 0),
            ('round_rect', (0.10, 0.14, 0.90, 0.78), 0.18, STONE_HIGHLIGHT, None, 0),
            ('round_rect', (0.10, 0.16, 0.90, 0.80), 0.18, STONE_BODY, None, 0),
            ('round_rect', (0.15, 0.21, 0.85, 0.75), 0.14, None, GOLD_ACCENT, 0.03),
            ('round_rect', (0.17, 0.23, 0.83, 0.73), 0.12, STONE_BED, None, 0),
            ('text', (0.50, 0.50), f'P{p_num}', TEXT, 0.32, 'bold'),
        ])
        return items

    return items


def draw(canvas, button, style, size):
    """Draws the icon of button filling a size x size Tk canvas (clearing it first)."""
    canvas.delete('all')
    items = primitives(button, style)
    if not items:
        return
    s = size
    for item in items:
        kind = item[0]
        if kind == 'oval':
            _, (x0, y0, x1, y1), fill, outline, width = item
            w = max(1, int(round(width * s))) if (outline and width > 0) else 0
            canvas.create_oval(x0 * s, y0 * s, x1 * s, y1 * s,
                               fill=fill or '', outline=outline or '', width=w)
        elif kind == 'round_rect':
            _, (x0, y0, x1, y1), r, fill, outline, width = item
            w = max(1, int(round(width * s))) if (outline and width > 0) else 0
            rx0, ry0, rx1, ry1 = x0 * s, y0 * s, x1 * s, y1 * s
            rad = min(r * s, (rx1 - rx0) / 2, (ry1 - ry0) / 2)
            if rad <= 1:
                canvas.create_rectangle(rx0, ry0, rx1, ry1,
                                        fill=fill or '', outline=outline or '', width=w)
            else:
                if fill:
                    canvas.create_rectangle(rx0 + rad, ry0, rx1 - rad, ry1, fill=fill, outline='')
                    canvas.create_rectangle(rx0, ry0 + rad, rx1, ry1 - rad, fill=fill, outline='')
                    canvas.create_oval(rx0, ry0, rx0 + 2 * rad, ry0 + 2 * rad, fill=fill, outline='')
                    canvas.create_oval(rx1 - 2 * rad, ry0, rx1, ry0 + 2 * rad, fill=fill, outline='')
                    canvas.create_oval(rx0, ry1 - 2 * rad, rx0 + 2 * rad, ry1, fill=fill, outline='')
                    canvas.create_oval(rx1 - 2 * rad, ry1 - 2 * rad, rx1, ry1, fill=fill, outline='')
                if outline and w > 0:
                    canvas.create_line(rx0 + rad, ry0, rx1 - rad, ry0, fill=outline, width=w)
                    canvas.create_line(rx0 + rad, ry1, rx1 - rad, ry1, fill=outline, width=w)
                    canvas.create_line(rx0, ry0 + rad, rx0, ry1 - rad, fill=outline, width=w)
                    canvas.create_line(rx1, ry0 + rad, rx1, ry1 - rad, fill=outline, width=w)
                    canvas.create_arc(rx0, ry0, rx0 + 2 * rad, ry0 + 2 * rad,
                                      start=90, extent=90, style='arc', outline=outline, width=w)
                    canvas.create_arc(rx1 - 2 * rad, ry0, rx1, ry0 + 2 * rad,
                                      start=0, extent=90, style='arc', outline=outline, width=w)
                    canvas.create_arc(rx1 - 2 * rad, ry1 - 2 * rad, rx1, ry1,
                                      start=270, extent=90, style='arc', outline=outline, width=w)
                    canvas.create_arc(rx0, ry1 - 2 * rad, rx0 + 2 * rad, ry1,
                                      start=180, extent=90, style='arc', outline=outline, width=w)
        elif kind == 'rect':
            _, (x0, y0, x1, y1), fill, outline, width = item
            w = max(1, int(round(width * s))) if (outline and width > 0) else 0
            canvas.create_rectangle(x0 * s, y0 * s, x1 * s, y1 * s,
                                    fill=fill or '', outline=outline or '', width=w)
        elif kind == 'polygon':
            _, pts, fill, outline, width = item
            w = max(1, int(round(width * s))) if (outline and width > 0) else 0
            flat = [coord for pt in pts for coord in (pt[0] * s, pt[1] * s)]
            canvas.create_polygon(*flat, fill=fill or '', outline=outline or '', width=w)
        elif kind == 'line':
            _, (x0, y0, x1, y1), fill, width = item
            w = max(1, int(round(width * s)))
            canvas.create_line(x0 * s, y0 * s, x1 * s, y1 * s, fill=fill, width=w, capstyle='round')
        elif kind == 'text':
            _, (x, y), txt, fill, size_ratio, weight = item
            font_size = max(5, int(round(size_ratio * s)))
            font = ('Segoe UI', font_size, 'bold' if weight == 'bold' else 'normal')
            canvas.create_text(x * s, y * s, text=txt, fill=fill, font=font, anchor='center')


_font_cache = {}


def render(button, style, size):
    """Returns a PIL.Image RGBA of size x size with the same drawing."""
    from PIL import Image, ImageDraw, ImageFont

    scale = 4
    canvas_s = size * scale
    img = Image.new('RGBA', (canvas_s, canvas_s), (0, 0, 0, 0))
    draw_obj = ImageDraw.Draw(img)
    items = primitives(button, style)
    if not items:
        return img.resize((size, size), Image.Resampling.LANCZOS)

    for item in items:
        kind = item[0]
        if kind == 'oval':
            _, (x0, y0, x1, y1), fill, outline, width = item
            w = max(1, int(round(width * canvas_s))) if (outline and width > 0) else 0
            draw_obj.ellipse([x0 * canvas_s, y0 * canvas_s, x1 * canvas_s, y1 * canvas_s],
                             fill=fill, outline=outline, width=w)
        elif kind == 'round_rect':
            _, (x0, y0, x1, y1), r, fill, outline, width = item
            w = max(1, int(round(width * canvas_s))) if (outline and width > 0) else 0
            rad = min(r * canvas_s, (x1 - x0) * canvas_s / 2, (y1 - y0) * canvas_s / 2)
            draw_obj.rounded_rectangle([x0 * canvas_s, y0 * canvas_s, x1 * canvas_s, y1 * canvas_s],
                                       radius=int(round(rad)), fill=fill, outline=outline, width=w)
        elif kind == 'rect':
            _, (x0, y0, x1, y1), fill, outline, width = item
            w = max(1, int(round(width * canvas_s))) if (outline and width > 0) else 0
            draw_obj.rectangle([x0 * canvas_s, y0 * canvas_s, x1 * canvas_s, y1 * canvas_s],
                               fill=fill, outline=outline, width=w)
        elif kind == 'polygon':
            _, pts, fill, outline, width = item
            w = max(1, int(round(width * canvas_s))) if (outline and width > 0) else 0
            p = [(pt[0] * canvas_s, pt[1] * canvas_s) for pt in pts]
            draw_obj.polygon(p, fill=fill, outline=outline, width=w)
        elif kind == 'line':
            _, (x0, y0, x1, y1), fill, width = item
            w = max(1, int(round(width * canvas_s)))
            draw_obj.line([(x0 * canvas_s, y0 * canvas_s), (x1 * canvas_s, y1 * canvas_s)],
                          fill=fill, width=w)
        elif kind == 'text':
            _, (x, y), txt, fill, size_ratio, weight = item
            font_size = max(5, int(round(size_ratio * canvas_s)))
            font_file = 'seguisym.ttf' if txt in ('−', '+') else ('segoeuib.ttf' if weight == 'bold' else 'segoeui.ttf')
            key = (font_file, font_size)
            if key not in _font_cache:
                font_path = os.path.join(r'C:\Windows\Fonts', font_file)
                try:
                    font = ImageFont.truetype(font_path, font_size)
                except Exception:
                    try:
                        font = ImageFont.truetype('segoeuib.ttf' if weight == 'bold' else 'segoeui.ttf', font_size)
                    except Exception:
                        font = ImageFont.load_default()
                _font_cache[key] = font
            else:
                font = _font_cache[key]
            draw_obj.text((x * canvas_s, y * canvas_s), txt, fill=fill, font=font, anchor='mm')

    return img.resize((size, size), Image.Resampling.LANCZOS)
