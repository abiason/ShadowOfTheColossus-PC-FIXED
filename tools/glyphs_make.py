#!/usr/bin/env python3
"""
glyphs_make.py - Generate Xbox and Nintendo in-game button icons derived from PlayStation originals.

For Shadow of the Colossus PC Port (AGY Iconos In-Game).
Usage:
    python tools/glyphs_make.py <dir_originales> <dir_salida> [--sheets <buzon_dir>]
"""

import os
import sys
import argparse
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter


# Font paths on Windows
FONT_CANDIDATES = [
    r"C:\Windows\Fonts\ariblk.ttf",   # Arial Black
    r"C:\Windows\Fonts\seguibl.ttf",  # Segoe UI Black
    r"C:\Windows\Fonts\arialbd.ttf",  # Arial Bold
]


def get_font(size, preferred=None):
    """Load a truetype font from Windows font directory with fallback."""
    candidates = []
    if preferred:
        candidates.append(preferred)
    candidates.extend(FONT_CANDIDATES)

    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
    return ImageFont.load_default()


def dilate_mask(mask, iterations=2):
    """Simple 2D binary dilation without scipy dependency."""
    m = mask.copy()
    for _ in range(iterations):
        padded = np.pad(m, 1, mode='constant', constant_values=False)
        m = (
            padded[:-2, 1:-1] | padded[2:, 1:-1] |
            padded[1:-1, :-2] | padded[1:-1, 2:] |
            padded[:-2, :-2]  | padded[:-2, 2:]  |
            padded[2:, :-2]   | padded[2:, 2:]   | m
        )
    return m


def extract_clean_disc(face_images):
    """
    Extracts an empty, clean button disc from the 4 face button originals
    (cross, circle, square, triangle).
    
    Uses multi-image pixel analysis:
    1. Detects colored symbol strokes where saturation (max - min RGB) > 8.
    2. Dilates symbol masks by 4 iterations to cover antialiasing and drop shadows.
    3. For every pixel, takes the average of clean candidates.
    4. Interpolates horizontally across rows for the tiny 4-5px overlap regions.
    5. Neutralizes the interior RGB to eliminate any chromatic aberration.
    """
    imgs = [np.array(im) for im in face_images]
    clean_masks = []

    for img in imgs:
        r = img[:, :, 0].astype(int)
        g = img[:, :, 1].astype(int)
        b = img[:, :, 2].astype(int)
        sat = np.maximum(np.maximum(r, g), b) - np.minimum(np.minimum(r, g), b)
        sym_mask = sat > 8
        dilated = dilate_mask(sym_mask, iterations=4)
        clean_masks.append(~dilated)

    disc = np.zeros((128, 128, 4), dtype=np.float32)
    known = np.zeros((128, 128), dtype=bool)

    for y in range(128):
        for x in range(128):
            samples = [imgs[i][y, x] for i in range(len(imgs)) if clean_masks[i][y, x]]
            if len(samples) > 0:
                known[y, x] = True
                disc[y, x] = np.mean(samples, axis=0)

    # Interpolate along rows for unknown overlap pixels
    for y in range(128):
        if not np.any(known[y]):
            continue
        for x in range(128):
            if not known[y, x]:
                left_x = x - 1
                while left_x >= 0 and not known[y, left_x]:
                    left_x -= 1
                right_x = x + 1
                while right_x < 128 and not known[y, right_x]:
                    right_x += 1

                if left_x >= 0 and right_x < 128:
                    weight = (x - left_x) / (right_x - left_x)
                    disc[y, x] = (1.0 - weight) * disc[y, left_x] + weight * disc[y, right_x]
                elif left_x >= 0:
                    disc[y, x] = disc[y, left_x]
                elif right_x < 128:
                    disc[y, x] = disc[y, right_x]

    # Neutralize interior RGB (R = G = B = mean) to eliminate any remnant color
    alpha = disc[:, :, 3]
    gray = np.mean(disc[:, :, :3], axis=-1)
    disc_clean = np.zeros((128, 128, 4), dtype=np.uint8)
    disc_clean[:, :, 0] = np.round(gray).astype(np.uint8)
    disc_clean[:, :, 1] = np.round(gray).astype(np.uint8)
    disc_clean[:, :, 2] = np.round(gray).astype(np.uint8)
    disc_clean[:, :, 3] = np.round(alpha).astype(np.uint8)

    return Image.fromarray(disc_clean)


