#!/usr/bin/env python3
"""
Generates the Catppuccin themes for the Beef IDE: Mocha, Macchiato, Frappe and Latte.
Each flavor gets its own folder next to this script containing:

    theme.toml      colors (select the folder, e.g. "Catppuccin/Latte", under UI > Theme)
    UI*.png         the IDE's images/DarkUI*.png atlases recolored with the flavor's palette
    cache/UI*.png   the same atlases prebuilt, so the theme works where the IDE can't run
                    images/ImgCreate itself (e.g. a packaged BeefIDE.app)

Run from anywhere (requires Pillow and numpy):

    python3 IDE/dist/themes/Catppuccin/make_themes.py [flavor ...]

Every color is assigned by palette role, so all flavors share one mapping:
  * Atlas grays go through a luminance ramp onto the base colors (crust, mantle, base,
    surface0-2, overlay0-2, subtext0-1, text). Pure white is kept, because the IDE tints
    those images (menu selection, glow dots, ...).
  * Saturated atlas pixels take the hue of the nearest accent, keeping their shading, with
    the saturation boosted so icons such as breakpoints stay vivid.
  * Syntax follows catppuccin/nvim: keywords mauve, types yellow, methods blue, strings
    green, numbers and booleans peach, value types (structs, enums, primitives) teal,
    fields and namespaces lavender, parameters maroon, comments overlay2.
"""

import os
import sys
import numpy as np
from PIL import Image

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

def find_images_dir():
    # The IDE's dist/images folder; this script lives somewhere under dist/themes
    d = SCRIPT_DIR
    while True:
        cand = os.path.join(d, "images", "DarkUI.png")
        if os.path.exists(cand):
            return os.path.dirname(cand)
        parent = os.path.dirname(d)
        if parent == d:
            sys.exit("Couldn't find images/DarkUI.png above " + SCRIPT_DIR)
        d = parent

# https://catppuccin.com/palette
FLAVORS = {
    "Mocha": dict(dark=True,
        rosewater=0xF5E0DC, flamingo=0xF2CDCD, pink=0xF5C2E7, mauve=0xCBA6F7, red=0xF38BA8, maroon=0xEBA0AC,
        peach=0xFAB387, yellow=0xF9E2AF, green=0xA6E3A1, teal=0x94E2D5, sky=0x89DCEB, sapphire=0x74C7EC,
        blue=0x89B4FA, lavender=0xB4BEFE, text=0xCDD6F4, subtext1=0xBAC2DE, subtext0=0xA6ADC8,
        overlay2=0x9399B2, overlay1=0x7F849C, overlay0=0x6C7086, surface2=0x585B70, surface1=0x45475A,
        surface0=0x313244, base=0x1E1E2E, mantle=0x181825, crust=0x11111B),
    "Macchiato": dict(dark=True,
        rosewater=0xF4DBD6, flamingo=0xF0C6C6, pink=0xF5BDE6, mauve=0xC6A0F6, red=0xED8796, maroon=0xEE99A0,
        peach=0xF5A97F, yellow=0xEED49F, green=0xA6DA95, teal=0x8BD5CA, sky=0x91D7E3, sapphire=0x7DC4E4,
        blue=0x8AADF4, lavender=0xB7BDF8, text=0xCAD3F5, subtext1=0xB8C0E0, subtext0=0xA5ADCB,
        overlay2=0x939AB7, overlay1=0x8087A2, overlay0=0x6E738D, surface2=0x5B6078, surface1=0x494D64,
        surface0=0x363A4F, base=0x24273A, mantle=0x1E2030, crust=0x181926),
    "Frappe": dict(dark=True,
        rosewater=0xF2D5CF, flamingo=0xEEBEBE, pink=0xF4B8E4, mauve=0xCA9EE6, red=0xE78284, maroon=0xEA999C,
        peach=0xEF9F76, yellow=0xE5C890, green=0xA6D189, teal=0x81C8BE, sky=0x99D1DB, sapphire=0x85C1DC,
        blue=0x8CAAEE, lavender=0xBABBF1, text=0xC6D0F5, subtext1=0xB5BFE2, subtext0=0xA5ADCE,
        overlay2=0x949CBB, overlay1=0x838BA7, overlay0=0x737994, surface2=0x626880, surface1=0x51576D,
        surface0=0x414559, base=0x303446, mantle=0x292C3C, crust=0x232634),
    "Latte": dict(dark=False,
        rosewater=0xDC8A78, flamingo=0xDD7878, pink=0xEA76CB, mauve=0x8839EF, red=0xD20F39, maroon=0xE64553,
        peach=0xFE640B, yellow=0xDF8E1D, green=0x40A02B, teal=0x179299, sky=0x04A5E5, sapphire=0x209FB5,
        blue=0x1E66F5, lavender=0x7287FD, text=0x4C4F69, subtext1=0x5C5F77, subtext0=0x6C6F85,
        overlay2=0x7C7F93, overlay1=0x8C8FA1, overlay0=0x9CA0B0, surface2=0xACB0BE, surface1=0xBCC0CC,
        surface0=0xCCD0DA, base=0xEFF1F5, mantle=0xE6E9EF, crust=0xDCE0E8),
}

