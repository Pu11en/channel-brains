"""Author original SVG contours; expand construction strokes into filled paths."""

import re
import xml.etree.ElementTree as ET
from pathlib import Path

import skia

ROOT = Path(__file__).resolve().parents[1]
BADGE = "M132 115 H380 A76 76 0 0 1 456 191 V321 A76 76 0 0 1 380 397 H132 A76 76 0 0 1 56 321 V191 A76 76 0 0 1 132 115 Z"
SIDE = """M149 220 C138 198 152 172 178 171
C190 149 218 147 239 160 C262 145 289 153 300 173
C327 166 351 181 354 205 C378 215 387 239 375 259
C385 282 370 304 346 307 C334 326 308 332 288 318
C275 325 260 326 249 322 L253 346 Q254 353 246 353
L227 353 Q219 353 218 345 L214 326
C191 337 170 326 163 307 C140 306 124 284 132 262
C119 245 127 224 149 220 Z"""


def parse(data):
    tokens = iter(re.findall(r"[MLCQZ]|-?\d+(?:\.\d+)?", data))
    path = skia.Path()
    sizes = {"M": 2, "L": 2, "C": 6, "Q": 4, "Z": 0}
    funcs = {"M": path.moveTo, "L": path.lineTo, "C": path.cubicTo,
             "Q": path.quadTo, "Z": path.close}
    for op in tokens:
        funcs[op](*[float(next(tokens)) for _ in range(sizes[op])])
    return path


def expand(data, width=20):
    paint = skia.Paint(Style=skia.Paint.kStroke_Style, StrokeWidth=width,
                       StrokeCap=skia.Paint.kRound_Cap, StrokeJoin=skia.Paint.kRound_Join)
    result = skia.Path()
    paint.getFillPath(parse(data), result)
    return result


def coords(points):
    return " ".join(f"{v:.2f}".rstrip("0").rstrip(".") for p in points for v in (p.x(), p.y()))


def serialize(path):
    iterator = skia.Path.RawIter(path)
    parts = []
    while True:
        verb, pts = iterator.next()
        if verb == skia.Path.kDone_Verb:
            break
        if verb == skia.Path.kMove_Verb:
            parts.append("M" + coords(pts))
        elif verb == skia.Path.kLine_Verb:
            parts.append("L" + coords(pts[1:]))
        elif verb == skia.Path.kQuad_Verb:
            parts.append("Q" + coords(pts[1:]))
        elif verb == skia.Path.kConic_Verb:
            qs = skia.Path.ConvertConicToQuads(*pts, iterator.conicWeight(), 2)
            for i in range(1, len(qs), 2):
                parts.append("Q" + coords(qs[i:i + 2]))
        elif verb == skia.Path.kCubic_Verb:
            parts.append("C" + coords(pts[1:]))
        elif verb == skia.Path.kClose_Verb:
            parts.append("Z")
    return " ".join(parts)


def cut(solid, folds, width=20):
    for fold in folds:
        solid = skia.Op(solid, expand(fold, width), skia.PathOp.kDifference_PathOp)
    return solid


def save(number, title, desc, brain, dx=3, dy=4, mirror=False):
    brain.transform(skia.Matrix.Translate(dx, dy))
    data = serialize(skia.Simplify(brain))
    if mirror:
        reflected = []
        is_x = True
        for token in re.findall(r"[MLCQZ]|-?\d+(?:\.\d+)?", data):
            if token in "MLCQZ":
                reflected.append(token)
                is_x = True
            else:
                reflected.append(f"{512 - float(token):.2f}" if is_x else token)
                is_x = not is_x
        data += " " + " ".join(reflected)
        brain = parse(data)
    svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" version="1.1" width="512" height="512" viewBox="0 0 512 512">
  <title>Channel Brains — {title}</title>
  <desc>{desc} Centered 400 by 282 badge, radius 76. All visible geometry consists of filled paths.</desc>
  <path fill="#FF0000" d="{BADGE}"/>
  <path fill="#FFFFFF" fill-rule="evenodd" d="{data}"/>
</svg>
'''
    target = ROOT / "concepts" / f"concept-{number}.svg"
    target.write_text(svg)
    ET.parse(target)
    b = brain.computeTightBounds()
    print(f"{target.name}: brain bounds {b}, {target.stat().st_size} bytes")


save(11, "Solid Brain", "A solid white side-profile brain with five broad 20 px gyrus cuts.",
     cut(parse(SIDE), [
         "M181 193 C173 214 187 232 211 232",
         "M252 181 C242 197 251 214 270 217",
         "M325 199 C337 220 324 240 303 240",
         "M151 274 C174 264 194 279 194 297",
         "M340 274 L314 274 C293 274 281 282 283 294",
     ]))

# A centered triangular aperture replaces the central fold; generous counters
# keep its play gesture distinct from the surrounding peripheral folds.
PLAY = """M151 220 C139 198 151 174 177 172
C188 151 216 148 239 160 C262 147 289 155 300 173
C327 167 351 183 354 206 C378 216 387 240 375 260
C385 282 371 305 346 307 C333 329 306 334 286 320
C266 333 243 331 226 320 C205 339 176 327 167 309
C142 310 125 287 133 265 C119 248 128 226 151 220 Z"""
play = cut(parse(PLAY), [
    "M182 196 C173 213 183 229 204 232",
    "M318 195 C329 210 325 223 315 229",
    "M156 275 C176 268 189 278 191 293",
    "M324 285 C308 284 299 293 298 305",
], 18)
play = skia.Op(play, parse("M234 216 L301 255 L234 294 Z"), skia.PathOp.kDifference_PathOp)
save(12, "Play Fissure", "A white brain enclosing a clean right-facing play triangle in negative space, with four 18 px peripheral cuts.", play, dy=14)

# Expand an actual 20 px centerline outline and merge its internal folds.
OUTLINE = """M159 219 C149 200 162 181 183 182
C194 163 218 160 239 173 C259 159 282 166 293 184
C316 177 337 190 339 212 C361 220 369 241 359 259
C369 278 355 297 335 298 C324 316 302 320 285 308
C270 318 252 316 239 310 L243 340 L225 340 L221 311
C201 326 179 316 175 299 C152 300 139 281 146 263
C135 246 140 226 159 219 Z"""
outline = expand(OUTLINE, 20)
for fold in [
    "M183 182 C179 205 188 222 210 224",
    "M293 184 C279 202 284 221 303 230",
    "M146 263 C169 251 196 262 200 283",
    "M335 298 C322 286 310 263 284 264",
]:
    outline = skia.Op(outline, expand(fold, 20), skia.PathOp.kUnion_PathOp)
save(13, "Outline Brain", "A hollow white side-profile brain with four connected folds; every 20 px construction stroke has been expanded into a fill.", outline, dx=4)

LEFT = """M246 182 C246 163 226 153 208 163
C195 151 173 162 171 181 C149 180 135 198 140 219
C124 233 125 256 140 269 C130 289 143 312 163 315
C165 336 187 349 207 340 C222 353 246 343 246 325 Z"""
left = cut(parse(LEFT), [
    "M189 198 C178 215 190 231 210 231",
    "M166 272 C185 269 203 282 198 303",
], 20)
save(14, "Top Brain", "Two exactly mirrored solid white hemispheres separated by a 20 px vertical fissure, with four bold 20 px folds.", left, dx=0, mirror=True)
