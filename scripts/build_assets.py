"""Genera los SVG del README de perfil con la estética del portafolio: figuras escritas en glifos.

Uso: python3 scripts/build_assets.py  (requiere Pillow)

Las imágenes de `source/*-glyphs.webp` son datos, como en el portafolio: R brillo, G profundidad,
B silueta. Cada SVG lleva Geist / Geist Mono embebidas para que la rejilla de glifos no dependa
de las fuentes de quien lo mire.
"""

from __future__ import annotations

import base64
import io
import math
from pathlib import Path
from xml.sax.saxutils import escape

from PIL import Image, ImageFilter, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parent
OUT = ROOT.parent / "assets"
SRC = ROOT / "source"
FONTS = ROOT / "fonts"

# Paleta del portafolio.
BG = "#0e0e10"
SURFACE = "#1a1a1e"
BORDER = "#2a2a30"
FG = "#f4f4f5"
MUTED = "#a1a1aa"
SUBTLE = "#71717a"
ACCENT = FG  # Sin lima en el README: el acento es blanco.
GREY_DARK = (0x3F, 0x3F, 0x46)
GREY_LIGHT = (0xE4, 0xE4, 0xE7)
LIME_LIGHT = (0xF4, 0xF4, 0xF5)  # Celdas de acento en blanco, no lima.

# Rampa de Paul Bourke, de dispersa a densa (la misma del portafolio).
RAMP = " .'`^\",:;Il!i><~+_-?][}{1)(|\\/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$"
MONO_ADVANCE = 0.6  # Avance de Geist Mono en em.
LEVELS = 6  # Tonos de gris por figura: menos tspans, mismo efecto.

SANS_METRICS = ImageFont.truetype(str(FONTS / "Geist-Regular.ttf"), 100)


def b64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode()


FONT_CSS = (
    "@font-face{font-family:G;src:url(data:font/woff2;base64,%s) format('woff2');font-weight:100 900}"
    "@font-face{font-family:GM;src:url(data:font/woff2;base64,%s) format('woff2');font-weight:100 900}"
    ".s{font-family:G,system-ui,sans-serif}.m{font-family:GM,ui-monospace,monospace}"
    "@media (prefers-reduced-motion:reduce){*{animation:none!important}}"
) % (b64(FONTS / "geist-latin.woff2"), b64(FONTS / "geist-mono-latin.woff2"))


def hex_rgb(c: tuple[int, int, int]) -> str:
    return "#%02x%02x%02x" % c


def mix(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))  # type: ignore[return-value]


def hash01(x: int, y: int, seed: int = 0) -> float:
    """Ruido determinista por celda (el mismo dibujo en cada build)."""
    h = (x * 374761393 + y * 668265263 + seed * 1442695041) & 0xFFFFFFFF
    h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
    return ((h ^ (h >> 16)) & 0xFFFF) / 0xFFFF


def svg_open(w: int, h: int, label: str, extra_css: str = "") -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
        f'role="img" aria-label="{escape(label)}"><title>{escape(label)}</title>'
        f"<style>{FONT_CSS}{extra_css}</style>"
    )


def text_width(text: str, size: float, tracking: float = 0.0) -> float:
    return SANS_METRICS.getlength(text) * size / 100 + tracking * len(text)


def wrap(text: str, size: float, width: float) -> list[str]:
    lines, line = [], ""
    for word in text.split():
        probe = f"{line} {word}".strip()
        if text_width(probe, size) > width and line:
            lines.append(line)
            line = word
        else:
            line = probe
    return lines + [line] if line else lines


# --------------------------------------------------------------------------------------------
# Figuras en glifos
# --------------------------------------------------------------------------------------------


