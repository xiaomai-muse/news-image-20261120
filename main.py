#!/usr/bin/env python3
"""Deterministic 1024x1024 news poster generator for Friday 20 November 2026."""

import math
import os
import struct
import zlib

# ==============================================================================
# 1. PALETTE
# ==============================================================================
WIDTH = 1024
HEIGHT = 1024

PAPER_BG = (244, 236, 218)       # Warm newsprint paper
CARD_BG = (251, 247, 238)        # Slightly brighter panel surface
ICON_BG = (233, 226, 210)        # Light icon box background
ICON_SKY_STORM = (224, 231, 239) # Cool light sky for cyclone panel
INK = (28, 25, 23)               # Near-black ink
SLATE = (58, 54, 50)             # Dark slate for decks
MUTED_RULE = (209, 200, 182)     # Subtle divider rule
RED = (188, 40, 36)              # Editorial red accent
BLUE = (29, 62, 110)             # Deep-blue accent
MID_BLUE = (56, 102, 152)        # Secondary wave blue
GOLD = (199, 147, 37)            # Touch of gold
WHITE = (250, 247, 240)          # Crisp off-white
DARK_FOOTER = (26, 29, 36)       # Dark footer strip background
FOOTER_TEXT = (247, 241, 227)    # Light cream footer text
GRAY_DARK = (76, 72, 68)         # Smoke / dark stone
GRAY_MID = (132, 125, 116)       # Mid stone / smoke
GRAY_LIGHT = (176, 168, 154)     # Light stone


