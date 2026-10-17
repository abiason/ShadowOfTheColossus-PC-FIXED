#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Generates a test sheet of all controller button icons in all styles and sizes.

Usage:
    python tools/button_icons_sheet.py <output.png>
    python tools/button_icons_sheet.py buzon/lamina_iconos.png
    python tools/button_icons_sheet.py buzon/lamina_canvas.png
"""
import os
from pathlib import Path
import sys

# Ensure launcher is in path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / 'launcher'))

import button_icons as icons


def build_pil_sheet(output_path):
    """Builds the icons sheet using button_icons.render() (PIL backend)."""
    from PIL import Image, ImageDraw, ImageFont

    card = icons.CARD
    text_color = icons.TEXT
    muted_color = icons.MUTED
    gold_color = icons.GOLD
    line_color = icons.LINE
    buttons = icons.PAD_BUTTONS
    styles = icons.STYLES
    names = icons.STYLE_NAMES

    col_w = 78
    margin_x = 130
    width = margin_x + len(buttons) * col_w + 30
    height = 620

    sheet = Image.new('RGBA', (width, height), card)
    draw = ImageDraw.Draw(sheet)

    def get_font(file_name, size):
        font_path = os.path.join(r'C:\Windows\Fonts', file_name)
        try:
            return ImageFont.truetype(font_path, size)
        except Exception:
            try:
                return ImageFont.truetype('segoeuib.ttf' if 'b' in file_name else 'segoeui.ttf', size)
            except Exception:
                return ImageFont.load_default()

    font_title = get_font('segoeuib.ttf', 18)
    font_sec = get_font('segoeuib.ttf', 14)
    font_style = get_font('segoeuib.ttf', 13)
    font_lbl = get_font('segoeui.ttf', 11)

    draw.text((24, 20), 'Shadow of the Colossus - Controller Button Icons (Relic Stone & Gold)',
              fill=gold_color, font=font_title)

    # 1. 64px Detailed section
    y_cursor = 60
    draw.text((24, y_cursor), 'DETAILED VIEW (64 px)', fill=text_color, font=font_sec)
    draw.line([(24, y_cursor + 20), (width - 24, y_cursor + 20)], fill=line_color, width=1)
    y_cursor += 32

    for style in styles:
        draw.text((24, y_cursor + 24), names[style], fill=gold_color, font=font_style)
        for col_idx, btn in enumerate(buttons):
            cx = margin_x + col_idx * col_w + (col_w - 64) // 2
            cy = y_cursor
            icon_img = icons.render(btn, style, 64)
            sheet.paste(icon_img, (cx, cy), icon_img)

            lbl = icons.label(btn, style)
            draw.text((cx + 32, cy + 68), lbl, fill=muted_color, font=font_lbl, anchor='mt')
        y_cursor += 90

    # 2. 28px Launcher section
    y_cursor += 15
    draw.text((24, y_cursor), 'LAUNCHER VIEW (28 px)', fill=text_color, font=font_sec)
    draw.line([(24, y_cursor + 20), (width - 24, y_cursor + 20)], fill=line_color, width=1)
    y_cursor += 32

    for style in styles:
        draw.text((24, y_cursor + 8), names[style], fill=gold_color, font=font_style)
        for col_idx, btn in enumerate(buttons):
            cx = margin_x + col_idx * col_w + (col_w - 28) // 2
            cy = y_cursor
            icon_img = icons.render(btn, style, 28)
            sheet.paste(icon_img, (cx, cy), icon_img)

            lbl = icons.label(btn, style)
            draw.text((cx + 14, cy + 32), lbl, fill=muted_color, font=font_lbl, anchor='mt')
        y_cursor += 54

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    sheet.save(output_path)
    print(f'Successfully generated PIL icon sheet: {output_path}')


def build_canvas_sheet(output_path):
    """Attempts to build the icons sheet using Tkinter Canvas (draw() backend)."""
    import tkinter as tk
    from io import BytesIO
    from PIL import Image

    card = icons.CARD
    text_color = icons.TEXT
    muted_color = icons.MUTED
    gold_color = icons.GOLD
    line_color = icons.LINE
    buttons = icons.PAD_BUTTONS
    styles = icons.STYLES
    names = icons.STYLE_NAMES

    col_w = 78
    margin_x = 130
    width = margin_x + len(buttons) * col_w + 30
    height = 620

    root = tk.Tk()
    root.title('Button Icons Sheet - Tk Canvas')
    root.geometry(f'{width}x{height}')
    root.configure(bg=card)

    canvas = tk.Canvas(root, width=width, height=height, bg=card, highlightthickness=0, bd=0)
    canvas.pack(fill='both', expand=True)

    # Title
    canvas.create_text(24, 28, text='Shadow of the Colossus - Controller Button Icons (Relic Stone & Gold)',
                       fill=gold_color, font=('Segoe UI', 15, 'bold'), anchor='w')

    # 1. 64px section
    y_cursor = 60
    canvas.create_text(24, y_cursor + 10, text='DETAILED VIEW (64 px)',
                       fill=text_color, font=('Segoe UI', 11, 'bold'), anchor='w')
    canvas.create_line(24, y_cursor + 20, width - 24, y_cursor + 20, fill=line_color, width=1)
    y_cursor += 32

    for style in styles:
        canvas.create_text(24, y_cursor + 32, text=names[style],
                           fill=gold_color, font=('Segoe UI', 11, 'bold'), anchor='w')
        for col_idx, btn in enumerate(buttons):
            cx = margin_x + col_idx * col_w + (col_w - 64) // 2
            cy = y_cursor
            sub_canvas = tk.Canvas(canvas, width=64, height=64, bg=card, highlightthickness=0, bd=0)
            icons.draw(sub_canvas, btn, style, 64)
            canvas.create_window(cx, cy, anchor='nw', window=sub_canvas)

            lbl = icons.label(btn, style)
            canvas.create_text(cx + 32, cy + 74, text=lbl,
                               fill=muted_color, font=('Segoe UI', 9), anchor='center')
        y_cursor += 90

    # 2. 28px section
    y_cursor += 15
    canvas.create_text(24, y_cursor + 10, text='LAUNCHER VIEW (28 px)',
                       fill=text_color, font=('Segoe UI', 11, 'bold'), anchor='w')
    canvas.create_line(24, y_cursor + 20, width - 24, y_cursor + 20, fill=line_color, width=1)
    y_cursor += 32

    for style in styles:
        canvas.create_text(24, y_cursor + 14, text=names[style],
                           fill=gold_color, font=('Segoe UI', 11, 'bold'), anchor='w')
        for col_idx, btn in enumerate(buttons):
            cx = margin_x + col_idx * col_w + (col_w - 28) // 2
            cy = y_cursor
            sub_canvas = tk.Canvas(canvas, width=28, height=28, bg=card, highlightthickness=0, bd=0)
            icons.draw(sub_canvas, btn, style, 28)
            canvas.create_window(cx, cy, anchor='nw', window=sub_canvas)

            lbl = icons.label(btn, style)
            canvas.create_text(cx + 14, cy + 38, text=lbl,
                               fill=muted_color, font=('Segoe UI', 8), anchor='center')
        y_cursor += 54

    root.update()

    # Try saving:
    # 1. PostScript -> PIL (requires Ghostscript)
    ps_data = canvas.postscript(colormode='color', width=width, height=height)
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    rasterized = False
    try:
        ps_img = Image.open(BytesIO(ps_data.encode('latin1')))
        ps_img.load()
        ps_img.save(output_path)
        print(f'Successfully rasterized Tk canvas via Ghostscript to: {output_path}')
        rasterized = True
    except Exception as gs_err:
        print(f'PostScript rasterization unavailable ({gs_err}). Trying PIL.ImageGrab...')

    # 2. If not rasterized, try PIL.ImageGrab
    if not rasterized:
        try:
            from PIL import ImageGrab
            x = root.winfo_rootx()
            y = root.winfo_rooty()
            w = root.winfo_width()
            h = root.winfo_height()
            grab = ImageGrab.grab(bbox=(x, y, x + w, y + h))
            grab.save(output_path)
            print(f'Successfully captured Tk window via ImageGrab to: {output_path}')
            rasterized = True
        except Exception as grab_err:
            print(f'ImageGrab failed ({grab_err}).')

    root.destroy()

    if not rasterized:
        print(f'AVISO: No se pudo generar la imagen rasterizada {output_path} desde Tk Canvas.')
        print('Causa: Ghostscript no está instalado en el sistema y ImageGrab.grab() no está disponible en sesiones no interactivas/headless de Windows.')


def main():
    if len(sys.argv) > 1:
        target = sys.argv[1]
    else:
        target = str(ROOT_DIR / 'buzon' / 'lamina_iconos.png')

    is_canvas = 'canvas' in os.path.basename(target).lower() or '--canvas' in sys.argv

    if is_canvas:
        build_canvas_sheet(target)
    else:
        build_pil_sheet(target)


if __name__ == '__main__':
    main()