def glyph_rows(
    data: Image.Image,
    cols: int,
    rows: int,
    *,
    seed: int,
    accent_rate: float = 0.012,
    lum_gain: float = 1.0,
    photo: Image.Image | None = None,
) -> list[list[tuple[str, int]]]:
    """Celdas de la figura: (glifo, clase) por columna. Clase -1 = vacío, LEVELS = lima.

    Con `photo`, el brillo sale de la foto original (más contraste en el rostro) y la imagen de
    datos solo aporta silueta y profundidad.
    """
    small = data.convert("RGB").resize((cols, rows), Image.Resampling.BOX)
    px = small.load()
    shade = None
    if photo is not None:
        grey = photo.convert("L").crop((0, 0, data.width, data.height))
        grey = grey.filter(ImageFilter.UnsharpMask(radius=6, percent=120, threshold=2))
        grey = grey.resize((cols, rows), Image.Resampling.BOX)
        # Ecualizado solo dentro de la silueta: la pared clara del fondo no cuenta.
        mask = small.getchannel("B").point(lambda v: 255 if v > 115 else 0)
        grey = Image.blend(grey, ImageOps.equalize(grey, mask=mask), 1.0)
        shade = grey.load()
    grid = []
    for y in range(rows):
        row = []
        for x in range(cols):
            r, g, b = px[x, y]
            silhouette = b / 255
            if silhouette < 0.45:
                row.append((" ", -1))
                continue
            base = shade[x, y] / 255 if shade is not None else r / 255
            lum = min(1.0, base * lum_gain) ** 0.62 * min(1.0, silhouette * 1.4)
            # Un poco de relieve con la profundidad para que no quede plano.
            lum = max(0.0, min(1.0, lum * (0.82 + 0.3 * g / 255)))
            idx = 8 + int(lum * (len(RAMP) - 9))
            idx = max(1, min(len(RAMP) - 1, idx + int((hash01(x, y, seed) - 0.5) * 6)))
            glyph = RAMP[idx]
            level = min(LEVELS - 1, int(lum * LEVELS))
            if lum > 0.15 and hash01(x, y, seed + 7) > 1 - accent_rate:
                level = LEVELS
            row.append((glyph, level))
        grid.append(row)
    return grid


def level_css(prefix: str, accent: str = hex_rgb(LIME_LIGHT)) -> str:
    rules = []
    for i in range(LEVELS):
        t = (i + 0.5) / LEVELS
        rules.append(f".{prefix}{i}{{fill:{hex_rgb(mix(GREY_DARK, GREY_LIGHT, t ** 0.75))}}}")
    rules.append(f".{prefix}{LEVELS}{{fill:{accent}}}")
    return "".join(rules)


def glyph_text(
    grid: list[list[tuple[str, int]]],
    x0: float,
    y0: float,
    cell: float,
    font: float,
    prefix: str,
    row_class: str = "",
    row_delay: tuple[float, float] | None = None,
) -> str:
    """Una <text> por fila con tspans por tramo de color; las letras caen en una rejilla cuadrada."""
    spacing = cell - font * MONO_ADVANCE
    out = []
    first_row = next((i for i, r in enumerate(grid) if any(c[1] >= 0 for c in r)), 0)
    for y, row in enumerate(grid):
        if all(c[1] < 0 for c in row):
            continue
        start = next(i for i, c in enumerate(row) if c[1] >= 0)
        end = max(i for i, c in enumerate(row) if c[1] >= 0) + 1
        spans, run, run_level = [], "", None
        for glyph, level in row[start:end]:
            level = level if level >= 0 else run_level  # los huecos se pegan al tramo actual
            if level != run_level and run:
                spans.append((run, run_level))
                run = ""
            run_level = level
            run += glyph
        if run:
            spans.append((run, run_level))
        body = "".join(
            f'<tspan class="{prefix}{lvl}">{escape(txt)}</tspan>' if lvl is not None else escape(txt)
            for txt, lvl in spans
        )
        style = ""
        if row_delay:
            style = f' style="animation-delay:{row_delay[0] + (y - first_row) * row_delay[1]:.3f}s"'
        cls = f' class="{row_class}"' if row_class else ""
        out.append(
            f'<text x="{x0 + start * cell:.1f}" y="{y0 + (y + 1) * cell:.1f}"{cls}{style} '
            f'letter-spacing="{spacing:.2f}">{body}</text>'
        )
    return (
        f'<g class="m" font-size="{font}" xml:space="preserve">' + "".join(out) + "</g>"
    )