# ==============================================================================
# 2. CANVAS PRIMITIVES
# ==============================================================================
class Canvas:
    """1024x1024 RGB framebuffer backed by a flat bytearray."""

    def __init__(self, width: int, height: int, bg: tuple[int, int, int]) -> None:
        self.width = width
        self.height = height
        self.buf = bytearray(bg) * (width * height)
        self.clip: tuple[int, int, int, int] | None = None

    def set_clip(self, x0: int, y0: int, x1: int, y1: int) -> None:
        """Restrict drawing to [x0, x1) x [y0, y1)."""
        self.clip = (
            max(0, x0),
            max(0, y0),
            min(self.width, x1),
            min(self.height, y1),
        )

    def clear_clip(self) -> None:
        """Remove active clipping rectangle."""
        self.clip = None

    def _bounds(self) -> tuple[int, int, int, int]:
        if self.clip is not None:
            return self.clip
        return (0, 0, self.width, self.height)

    def put_pixel(self, x: int, y: int, color: tuple[int, int, int]) -> None:
        """Set a single pixel if inside canvas and clip bounds."""
        bx0, by0, bx1, by1 = self._bounds()
        if bx0 <= x < bx1 and by0 <= y < by1:
            idx = (y * self.width + x) * 3
            self.buf[idx] = color[0]
            self.buf[idx + 1] = color[1]
            self.buf[idx + 2] = color[2]

    def fill_rect(
        self, x: int, y: int, w: int, h: int, color: tuple[int, int, int]
    ) -> None:
        """Fill an axis-aligned rectangle."""
        if w <= 0 or h <= 0:
            return
        bx0, by0, bx1, by1 = self._bounds()
        x0 = max(bx0, x)
        y0 = max(by0, y)
        x1 = min(bx1, x + w)
        y1 = min(by1, y + h)
        if x0 >= x1 or y0 >= y1:
            return
        row_bytes = bytes(color) * (x1 - x0)
        stride = self.width * 3
        span = (x1 - x0) * 3
        for py in range(y0, y1):
            start = py * stride + x0 * 3
            self.buf[start : start + span] = row_bytes

    def stroke_rect(
        self,
        x: int,
        y: int,
        w: int,
        h: int,
        color: tuple[int, int, int],
        thickness: int = 1,
    ) -> None:
        """Stroke an axis-aligned rectangle inward."""
        if w <= 0 or h <= 0 or thickness <= 0:
            return
        t = min(thickness, w // 2 + 1, h // 2 + 1)
        self.fill_rect(x, y, w, t, color)
        self.fill_rect(x, y + h - t, w, t, color)
        self.fill_rect(x, y, t, h, color)
        self.fill_rect(x + w - t, y, t, h, color)

    def fill_circle(
        self, cx: int, cy: int, radius: int, color: tuple[int, int, int]
    ) -> None:
        """Fill a circle centered at (cx, cy)."""
        if radius < 0:
            return
        if radius == 0:
            self.put_pixel(cx, cy, color)
            return
        bx0, by0, bx1, by1 = self._bounds()
        r2 = radius * radius
        y_start = max(by0, cy - radius)
        y_end = min(by1 - 1, cy + radius)
        for py in range(y_start, y_end + 1):
            dy = py - cy
            dx = math.isqrt(r2 - dy * dy)
            x_start = max(bx0, cx - dx)
            x_end = min(bx1 - 1, cx + dx)
            if x_start <= x_end:
                span = (x_end - x_start + 1) * 3
                start = (py * self.width + x_start) * 3
                self.buf[start : start + span] = bytes(color) * (x_end - x_start + 1)

    def draw_line(
        self,
        x0: int,
        y0: int,
        x1: int,
        y1: int,
        color: tuple[int, int, int],
        thickness: int = 1,
    ) -> None:
        """Draw a thick line using Bresenham's algorithm with round endcaps."""
        dx = abs(x1 - x0)
        dy = -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        rad = max(0, (thickness - 1) // 2)
        even_extra = 1 if thickness > 1 and thickness % 2 == 0 else 0

        while True:
            if thickness <= 1:
                self.put_pixel(x0, y0, color)
            elif rad == 0 and even_extra == 1:
                self.fill_rect(x0, y0, 2, 2, color)
            else:
                self.fill_circle(x0, y0, rad, color)
                if even_extra:
                    self.fill_circle(x0 + 1, y0 + 1, rad, color)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy

    def fill_polygon(
        self, points: list[tuple[int, int]], color: tuple[int, int, int]
    ) -> None:
        """Scanline-fill a closed polygon defined by integer (x, y) vertices."""
        if len(points) < 3:
            return
        bx0, by0, bx1, by1 = self._bounds()
        min_y = max(by0, min(p[1] for p in points))
        max_y = min(by1 - 1, max(p[1] for p in points))
        n = len(points)
        c_bytes = bytes(color)

        for py in range(min_y, max_y + 1):
            xs: list[int] = []
            for i in range(n):
                x_a, y_a = points[i]
                x_b, y_b = points[(i + 1) % n]
                if y_a == y_b:
                    continue
                if min(y_a, y_b) <= py < max(y_a, y_b):
                    x_int = x_a + (py - y_a) * (x_b - x_a) / (y_b - y_a)
                    xs.append(int(round(x_int)))
            xs.sort()
            for i in range(0, len(xs) - 1, 2):
                sx0 = max(bx0, xs[i])
                sx1 = min(bx1 - 1, xs[i + 1])
                if sx0 <= sx1:
                    cnt = sx1 - sx0 + 1
                    start = (py * self.width + sx0) * 3
                    self.buf[start : start + cnt * 3] = c_bytes * cnt


# ==============================================================================
# 3. PNG ENCODER
# ==============================================================================
def _png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    """Build a single PNG chunk with length, type, payload, and CRC32."""
    crc = zlib.crc32(chunk_type + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + chunk_type + data + struct.pack(">I", crc)


def encode_png(canvas: Canvas) -> bytes:
    """Encode an RGB Canvas into deterministic PNG bytes using zlib."""
    signature = b"\x89PNG\r\n\x1a\n"
    ihdr_data = struct.pack(">IIBBBBB", canvas.width, canvas.height, 8, 2, 0, 0, 0)
    ihdr = _png_chunk(b"IHDR", ihdr_data)

    stride = canvas.width * 3
    raw = bytearray((stride + 1) * canvas.height)
    mv = memoryview(canvas.buf)
    for y in range(canvas.height):
        dst_start = y * (stride + 1)
        raw[dst_start] = 0  # Filter type 0 (None)
        src_start = y * stride
        raw[dst_start + 1 : dst_start + 1 + stride] = mv[src_start : src_start + stride]

    compressed = zlib.compress(bytes(raw), level=6)
    idat = _png_chunk(b"IDAT", compressed)
    iend = _png_chunk(b"IEND", b"")
    return signature + ihdr + idat + iend


# ==============================================================================
# 4. FONT (Stroke-vector font on a 6x11 grid: x in 0..5, y in 0..10, advance 8)
# ==============================================================================
GLYPH_W = 6
GLYPH_H = 11
GLYPH_ADVANCE = 8

# Each glyph is a list of polylines; each polyline is a tuple of (x, y) points.
FONT: dict[str, list[tuple[tuple[int, int], ...]]] = {
    " ": [],
    "A": [((0, 10), (0, 3), (2, 0), (3, 0), (5, 3), (5, 10)), ((0, 6), (5, 6))],
    "B": [
        ((0, 10), (0, 0), (4, 0), (5, 1), (5, 4), (4, 5), (0, 5)),
        ((4, 5), (5, 6), (5, 9), (4, 10), (0, 10)),
    ],
    "C": [((5, 2), (4, 0), (1, 0), (0, 2), (0, 8), (1, 10), (4, 10), (5, 8))],
    "D": [((0, 10), (0, 0), (3, 0), (5, 2), (5, 8), (3, 10), (0, 10))],
    "E": [((5, 0), (0, 0), (0, 10), (5, 10)), ((0, 5), (4, 5))],
    "F": [((5, 0), (0, 0), (0, 10)), ((0, 5), (4, 5))],
    "G": [
        ((5, 2), (4, 0), (1, 0), (0, 2), (0, 8), (1, 10), (4, 10), (5, 8), (5, 5), (3, 5))
    ],
    "H": [((0, 0), (0, 10)), ((5, 0), (5, 10)), ((0, 5), (5, 5))],
    "I": [((1, 0), (4, 0)), ((2, 0), (2, 10)), ((1, 10), (4, 10))],
    "J": [((2, 0), (5, 0)), ((4, 0), (4, 8), (3, 10), (1, 10), (0, 8))],
    "K": [((0, 0), (0, 10)), ((5, 0), (0, 5), (5, 10))],
    "L": [((0, 0), (0, 10), (5, 10))],
    "M": [((0, 10), (0, 0), (2, 5), (3, 5), (5, 0), (5, 10))],
    "N": [((0, 10), (0, 0), (5, 10), (5, 0))],
    "O": [((1, 0), (4, 0), (5, 2), (5, 8), (4, 10), (1, 10), (0, 8), (0, 2), (1, 0))],
    "P": [((0, 10), (0, 0), (4, 0), (5, 1), (5, 4), (4, 5), (0, 5))],
    "Q": [
        ((1, 0), (4, 0), (5, 2), (5, 8), (4, 10), (1, 10), (0, 8), (0, 2), (1, 0)),
        ((3, 7), (5, 10)),
    ],
    "R": [
        ((0, 10), (0, 0), (4, 0), (5, 1), (5, 4), (4, 5), (0, 5)),
        ((2, 5), (5, 10)),
    ],
    "S": [
        ((5, 2), (4, 0), (1, 0), (0, 2), (0, 4), (1, 5), (4, 5), (5, 6), (5, 8), (4, 10), (1, 10), (0, 8))
    ],
    "T": [((0, 0), (5, 0)), ((2, 0), (2, 10))],
    "U": [((0, 0), (0, 8), (1, 10), (4, 10), (5, 8), (5, 0))],
    "V": [((0, 0), (0, 2), (2, 10), (3, 10), (5, 2), (5, 0))],
    "W": [((0, 0), (0, 10), (2, 6), (3, 6), (5, 10), (5, 0))],
    "X": [((0, 0), (5, 10)), ((5, 0), (0, 10))],
    "Y": [((0, 0), (2, 5), (5, 0)), ((2, 5), (2, 10))],
    "Z": [((0, 0), (5, 0), (0, 10), (5, 10))],
    "0": [
        ((1, 0), (4, 0), (5, 2), (5, 8), (4, 10), (1, 10), (0, 8), (0, 2), (1, 0)),
        ((1, 8), (4, 2)),
    ],
    "1": [((1, 2), (3, 0), (3, 10)), ((1, 10), (5, 10))],
    "2": [((0, 2), (1, 0), (4, 0), (5, 2), (5, 4), (0, 10), (5, 10))],
    "3": [
        ((0, 1), (1, 0), (4, 0), (5, 2), (5, 4), (3, 5), (5, 6), (5, 8), (4, 10), (1, 10), (0, 9)),
        ((2, 5), (3, 5)),
    ],
    "4": [((4, 10), (4, 0), (0, 6), (5, 6))],
    "5": [((5, 0), (0, 0), (0, 4), (4, 4), (5, 5), (5, 8), (4, 10), (1, 10), (0, 9))],
    "6": [
        ((4, 0), (1, 0), (0, 2), (0, 8), (1, 10), (4, 10), (5, 8), (5, 6), (4, 5), (0, 5))
    ],
    "7": [((0, 0), (5, 0), (2, 10))],
    "8": [
        ((1, 5), (0, 4), (0, 1), (1, 0), (4, 0), (5, 1), (5, 4), (4, 5), (1, 5), (0, 6), (0, 9), (1, 10), (4, 10), (5, 9), (5, 6), (4, 5))
    ],
    "9": [
        ((1, 10), (4, 10), (5, 8), (5, 2), (4, 0), (1, 0), (0, 2), (0, 4), (1, 5), (5, 5))
    ],
    ".": [((2, 9), (3, 9), (3, 10), (2, 10), (2, 9))],
    ",": [((2, 8), (3, 8), (3, 10), (1, 11))],
    ":": [((2, 3), (3, 3), (3, 4), (2, 4), (2, 3)), ((2, 8), (3, 8), (3, 9), (2, 9), (2, 8))],
    ";": [((2, 3), (3, 3), (3, 4), (2, 4), (2, 3)), ((2, 8), (3, 8), (3, 10), (1, 11))],
    "'": [((2, 0), (3, 0), (2, 3))],
    '"': [((1, 0), (1, 3)), ((4, 0), (4, 3))],
    "-": [((1, 5), (4, 5))],
    "/": [((0, 10), (5, 0))],
    "(": [((4, 0), (2, 2), (2, 8), (4, 10))],
    ")": [((1, 0), (3, 2), (3, 8), (1, 10))],
    "%": [
        ((0, 10), (5, 0)),
        ((0, 1), (1, 1), (1, 2), (0, 2), (0, 1)),
        ((4, 8), (5, 8), (5, 9), (4, 9), (4, 8)),
    ],
    "$": [
        ((5, 2), (4, 1), (1, 1), (0, 2), (0, 4), (1, 5), (4, 5), (5, 6), (5, 8), (4, 9), (1, 9), (0, 8)),
        ((2, 0), (2, 10)),
    ],
    "&": [
        ((5, 10), (1, 4), (1, 1), (2, 0), (3, 0), (4, 1), (4, 3), (0, 7), (0, 9), (1, 10), (3, 10), (5, 7))
    ],
    "+": [((2, 2), (2, 8)), ((0, 5), (5, 5))],
    "!": [((2, 0), (2, 6)), ((2, 9), (3, 9), (3, 10), (2, 10), (2, 9))],
    "?": [
        ((0, 2), (1, 0), (4, 0), (5, 2), (5, 4), (2, 6), (2, 7)),
        ((2, 9), (3, 9), (3, 10), (2, 10), (2, 9)),
    ],
    "\u2022": [((2, 4), (3, 4), (3, 6), (2, 6), (2, 4))],
}


# ==============================================================================
# 5. TEXT HELPERS
# ==============================================================================
def measure_text(text: str, scale: int | float) -> int:
    """Return pixel width of single-line text at the given scale."""
    if not text:
        return 0
    return int(round(len(text) * GLYPH_ADVANCE * scale - (GLYPH_ADVANCE - GLYPH_W) * scale))


def draw_text(
    canvas: Canvas,
    text: str,
    x: int,
    y: int,
    scale: int | float,
    color: tuple[int, int, int],
    thickness: int = 1,
) -> None:
    """Render single-line text using the stroke-vector font."""
    cx = float(x)
    step = GLYPH_ADVANCE * scale
    for ch in text.upper():
        strokes = FONT.get(ch, FONT[" "])
        for poly in strokes:
            for i in range(len(poly) - 1):
                px0, py0 = poly[i]
                px1, py1 = poly[i + 1]
                canvas.draw_line(
                    int(round(cx + px0 * scale)),
                    int(round(y + py0 * scale)),
                    int(round(cx + px1 * scale)),
                    int(round(y + py1 * scale)),
                    color,
                    thickness=thickness,
                )
        cx += step


def draw_text_centered(
    canvas: Canvas,
    text: str,
    cx: int,
    y: int,
    scale: int | float,
    color: tuple[int, int, int],
    thickness: int = 1,
) -> None:
    """Render text horizontally centered around cx."""
    w = measure_text(text, scale)
    draw_text(canvas, text, cx - w // 2, y, scale, color, thickness=thickness)


def wrap_text(text: str, max_width: int, scale: int | float) -> list[str]:
    """Greedy word-wrap so no line exceeds max_width pixels."""
    words = text.split()
    if not words:
        return []
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if measure_text(candidate, scale) <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


# ==============================================================================
# 6. MASTHEAD
# ==============================================================================
def draw_masthead(canvas: Canvas) -> None:
    """Draw the newspaper front-page masthead band."""
    x0, x1 = 24, 1000
    w = x1 - x0
    cx = WIDTH // 2

    # Top double rules
    canvas.fill_rect(x0, 18, w, 4, INK)
    canvas.fill_rect(x0, 25, w, 2, GOLD)

    # Overline
    draw_text_centered(
        canvas, "THE WORLD IN ONE IMAGE", cx, 36, scale=2, color=RED, thickness=3
    )

    # Big title
    draw_text_centered(
        canvas, "FRIDAY 20 NOVEMBER 2026", cx, 68, scale=4, color=INK, thickness=5
    )

    # Subline
    draw_text_centered(
        canvas,
        "SIX STORIES THAT DEFINED THE DAY",
        cx,
        126,
        scale=2,
        color=SLATE,
        thickness=3,
    )

    # Bottom masthead rules
    canvas.fill_rect(x0, 158, w, 2, RED)
    canvas.fill_rect(x0, 163, w, 4, INK)


# ==============================================================================
# 7. FOOTER
# ==============================================================================
def draw_footer(canvas: Canvas) -> None:
    """Draw the dark bottom ticker strip with two legible lines."""
    fx, fy, fw, fh = 24, 922, 976, 84
    canvas.fill_rect(fx, fy, fw, fh, DARK_FOOTER)
    canvas.fill_rect(fx, fy, fw, 3, GOLD)

    line1 = (
        "NZ 243/5 AS NICHOLLS CENTURY STEADIES TEST \u2022 "
        "GTA VI LAUNCHES IN INDIA \u2022 "
        "YUNUS HOME SET ON FIRE IN BANGLADESH"
    )
    line2 = (
        "FIJI DECLARES DISASTER OVER EL NINO DROUGHT \u2022 "
        "S KOREA COURT OVERTURNS HAN DUCK-SOO CONVICTION"
    )

    cx = fx + fw // 2
    draw_text_centered(canvas, line1, cx, fy + 18, scale=1, color=FOOTER_TEXT, thickness=2)
    draw_text_centered(canvas, line2, cx, fy + 48, scale=1, color=FOOTER_TEXT, thickness=2)


# ==============================================================================
# 8. PANELS
# ==============================================================================
STORIES = [
    {
        "kicker": "SUMMIT",
        "headline": "TRUMP, XI AND PUTIN MEET IN SHENZHEN",
        "deck": "JOINT DECLARATION ON NUCLEAR SECURITY; 'DECLARATION TOWARDS PEACE'",
        "icon": "summit",
    },
    {
        "kicker": "COURT",
        "headline": "ICJ: MYANMAR COMMITTED GENOCIDE",
        "deck": "LANDMARK RULING ON 2017 ROHINGYA CAMPAIGN",
        "icon": "court",
    },
    {
        "kicker": "STORM",
        "headline": "CYCLONE AKVAN HITS EAST COAST",
        "deck": "LANDFALL BETWEEN PURI AND GOPALPUR; 1.2 LAKH EVACUATED",
        "icon": "storm",
    },
    {
        "kicker": "GULF",
        "headline": "IRAN HITS US BASE IN KUWAIT",
        "deck": "ATTACKS ON KUWAIT AND BAHRAIN; TANKERS HIT MINES OFF HORMUZ",
        "icon": "gulf",
    },
    {
        "kicker": "GAZA",
        "headline": "ISRAEL OPENS GROUND OPERATION IN GAZA",
        "deck": "GROUND PUSH INTO HAMAS-HELD CENTRAL GAZA",
        "icon": "gaza",
    },
    {
        "kicker": "BUSINESS",
        "headline": "ANTHROPIC IPO PRICED AT $83",
        "deck": "$83 A SHARE; TARGETS $1.5 TRILLION VALUATION",
        "icon": "business",
    },
]


def draw_panel(
    canvas: Canvas, x: int, y: int, w: int, h: int, story: dict[str, str]
) -> None:
    """Render a single news story panel with kicker, headline, deck, and icon."""
    canvas.fill_rect(x, y, w, h, CARD_BG)
    canvas.stroke_rect(x, y, w, h, INK, thickness=2)
    canvas.fill_rect(x, y, w, 5, BLUE)

    pad = 14
    inner_w = w - 2 * pad

    # Kicker
    draw_text(canvas, story["kicker"], x + pad, y + 14, scale=2, color=RED, thickness=3)

    # Headline (at most 2 lines)
    hl_lines = wrap_text(story["headline"], inner_w, scale=2)[:2]
    hl_y = y + 44
    for line in hl_lines:
        draw_text(canvas, line, x + pad, hl_y, scale=2, color=INK, thickness=3)
        hl_y += 28

    # Subtle divider
    div_y = y + 102
    canvas.fill_rect(x + pad, div_y, inner_w, 2, MUTED_RULE)

    # Icon box on the lower right
    icon_w, icon_h = 120, 108
    ix = x + w - pad - icon_w
    iy = div_y + 10
    draw_icon(canvas, story["icon"], ix, iy, icon_w, icon_h)

    # Deck on the lower left (at most 2 lines; bump to scale 1.5 when it fits)
    deck_w = ix - (x + pad) - 12
    deck_lines_15 = wrap_text(story["deck"], deck_w, scale=1.5)
    if len(deck_lines_15) <= 2:
        deck_scale: int | float = 1.5
        deck_thickness = 3
        deck_lines = deck_lines_15
        dy = iy + 16
        line_step = 28
    else:
        deck_scale = 1
        deck_thickness = 2
        deck_lines = wrap_text(story["deck"], deck_w, scale=1)[:2]
        dy = iy + 18
        line_step = 22
    for line in deck_lines:
        draw_text(
            canvas,
            line,
            x + pad,
            dy,
            scale=deck_scale,
            color=SLATE,
            thickness=deck_thickness,
        )
        dy += line_step


# ==============================================================================
# 9. ICONS (strictly clipped inside each icon frame; background before foreground)
# ==============================================================================
def draw_icon(
    canvas: Canvas, kind: str, x: int, y: int, w: int, h: int
) -> None:
    """Draw a flat vector-style icon strictly inside its framed box."""
    bg = ICON_SKY_STORM if kind == "storm" else ICON_BG
    canvas.fill_rect(x, y, w, h, bg)

    # Clip interior to 2px inside the border so nothing ever overflows
    canvas.set_clip(x + 2, y + 2, x + w - 2, y + h - 2)

    if kind == "summit":
        _icon_summit(canvas, x, y, w, h)
    elif kind == "court":
        _icon_court(canvas, x, y, w, h)
    elif kind == "storm":
        _icon_storm(canvas, x, y, w, h)
    elif kind == "gulf":
        _icon_gulf(canvas, x, y, w, h)
    elif kind == "gaza":
        _icon_gaza(canvas, x, y, w, h)
    elif kind == "business":
        _icon_business(canvas, x, y, w, h)

    canvas.clear_clip()
    canvas.stroke_rect(x, y, w, h, INK, thickness=2)


def _icon_summit(canvas: Canvas, x: int, y: int, w: int, h: int) -> None:
    """Three small flags side by side (China, USA, Russia)."""
    ground_y = y + h - 14
    canvas.fill_rect(x + 8, ground_y, w - 16, 3, INK)

    pole_xs = [x + 16, x + 50, x + 84]
    flag_w, flag_h = 26, 20
    top_y = y + 22

    # Flag 1: China (red with gold stars)
    px = pole_xs[0]
    canvas.fill_rect(px + 2, top_y, flag_w, flag_h, RED)
    canvas.fill_circle(px + 7, top_y + 6, 3, GOLD)
    canvas.fill_circle(px + 12, top_y + 4, 1, GOLD)
    canvas.fill_circle(px + 13, top_y + 8, 1, GOLD)
    canvas.stroke_rect(px + 2, top_y, flag_w, flag_h, INK, thickness=1)

    # Flag 2: USA (stripes + blue canton)
    px = pole_xs[1]
    for s in range(5):
        c = RED if s % 2 == 0 else WHITE
        canvas.fill_rect(px + 2, top_y + s * 4, flag_w, 4, c)
    canvas.fill_rect(px + 2, top_y, 12, 11, BLUE)
    canvas.put_pixel(px + 6, top_y + 4, WHITE)
    canvas.put_pixel(px + 9, top_y + 7, WHITE)
    canvas.stroke_rect(px + 2, top_y, flag_w, flag_h, INK, thickness=1)

    # Flag 3: Russia (white, blue, red horizontal bands)
    px = pole_xs[2]
    canvas.fill_rect(px + 2, top_y, flag_w, 7, WHITE)
    canvas.fill_rect(px + 2, top_y + 7, flag_w, 6, BLUE)
    canvas.fill_rect(px + 2, top_y + 13, flag_w, 7, RED)
    canvas.stroke_rect(px + 2, top_y, flag_w, flag_h, INK, thickness=1)

    # Draw poles and finials in foreground
    for px in pole_xs:
        canvas.fill_rect(px, top_y - 4, 3, ground_y - (top_y - 4), INK)
        canvas.fill_circle(px + 1, top_y - 6, 3, GOLD)


def _icon_court(canvas: Canvas, x: int, y: int, w: int, h: int) -> None:
    """Scales of justice above a courthouse colonnade."""
    cx = x + w // 2

    # Background: courthouse colonnade (lower half)
    base_y = y + h - 12
    canvas.fill_rect(x + 14, base_y - 5, w - 28, 5, GRAY_DARK)
    canvas.fill_rect(x + 18, base_y - 9, w - 36, 4, GRAY_MID)

    # Pediment (triangle) and entablature
    roof_y = base_y - 36
    canvas.fill_polygon(
        [(x + 16, roof_y), (cx, roof_y - 12), (x + w - 16, roof_y)], GRAY_LIGHT
    )
    canvas.fill_rect(x + 16, roof_y, w - 32, 4, INK)

    # 4 foreground columns
    for col_x in (x + 24, x + 44, x + 68, x + 88):
        canvas.fill_rect(col_x, roof_y + 4, 8, 23, WHITE)
        canvas.stroke_rect(col_x, roof_y + 4, 8, 23, INK, thickness=1)

    # Foreground: scales of justice (upper half)
    post_top = y + 12
    beam_y = y + 20
    canvas.fill_rect(cx - 2, post_top, 4, 36, INK)
    canvas.fill_circle(cx, post_top, 3, GOLD)
    canvas.fill_rect(cx - 32, beam_y - 1, 64, 3, GOLD)

    for pan_x in (cx - 28, cx + 28):
        canvas.draw_line(pan_x, beam_y + 1, pan_x - 10, beam_y + 18, INK, thickness=1)
        canvas.draw_line(pan_x, beam_y + 1, pan_x + 10, beam_y + 18, INK, thickness=1)
        canvas.fill_polygon(
            [
                (pan_x - 12, beam_y + 18),
                (pan_x + 12, beam_y + 18),
                (pan_x + 7, beam_y + 24),
                (pan_x - 7, beam_y + 24),
            ],
            GOLD,
        )


def _icon_storm(canvas: Canvas, x: int, y: int, w: int, h: int) -> None:
    """Spiral cyclone swirl over layered waves."""
    cx = x + w // 2
    cy = y + 40

    # Cyclone spiral
    pts: list[tuple[int, int]] = []
    steps = 64
    for i in range(steps + 1):
        theta = 0.25 + i * (4.1 * math.pi / steps)
        r = 3.0 + (28.0 * i / steps)
        px = int(round(cx + r * math.cos(theta)))
        py = int(round(cy + r * 0.72 * math.sin(theta)))
        pts.append((px, py))

    for i in range(len(pts) - 1):
        thick = 2 if i < 20 else 3
        canvas.draw_line(
            pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1], BLUE, thickness=thick
        )

    # Storm eye
    canvas.fill_circle(cx, cy, 4, RED)

    # Layered waves at bottom
    wave_y1 = y + h - 24
    wave_y2 = y + h - 14
    canvas.fill_rect(x + 4, wave_y1, w - 8, 22, MID_BLUE)
    for wx in range(x + 12, x + w - 8, 20):
        canvas.fill_circle(wx, wave_y1, 10, MID_BLUE)
    canvas.fill_rect(x + 4, wave_y2, w - 8, 12, BLUE)
    for wx in range(x + 6, x + w - 6, 18):
        canvas.fill_circle(wx, wave_y2, 8, BLUE)


def _icon_gulf(canvas: Canvas, x: int, y: int, w: int, h: int) -> None:
    """Oil tanker on waves with a rising plume of smoke."""
    # Background: rising smoke plume
    smoke_circles = [
        (x + 64, y + 50, 7, GRAY_DARK),
        (x + 70, y + 40, 9, GRAY_DARK),
        (x + 78, y + 30, 11, GRAY_MID),
        (x + 88, y + 20, 12, GRAY_LIGHT),
    ]
    for sx, sy, sr, sc in smoke_circles:
        canvas.fill_circle(sx, sy, sr, sc)
    canvas.fill_circle(x + 61, y + 55, 4, RED)

    # Midground: oil tanker hull and superstructure
    hull_y = y + 58
    canvas.fill_polygon(
        [
            (x + 14, hull_y),
            (x + 98, hull_y),
            (x + 90, hull_y + 20),
            (x + 20, hull_y + 20),
        ],
        INK,
    )
    canvas.fill_rect(x + 17, hull_y + 10, 78, 3, RED)
    # Bridge at stern (left)
    canvas.fill_rect(x + 22, hull_y - 14, 16, 14, WHITE)
    canvas.stroke_rect(x + 22, hull_y - 14, 16, 14, INK, thickness=1)
    canvas.fill_rect(x + 25, hull_y - 10, 10, 4, BLUE)
    # Deck cargo piping
    canvas.fill_rect(x + 42, hull_y - 5, 36, 5, GRAY_MID)

    # Foreground: waves overlapping bottom of hull
    wy = y + h - 20
    canvas.fill_rect(x + 4, wy, w - 8, 18, BLUE)
    for wx in range(x + 10, x + w - 8, 16):
        canvas.fill_circle(wx, wy, 7, BLUE)


def _icon_gaza(canvas: Canvas, x: int, y: int, w: int, h: int) -> None:
    """City skyline with a ground arrow advancing across it."""
    ground_y = y + h - 14
    canvas.fill_rect(x + 6, ground_y, w - 12, 4, INK)

    # Background: skyline buildings
    buildings = [
        (x + 10, ground_y - 44, 16, 44, GRAY_LIGHT),
        (x + 28, ground_y - 62, 18, 62, GRAY_MID),
        (x + 48, ground_y - 36, 15, 36, GRAY_LIGHT),
        (x + 65, ground_y - 56, 20, 56, GRAY_MID),
        (x + 87, ground_y - 48, 18, 48, GRAY_LIGHT),
    ]
    for bx, by, bw, bh, bc in buildings:
        canvas.fill_rect(bx, by, bw, bh, bc)
        canvas.stroke_rect(bx, by, bw, bh, INK, thickness=1)
        for wy in range(by + 6, ground_y - 8, 10):
            canvas.fill_rect(bx + 4, wy, 3, 4, DARK_FOOTER)
            if bw >= 18:
                canvas.fill_rect(bx + 10, wy, 3, 4, DARK_FOOTER)

    # Foreground: advancing ground arrow
    ay = y + 60
    canvas.fill_rect(x + 10, ay - 6, 68, 12, RED)
    canvas.fill_polygon(
        [(x + 76, ay - 15), (x + 106, ay), (x + 76, ay + 15)], RED
    )
    # Crisp dark outline around arrow
    canvas.draw_line(x + 10, ay - 6, x + 76, ay - 6, INK, thickness=2)
    canvas.draw_line(x + 10, ay + 6, x + 76, ay + 6, INK, thickness=2)
    canvas.draw_line(x + 10, ay - 6, x + 10, ay + 6, INK, thickness=2)
    canvas.draw_line(x + 76, ay - 15, x + 106, ay, INK, thickness=2)
    canvas.draw_line(x + 106, ay, x + 76, ay + 15, INK, thickness=2)
    canvas.draw_line(x + 76, ay - 15, x + 76, ay - 6, INK, thickness=2)
    canvas.draw_line(x + 76, ay + 6, x + 76, ay + 15, INK, thickness=2)


def _icon_business(canvas: Canvas, x: int, y: int, w: int, h: int) -> None:
    """Rising bar chart with an upward arrow."""
    base_y = y + h - 14
    left_x = x + 14

    # Grid lines
    for gy in (y + 24, y + 46, y + 68):
        canvas.fill_rect(left_x, gy, w - 28, 1, MUTED_RULE)

    # Rising bars
    bars = [
        (left_x + 4, 20, BLUE),
        (left_x + 26, 34, BLUE),
        (left_x + 48, 48, BLUE),
        (left_x + 70, 64, GOLD),
    ]
    for bx, bh, bc in bars:
        canvas.fill_rect(bx, base_y - bh, 16, bh, bc)
        canvas.stroke_rect(bx, base_y - bh, 16, bh, INK, thickness=1)

    # Baseline
    canvas.fill_rect(left_x, base_y, w - 28, 3, INK)

    # Upward trend arrow
    ax0, ay0 = left_x + 8, base_y - 30
    ax1, ay1 = left_x + 78, y + 18
    canvas.draw_line(ax0, ay0, ax1, ay1, RED, thickness=4)
    canvas.fill_polygon(
        [(ax1 - 12, ay1 - 2), (ax1 + 5, ay1 - 4), (ax1 + 1, ay1 + 12)], RED
    )


# ==============================================================================
# 10. RENDER
# ==============================================================================
def render_poster() -> Canvas:
    """Compose the full 1024x1024 newspaper front-page poster."""
    canvas = Canvas(WIDTH, HEIGHT, PAPER_BG)
    draw_masthead(canvas)

    # 2-column x 3-row grid of story panels
    col_xs = [24, 522]
    panel_w = 478
    row_ys = [184, 430, 676]
    panel_h = 232

    # Subtle vertical center column rule
    canvas.fill_rect(511, 184, 2, 724, MUTED_RULE)

    for idx, story in enumerate(STORIES):
        row = idx // 2
        col = idx % 2
        draw_panel(canvas, col_xs[col], row_ys[row], panel_w, panel_h, story)

    draw_footer(canvas)
    return canvas


# ==============================================================================
# 11. MAIN
# ==============================================================================
def main() -> int:
    """Render poster and deterministically write entry.png."""
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR") or "/output"
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "entry.png")

    canvas = render_poster()
    png_bytes = encode_png(canvas)
    with open(out_path, "wb") as f:
        f.write(png_bytes)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