# Accent roles and their saturation boost for icons. Red and yellow get the most so
# breakpoints, errors and warnings pop. Boosts cap at full saturation (Latte is already near it).
ACCENT_BOOSTS = [
    ("red", 1.9), ("peach", 1.6), ("yellow", 1.9), ("green", 1.6), ("teal", 1.6), ("sky", 1.6),
    ("sapphire", 1.6), ("blue", 1.6), ("lavender", 1.6), ("mauve", 1.6), ("pink", 1.6),
]

def mix(a, b, t):
    ca = [(a >> s) & 0xFF for s in (16, 8, 0)]
    cb = [(b >> s) & 0xFF for s in (16, 8, 0)]
    c = [round(x + (y - x) * t) for x, y in zip(ca, cb)]
    return (c[0] << 16) | (c[1] << 8) | c[2]

def derived(p):
    """Colors built from the palette that both the atlas and theme.toml use"""
    d = {}
    # Panels and inactive tabs: between base and surface0
    d["panel"] = mix(p["base"], p["surface0"], 0.55)
    if p["dark"]:
        d["shadow"] = mix(p["crust"], 0x000000, 0.35)  # deepest outlines, darker than crust
        d["outline"] = p["crust"]
        d["dialogOutlineOut"] = p["crust"]
    else:
        # On a light theme, outlines and shadows must be darker than the backgrounds
        d["shadow"] = p["overlay1"]
        d["outline"] = p["overlay0"]
        d["dialogOutlineOut"] = p["overlay0"]
    return d

# ---------------------------------------------------------------------------------------
# theme.toml
# ---------------------------------------------------------------------------------------

# (key, role) or (key, role, alpha). Roles are palette names or derived() names.
COLOR_ROLES = [
    "# UI",
    ("Text", "text"),
    ("TextDisabled", "overlay1"),
    ("TextSelected", "surface1"),
    ("Window", "panel"),
    ("DialogOutlineIn", "surface1"),
    ("DialogOutlineOut", "dialogOutlineOut"),
    ("Grid", "text", 0x0C),
    ("Background", "crust"),
    ("SelectedOutline", "lavender"),
    ("MenuFocused", "mauve"),
    ("MenuSelected", "overlay2"),
    ("AutoCompleteSubText", "subtext0"),
    ("AutoCompleteDocText", "subtext1"),
    ("AutoCompleteActiveText", "lavender"),
    ("WorkspaceDisabledText", "overlay1"),
    ("WorkspaceFailedText", "red"),
    ("WorkspaceManualIncludeText", "lavender"),
    ("WorkspaceIgnoredText", "overlay0"),
    "",
    "# Code",
    ("Code", "text"),
    ("Keyword", "mauve"),
    ("Literal", "green"),
    ("Number", "peach"),
    ("Identifier", "text"),
    ("Local", "text"),
    ("Parameter", "maroon"),
    ("Member", "lavender"),
    ("Static", "lavender"),
    ("Method", "blue"),
    ("Comment", "overlay2"),
    ("Type", "yellow"),
    ("PrimitiveType", "teal"),  # value types are teal, classes and other types yellow
    ("Struct", "teal"),  # structs and enums
    ("RefType", "yellow"),
    ("Interface", "yellow"),
    ("GenericParam", "yellow"),
    ("Namespace", "lavender"),
    "",
    "# Debugger / output",
    ("DisassemblyText", "subtext0"),
    ("DisassemblyFileName", "blue"),
    ("Error", "red"),
    ("BuildText", "overlay1"),
    ("BuildError", "red"),
    ("BuildWarning", "yellow"),
    ("BuildSuccess", "green"),
    ("VisibleWhiteSpace", "surface1"),
    "",
    "# Editor highlights",
    ("CurrentLineHilite", "surface0"),
    ("CurrentLineNumberHilite", "text", 0x18),
    ("CharPairHilite", "text", 0x30),
    ("CodeHilite", "surface1"),
    ("CodeHiliteUnfocused", "surface1", 0x80),
]