def stars(w: int, h: int, count: int, seed: int, avoid: tuple[tuple[int, int, int, int], ...] = ()) -> str:
    out = []
    glyphs = "+×*·"
    for i in range(count * 3):
        x = hash01(i, 1, seed) * w
        y = hash01(i, 2, seed) * h
        if any(a[0] < x < a[2] and a[1] < y < a[3] for a in avoid):
            continue
        g = glyphs[int(hash01(i, 3, seed) * len(glyphs))]
        size = 9 + hash01(i, 4, seed) * 6
        dur = 3 + hash01(i, 5, seed) * 4
        delay = hash01(i, 6, seed) * 4
        out.append(
            f'<text x="{x:.0f}" y="{y:.0f}" font-size="{size:.0f}" class="st" '
            f'style="animation-duration:{dur:.1f}s;animation-delay:{delay:.1f}s">{g}</text>'
        )
        if len(out) >= count:
            break
    return f'<g class="m" fill="#3f3f46">{"".join(out)}</g>'


# --------------------------------------------------------------------------------------------
# Hero: nombre + David en glifos
# --------------------------------------------------------------------------------------------


def build_hero() -> None:
    w, h = 1280, 620
    cell, font = 4.6, 6.2
    fig_x, fig_y, fig_w = 520, 18, 900
    data = Image.open(SRC / "david-glyphs.webp")
    cols = int(fig_w / cell)
    rows_full = int(cols * data.height / data.width)
    rows_visible = int((h - fig_y) / cell)
    photo = Image.open(SRC / "david.jpg")
    cols_visible = int((w - fig_x) / cell) + 1
    grid = [r[:cols_visible] for r in glyph_rows(data, cols, rows_full, seed=3, photo=photo)[:rows_visible]]

    css = (
        level_css("d")
        + ".rw{animation:w .7s cubic-bezier(.22,1,.36,1) both}"
        ".rw tspan{animation:ink 1.6s ease-out both;animation-delay:inherit}"
        "@keyframes w{from{opacity:0;transform:translateY(-4px)}to{opacity:1;transform:none}}"
        f"@keyframes ink{{0%{{fill:{ACCENT}}}}}"
        ".rv{animation:rv .9s cubic-bezier(.22,1,.36,1) both}"
        "@keyframes rv{from{opacity:0;transform:translateY(18px)}to{opacity:1;transform:none}}"
        ".st{animation:tw 5s ease-in-out infinite both}"
        "@keyframes tw{0%,100%{opacity:.25}50%{opacity:1}}"
        ".dot{animation:pulse 2.4s ease-in-out infinite}"
        "@keyframes pulse{0%,100%{opacity:1}50%{opacity:.35}}"
        ".cur{animation:blink 1s steps(1) infinite}@keyframes blink{50%{opacity:0}}"
    )

    def rv(delay: float) -> str:
        return f'class="rv" style="animation-delay:{delay}s"'

    tx = 64
    cta_label = "VER PORTAFOLIO ↗"
    cta_w = len(cta_label) * 13 * MONO_ADVANCE + 2 * 1.2 * len(cta_label) + 44
    parts = [
        svg_open(w, h, "Bastian A. Sanchez — Desarrollador web full stack. Retrato del David escrito en glifos.", css),
        '<defs><clipPath id="card"><rect width="1280" height="620" rx="20"/></clipPath></defs>',
        f'<g clip-path="url(#card)"><rect width="{w}" height="{h}" fill="{BG}"/>',
        stars(w, h, 46, seed=11, avoid=((640, 0, 1280, 620), (40, 50, 520, 90), (40, 140, 520, 480), (40, 490, 520, 580))),
        glyph_text(grid, fig_x, fig_y, cell, font, "d", "rw", (0.25, 0.016)),
        "</g>",
        # Texto.
        f'<g {rv(0.2)}><text x="{tx}" y="78" class="m" font-size="13" fill="{SUBTLE}" letter-spacing="1.3">'
        f'// GALAPAN · APIZACO, TLAXCALA — MX</text></g>',
        f'<g {rv(0.5)}><text x="{tx - 4}" y="246" class="s" font-size="98" font-weight="500" '
        f'letter-spacing="-2.9" fill="{FG}">Bastian A.</text></g>',
        f'<g {rv(0.62)}><text x="{tx - 4}" y="336" class="s" font-size="98" font-weight="500" '
        f'letter-spacing="-2.9" fill="{MUTED}">Sanchez</text></g>',
        f'<g {rv(0.8)}><text x="{tx}" y="396" class="m" font-size="15" fill="{FG}">'
        f'Desarrollador web full stack<tspan fill="{ACCENT}" class="cur">_</tspan></text>'
        f'<text x="{tx}" y="436" class="s" font-size="23" fill="{MUTED}">Construyo interfaces web rápidas,</text>'
        f'<text x="{tx}" y="466" class="s" font-size="23" fill="{MUTED}">accesibles y con movimiento.</text></g>',
        f'<g {rv(0.95)}>'
        f'<rect x="{tx}" y="508" width="{cta_w:.0f}" height="50" rx="4" fill="{ACCENT}"/>'
        f'<text x="{tx + 22}" y="538" class="m" font-size="13" letter-spacing="1.2" fill="{BG}">{cta_label}</text>'
        f'<rect x="{tx + cta_w + 10:.0f}" y="508" width="214" height="50" rx="4" fill="{SURFACE}" stroke="{BORDER}"/>'
        f'<circle cx="{tx + cta_w + 32:.0f}" cy="533" r="4" fill="{ACCENT}" class="dot"/>'
        f'<text x="{tx + cta_w + 46:.0f}" y="538" class="m" font-size="13" letter-spacing="1.2" fill="{FG}">'
        f"OPEN TO WORK</text></g>",
        f'<rect x=".5" y=".5" width="{w - 1}" height="{h - 1}" rx="19.5" fill="none" stroke="{BORDER}"/>',
        "</svg>",
    ]
    (OUT / "hero.svg").write_text("".join(parts), encoding="utf-8")


