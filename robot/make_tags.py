"""Generate a printable A4 PDF of AprilTag 36h11 markers at exact physical sizes.

    uv run python robot/make_tags.py                                  # default set -> apriltag-36h11-a4.pdf (in this folder)
    uv run python robot/make_tags.py --spec "50:0-5,40:10-15" -o tags.pdf
    uv run python robot/make_tags.py --spec "card" --fill none

SPEC is a comma-separated list of items, placed left to right, top to bottom:
    SIZE_MM:ID or SIZE_MM:FIRST-LAST   tags; SIZE_MM is the edge of the black square
    card                               the colour reference card (full page width)
    |                                  start a new page
FILL (SIZE_MM:FIRST_ID, or "none") puts extra tags into every gap and into the
space left at the bottom of each page, numbered upwards from FIRST_ID.

Each tag gets a white quiet zone one cell wide, a grey cut line and a label. The
PDF is vector, written in millimetres. Print at 100 % / "actual size" (never
"fit to page") and check the 100 mm ruler on each page with a real ruler.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass

import cv2

PAGE_W, PAGE_H = 210.0, 297.0  # A4, mm
MARGIN = 10.0  # most printers cannot print closer to the edge
HEADER_H = 14.0  # title + ruler
LABEL_H = 4.5
CELLS = 8  # 36h11: 6x6 data bits + 1-cell black border
MM = 72 / 25.4  # PDF points per mm
USABLE_W = PAGE_W - 2 * MARGIN
USABLE_H = PAGE_H - 2 * MARGIN - HEADER_H

# id ranges by purpose and size; see docs/en/user/robot-calibration.md
DEFAULT_SPEC = '70:20-21,50:0-2,40:10-12 | card,50:3-5,40:13-15'
DEFAULT_FILL = '30:30'

# Colour reference card: a tag at each end, 2 rows x 5 patches in between.
CARD_TAG_IDS = (90, 91)
CARD_TAG_SIZE = 30.0
CARD_PITCH = 23.0  # patch pitch; the inked square is inset by CARD_INSET on every side
CARD_INSET = 1.0
CARD_PATCHES = [  # (name, PDF fill operator); neutrals in DeviceGray so a printer can use black ink only
    [('white', None), ('grey75', '0.75 g'), ('grey50', '0.5 g'), ('grey25', '0.25 g'), ('black', '0 g')],
    [('red', '1 0 0 rg'), ('yellow', '1 1 0 rg'), ('green', '0 1 0 rg'), ('blue', '0 0 1 rg'), ('magenta', '1 0 1 rg')],
]


def card_layout() -> dict:
    """Card geometry in mm, origin at the card's top-left corner, y down.

    Returns tag squares as {id: (x, y, size)} and patches as {name: (x, y, size)} (the inked square).
    """
    quiet = CARD_TAG_SIZE / CELLS
    body_h = CARD_PITCH * len(CARD_PATCHES)
    tag_y = (body_h - CARD_TAG_SIZE) / 2
    x0 = CARD_TAG_SIZE + 2 * quiet
    patches = {
        name: (x0 + j * CARD_PITCH + CARD_INSET, i * CARD_PITCH + CARD_INSET, CARD_PITCH - 2 * CARD_INSET)
        for i, row in enumerate(CARD_PATCHES)
        for j, (name, _) in enumerate(row)
    }
    width = 2 * x0 + CARD_PITCH * len(CARD_PATCHES[0])
    return {
        'width': width,
        'height': body_h + LABEL_H,
        'tags': {
            CARD_TAG_IDS[0]: (quiet, tag_y, CARD_TAG_SIZE),
            CARD_TAG_IDS[1]: (width - quiet - CARD_TAG_SIZE, tag_y, CARD_TAG_SIZE),
        },
        'patches': patches,
    }


@dataclass
class Block:
    w: float
    h: float
    size: float = 0.0  # tag edge; 0 for the card
    tag_id: int = -1


def tag_block(size: float, tag_id: int) -> Block:
    patch = size + 2 * size / CELLS
    return Block(patch, patch + LABEL_H, size, tag_id)


def parse_spec(spec: str) -> list[list[Block]]:
    """One list of blocks per forced page."""
    groups = []
    for page in spec.split('|'):
        blocks = []
        for part in filter(None, (p.strip() for p in page.split(','))):
            if part == 'card':
                c = card_layout()
                blocks.append(Block(c['width'], c['height']))
                continue
            size, ids = part.split(':')
            first, _, last = ids.partition('-')
            blocks += [tag_block(float(size), i) for i in range(int(first), int(last or first) + 1)]
        groups.append(blocks)
    return groups


def layout(groups: list[list[Block]], fill: tuple[float, int] | None) -> list[list[tuple[float, float, Block]]]:
    """Shelf-pack blocks into pages, then fill the gaps. Returns per page (x, y, block), top-left in mm."""
    eps = 1e-6
    # a shelf is a list of columns, a column a list of blocks stacked top to bottom
    shelf_w = lambda shelf: sum(max(b.w for b in col) for col in shelf)
    shelf_h = lambda shelf: max(sum(b.h for b in col) for col in shelf)
    pages: list[list[list[list[Block]]]] = []
    for blocks in groups:
        page, shelf = [], []

        def close():
            nonlocal page, shelf
            if shelf:
                if sum(map(shelf_h, page)) + shelf_h(shelf) > USABLE_H + eps:
                    pages.append(page)
                    page = []
                page.append(shelf)
                shelf = []

        for b in blocks:
            if b.w > USABLE_W + eps or b.h > USABLE_H + eps:
                raise ValueError(f'a {b.size:g} mm tag does not fit on A4')
            if shelf and shelf_w(shelf) + b.w > USABLE_W + eps:
                close()
            shelf.append([b])
        close()
        pages.append(page)

    if fill:
        size, next_id = fill
        probe = tag_block(size, 0)
        for page in pages:
            for shelf in page:  # gaps at the end of each row
                stack = int((shelf_h(shelf) + eps) // probe.h)
                while stack and shelf_w(shelf) + probe.w <= USABLE_W + eps:
                    shelf.append([tag_block(size, next_id + k) for k in range(stack)])
                    next_id += stack
            per_row = int((USABLE_W + eps) // probe.w)
            while sum(map(shelf_h, page)) + probe.h <= USABLE_H + eps:  # space at the bottom of the page
                page.append([[tag_block(size, next_id + k)] for k in range(per_row)])
                next_id += per_row

    placed = []
    for page in pages:
        items, y = [], MARGIN + HEADER_H
        for shelf in page:
            x = MARGIN + (USABLE_W - shelf_w(shelf)) / 2  # centre the row
            for col in shelf:
                cy = y
                for b in col:
                    items.append((x, cy, b))
                    cy += b.h
                x += max(b.w for b in col)
            y += shelf_h(shelf)
        placed.append(items)
    return placed


def text(x: float, y: float, size: float, s: str) -> str:
    # the page matrix flips y (origin top-left), so flip the glyphs back
    return f'BT /F1 {size:.2f} Tf 1 0 0 -1 {x:.3f} {y:.3f} Tm ({s}) Tj ET\n'


def draw_tag(x: float, y: float, size: float, tag_id: int, dictionary) -> str:
    """The black square with its top-left corner at (x, y)."""
    cell = size / CELLS
    bits = cv2.aruco.generateImageMarker(dictionary, tag_id, CELLS) > 0  # True = white cell
    # every white cell in one path, one fill: no anti-aliasing seams between neighbours
    white = ''.join(
        f'{x + c * cell:.4f} {y + r * cell:.4f} {cell:.4f} {cell:.4f} re\n'
        for r in range(CELLS)
        for c in range(CELLS)
        if bits[r, c]
    )
    return f'0 g {x:.4f} {y:.4f} {size:.4f} {size:.4f} re f\n1 g\n{white}f\n'


def cut_line(x: float, y: float, w: float, h: float) -> str:
    return f'0.6 G 0.1 w {x:.4f} {y:.4f} {w:.4f} {h:.4f} re S\n'


def draw_card(x: float, y: float, dictionary) -> str:
    c = card_layout()
    out = [cut_line(x, y, c['width'], c['height'])]
    for tag_id, (tx, ty, size) in c['tags'].items():
        out.append(draw_tag(x + tx, y + ty, size, tag_id, dictionary))
    fills = {name: op for row in CARD_PATCHES for name, op in row}
    for name, (px, py, s) in c['patches'].items():
        rect = f'{x + px:.4f} {y + py:.4f} {s:.4f} {s:.4f} re'
        out.append(f'{fills[name]} {rect} f\n' if fills[name] else f'0.6 G 0.1 w {rect} S\n')  # white = bare paper
    label = (
        f'colour card  -  36h11 id {CARD_TAG_IDS[0]} / {CARD_TAG_IDS[1]}, {CARD_TAG_SIZE:g} mm  -  '
        'top: white, grey 75 / 50 / 25 %, black  -  bottom: red, yellow, green, blue, magenta'
    )
    out.append('0 g\n' + text(x + CARD_TAG_SIZE / CELLS, y + c['height'] - LABEL_H + 3.2, 2.6, label))
    return ''.join(out)


def page_stream(items, page_no: int, n_pages: int, dictionary) -> str:
    out = [f'{MM:.6f} 0 0 {-MM:.6f} 0 {PAGE_H * MM:.4f} cm\n']  # work in mm, y down
    out.append(
        '0 g\n'
        + text(
            MARGIN,
            MARGIN + 3.5,
            3.2,
            f"AprilTag 36h11  -  PRINT AT 100% (ACTUAL SIZE), NOT 'FIT TO PAGE'  -  page {page_no}/{n_pages}",
        )
    )
    # 100 mm check ruler with 10 mm ticks
    rx, ry = MARGIN, MARGIN + 9.0
    out.append(f'0 G 0.15 w {rx:.3f} {ry:.3f} m {rx + 100:.3f} {ry:.3f} l S\n')
    for k in range(11):
        out.append(f'{rx + 10 * k:.3f} {ry - (2.0 if k % 5 == 0 else 1.2):.3f} m {rx + 10 * k:.3f} {ry:.3f} l S\n')
    out.append(text(rx + 102, ry, 2.8, 'this line must measure exactly 100 mm'))

    for x, y, b in items:
        if b.tag_id < 0:
            out.append(draw_card(x, y, dictionary))
            continue
        cell = b.size / CELLS
        out.append(cut_line(x, y, b.w, b.h))
        out.append(draw_tag(x + cell, y + cell, b.size, b.tag_id, dictionary))
        out.append('0 g\n' + text(x + cell, y + b.h - LABEL_H + 3.2, 2.6, f'36h11  id {b.tag_id}  {b.size:g} mm'))
    return ''.join(out)


def write_pdf(path: str, streams: list[str]) -> None:
    n = len(streams)
    font_id = 3
    page_id = lambda k: 4 + 2 * k
    objs: dict[int, bytes] = {
        1: b'<< /Type /Catalog /Pages 2 0 R >>',
        2: f'<< /Type /Pages /Count {n} /Kids [{" ".join(f"{page_id(k)} 0 R" for k in range(n))}] >>'.encode(),
        font_id: b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
    }
    for k, s in enumerate(streams):
        data = s.encode('ascii')
        objs[page_id(k)] = (
            f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {PAGE_W * MM:.4f} {PAGE_H * MM:.4f}] '
            f'/Resources << /Font << /F1 {font_id} 0 R >> >> /Contents {page_id(k) + 1} 0 R >>'
        ).encode()
        objs[page_id(k) + 1] = b'<< /Length %d >>\nstream\n' % len(data) + data + b'\nendstream'

    buf = bytearray(b'%PDF-1.4\n')
    offsets = {}
    for num in sorted(objs):
        offsets[num] = len(buf)
        buf += b'%d 0 obj\n' % num + objs[num] + b'\nendobj\n'
    xref = len(buf)
    buf += b'xref\n0 %d\n0000000000 65535 f \n' % (len(objs) + 1)
    for num in sorted(objs):
        buf += b'%010d 00000 n \n' % offsets[num]
    buf += b'trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n' % (len(objs) + 1, xref)
    with open(path, 'wb') as f:
        f.write(buf)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        '--spec', default=DEFAULT_SPEC, help="tags (SIZE_MM:ID or SIZE_MM:FIRST-LAST), 'card', '|' for a page break"
    )
    ap.add_argument('--fill', default=DEFAULT_FILL, help="SIZE_MM:FIRST_ID tags for the leftover space, or 'none'")
    ap.add_argument('-o', '--out', default='apriltag-36h11-a4.pdf')
    args = ap.parse_args()

    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_APRILTAG_36h11)
    fill = None
    if args.fill != 'none':
        size, first = args.fill.split(':')
        fill = (float(size), int(first))
    pages = layout(parse_spec(args.spec), fill)

    ids = [b.tag_id for items in pages for _, _, b in items if b.tag_id >= 0]
    ids += [i for items in pages for _, _, b in items if b.tag_id < 0 for i in CARD_TAG_IDS]
    dup = sorted({i for i in ids if ids.count(i) > 1})
    if dup:
        print(f'error: tag ids used more than once: {dup}', file=sys.stderr)
        return 1
    if max(ids) >= dictionary.bytesList.shape[0]:
        print(f'error: 36h11 has ids 0-{dictionary.bytesList.shape[0] - 1}', file=sys.stderr)
        return 1

    write_pdf(args.out, [page_stream(items, k + 1, len(pages), dictionary) for k, items in enumerate(pages)])
    by_size: dict[float, list[int]] = {}
    for items in pages:
        for _, _, b in items:
            if b.tag_id >= 0:
                by_size.setdefault(b.size, []).append(b.tag_id)
    summary = ', '.join(f'{s:g} mm: {min(v)}-{max(v)} ({len(v)})' for s, v in sorted(by_size.items(), reverse=True))
    print(f'wrote {args.out}: {len(ids)} tags on {len(pages)} A4 page(s); {summary}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