PALETTE_ORDER = [
    ["rosewater", "flamingo", "pink", "mauve"],
    ["red", "maroon", "peach", "yellow"],
    ["green", "teal", "sky", "sapphire"],
    ["blue", "lavender"],
    ["text", "subtext1", "subtext0"],
    ["overlay2", "overlay1", "overlay0"],
    ["surface2", "surface1", "surface0"],
    ["base", "mantle", "crust"],
]

def write_theme_toml(name, p, path):
    colors = dict(p)
    colors.update(derived(p))
    lines = [
        f"# Catppuccin {name} theme for the Beef IDE",
        f"# Palette: https://catppuccin.com/palette ({name})",
        "#",
    ]
    for row in PALETTE_ORDER:
        lines.append("#   " + "  ".join(f"{r:<9} {p[r]:06X}" for r in row).rstrip())
    lines += [
        "#",
        "# Colors are 0xAARRGGBB. Generated by ../make_themes.py, along with the UI images (UI*.png).",
        "# Syntax follows catppuccin/nvim: keywords mauve, types yellow, methods blue, strings green,",
        "# numbers and booleans peach, value types (structs, enums, primitives) teal, other types yellow,",
        "# fields and namespaces lavender, parameters maroon, comments overlay2.",
        "# The icon atlas uses saturation-boosted accents so breakpoints stand out.",
        "",
        "[Colors]",
    ]
    for entry in COLOR_ROLES:
        if isinstance(entry, str):
            lines.append(entry)
            continue
        key, role = entry[0], entry[1]
        alpha = entry[2] if len(entry) > 2 else 0xFF
        lines.append(f"{key} = 0x{alpha:02X}{colors[role]:06X}")
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")

# ---------------------------------------------------------------------------------------
# UI atlas
# ---------------------------------------------------------------------------------------

def hexrgb(h):
    return np.array([(h >> 16) & 0xFF, (h >> 8) & 0xFF, h & 0xFF], dtype=np.float64)

def rgb_to_hsv(rgb):
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    mx = rgb.max(axis=-1)
    mn = rgb.min(axis=-1)
    d = mx - mn
    h = np.zeros_like(mx)
    nz = d > 1e-9
    rm = nz & (mx == r)
    gm = nz & (mx == g) & ~rm
    bm = nz & ~rm & ~gm
    h[rm] = ((g[rm] - b[rm]) / d[rm]) % 6
    h[gm] = (b[gm] - r[gm]) / d[gm] + 2
    h[bm] = (r[bm] - g[bm]) / d[bm] + 4
    h = h * 60.0
    s = np.where(mx > 1e-9, d / np.maximum(mx, 1e-9), 0)
    return h, s, mx