# --------------------------------------------------------------------------------------------
# Cinta: la frase del portafolio corriendo en mono
# --------------------------------------------------------------------------------------------


def build_seam() -> None:
    w, h = 1280, 56
    phrase = "PREFIERO SOBRESALIR EN EL CONOCIMIENTO DE LO EXCELENTE QUE EN LA EXTENSIÓN DE MI PODER Y DOMINIO — ALEJANDRO MAGNO"
    size, tracking = 14, 2.2
    sep = "   ✦   "
    unit = phrase + sep
    unit_w = len(unit) * (size * MONO_ADVANCE + tracking)
    reps = math.ceil(w / unit_w) + 1
    spans = "".join(
        f"<tspan>{escape(phrase)}</tspan><tspan fill=\"{ACCENT}\">{sep}</tspan>" for _ in range(reps)
    )
    css = (
        f".mq{{animation:mq {unit_w / 38:.1f}s linear infinite}}"
        f"@keyframes mq{{to{{transform:translateX(-{unit_w:.1f}px)}}}}"
    )
    svg = (
        svg_open(w, h, "Prefiero sobresalir en el conocimiento de lo excelente que en la extensión de mi poder y dominio — Alejandro Magno", css)
        + f'<rect width="{w}" height="{h}" rx="10" fill="{BG}"/>'
        + f'<g class="mq"><text x="0" y="33" class="m" font-size="{size}" letter-spacing="{tracking}" '
        f'fill="{SUBTLE}" xml:space="preserve">{spans}</text></g>'
        + f'<rect x=".5" y=".5" width="{w - 1}" height="{h - 1}" rx="9.5" fill="none" stroke="{BORDER}"/>'
        + "</svg>"
    )
    (OUT / "seam.svg").write_text(svg, encoding="utf-8")


# --------------------------------------------------------------------------------------------
# Proyectos: la captura se escribe en glifos y luego aparece la real
# --------------------------------------------------------------------------------------------