def render_face_glyph(base_disc, char, base_color, outline_color=(15, 15, 15, 255), font_size=66):
    """
    Renders a bold character onto the clean disc with:
    - Accurate centering
    - Dark antialiased outline
    - Subtle top-down specular gradient on the letter body
    """
    font = get_font(font_size)
    txt_layer = Image.new('RGBA', base_disc.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(txt_layer)

    # Calculate centered bounding box
    stroke_w = 2
    bb = d.textbbox((0, 0), char, font=font, stroke_width=stroke_w)
    w = bb[2] - bb[0]
    h = bb[3] - bb[1]
    x = 64 - w // 2 - bb[0]
    y = 64 - h // 2 - bb[1]

    # Draw dark stroke outline
    d.text((x, y), char, font=font, fill=outline_color, stroke_width=stroke_w, stroke_fill=outline_color)

    # Render inner letter mask
    inner_mask = Image.new('L', base_disc.size, 0)
    d_m = ImageDraw.Draw(inner_mask)
    d_m.text((x, y), char, font=font, fill=255)

    # Parse base color
    if isinstance(base_color, str):
        base_rgb = tuple(int(base_color.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
    else:
        base_rgb = base_color[:3]

    # Vertical gradient: slightly brighter at top, richer at bottom
    top_rgb = np.clip(np.array(base_rgb) * 1.20 + 20, 0, 255).astype(np.uint8)
    bot_rgb = np.clip(np.array(base_rgb) * 0.95, 0, 255).astype(np.uint8)

    grad_arr = np.zeros((base_disc.height, base_disc.width, 4), dtype=np.uint8)
    y0 = y + bb[1]
    y1 = y + bb[3]
    h_span = max(1, y1 - y0)

    for row in range(base_disc.height):
        if row < y0:
            t = 0.0
        elif row > y1:
            t = 1.0
        else:
            t = (row - y0) / h_span
        col = (1.0 - t) * top_rgb + t * bot_rgb
        grad_arr[row, :, :3] = col.astype(np.uint8)
        grad_arr[row, :, 3] = 255

    grad_im = Image.fromarray(grad_arr)
    txt_layer.paste(grad_im, (0, 0), inner_mask)

    result = base_disc.copy()
    result.alpha_composite(txt_layer)
    return result


def inpaint_piece_text(im_arr, btn_name):
    """
    Seamlessly erases text, dark outline, and drop shadow from triggers/bumpers
    by detecting the text silhouette, dilating by 5-6px to include all outline/shadow,
    and interpolating row-by-row between the clean plastic colors at left and right.
    Leaves all pixels outside the dilated mask completely untouched.
    """
    res = im_arr.copy()
    # 1. Detect text core
    core = (im_arr[:, :, 0] > 180) & (im_arr[:, :, 1] > 180) & (im_arr[:, :, 2] > 180) & (im_arr[:, :, 3] > 200)

    # Restrict to button text region
    if btn_name in ('r1', 'l1'):
        core[0:50, :] = False
        core[86:, :] = False
        core[:, 0:35] = False
        core[:, 88:] = False
        iter_count = 5
    elif btn_name == 'l2':
        core[0:46, :] = False
        core[82:, :] = False
        core[:, 0:42] = False
        core[:, 94:] = False
        iter_count = 6
    elif btn_name == 'r2':
        core[0:46, :] = False
        core[82:, :] = False
        core[:, 0:28] = False
        core[:, 88:] = False
        iter_count = 5
    else:
        iter_count = 5

    mask_dil = dilate_mask(core, iterations=iter_count)

    for y in range(128):
        xs = np.where(mask_dil[y])[0]
        if len(xs) == 0:
            continue
        x_min, x_max = xs.min(), xs.max()
        x_left = x_min - 1
        x_right = x_max + 1

        c_left = im_arr[y, x_left].astype(float)
        c_right = im_arr[y, x_right].astype(float)

        span = max(1, x_right - x_left)
        for x in range(x_min, x_max + 1):
            t = (x - x_left) / span
            res[y, x] = np.round((1.0 - t) * c_left + t * c_right).astype(np.uint8)

    return res


def render_trigger_glyph(base_img, text, center_pos, font_size=50):
    """
    Renders trigger/bumper text in white with thick dark outline (stroke=3)
    and soft drop shadow underneath, matching original PlayStation in-game typography.
    """
    font = get_font(font_size)
    cx, cy = center_pos

    dummy = Image.new('RGBA', (200, 200), (0, 0, 0, 0))
    d_d = ImageDraw.Draw(dummy)
    bb = d_d.textbbox((0, 0), text, font=font, stroke_width=3)
    w = bb[2] - bb[0]
    h = bb[3] - bb[1]

    x = cx - w // 2 - bb[0]
    y = cy - h // 2 - bb[1]

    # 1. Soft drop shadow offset down by 2 px
    d_shadow = Image.new('RGBA', base_img.size, (0, 0, 0, 0))
    d_s_draw = ImageDraw.Draw(d_shadow)
    d_s_draw.text((x, y + 2), text, font=font, fill=(0, 0, 0, 180), stroke_width=4, stroke_fill=(0, 0, 0, 180))
    d_shadow = d_shadow.filter(ImageFilter.GaussianBlur(radius=1.2))

    # 2. Crisp dark outline: stroke_width=3
    d_outline = Image.new('RGBA', base_img.size, (0, 0, 0, 0))
    d_o_draw = ImageDraw.Draw(d_outline)
    d_o_draw.text((x, y), text, font=font, fill=(10, 10, 10, 255), stroke_width=3, stroke_fill=(10, 10, 10, 255))

    # 3. White text core
    d_white = Image.new('RGBA', base_img.size, (0, 0, 0, 0))
    d_w_draw = ImageDraw.Draw(d_white)
    d_w_draw.text((x, y), text, font=font, fill=(255, 255, 255, 255))

    result = base_img.copy()
    result.alpha_composite(d_shadow)
    result.alpha_composite(d_outline)
    result.alpha_composite(d_white)
    return result


def render_touchpad_glyph(clean_disc, platform):
    """
    Renders Xbox View or Nintendo Minus button on a smaller glossy plastic disc.
    """
    btn_size = 84
    disc_small = clean_disc.resize((btn_size, btn_size), Image.Resampling.LANCZOS)

    canvas = Image.new('RGBA', (128, 128), (0, 0, 0, 0))
    offset = (128 - btn_size) // 2
    canvas.paste(disc_small, (offset, offset), disc_small)

    d = ImageDraw.Draw(canvas)
    cx, cy = 64, 64

    if platform == 'xbox':
        # Xbox View symbol: two overlapping rectangles
        rw, rh = 22, 16
        dx, dy = 4, 3

        # Back rectangle (upper-right)
        rx1, ry1 = cx - rw // 2 + dx, cy - rh // 2 - dy
        rx2, ry2 = rx1 + rw, ry1 + rh
        d.rectangle([rx1 - 1, ry1 - 1, rx2 + 1, ry2 + 1], outline=(15, 15, 15, 255), width=3)
        d.rectangle([rx1, ry1, rx2, ry2], outline=(245, 245, 245, 255), width=2)

        # Front rectangle (lower-left) with opaque dark interior
        fx1, fy1 = cx - rw // 2 - dx, cy - rh // 2 + dy
        fx2, fy2 = fx1 + rw, fy1 + rh
        d.rectangle([fx1 - 1, fy1 - 1, fx2 + 1, fy2 + 1], fill=(22, 22, 22, 255), outline=(15, 15, 15, 255), width=3)
        d.rectangle([fx1, ry1, rx1, fy2], fill=(22, 22, 22, 255))
        d.rectangle([fx1, fy1, fx2, fy2], outline=(245, 245, 245, 255), width=2)

    elif platform == 'nintendo':
        # Nintendo Minus symbol: clean horizontal bar
        mw, mh = 26, 6
        mx1, my1 = cx - mw // 2, cy - mh // 2
        mx2, my2 = mx1 + mw, my1 + mh
        d.rectangle([mx1 - 2, my1 - 2, mx2 + 2, my2 + 2], fill=(15, 15, 15, 255))
        d.rectangle([mx1, my1, mx2, my2], fill=(245, 245, 245, 255))

    return canvas


def render_options_glyph(clean_disc, platform):
    """
    Renders Xbox Menu (three horizontal bars) or Nintendo Plus (+) on a small disc.
    """
    btn_size = 84
    disc_small = clean_disc.resize((btn_size, btn_size), Image.Resampling.LANCZOS)
    canvas = Image.new('RGBA', (128, 128), (0, 0, 0, 0))
    offset = (128 - btn_size) // 2
    canvas.paste(disc_small, (offset, offset), disc_small)

    d = ImageDraw.Draw(canvas)
    cx, cy = 64, 64

    if platform == 'xbox':
        # Menu symbol: three horizontal lines
        bw = 24
        bh = 3
        gap = 4
        total_h = 3 * bh + 2 * gap
        top_y = cy - total_h // 2
        for i in range(3):
            y = top_y + i * (bh + gap)
            x1 = cx - bw // 2
            x2 = x1 + bw
            d.rectangle([x1 - 1, y - 1, x2 + 1, y + bh], fill=(15, 15, 15, 255))
            d.rectangle([x1, y, x2, y + bh - 1], fill=(245, 245, 245, 255))
    elif platform == 'nintendo':
        # Plus symbol: cross
        w, l = 6, 24
        # Horizontal bar
        d.rectangle([cx - l // 2 - 1, cy - w // 2 - 1, cx + l // 2 + 1, cy + w // 2 + 1], fill=(15, 15, 15, 255))
        # Vertical bar
        d.rectangle([cx - w // 2 - 1, cy - l // 2 - 1, cx + w // 2 + 1, cy + l // 2 + 1], fill=(15, 15, 15, 255))
        # White fills
        d.rectangle([cx - l // 2, cy - w // 2, cx + l // 2, cy + w // 2], fill=(245, 245, 245, 255))
        d.rectangle([cx - w // 2, cy - l // 2, cx + w // 2, cy + l // 2], fill=(245, 245, 245, 255))

    return canvas


def make_glyphs(orig_dir, out_dir):
    """
    Main processing function:
    Reads <orig_dir>/*_<button>.png, generates:
    <out_dir>/xbox/<hash>.png
    <out_dir>/nintendo/<hash>.png
    """
    xbox_dir = os.path.join(out_dir, 'xbox')
    nin_dir = os.path.join(out_dir, 'nintendo')
    os.makedirs(xbox_dir, exist_ok=True)
    os.makedirs(nin_dir, exist_ok=True)

    files = [f for f in os.listdir(orig_dir) if f.endswith('.png')]

    # Index by button name
    btn_files = {}
    for f in files:
        parts = f[:-4].split('_', 1)
        if len(parts) == 2:
            hash_str, btn_name = parts[0], parts[1]
            btn_files[btn_name] = (hash_str, os.path.join(orig_dir, f))

    # 1. Clean Disc from Face Buttons
    face_names = ['cross', 'circle', 'square', 'triangle']
    if all(name in btn_files for name in face_names):
        face_images = [Image.open(btn_files[name][1]) for name in face_names]
        clean_disc = extract_clean_disc(face_images)
        print("  [+] Clean disc successfully extracted from 4 face buttons.")
    else:
        print("  [!] Warning: Some face buttons missing, using fallback disc extraction.")
        clean_disc = None

    # Mappings for face buttons
    xbox_face_map = {
        'cross': ('A', '#6cc24a'),     # Green A (bottom)
        'circle': ('B', '#e8483f'),    # Red B (right)
        'square': ('X', '#3d8fe8'),    # Blue X (left)
        'triangle': ('Y', '#f5c42e'),  # Yellow Y (top)
    }
    nin_face_map = {
        'cross': ('B', '#f0f0f0'),     # B (bottom)
        'circle': ('A', '#f0f0f0'),    # A (right)
        'square': ('Y', '#f0f0f0'),    # Y (left)
        'triangle': ('X', '#f0f0f0'),  # X (top)
    }

    generated = []

    for f in files:
        parts = f[:-4].split('_', 1)
        if len(parts) != 2:
            print(f"  [!] Skipping file with unexpected name: {f}")
            continue

        hash_str, btn_name = parts[0], parts[1]
        orig_path = os.path.join(orig_dir, f)
        orig_img = Image.open(orig_path)
        orig_arr = np.array(orig_img)

        xbox_img = None
        nin_img = None

        # A) Face Buttons
        if btn_name in xbox_face_map:
            ch_x, col_x = xbox_face_map[btn_name]
            xbox_img = render_face_glyph(clean_disc, ch_x, col_x)

            ch_n, col_n = nin_face_map[btn_name]
            nin_img = render_face_glyph(clean_disc, ch_n, col_n)

        # B) Bumpers
        elif btn_name in ('r1', 'l1'):
            cx = 61 if btn_name == 'r1' else 67
            clean_arr = inpaint_piece_text(orig_arr, btn_name)
            base_cleaned = Image.fromarray(clean_arr)

            txt_x = 'RB' if btn_name == 'r1' else 'LB'
            txt_n = 'R' if btn_name == 'r1' else 'L'

            xbox_img = render_trigger_glyph(base_cleaned, txt_x, (cx, 68), font_size=50)
            nin_img = render_trigger_glyph(base_cleaned, txt_n, (cx, 68), font_size=50)

        # C) Triggers
        elif btn_name in ('l2', 'r2'):
            cx = 66 if btn_name == 'l2' else 59
            txt_x = 'LT' if btn_name == 'l2' else 'RT'
            txt_n = 'ZL' if btn_name == 'l2' else 'ZR'

            clean_arr = inpaint_piece_text(orig_arr, btn_name)
            base_cleaned = Image.fromarray(clean_arr)

            xbox_img = render_trigger_glyph(base_cleaned, txt_x, (cx, 66), font_size=50)
            nin_img = render_trigger_glyph(base_cleaned, txt_n, (cx, 66), font_size=50)

        # D) Touchpad
        elif btn_name == 'touchpad':
            xbox_img = render_touchpad_glyph(clean_disc, 'xbox')
            nin_img = render_touchpad_glyph(clean_disc, 'nintendo')

        # E) Sticks & D-Pad (identical controllers / identical prompts)
        elif btn_name.startswith('stick_') or btn_name.startswith('dpad_') or btn_name in ('l3', 'r3'):
            xbox_img = orig_img.copy()
            nin_img = orig_img.copy()

        # F) Options & Share
        elif btn_name == 'options':
            xbox_img = render_options_glyph(clean_disc, 'xbox')
            nin_img = render_options_glyph(clean_disc, 'nintendo')

        elif btn_name == 'share':
            xbox_img = render_touchpad_glyph(clean_disc, 'xbox')
            nin_img = render_touchpad_glyph(clean_disc, 'nintendo')

        # G) Fallback unknown button
        else:
            print(f"  [!] Unknown button family '{btn_name}', copying original as fallback.")
            xbox_img = orig_img.copy()
            nin_img = orig_img.copy()

        # Save files by hash
        xbox_out_path = os.path.join(xbox_dir, f"{hash_str}.png")
        nin_out_path = os.path.join(nin_dir, f"{hash_str}.png")

        xbox_img.save(xbox_out_path, format="PNG")
        nin_img.save(nin_out_path, format="PNG")

        generated.append((btn_name, hash_str, orig_img, xbox_img, nin_img))
        print(f"  [+] Generated: {btn_name:12s} -> xbox/{hash_str}.png, nintendo/{hash_str}.png")

    return generated


def generate_comparison_sheets(generated_items, buzon_dir):
    """
    Generates the two acceptance comparison sheets in buzon_dir:
    1. buzon/comparacion_juego.png: 2x magnified on medium gray (#484848), side-by-side original | xbox | nintendo.
    2. buzon/comparacion_pequeno.png: 128px and 32px on dark background (#141619).
    """
    os.makedirs(buzon_dir, exist_ok=True)

    # Preferred display order
    order = [
        'cross', 'circle', 'square', 'triangle',
        'r1', 'l1', 'l2', 'r2',
        'touchpad',
        'dpad_left', 'dpad_right', 'dpad_up', 'dpad_down',
        'stick_l', 'stick_r', 'l3', 'r3', 'options', 'share'
    ]

    items = sorted(
        generated_items,
        key=lambda item: order.index(item[0]) if item[0] in order else 99
    )

    font_title = get_font(22)
    font_header = get_font(18)
    font_label = get_font(15)

    # -------------------------------------------------------------
    # 1. comparacion_juego.png (2x magnified on medium gray)
    # -------------------------------------------------------------
    # Layout:
    # Title bar + Header row + N icon rows
    col_w = 280
    row_h = 280
    label_w = 180
    header_h = 70
    title_h = 60
    total_w = label_w + 3 * col_w + 40
    total_h = title_h + header_h + len(items) * row_h + 30

    bg_color = (72, 72, 74, 255)
    card_bg = (56, 56, 58, 255)

    sheet_2x = Image.new('RGBA', (total_w, total_h), bg_color)
    d = ImageDraw.Draw(sheet_2x)

    # Title
    d.text((30, 20), "COMPARATIVA DE ICONOS DENTRO DEL JUEGO (XBOX & NINTENDO vs ORIGINAL)", font=font_title, fill=(240, 240, 240, 255))

    # Headers
    headers = [("Original (PlayStation)", label_w + 20),
               ("Xbox (Derivado)", label_w + 20 + col_w),
               ("Nintendo (Derivado)", label_w + 20 + 2 * col_w)]

    for text, hx in headers:
        d.text((hx + (col_w - 256) // 2, title_h + 20), text, font=font_header, fill=(225, 225, 225, 255))

    # Separator line
    d.line([(20, title_h + header_h - 10), (total_w - 20, title_h + header_h - 10)], fill=(90, 90, 92, 255), width=2)

    for i, (btn_name, hash_str, orig_img, xbox_img, nin_img) in enumerate(items):
        y_top = title_h + header_h + i * row_h

        # Alternate row background
        if i % 2 == 1:
            d.rectangle([15, y_top + 5, total_w - 15, y_top + row_h - 5], fill=(64, 64, 66, 255))

        # Row label
        label_text = f"{btn_name.upper()}\n{hash_str[:8]}..."
        d.text((30, y_top + 110), label_text, font=font_label, fill=(200, 200, 200, 255))

        # Scale 2x with nearest neighbor/clean sampling
        imgs_row = [orig_img, xbox_img, nin_img]
        for c_idx, im in enumerate(imgs_row):
            x_box = label_w + 20 + c_idx * col_w
            # Card background
            d.rounded_rectangle([x_box, y_top + 10, x_box + 260, y_top + 270], radius=8, fill=card_bg, outline=(80, 80, 84, 255), width=1)

            im_2x = im.resize((256, 256), Image.Resampling.NEAREST)
            sheet_2x.alpha_composite(im_2x, (x_box + 2, y_top + 12))

    comp_juego_path = os.path.join(buzon_dir, 'comparacion_juego.png')
    sheet_2x.save(comp_juego_path, format="PNG")
    print(f"  [+] Sheet saved: {comp_juego_path} ({total_w}x{total_h})")

    # -------------------------------------------------------------
    # 2. comparacion_pequeno.png (128px & 32px on dark background)
    # -------------------------------------------------------------
    dark_bg = (20, 22, 25, 255)
    row_h_sm = 150
    total_w_sm = 1060
    total_h_sm = title_h + header_h + len(items) * row_h_sm + 30

    sheet_sm = Image.new('RGBA', (total_w_sm, total_h_sm), dark_bg)
    d_sm = ImageDraw.Draw(sheet_sm)

    d_sm.text((30, 20), "ESCALA REAL (128 px) Y HUD EN JUEGO (32 px) SOBRE FONDO OSCURO", font=font_title, fill=(240, 240, 240, 255))

    # Header groups:
    # Top group labels
    d_sm.text((290, title_h + 10), "TAMAÑO REAL (128×128)", font=font_header, fill=(220, 220, 220, 255))
    d_sm.text((740, title_h + 10), "HUD EN JUEGO (32×32)", font=font_header, fill=(190, 205, 225, 255))

    # Subheaders for each column
    d_sm.text((215, title_h + 38), "Original", font=font_label, fill=(180, 180, 180, 255))
    d_sm.text((365, title_h + 38), "Xbox", font=font_label, fill=(180, 180, 180, 255))
    d_sm.text((495, title_h + 38), "Nintendo", font=font_label, fill=(180, 180, 180, 255))

    d_sm.text((675, title_h + 38), "Original", font=font_label, fill=(170, 180, 195, 255))
    d_sm.text((790, title_h + 38), "Xbox", font=font_label, fill=(170, 180, 195, 255))
    d_sm.text((900, title_h + 38), "Nintendo", font=font_label, fill=(170, 180, 195, 255))

    d_sm.line([(20, title_h + header_h - 10), (total_w_sm - 20, title_h + header_h - 10)], fill=(40, 45, 52, 255), width=2)

    for i, (btn_name, hash_str, orig_img, xbox_img, nin_img) in enumerate(items):
        y_top = title_h + header_h + i * row_h_sm

        if i % 2 == 1:
            d_sm.rectangle([15, y_top + 5, total_w_sm - 15, y_top + row_h_sm - 5], fill=(26, 29, 34, 255))

        # Label
        d_sm.text((30, y_top + 55), btn_name.upper(), font=font_label, fill=(180, 185, 195, 255))

        # 128 px
        sheet_sm.alpha_composite(orig_img, (180, y_top + 10))
        sheet_sm.alpha_composite(xbox_img, (320, y_top + 10))
        sheet_sm.alpha_composite(nin_img, (460, y_top + 10))

        # Vertical separator
        d_sm.line([(615, y_top + 10), (615, y_top + row_h_sm - 10)], fill=(45, 50, 58, 255), width=1)

        # 32 px HUD scaled
        o_32 = orig_img.resize((32, 32), Image.Resampling.LANCZOS)
        x_32 = xbox_img.resize((32, 32), Image.Resampling.LANCZOS)
        n_32 = nin_img.resize((32, 32), Image.Resampling.LANCZOS)

        sheet_sm.alpha_composite(o_32, (685, y_top + 58))
        sheet_sm.alpha_composite(x_32, (795, y_top + 58))
        sheet_sm.alpha_composite(n_32, (915, y_top + 58))

    comp_peq_path = os.path.join(buzon_dir, 'comparacion_pequeno.png')
    sheet_sm.save(comp_peq_path, format="PNG")
    print(f"  [+] Sheet saved: {comp_peq_path} ({total_w_sm}x{total_h_sm})")

    # -------------------------------------------------------------
    # 3. gatillos_x3.png (Original | Xbox | Nintendo ampliados x3)
    # -------------------------------------------------------------
    gatillo_names = ['r1', 'l2', 'r2']
    gatillo_items = [it for it in items if it[0] in gatillo_names]

    if gatillo_items:
        g_col_w = 420
        g_row_h = 420
        g_label_w = 160
        g_header_h = 70
        g_title_h = 60
        g_total_w = g_label_w + 3 * g_col_w + 40
        g_total_h = g_title_h + g_header_h + len(gatillo_items) * g_row_h + 30

        sheet_g3 = Image.new('RGBA', (g_total_w, g_total_h), (55, 55, 58, 255))
        d_g3 = ImageDraw.Draw(sheet_g3)

        d_g3.text((30, 20), "REVISIÓN DE GATILLOS Y BUMPERS (AMPLIADO ×3)", font=font_title, fill=(240, 240, 240, 255))

        g_headers = [
            ("Original (PlayStation)", g_label_w + 20),
            ("Xbox (RB / LT / RT)", g_label_w + 20 + g_col_w),
            ("Nintendo (R / ZL / ZR)", g_label_w + 20 + 2 * g_col_w)
        ]
        for text, hx in g_headers:
            d_g3.text((hx + (g_col_w - 384) // 2, g_title_h + 20), text, font=font_header, fill=(225, 225, 225, 255))

        d_g3.line([(20, g_title_h + g_header_h - 10), (g_total_w - 20, g_title_h + g_header_h - 10)], fill=(80, 80, 84, 255), width=2)

        for i, (btn_name, hash_str, orig_img, xbox_img, nin_img) in enumerate(gatillo_items):
            y_top = g_title_h + g_header_h + i * g_row_h
            d_g3.text((30, y_top + 180), btn_name.upper(), font=font_label, fill=(200, 200, 200, 255))

            for c_idx, im in enumerate([orig_img, xbox_img, nin_img]):
                x_box = g_label_w + 20 + c_idx * g_col_w
                d_g3.rounded_rectangle([x_box, y_top + 10, x_box + 394, y_top + 404], radius=8, fill=(44, 44, 46, 255), outline=(70, 70, 74, 255), width=1)
                im_3x = im.resize((384, 384), Image.Resampling.NEAREST)
                sheet_g3.alpha_composite(im_3x, (x_box + 5, y_top + 15))

        gatillos_path = os.path.join(buzon_dir, 'gatillos_x3.png')
        sheet_g3.save(gatillos_path, format="PNG")
        print(f"  [+] Sheet saved: {gatillos_path} ({g_total_w}x{g_total_h})")


def main():
    parser = argparse.ArgumentParser(description="Generate Xbox and Nintendo in-game button icons.")
    parser.add_argument("orig_dir", help="Directory with original <hash>_<button>.png files")
    parser.add_argument("out_dir", help="Directory where xbox/ and nintendo/ will be created")
    parser.add_argument("--sheets", help="Optional buzon directory to output comparison sheets", default=None)

    args = parser.parse_args()

    print(f"[>] Generating glyphs from '{args.orig_dir}' into '{args.out_dir}'...")
    generated_items = make_glyphs(args.orig_dir, args.out_dir)

    if args.sheets:
        print(f"[>] Generating comparison sheets in '{args.sheets}'...")
        generate_comparison_sheets(generated_items, args.sheets)

    print("[+] All glyphs generated successfully.")


if __name__ == '__main__':
    main()
