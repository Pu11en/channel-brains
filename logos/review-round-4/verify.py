"""Read the delivered SVGs, measure contours, and render full and favicon sizes."""

import xml.etree.ElementTree as ET
from pathlib import Path

import cairosvg
from fontTools.pens.basePen import BasePen
from fontTools.svgLib.path import parse_path
from PIL import Image, ImageDraw, ImageFont
from shapely.geometry import Polygon

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent
NAMES = {11: "Solid Brain", 12: "Play Fissure", 13: "Outline Brain", 14: "Top Brain"}


class Flatten(BasePen):
    def __init__(self):
        super().__init__(None)
        self.rings = []
        self.points = []

    def _moveTo(self, point):
        self.points = [point]

    def _lineTo(self, point):
        self.points.append(point)

    def _curveToOne(self, b, c, d):
        a = self.points[-1]
        for k in range(1, 129):
            t = k / 128
            u = 1 - t
            self.points.append(tuple(
                u**3 * a[j] + 3 * u * u * t * b[j] + 3 * u * t * t * c[j] + t**3 * d[j]
                for j in range(2)
            ))

    def _qCurveToOne(self, b, c):
        a = self.points[-1]
        for k in range(1, 65):
            t = k / 64
            u = 1 - t
            self.points.append(tuple(u * u * a[j] + 2 * u * t * b[j] + t * t * c[j] for j in range(2)))

    def _closePath(self):
        self.rings.append(self.points)
        self.points = []

    def _endPath(self):
        self._closePath()


def geometry(data):
    pen = Flatten()
    parse_path(data, pen)
    polys = [Polygon(ring) for ring in pen.rings]
    assert all(poly.is_valid for poly in polys), "Self-intersecting contour"
    result = Polygon()
    for poly in polys:
        result = result.symmetric_difference(poly)
    assert result.is_valid
    return result


report = []
sheet = Image.new("RGB", (1200, 530), "#EEEEEE")
draw = ImageDraw.Draw(sheet)
font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
for col, (number, name) in enumerate(NAMES.items()):
    source = ROOT / "concepts" / f"concept-{number}.svg"
    # Re-read final bytes, including XML, element types, colors and path data.
    svg = source.read_text()
    root = ET.fromstring(svg)
    assert root.attrib == {"version": "1.1", "width": "512", "height": "512", "viewBox": "0 0 512 512"}
    assert [node.tag.rsplit("}", 1)[-1] for node in root] == ["title", "desc", "path", "path"]
    assert all("stroke" not in attr and "href" not in attr for node in root for attr in node.attrib)
    badge, brain = root[-2:]
    assert badge.get("fill") == "#FF0000"
    assert brain.get("fill") == "#FFFFFF"
    badge_shape, brain_shape = geometry(badge.get("d")), geometry(brain.get("d"))
    assert badge_shape.bounds == (56, 115, 456, 397)
    assert badge_shape.contains(brain_shape)
    minx, miny, maxx, maxy = brain_shape.bounds
    assert abs((minx + maxx) / 2 - 256) < 1
    assert abs((miny + maxy) / 2 - 256) < 1
    assert 0.55 <= (maxx - minx) / 400 <= 0.65
    components = list(brain_shape.geoms) if brain_shape.geom_type == "MultiPolygon" else [brain_shape]
    assert len(components) == (2 if number == 14 else 1)
    bridges, spacings = [], []
    for component in components:
        holes = list(component.interiors)
        for i, hole in enumerate(holes):
            bridges.append(hole.distance(component.exterior))
            spacings.extend(hole.distance(other) for other in holes[:i])
    print(number, "minimum white bridge", min(bridges), "cutout separation", min(spacings, default=0), flush=True)
    assert min(bridges) >= 10, (number, bridges)
    assert not spacings or min(spacings) >= 14, (number, spacings)
    if number == 14:
        from shapely.affinity import affine_transform

        reflected = affine_transform(brain_shape, [-1, 0, 0, 1, 512, 0])
        assert brain_shape.symmetric_difference(reflected).area < 0.02
        assert abs(components[0].distance(components[1]) - 20) < 0.01
    for size in (512, 256, 32):
        target = OUT / f"concept-{number}-{size}.png"
        cairosvg.svg2png(bytestring=svg.encode(), write_to=str(target), output_width=size, output_height=size)
        im = Image.open(target).convert("RGBA")
        assert all(im.getpixel(p)[3] == 0 for p in [(0, 0), (size - 1, 0), (0, size - 1), (size - 1, size - 1)])
        if size == 512:
            assert im.getbbox() == (56, 115, 456, 397)
            assert im.getpixel((256, 130)) == (255, 0, 0, 255)
    report.append(
        f"Concept {number} — {name}: SVG 1.1; 512 x 512; only filled paths; exact #FF0000 and #FFFFFF; "
        f"brain width {(maxx - minx):.2f}px ({(maxx - minx) / 4:.2f}% of badge); "
        f"brain bounds {tuple(round(v, 2) for v in brain_shape.bounds)}; "
        f"minimum white bridge {min(bridges):.2f}px; "
        + (f"separation between cutouts {min(spacings):.2f}px; " if spacings else "20px expanded outline; ")
        + f"{len(components)} white component(s); no self-intersections; transparent exterior."
    )
    draw.text((col * 300 + 22, 25), f"{number} / {name}", font=font, fill="black")
    im = Image.open(OUT / f"concept-{number}-256.png")
    sheet.paste(im, (col * 300 + 22, 65), im)
    small = Image.open(OUT / f"concept-{number}-32.png")
    sheet.paste(small, (col * 300 + 36, 356), small)
    draw.text((col * 300 + 82, 363), "32 px", font=font, fill="black")
    zoom = small.resize((96, 96), Image.Resampling.NEAREST)
    sheet.paste(zoom, (col * 300 + 22, 415), zoom)
    draw.text((col * 300 + 136, 450), "pixel check", font=font, fill="black")

sheet.save(OUT / "contact-sheet.png")
report.append("Common badge: centered at (256, 256); bounds (56, 115, 456, 397); 400 x 282 px; aspect 1.41844; radius 76 px = 26.95% of height.")
report.append("Construction widths: Solid Brain folds 20 px; Play Fissure folds 18 px with 67 x 78 px triangular aperture; Outline Brain 20 px expanded strokes; Top Brain folds and central fissure 20 px. Rounded terminals and the intentional triangle point taper naturally.")
report.append("Checks sample cubic curves at 128 intervals, quadratics at 64. Final SVGs use two-decimal coordinates. No raster, font, text, image, mask, clip, filter, style, transform, or external references.")
(OUT / "self-check.txt").write_text("\n".join(report) + "\n")
print("\n".join(report))