PROJECTS = [
    {
        "slug": "aetherys",
        "index": "01",
        "title": "Aetherys",
        "year": "2026",
        "role": "Diseño y desarrollo",
        "image": "Aetherys.png",
        "url": "aetherys.vercel.app",
        "description": "Sitio de un estudio de software a medida: desarrollo web, plataformas SaaS, "
        "integración de IA y modernización de sistemas, con escenas WebGL, scroll suave y "
        "animaciones de interacción.",
        "stack": ["React", "TypeScript", "Vite", "Three.js", "Framer Motion", "Lenis", "Tailwind CSS"],
    },
    {
        "slug": "smyt",
        "index": "02",
        "title": "SMyT Tlaxcala",
        "year": "2026",
        "role": "Desarrollo full stack",
        "image": "SMyT.png",
        "url": "s-my-t-v2.vercel.app",
        "description": "Plataforma para la Secretaría de Movilidad y Transporte de Tlaxcala: depósitos "
        "vehiculares, registro en cuatro etapas, traslados georreferenciados, expedientes con "
        "verificación SHA-256 y control de acceso por roles.",
        "stack": ["React", "Vite", "Tailwind CSS", "Node.js", "Express", "Prisma", "PostgreSQL", "Supabase"],
    },
    {
        "slug": "portfolio",
        "index": "03",
        "title": "Portafolio",
        "year": "2026",
        "role": "Diseño y desarrollo",
        "image": "Portfolio.png",
        "url": "bastian4le.vercel.app",
        "description": "Portafolio bilingüe con figuras escritas en glifos sobre WebGL, una galaxia de "
        "partículas en el hero, scroll suave y animaciones que respetan el movimiento reducido.",
        "stack": ["Next.js", "React", "TypeScript", "Three.js", "Motion", "Lenis", "Tailwind CSS"],
    },
]


def screenshot_glyphs(img: Image.Image, cols: int, rows: int, seed: int) -> list[list[tuple[str, int]]]:
    """La captura como figura: el brillo elige glifo y tono; todo cuenta como silueta."""
    small = img.convert("L").resize((cols, rows), Image.Resampling.BOX)
    px = small.load()
    grid = []
    for y in range(rows):
        row = []
        for x in range(cols):
            lum = px[x, y] / 255
            lum = lum ** 0.8
            if lum < 0.06:
                row.append(("." if hash01(x, y, seed) > 0.7 else " ", 0 if hash01(x, y, seed) > 0.7 else -1))
                continue
            idx = max(1, min(len(RAMP) - 1, 6 + int(lum * (len(RAMP) - 7))))
            level = min(LEVELS - 1, int(lum * LEVELS))
            if lum > 0.2 and hash01(x, y, seed + 5) > 0.985:
                level = LEVELS
            row.append((RAMP[idx], level))
        grid.append(row)
    return grid