def boost_saturation(rgb, factor):
    h, s, v = rgb_to_hsv(rgb[None, :] / 255.0)
    h, s, v = h[0], min(1.0, s[0] * factor), v[0]
    c = v * s
    x = c * (1 - abs((h / 60.0) % 2 - 1))
    m = v - c
    sector = int(h // 60) % 6
    r, g, b = [(c, x, 0), (x, c, 0), (0, c, x), (0, x, c), (x, 0, c), (c, 0, x)][sector]
    return np.array([r + m, g + m, b + m]) * 255.0

def gray_ramp(p):
    """Original atlas gray level -> palette color. Anchors chosen from the default atlas:
    10 = outlines, 28 = Bkg, 45 = EditBox (editor), 68 = Window/inactive tab,
    82 = active tab, 99 = buttons, 118+ = highlights/glyphs"""
    d = derived(p)
    return [
        (0,   d["shadow"]),
        (10,  d["outline"]),
        (29,  p["mantle"] if p["dark"] else p["crust"]),
        (45,  p["base"]),
        (68,  d["panel"]),
        (82,  p["surface0"]),
        (99,  p["surface1"]),
        (118, p["surface2"]),
        (140, p["overlay0"]),
        (165, p["overlay1"]),
        (190, p["overlay2"]),
        (210, p["subtext0"]),
        (230, p["subtext1"]),
        (250, p["text"]),
        (254, p["text"]),
        (255, 0xFFFFFF),  # white tint masks stay white
    ]

# DarkTheme.ImageIdx values below this are UI chrome (backgrounds, buttons, tabs, scrollbars,
# menus); the active tab's colored underline must not make it count as an icon
FIRST_ICON_IDX = 49
ATLAS_COLS = 20
ATLAS_CELL = 20  # pixels per cell at 1x

def icon_cell_masks(s, v, alpha, width):
    """Per-pixel masks of the atlas's icon area (cells from FIRST_ICON_IDX on) and of the
    cells in it that hold colored icons"""
    cell = ATLAS_CELL * width // (ATLAS_CELL * ATLAS_COLS)
    area = np.zeros(s.shape, dtype=bool)
    colored_cells = np.zeros(s.shape, dtype=bool)
    rows, cols = s.shape[0] // cell, s.shape[1] // cell
    for row in range(rows):
        for col in range(cols):
            if row * cols + col < FIRST_ICON_IDX:
                continue
            ys, xs = slice(row * cell, (row + 1) * cell), slice(col * cell, (col + 1) * cell)
            area[ys, xs] = True
            colored = (s[ys, xs] > 0.35) & (v[ys, xs] > 0.25) & (alpha[ys, xs] > 128)
            if colored.sum() >= max(2, cell * cell // 100):
                colored_cells[ys, xs] = True
    return area, colored_cells

def apply_ramp(luma, ramp):
    xs = np.array([x for x, _ in ramp], dtype=np.float64)
    out = np.empty(luma.shape + (3,))
    for c in range(3):
        ys = np.array([hexrgb(col)[c] for _, col in ramp])
        out[..., c] = np.interp(luma, xs, ys)
    return out

def recolor(img, p):
    ramp = gray_ramp(p)
    accent_rgb = np.array([boost_saturation(hexrgb(p[r]), f) for r, f in ACCENT_BOOSTS])
    accent_h, _, accent_v = rgb_to_hsv(accent_rgb / 255.0)

    a = np.asarray(img.convert("RGBA"), dtype=np.float64)
    rgb = a[..., :3]
    alpha = a[..., 3:]

    h, s, v = rgb_to_hsv(rgb / 255.0)

    # Grays: use luma so slightly tinted grays land on the right step
    luma = rgb @ np.array([0.299, 0.587, 0.114])
    gray_out = apply_ramp(luma, ramp)

    # Accents: nearest hue, scaled by the pixel's brightness
    dh = np.abs(h[..., None] - accent_h[None, None, :])
    dh = np.minimum(dh, 360 - dh)
    idx = dh.argmin(axis=-1)
    shade = np.clip(v / accent_v[idx], 0, 1)[..., None]
    acc_out = accent_rgb[idx] * shade

    w = np.clip((s - 0.15) / 0.25, 0, 1)
    # Very dark pixels carry little hue information
    w *= np.clip(v / 0.25, 0, 1)
    w = w[..., None]

    if not p["dark"]:
        # The light theme's chrome ramp turns black into a light outline gray and white into dark
        # text. In the icon area that's wrong in two ways, so:
        #  * colored icon cells keep their light/dark relationship, from a dark text shade up to
        #    white (breakpoint highlights, the "i" in info icons stay white)
        #  * black glyphs ({ }, //, ?, x) stay dark; lighter gray glyphs still invert to dark
        dark_text = mix(p["text"], 0x000000, 0.4)
        area, colored_cells = icon_cell_masks(s, v, alpha[..., 0], img.width)
        glyph_ramp = [(0, dark_text), (20, dark_text)] + [(x, c) for x, c in ramp if x >= 45]
        gray_out = np.where(area[..., None], apply_ramp(luma, glyph_ramp), gray_out)
        icon_ramp = [(0, dark_text), (255, 0xFFFFFF)]
        gray_out = np.where(colored_cells[..., None], apply_ramp(luma, icon_ramp), gray_out)

    out = gray_out * (1 - w) + acc_out * w
    res = np.concatenate([np.clip(np.round(out), 0, 255), alpha], axis=-1).astype(np.uint8)
    return Image.fromarray(res, "RGBA")

# ---------------------------------------------------------------------------------------

def make_flavor(name, images_dir):
    p = FLAVORS[name]
    out_dir = os.path.join(SCRIPT_DIR, name)
    os.makedirs(os.path.join(out_dir, "cache"), exist_ok=True)
    write_theme_toml(name, p, os.path.join(out_dir, "theme.toml"))
    for src, dst in (("DarkUI.png", "UI.png"), ("DarkUI_2.png", "UI_2.png"), ("DarkUI_4.png", "UI_4.png")):
        img = recolor(Image.open(os.path.join(images_dir, src)), p)
        img.save(os.path.join(out_dir, dst))
        img.save(os.path.join(out_dir, "cache", dst))
    print("wrote", name)

def main():
    names = sys.argv[1:] or list(FLAVORS)
    for n in names:
        if n not in FLAVORS:
            sys.exit(f"Unknown flavor '{n}' (choose from {', '.join(FLAVORS)})")
    images_dir = find_images_dir()
    for n in names:
        make_flavor(n, images_dir)

if __name__ == "__main__":
    main()