def build_project(p: dict) -> None:
    w, h = 1280, 440
    pad = 28
    sx, sy, sw, sh = pad, pad, 640, h - 2 * pad
    shot = Image.open(SRC / p["image"]).convert("RGB")
    # Recorte superior con la proporción del hueco (como object-fit: cover; object-position: top).
    crop_h = int(shot.width * sh / sw)
    shot = shot.crop((0, 0, shot.width, min(shot.height, crop_h)))
    buf = io.BytesIO()
    shot.resize((sw * 2, int(sw * 2 * shot.height / shot.width)), Image.Resampling.LANCZOS).save(
        buf, "JPEG", quality=74, optimize=True, progressive=True
    )
    shot_b64 = base64.b64encode(buf.getvalue()).decode()

    cell, font = 7.0, 9.2
    cols, rows = int(sw / cell), int(sh / cell)
    grid = screenshot_glyphs(shot, cols, rows, seed=len(p["slug"]))
    accent = p.get("accent", ACCENT)

    css = (
        level_css("p", accent)
        + ".gl{animation:gl 1.1s 1.5s ease-in both}@keyframes gl{to{opacity:0}}"
        ".sh{animation:sh 1.1s 1.5s ease-out both}@keyframes sh{from{opacity:0}to{opacity:1}}"
        ".rw{animation:w .5s ease-out both}.rw tspan{animation:ink 1.2s ease-out both;animation-delay:inherit}"
        "@keyframes w{from{opacity:0}to{opacity:1}}"
        f"@keyframes ink{{0%{{fill:{accent}}}}}"
        ".rv{animation:rv .9s cubic-bezier(.22,1,.36,1) both}"
        "@keyframes rv{from{opacity:0;transform:translateY(14px)}to{opacity:1;transform:none}}"
    )

    tx = sx + sw + 44
    tw = w - tx - 44
    desc_lines = wrap(p["description"], 18, tw)
    parts = [
        svg_open(w, h, f'{p["index"]} {p["title"]} — {p["description"]}', css),
        f'<defs><clipPath id="c"><rect width="{w}" height="{h}" rx="16"/></clipPath>'
        f'<clipPath id="s"><rect x="{sx}" y="{sy}" width="{sw}" height="{sh}" rx="10"/></clipPath></defs>',
        f'<g clip-path="url(#c)"><rect width="{w}" height="{h}" fill="{BG}"/>',
        f'<g clip-path="url(#s)"><rect x="{sx}" y="{sy}" width="{sw}" height="{sh}" fill="{SURFACE}"/>',
        f'<g class="gl">{glyph_text(grid, sx, sy - 1, cell, font, "p", "rw", (0.1, 0.018))}</g>',
        f'<image class="sh" x="{sx}" y="{sy}" width="{sw}" height="{sh}" preserveAspectRatio="xMidYMin slice" '
        f'href="data:image/jpeg;base64,{shot_b64}"/>',
        f'<rect x="{sx + .5}" y="{sy + .5}" width="{sw - 1}" height="{sh - 1}" rx="9.5" fill="none" stroke="{BORDER}"/></g>',
        "</g>",
    ]

    y = sy + 30
    text = [
        f'<text x="{tx}" y="{y}" class="m" font-size="13" letter-spacing="1.3" fill="{SUBTLE}">'
        f'<tspan fill="{accent}">{p["index"]}</tspan>  //  {p["year"]}</text>',
        f'<text x="{tx - 2}" y="{y + 66}" class="s" font-size="54" font-weight="500" letter-spacing="-1.6" '
        f'fill="{FG}">{escape(p["title"])}</text>',
    ]
    y += 110
    for line in desc_lines:
        text.append(f'<text x="{tx}" y="{y}" class="s" font-size="18" fill="{MUTED}">{escape(line)}</text>')
        y += 27
    y += 18
    text.append(
        f'<text x="{tx}" y="{y}" class="m" font-size="12" letter-spacing="1.2" fill="{SUBTLE}">ROL</text>'
        f'<text x="{tx + 54}" y="{y}" class="m" font-size="13" fill="{FG}">{escape(p["role"])}</text>'
    )
    y += 22
    chip_x, chip_y = tx, y
    chip_size = 12
    for tech in p["stack"]:
        cw = len(tech) * chip_size * MONO_ADVANCE + 24
        if chip_x + cw > tx + tw:
            chip_x, chip_y = tx, chip_y + 36
        text.append(
            f'<rect x="{chip_x:.1f}" y="{chip_y}" width="{cw:.1f}" height="28" rx="4" fill="{SURFACE}" stroke="{BORDER}"/>'
            f'<text x="{chip_x + 12:.1f}" y="{chip_y + 18.5}" class="m" font-size="{chip_size}" fill="{MUTED}">{escape(tech)}</text>'
        )
        chip_x += cw + 8
    text.append(
        f'<text x="{tx}" y="{sy + sh - 4}" class="m" font-size="14" fill="{accent}">↗ {p["url"]}</text>'
    )
    parts.append(f'<g class="rv" style="animation-delay:.3s">{"".join(text)}</g>')
    parts.append(f'<rect x=".5" y=".5" width="{w - 1}" height="{h - 1}" rx="15.5" fill="none" stroke="{BORDER}"/>')
    parts.append("</svg>")
    (OUT / f'project-{p["slug"]}.svg').write_text("".join(parts), encoding="utf-8")


# --------------------------------------------------------------------------------------------
# Cierre: las manos de "La creación de Adán"
# --------------------------------------------------------------------------------------------


def fingertip(grid: list[list[tuple[str, int]]], rightmost: bool) -> tuple[int, int]:
    """(columna, fila) de la punta del dedo: la celda de silueta más hacia el centro."""
    best: tuple[int, int] | None = None
    for y, r in enumerate(grid):
        filled = [x for x, c in enumerate(r) if c[1] >= 0]
        if not filled:
            continue
        x = filled[-1] if rightmost else filled[0]
        if best is None or (x > best[0] if rightmost else x < best[0]):
            best = (x, y)
    return best or (0, 0)


def build_footer() -> None:
    w, h = 1280, 330
    cell, font = 5.4, 7.2
    gap = 56
    hand_w = (w - gap) / 2 - 20
    adam = Image.open(SRC / "adam-glyphs.webp")
    god = Image.open(SRC / "god-glyphs.webp")

    def hand(img: Image.Image, seed: int) -> tuple[list, int, int]:
        cols = int(hand_w / cell)
        rows = int(cols * img.height / img.width)
        return glyph_rows(img, cols, rows, seed=seed, accent_rate=0.01, lum_gain=1.1), cols, rows

    ga, ca, ra = hand(adam, 21)
    gg, cg, rg = hand(god, 22)
    ax = w / 2 - gap / 2 - ca * cell
    gx = w / 2 + gap / 2
    top = 26

    # La escritura sale de cada punta de dedo hacia afuera: máscaras que se abren con SMIL.
    reveal = 2.4
    adam_w = ca * cell + 2
    god_w = cg * cell + 2
    css = level_css("f") + (
        ".spark{animation:sp 3s 2.4s ease-in-out infinite both}@keyframes sp{0%,100%{opacity:.2}50%{opacity:1}}"
    )
    (tax, tay), (tgx, tgy) = fingertip(ga, True), fingertip(gg, False)
    spark_x = (ax + (tax + 1) * cell + gx + tgx * cell) / 2
    spark_y = top + ((tay + tgy) / 2 + 1) * cell + 4
    parts = [
        svg_open(w, h, "Las manos de La creación de Adán escritas en glifos.", css),
        "<defs>"
        f'<clipPath id="a"><rect x="{ax + adam_w:.1f}" y="0" width="0" height="{h}">'
        f'<animate attributeName="width" from="0" to="{adam_w:.1f}" dur="{reveal}s" fill="freeze" calcMode="spline" keySplines=".22 1 .36 1" keyTimes="0;1"/>'
        f'<animate attributeName="x" from="{ax + adam_w:.1f}" to="{ax:.1f}" dur="{reveal}s" fill="freeze" calcMode="spline" keySplines=".22 1 .36 1" keyTimes="0;1"/>'
        "</rect></clipPath>"
        f'<clipPath id="g"><rect x="{gx:.1f}" y="0" width="0" height="{h}">'
        f'<animate attributeName="width" from="0" to="{god_w:.1f}" dur="{reveal}s" fill="freeze" calcMode="spline" keySplines=".22 1 .36 1" keyTimes="0;1"/>'
        "</rect></clipPath>"
        f'<clipPath id="c"><rect width="{w}" height="{h}" rx="16"/></clipPath>'
        "</defs>",
        f'<g clip-path="url(#c)"><rect width="{w}" height="{h}" fill="{BG}"/>',
        stars(w, h, 30, seed=5),
        f'<g clip-path="url(#a)">{glyph_text(ga, ax, top, cell, font, "f")}</g>',
        f'<g clip-path="url(#g)">{glyph_text(gg, gx, top, cell, font, "f")}</g>',
        f'<text x="{spark_x:.0f}" y="{spark_y:.0f}" text-anchor="middle" class="m spark" font-size="16" fill="{ACCENT}">+</text>',
        "</g>",
        f'<rect x=".5" y=".5" width="{w - 1}" height="{h - 1}" rx="15.5" fill="none" stroke="{BORDER}"/>',
        "</svg>",
    ]
    (OUT / "footer.svg").write_text("".join(parts), encoding="utf-8")


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    build_hero()
    build_seam()
    for project in PROJECTS:
        build_project(project)
    build_footer()
    for f in sorted(OUT.glob("*.svg")):
        print(f"{f.name:28} {f.stat().st_size / 1024:7.1f} KB")
