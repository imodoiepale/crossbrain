"""DESIRE x Kling: premium lyric motion graphics drawn per frame over the ping-pong Kling loop.

    python kling_fx.py 169|916                     full video -> kling-<fmt>-lyric-video-premium.mp4
    python kling_fx.py 169 --preview 2.5,64.5,93    stills  -> scratch dir
    python kling_fx.py 169 --clip 60 8              short test mp4 -> scratch dir

Pipeline: ffmpeg decodes the looped clip at native size -> a virtual camera reframes it per section (one lanczos
resample, beat kicks, shake) -> beat bloom, light leaks, the suite's jet -> numpy draws the text and
light layers -> ffmpeg encodes with Quick Sync (x264 fallback). Word timings come from desire_suite (read-only).
"""
import math
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, r"C:\path\to\project\tools")
import json  # noqa: E402
import desire_suite as ds  # noqa: E402  (word timings, line groups; adds tools/_pylib for Pillow)

# the artist's edited lyric text on the aligned timings (sync_words.py), when present
_EDITED = Path(r"C:\path\to\project\output\kling-lyrics\desire-words-edited.json")
if _EDITED.exists():
    ds.words = lambda: json.loads(_EDITED.read_text(encoding="utf-8"))
import cv2  # noqa: E402
import numpy as np  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

OUT = Path(r"C:\path\to\project\output\kling-lyrics")
SCR = Path(r"C:\path\to\scratch")
PP = {f: SCR / f"pp-{f}.mp4" for f in ("169", "916")}   # 8 s clip, forward + reversed (15.917 s seamless loop)
PP_LEN = 382 / 24
FPS, DUR = 24, 176.4
NFR = round(DUR * FPS)
WAV = ds.LAYERS / "desire-mix.wav"
CINZEL = str(OUT / "fonts/CinzelDecorative-Bold.ttf")
CORM = str(OUT / "fonts/CormorantGaramond-Italic.ttf")
f32 = np.float32

# roi = the band of the frame we draw into (x, y, w, h); anchor = block centre inside the roi.
CFG = {
    "169": dict(W=1920, H=1080, roi=(0, 60, 1000, 960), anchor=(480, 480), maxw=840, verse=122, disp=126,
                title=190, haze=0.34, q="18"),
    "916": dict(W=1080, H=1920, roi=(0, 860, 1080, 960), anchor=(540, 484), maxw=940, verse=106, disp=112,
                title=170, haze=0.5, q="20"),
}

CREAM, GOLD, EMBER, ROSE = (1.0, 0.97, 0.91), (1.0, 0.78, 0.45), (1.0, 0.42, 0.12), (1.0, 0.55, 0.68)
MOTIFS = [  # line text keywords -> light motif behind the words
    ("embers", "fire burning desire tired higher"),
    ("gold", "money dough paid payback collector maybach dollars madollars paper retire run"),
    ("streaks", "fly radar jamaica higher maybach"),
    ("rays", "gods inside design defiance amazing letting lately"),
    ("pink", "lovely love tonight body sexy party lify joking"),
]


def ease(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


_fonts = {}


def font(path, size):
    k = (path, size)
    if k not in _fonts:
        f = ImageFont.truetype(path, size)
        if path == CORM:
            f.set_variation_by_name("Bold Italic")
        _fonts[k] = f
    return _fonts[k]


def disc(r, soft=0.35):
    """Soft bokeh disc sprite (radius r)."""
    n = int(r * 2 + 6)
    yy, xx = np.mgrid[0:n, 0:n].astype(f32) - (n - 1) / 2
    d = np.sqrt(xx * xx + yy * yy) / r
    return np.clip((1 - d) / soft, 0, 1) ** 1.5 * (0.6 + 0.4 * np.clip(d, 0, 1))  # brighter rim, like a lens bokeh


def dot(r):
    n = int(r * 6 + 3)
    yy, xx = np.mgrid[0:n, 0:n].astype(f32) - (n - 1) / 2
    return np.exp(-(xx * xx + yy * yy) / (2 * r * r)).astype(f32)


def star(r):
    """Four-point glint: two thin gaussian streaks plus a hot core."""
    n = int(r * 2 + 1)
    yy, xx = np.mgrid[0:n, 0:n].astype(f32) - r
    s = np.exp(-(yy ** 2) / 2.0) * np.exp(-np.abs(xx) / (r * 0.35)) + np.exp(-(xx ** 2) / 2.0) * np.exp(-np.abs(yy) / (r * 0.35))
    return np.clip(s + 1.2 * np.exp(-(xx ** 2 + yy ** 2) / (r * 0.18) ** 2), 0, 1.5).astype(f32)


def rays_sprite(n=1300):
    yy, xx = np.mgrid[0:n, 0:n].astype(f32) - n / 2
    r, th = np.sqrt(xx * xx + yy * yy) + 1e-3, np.arctan2(yy, xx)
    beams = (0.5 + 0.5 * np.cos(11 * th)) ** 8 + 0.6 * (0.5 + 0.5 * np.cos(7 * th + 1.3)) ** 14
    return (beams * np.exp(-r / 330) * np.clip((r - 60) / 140, 0, 1)).astype(f32)


SPR = dict(disc=[disc(r) for r in (7, 10, 14, 19, 25)], dot=[dot(r) for r in (1.2, 1.8, 2.6)],
           star=[star(r) for r in (9, 14, 20)], rays=rays_sprite())


def add(dst, spr, x, y, col, k=1.0):
    """Additive blit of a 2-D sprite (top-left x, y) into an HxWx3 light buffer, clipped."""
    h, w = spr.shape
    H, W = dst.shape[:2]
    x, y = int(x), int(y)
    x0, y0, x1, y1 = max(0, x), max(0, y), min(W, x + w), min(H, y + h)
    if x0 >= x1 or y0 >= y1:
        return
    s = spr[y0 - y:y1 - y, x0 - x:x1 - x, None]
    dst[y0:y1, x0:x1] += s * (np.asarray(col, f32) * k)


def over(C, A, a, c, x, y):
    """Premultiplied 'over' of alpha a (h,w) with colour c (h,w,3 or 1,1,3) into C/A at (x, y)."""
    h, w = a.shape
    H, W = A.shape
    x, y = int(x), int(y)
    x0, y0, x1, y1 = max(0, x), max(0, y), min(W, x + w), min(H, y + h)
    if x0 >= x1 or y0 >= y1:
        return
    aa = a[y0 - y:y1 - y, x0 - x:x1 - x]
    if c.shape[0] > 1:                                       # (h,1,3) gradient or full (h,w,3) colour
        c = c[y0 - y:y1 - y]
    cc = c[:, x0 - x:x1 - x] if c.shape[1] > 1 else c
    inv = 1 - aa
    C[y0:y1, x0:x1] = C[y0:y1, x0:x1] * inv[..., None] + aa[..., None] * cc
    A[y0:y1, x0:x1] = A[y0:y1, x0:x1] * inv + aa


class Word:
    def __init__(self, text, fnt, size, ws, we, top, bot, glow, punch=False):
        self.text, self.size, self.ws, self.we, self.glow, self.punch = text, size, ws, we, glow, punch
        f = font(fnt, size)
        asc, desc = f.getmetrics()
        self.adv = f.getlength(text)
        self.P = P = int(size * 0.55)
        img = Image.new("L", (int(self.adv + 2 * P + size * 0.3), asc + desc + 2 * P))
        ImageDraw.Draw(img).text((P, P + asc), text, font=f, anchor="ls", fill=255)
        m = np.asarray(img, f32) / 255
        self.m = m
        self.mb = cv2.GaussianBlur(m, (0, 0), size * 0.07)
        self.g = cv2.GaussianBlur(m, (0, 0), size * 0.16) * 1.6 + cv2.GaussianBlur(m, (0, 0), size * 0.05) * 0.6
        u = np.clip((np.arange(m.shape[0], dtype=f32) - P) / max(1, asc + desc), 0, 1)[:, None, None]
        self.fill = np.asarray(top, f32) * (1 - u) + np.asarray(bot, f32) * u      # vertical gradient (h,1,3)
        self.asc = asc
        self.xs = np.arange(m.shape[1], dtype=f32)


class Line:
    """A block of rows of Words, its timing, light motifs and cached sprites."""

    def __init__(self, rows, s, e, cx, cy, kind, motifs, seed, pre=0.3, haze=0.35, gaps=None):
        self.s, self.e, self.kind, self.motifs, self.pre, self.haze = s, e, kind, motifs, pre, haze
        self.kick = 0.0                                      # set per frame by FX (audio kick envelope)
        lh = [max(w.size for w in r) * (1.12 if kind != "title" else 1.0) for r in rows]
        y = cy - sum(lh) / 2
        self.words, xs0, xs1 = [], [], []
        for r, h, gap in zip(rows, lh, gaps or [None] * len(rows)):
            sp = [gap if gap is not None else font(CORM if kind == "verse" else CINZEL, w.size).getlength(" ") for w in r]
            width = sum(w.adv for w in r) + sum(sp[:-1])
            x = cx - width / 2
            base = y + h / 2 + r[0].size * 0.33        # baseline that centres cap height in the row
            for w, g in zip(r, sp):
                w.x, w.y = x - w.P, base - w.asc - w.P
                self.words.append(w)
                x += w.adv + g
            xs0.append(cx - width / 2)
            xs1.append(cx + width / 2)
            y += h
        self.cx, self.cy = cx, cy
        self.bx0, self.bx1, self.by0, self.by1 = min(xs0), max(xs1), cy - sum(lh) / 2, cy + sum(lh) / 2
        rng = np.random.default_rng(seed)
        bw, bh = self.bx1 - self.bx0, self.by1 - self.by0
        self.p = {}
        n = 26
        self.p["motes"] = dict(x=rng.uniform(self.bx0 - 260, self.bx1 + 260, n), y=rng.uniform(-1, 1, n), v=rng.uniform(10, 28, n),
                               ph=rng.uniform(0, 6.3, n), k=rng.integers(0, 5, n), span=bh + 420)
        n = 46
        self.p["embers"] = dict(x=rng.uniform(self.bx0 - 200, self.bx1 + 200, n), v=rng.uniform(70, 190, n),
                                ph=rng.uniform(0, 1, n), ph2=rng.uniform(0, 6.3, n), k=rng.integers(0, 3, n))
        n = 18
        self.p["gold"] = dict(x=rng.uniform(self.bx0 - 120, self.bx1 + 120, n), y=rng.uniform(self.by0 - 150, self.by1 + 150, n),
                              f=rng.uniform(0.6, 1.4, n), ph=rng.uniform(0, 1, n), k=rng.integers(0, 3, n))
        n = 7
        self.p["streaks"] = dict(y=rng.uniform(self.by0 - 160, self.by1 + 160, n), v=rng.uniform(700, 1300, n),
                                 ph=rng.uniform(0, 1, n), L=rng.uniform(180, 420, n))
        self.haze_spr = None
        if haze:
            pad = int(max(w.size for w in self.words) * 1.1)
            hs = np.zeros((int(bh) + 2 * pad, int(bw) + 2 * pad), f32)
            cv2.rectangle(hs, (pad, pad), (pad + int(bw), pad + int(bh)), 1.0, -1)
            self.haze_spr = (cv2.GaussianBlur(hs, (0, 0), pad * 0.45) * haze, self.bx0 - pad, self.by0 - pad)

    # ------------------------------------------------------------------ drawing
    def draw(self, t, C, A, L):
        s, e = self.s, self.e
        lin, lout = ease((t - s) / 0.35), ease((e - t) / 0.45)
        vis = min(lin, lout)
        drift = -12 * (t - s) / max(0.5, e - s) - 28 * (1 - lout)
        if self.haze_spr is not None:
            hs, hx, hy = self.haze_spr
            over(C, A, hs * vis, np.zeros((1, 1, 3), f32), hx, hy + drift)
        self.motif_light(t, L, vis)
        if self.kind in ("verse", "swa"):                    # gold hairline drawing out under the block
            wcur = ease((t - s - 0.1) / 0.8) * (self.bx1 - self.bx0 + 90)
            if wcur > 4:
                yl = int(self.by1 + 8 + drift)
                xs = np.arange(int(wcur), dtype=f32)
                taper = np.sin(np.pi * (xs + 0.5) / wcur) ** 0.8
                prof = np.exp(-(np.arange(-9, 10, dtype=f32) ** 2) / 2.0) + 0.25 * np.exp(-(np.arange(-9, 10, dtype=f32) ** 2) / 30.0)
                add(L, prof[:, None] * taper[None, :], self.cx - wcur / 2, yl - 9, GOLD, 0.55 * lout)
        sway = 6 * math.sin(0.8 * t + self.cx * 0.01 + s)                 # the whole block floats
        bounce = -8 * self.kick if self.kind in ("chant", "fire", "title") else -2 * self.kick
        for j, w in enumerate(self.words):
            side = 1 if j % 2 else -1
            k = ease((t - w.ws) / 0.3) if t >= w.ws else 0.0
            op = (self.pre * lin + (1 - self.pre * lin) * k) * lout
            if op < 0.004:
                continue
            bm = max(1 - k, 1 - lout)
            a = (w.m * (1 - bm) + w.mb * bm) * op
            gl = (0.3 + 1.1 * math.exp(-(t - w.ws) / 0.35)) * k * lout if t >= w.ws else 0.05 * op
            gm = w.g * gl
            c = w.fill
            fly = (1 - k) ** 2                                # words fly in from below and alternate sides, then scatter out
            dy = drift + 46 * fly + bounce
            x, y = w.x + sway + side * (34 * fly + 22 * (1 - lout)), w.y + dy
            if t >= w.ws:
                sc = 1 + 0.2 * fly + (0.32 * math.exp(-(t - w.ws) / 0.11) if w.punch and t >= w.ws else 0.0)
                if sc > 1.01:
                    h0, w0 = a.shape
                    nw, nh = int(w0 * sc), int(h0 * sc)
                    a = cv2.resize(a, (nw, nh))
                    gm = cv2.resize(gm, (nw, nh))
                    c = cv2.resize(np.repeat(w.fill, w0, 1), (nw, nh))
                    x, y = x - (nw - w0) / 2, y - (nh - h0) / 2
            add(L, gm, x, y, w.glow, 0.55)
            over(C, A, a, c, x, y)
            if w.ws <= t <= w.we + 0.2:                       # light sweep runs across the word as it is sung
                p = (t - w.ws) / max(0.18, w.we - w.ws + 0.2)
                band = np.exp(-(((w.xs - (w.P + p * w.adv)) / (w.size * 0.45)) ** 2))
                add(L, a * band[None, :] if a.shape[1] == band.shape[0] else a, x, y, (1.0, 0.95, 0.85), 0.7)

    def motif_light(self, t, L, vis):
        if vis <= 0.01:
            return
        dt = t - self.s
        P = self.p["motes"]
        col = ROSE if "pink" in self.motifs else GOLD
        for i in range(len(P["x"])):
            y = self.by1 + 210 - ((P["y"][i] * 999 + P["v"][i] * dt) % P["span"])
            tw = 0.55 + 0.45 * math.sin(1.7 * t + P["ph"][i])
            spr = SPR["disc"][P["k"][i]]
            add(L, spr, P["x"][i] - spr.shape[1] / 2 + 14 * math.sin(0.4 * t + P["ph"][i]), y - spr.shape[0] / 2, col, 0.16 * tw * vis)
        if "embers" in self.motifs:
            P = self.p["embers"]
            span = self.by1 - self.by0 + 560
            for i in range(len(P["x"])):
                u = (P["ph"][i] + P["v"][i] * dt / span) % 1.0
                y = self.by1 + 260 - u * span
                x = P["x"][i] + 22 * math.sin(1.4 * t + P["ph2"][i]) + 40 * u
                fl = (0.55 + 0.45 * math.sin(11 * t + P["ph2"][i] * 3)) * math.sin(math.pi * u)
                spr = SPR["dot"][P["k"][i]]
                add(L, spr, x, y, EMBER, 1.6 * fl * vis)
        if "gold" in self.motifs:
            P = self.p["gold"]
            for i in range(len(P["x"])):
                a = max(0.0, math.sin(2 * math.pi * (P["f"][i] * dt + P["ph"][i]))) ** 4
                spr = SPR["star"][P["k"][i]]
                add(L, spr, P["x"][i] - spr.shape[1] / 2, P["y"][i] - spr.shape[0] / 2, (1.0, 0.86, 0.55), 0.9 * a * vis)
        if "streaks" in self.motifs:
            P = self.p["streaks"]
            W = L.shape[1]
            for i in range(len(P["y"])):
                x = W + 300 - ((P["ph"][i] * (W + 900) + P["v"][i] * dt) % (W + 900))
                ln = int(P["L"][i])
                tail = np.linspace(1, 0, ln, dtype=f32) ** 1.6
                prof = np.array([0.25, 0.7, 1.0, 0.7, 0.25], f32)
                add(L, prof[:, None] * tail[None, :], x, P["y"][i] - 2, (1.0, 0.9, 0.75), 0.5 * vis)
                add(L, SPR["dot"][2], x - 8, P["y"][i] - 8, (1.0, 0.95, 0.85), 1.0 * vis)
        if "rays" in self.motifs:
            R = SPR["rays"]
            n = R.shape[0]
            M = cv2.getRotationMatrix2D((n / 2, n / 2), 5 * t, 1.0)
            M[0, 2] += self.cx - n / 2
            M[1, 2] += self.cy - n / 2
            rot = cv2.warpAffine(R, M, (L.shape[1], L.shape[0]))
            L += rot[..., None] * (np.asarray(GOLD, f32) * 0.30 * vis * (0.85 + 0.15 * math.sin(2.1 * t)))
        if "rings" in self.motifs:
            for w in self.words:
                u = (t - w.ws) / 1.4
                if 0 <= u < 1:
                    r = int(50 + 560 * (1 - (1 - u) ** 2))
                    a = (1 - u) ** 2
                    c = (int(self.cx), int(self.cy))
                    cv2.circle(L, c, r, tuple(float(v) * 0.12 * a for v in EMBER), 18, cv2.LINE_AA)
                    cv2.circle(L, c, r, tuple(float(v) * 0.55 * a for v in GOLD), 3, cv2.LINE_AA)


# ---------------------------------------------------------------------- song structure -> Lines
def wrap(words, sp, mw):
    rows, cur, wd = [], [], 0
    for w in words:
        if cur and wd + sp + w.adv > mw:
            rows.append(cur)
            cur, wd = [], 0
        wd += (sp if cur else 0) + w.adv
        cur.append(w)
    return rows + [cur]


def build_lines(fmt):
    c = CFG[fmt]
    cx, cy = c["anchor"]
    out = []
    # epic title: EPALLE tracks out (Cormorant caps: Cinzel Decorative's ornamental L read as "I"), DESIRE assembles
    T = c["title"]
    r1 = [Word(ch, CINZEL, T, 1.9 + 0.17 * i, 2.5 + 0.17 * i, (1.0, 0.95, 0.85), (1.0, 0.68, 0.32), EMBER, punch=True)
          for i, ch in enumerate("DESIRE")]
    # (DESIRE / rule / E P A L L E signature now comes from the suite's alpha clips: see encode_cmd)
    # his "Epalle" shout at 13.15 s (isolated vocal), spelled as his name; the 7.7 s / 17.6 s ad-libs stay unlabelled
    r0 = [Word(ch, CORM, int(T * 0.62), 13.15 + 0.06 * i, 13.6 + 0.06 * i, CREAM, GOLD, EMBER, punch=True) for i, ch in enumerate("EPALLE")]
    out.append(Line([r0], 13.0, 16.0, cx, cy, "title", {"rays", "embers"}, 8, pre=0.0, haze=c["haze"], gaps=[T * 0.06]))
    ls = ds.lines()
    for li, ws in enumerate(ls):
        s = ws[0]["start_ms"] / 1000 - 0.15
        nxt = ls[li + 1][0]["start_ms"] / 1000 - 0.06 if li + 1 < len(ls) else DUR
        e = max(s + 0.6, min(nxt, ws[-1]["end_ms"] / 1000 + 1.4))
        text = " ".join(w["text"] for w in ws).lower()
        motifs = {m for m, keys in MOTIFS if any(k in text.split() or k in text for k in keys.split())}
        if li in ds.FIRE_LINES:
            kind, fnt, size, case, top, bot, glow, punch = "fire", CINZEL, c["disp"], ds.dr_case, (1.0, 0.93, 0.78), (1.0, 0.55, 0.18), EMBER, True
            motifs |= {"embers", "rays"}
        elif li in ds.STOMP:
            kind, fnt, size, case, top, bot, glow, punch = "chant", CINZEL, c["disp"], ds.dr_case, (1.0, 0.9, 0.7), GOLD, EMBER, True
            motifs |= {"rings", "embers"}
        elif li in ds.SWAHILI:
            kind, fnt, size, case, top, bot, glow, punch = "swa", CINZEL, int(c["disp"] * 0.78), str.upper, CREAM, (1.0, 0.8, 0.62), ROSE, False
        else:
            kind, fnt, size, case, top, bot, glow, punch = "verse", CORM, c["verse"], lambda x: x, CREAM, GOLD, GOLD, False
        for _ in range(4):                                   # wrap; shrink until it fits in 3 rows
            words = []
            for j, w in enumerate(ws):
                hot = li in ds.HAYA and ds.norm(w["text"]) == "haya"
                txt = case(w["text"]) if kind in ("verse", "swa") or j == 0 else w["text"].lower()   # dr_case: first word only
                words.append(Word(txt, fnt, size, w["start_ms"] / 1000, w["end_ms"] / 1000, top,
                                  EMBER if hot else bot, EMBER if hot else glow, punch or hot))
            sp = font(fnt, size).getlength(" ")
            rows = wrap(words, sp, c["maxw"])
            for mw in range(int(c["maxw"]) - 20, int(c["maxw"] * 0.4), -20):   # balance rows: no orphan words
                r2 = wrap(words, sp, mw)
                if len(r2) != len(rows):
                    break
                rows = r2
            if len(rows) <= 3:
                break
            size = int(size * 0.86)
        out.append(Line(rows, s, e, cx, cy, kind, motifs, li, haze=c["haze"]))
    return out


# ---------------------------------------------------------------------- frame loop
NAT = {"169": (1280, 720), "916": (720, 1280)}           # the Kling clips' native size (decoded as-is, resampled once)
# framing targets as fractions of the frame (where the face / sun / water sit in the Kling shot)
SPOTS = {"169": dict(wide=(0.5, 0.5), face=(0.5, 0.3), sun=(0.56, 0.24), water=(0.48, 0.8), sky=(0.3, 0.3)),
         "916": dict(wide=(0.5, 0.5), face=(0.5, 0.32), sun=(0.5, 0.27), water=(0.5, 0.78), sky=(0.5, 0.2))}
AUD = np.load(ds.LAYERS / "audio.npz")


def snap_beat(t):
    b = AUD["beats"]
    return float(b[np.argmin(np.abs(b - t))]) if len(b) else t


def shot_list(fmt):
    """Camera plan, one shot per song section: (t0, t1, cut, (z0, spot0), (z1, spot1)).
    Hard cuts land on the beat at chorus / climax entries; everything else glides."""
    ls = ds.lines()
    ch = [(ls[a][0]["start_ms"] / 1000, ls[b][-1]["end_ms"] / 1000) for a, b in ds.CHORUS if len(ls) > b]
    clim = ds.climax_start()
    hard = [snap_beat(a) for a, _ in ch] + [snap_beat(b) for _, b in ch] + [snap_beat(clim)]
    marks = [0.0]
    for m in sorted({17.5, DUR - 14.0, *hard}):
        if m - marks[-1] >= 3.0:                             # no shot shorter than 3 s
            marks.append(m)
    cuts = [marks[0]]
    for m in marks[1:] + [DUR]:                              # split long sections into ~8 s camera moves (not intro/outro)
        n = 1 if m <= 17.5 or cuts[-1] >= DUR - 14.01 else max(1, round((m - cuts[-1]) / 8.0))
        cuts += [snap_beat(cuts[-1] + (m - cuts[-1]) * k / n) for k in range(1, n)] + [m]
    cuts = sorted(set(round(x, 3) for x in cuts))
    verse = [(1.06, "wide", 1.22, "face"), (1.25, "sun", 1.1, "face"), (1.18, "water", 1.06, "wide"),
             (1.08, "sky", 1.24, "face"), (1.3, "face", 1.12, "sun")]
    chorus = [(1.32, "face", 1.2, "face"), (1.04, "wide", 1.12, "sun"), (1.24, "water", 1.3, "face")]
    shots, vi, ci = [], 0, 0
    for t0, t1 in zip(cuts, cuts[1:]):
        mid = (t0 + t1) / 2
        if t1 <= 17.6:
            p = (1.0, "wide", 1.12, "face")                   # intro: slow push-in under the title
        elif t0 >= DUR - 14.01:
            p = (1.22, "face", 1.0, "wide")                   # outro: pull back out to the full frame
        elif any(a - 0.3 <= mid <= b + 0.3 for a, b in ch) or mid >= clim:
            p, ci = chorus[ci % len(chorus)], ci + 1
        else:
            p, vi = verse[vi % len(verse)], vi + 1
        cut = any(abs(t0 - h) < 0.05 for h in hard)
        shots.append((t0, t1, cut, (p[0], SPOTS[fmt][p[1]]), (p[2], SPOTS[fmt][p[3]])))
    return shots


class Camera:
    """Virtual camera over the loop: per-section reframing, beat kicks, shake on hits."""

    def __init__(self, fmt):
        self.fmt, self.shots = fmt, shot_list(fmt)
        self.W, self.H = CFG[fmt]["W"], CFG[fmt]["H"]

    def at(self, t):
        for i, (t0, t1, cut, a, b) in enumerate(self.shots):
            if t0 <= t < t1 or i == len(self.shots) - 1:
                u = ease((t - t0) / max(0.1, t1 - t0)) * 0.85 + 0.15 * (t - t0) / max(0.1, t1 - t0)
                z = a[0] + (b[0] - a[0]) * u
                fx, fy = (a[1][0] + (b[1][0] - a[1][0]) * u, a[1][1] + (b[1][1] - a[1][1]) * u)
                if i and not cut and t - t0 < 1.4:            # glide out of the previous shot's end framing
                    _, _, _, _, pb = self.shots[i - 1]
                    g = ease((t - t0) / 1.4)
                    z, fx, fy = pb[0] + (z - pb[0]) * g, pb[1][0] + (fx - pb[1][0]) * g, pb[1][1] + (fy - pb[1][1]) * g
                return z, fx, fy

    def matrix(self, t, A, hit):
        z, fx, fy = self.at(t)
        z *= 1 + 0.018 * A["kick"] ** 2 + 0.03 * A["kick"] ** 2 * hit      # breathes on the kick, punches in the chorus
        W, H = self.W, self.H
        cx = min(max(fx * W, W / (2 * z)), W - W / (2 * z))
        cy = min(max(fy * H, H / (2 * z)), H - H / (2 * z))
        sh = 7 * A["onset"] ** 3 * hit                                       # shake on hits (stays inside the overscan)
        cx += sh * math.sin(t * 91.0)
        cy += sh * math.cos(t * 77.0)
        nw, nh = NAT[self.fmt]
        s = z * W / nw                                                       # native clip -> output, zoomed: one resample
        ox, oy = cx * nw / W, cy * nh / H
        return np.array([[s, 0, W / 2 - s * ox], [0, s, H / 2 - s * oy]], np.float32), z


class FX:
    def __init__(self, fmt):
        self.fmt = fmt
        self.c = CFG[fmt]
        self.lines = build_lines(fmt)
        self.cam = Camera(fmt)
        ev = ds.events()
        self.chorus = [(a, b) for k, a, b in ev if k == "chorus"]
        self.clim = ds.climax_start()
        self.cuts = [s[0] for s in self.cam.shots if s[2]]
        W, H = self.c["W"], self.c["H"]
        # the suite's jet + contrails on "Jamaica" (desire_suite.sky_layer, unchanged)
        import types
        self.sky = types.SimpleNamespace(W=W, H=H, fmt=fmt, plane_img=ds.plane_cutout(), events=[e for e in ev if e[0] == "plane"])
        self.leak_x = np.linspace(-1, 1, W // 4, dtype=f32)[None, :]
        self.leak_y = np.linspace(-1, 1, H // 4, dtype=f32)[:, None]
        x0, y0, w, h = self.c["roi"]
        fy = np.minimum(np.arange(h, dtype=f32), np.arange(h, dtype=f32)[::-1]) / 70
        fx = np.minimum(np.arange(w, dtype=f32), np.arange(w, dtype=f32)[::-1]) / 70
        if x0 == 0:
            fx[: w // 2] = 1                                 # left roi edge is the frame edge: no feather there
        self.feather = np.clip(np.minimum(fy[:, None], fx[None, :]), 0, 1)[..., None]

    def frame(self, t, nat):
        rgb = self.background(t, nat)
        x0, y0, w, h = self.c["roi"]
        act = [ln for ln in self.lines if ln.s <= t < ln.e]
        for ln in act:
            ln.kick = self.A["kick"] ** 2
        if not act:
            return rgb
        C = np.zeros((h, w, 3), f32)
        A = np.zeros((h, w), f32)
        L = np.zeros((h, w, 3), f32)
        for ln in act:
            ln.draw(t, C, A, L)
        bg = rgb[y0:y0 + h, x0:x0 + w].astype(f32) / 255
        o = bg * (1 - A[..., None]) + C
        o = 1 - (1 - np.clip(o, 0, 1)) * (1 - np.clip(L * self.feather, 0, 1))      # light layers: screen blend
        rgb[y0:y0 + h, x0:x0 + w] = (o * 255 + 0.5).astype(np.uint8)
        return rgb

    def background(self, t, nat):
        """Native Kling frame -> camera move, beat bloom, light leaks on cuts, flashes, the jet, chromatic split."""
        W, H = self.c["W"], self.c["H"]
        i = min(int(round(t * FPS)), len(AUD["kick"]) - 1)
        A = self.A = {k: float(AUD[k][i]) for k in ("energy", "smooth", "kick", "high", "onset")}
        hit = max([ds.env(t, a, b) for a, b in self.chorus] + [ease((t - self.clim) / 4.0)])
        M, z = self.cam.matrix(t, A, hit)
        bg = cv2.warpAffine(nat, M, (W, H), flags=cv2.INTER_LANCZOS4, borderMode=cv2.BORDER_REFLECT)
        bg = cv2.addWeighted(bg, 1.6, cv2.GaussianBlur(bg, (0, 0), 1.1 + 0.3 * z), -0.6, 0)   # light unsharp after the zoom
        # bloom: the sun and highlights swell on the kick (quarter-res, screen-added)
        q = cv2.resize(bg, (W // 4, H // 4), interpolation=cv2.INTER_AREA).astype(f32) / 255
        lt = cv2.GaussianBlur(np.maximum(q - 0.8, 0), (0, 0), 9) * (0.3 + 1.0 * A["kick"] ** 2 + 0.5 * hit)
        for c0 in self.cuts:                                  # warm light leak sweeping across on every hard cut
            u = t - c0
            if 0 <= u < 1.3:
                pos = -1.2 + 2.8 * u / 1.3
                g = np.exp(-((self.leak_x - pos) ** 2) / 0.12) * (0.7 + 0.3 * (1 - np.abs(self.leak_y)))
                lt += g[..., None] * (ds.WARM * 0.55 * (1 - u / 1.3) ** 1.5)
        lt += 0.09 * A["onset"] ** 4 * hit                    # flash on the hardest hits
        bg = cv2.add(bg, cv2.convertScaleAbs(cv2.resize(lt, (W, H), interpolation=cv2.INTER_LINEAR), alpha=255.0))
        if any(a - 0.2 <= t <= b + 2.5 for _, a, b in self.sky.events):
            f = bg.astype(f32) / 255
            ds.sky_layer(self.sky, f, t, 0.6)
            bg = cv2.convertScaleAbs(np.nan_to_num(f), alpha=255.0)
        sh = int(round(3 * A["kick"] ** 2 * (1 + hit)))
        if sh:                                                # chromatic split on the kick
            bg[..., 0] = np.roll(bg[..., 0], sh, 1)
            bg[..., 2] = np.roll(bg[..., 2], -sh, 1)
        return bg


def decoder(fmt, t0, n):
    c = CFG[fmt]
    vf = "scale=in_color_matrix=bt709:in_range=tv,format=rgb24"   # native size: the camera resamples once (lanczos)
    return subprocess.Popen(["ffmpeg", "-v", "error", "-ss", f"{t0 % PP_LEN:.4f}", "-stream_loop", "-1", "-i", str(PP[fmt]),
                             "-vf", vf, "-frames:v", str(n), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                            stdout=subprocess.PIPE, bufsize=1 << 24)


# the suite's title signature (DESIRE, gold rule, E P A L L E), copied from _layers/title so a suite re-render can't change it mid-encode
TITLE = {f: [Path(__file__).with_name("title") / f"v1-solar-pulse-{f}-{k}.mov" for k in ("intro", "outro")] for f in ("169", "916")}
TITLE_XY = {"169": (22, 0), "916": (97, 32)}


def title_fc(fmt, t0):
    """Intro clip (0-12 s), transparent gap, outro clip (from DUR-14 s, frame-exact like the suite), overlaid on stdin video."""
    x, y = TITLE_XY[fmt]
    w, h = (970, 416) if fmt == "169" else (884, 408)
    gap = (int((DUR - 14.0) * FPS) - 12 * FPS) / FPS
    return (f"[2:v]format=rgba[ti];color=c=black@0.0:s={w}x{h}:r={FPS}:d={gap:.6f},format=rgba[tg];[3:v]format=rgba[to];"
            f"[ti][tg][to]concat=n=3:v=1:a=0,trim=start={t0:.4f},setpts=PTS-STARTPTS[tt];"
            f"[0:v][tt]overlay=x={x}:y={y}:eof_action=pass:format=auto,scale=out_color_matrix=bt709:out_range=tv[v]")


def encode_cmd(fmt, out, t0, dur, qsv=True):
    c = CFG[fmt]
    v = (["-c:v", "h264_qsv", "-global_quality", c["q"], "-look_ahead", "0", "-preset", "medium", "-profile:v", "high", "-g", "48", "-pix_fmt", "nv12"]
         if qsv else ["-c:v", "libx264", "-preset", "faster", "-crf", c["q"], "-profile:v", "high", "-g", "48", "-pix_fmt", "yuv420p", "-threads", "2"])
    return (["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{c['W']}x{c['H']}", "-r", str(FPS), "-i", "-",
             "-ss", f"{t0:.3f}", "-t", f"{dur:.3f}", "-i", str(WAV), "-i", str(TITLE[fmt][0]), "-i", str(TITLE[fmt][1]),
             "-filter_complex", title_fc(fmt, t0), "-map", "[v]", "-map", "1:a"] + v +
            ["-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv",
             "-bsf:v", "h264_metadata=colour_primaries=1:transfer_characteristics=1:matrix_coefficients=1:video_full_range_flag=0",
             "-c:a", "aac", "-b:a", "320k", "-ar", "48000", "-shortest", "-map_metadata", "-1", "-map_chapters", "-1",
             "-fflags", "+bitexact", "-movflags", "+faststart", str(out)])


def run(fmt, out, t0=0.0, dur=DUR):
    fx, c = FX(fmt), CFG[fmt]
    n = round(dur * FPS)
    nw, nh = NAT[fmt]
    size = nw * nh * 3
    for qsv in (True, False):
        dec = decoder(fmt, t0, n)
        enc = subprocess.Popen(encode_cmd(fmt, out, t0, dur, qsv), stdin=subprocess.PIPE)
        t_start = time.time()
        try:
            for i in range(n):
                buf = dec.stdout.read(size)
                if len(buf) < size:
                    raise RuntimeError(f"decoder ended at frame {i}")
                rgb = np.frombuffer(buf, np.uint8).reshape(nh, nw, 3)
                enc.stdin.write(fx.frame(t0 + i / FPS, rgb).tobytes())
                if i % 240 == 0:
                    el = time.time() - t_start
                    print(f"{fmt} frame {i}/{n}  {i / max(el, 1e-3):.1f} fps", flush=True)
            enc.stdin.close()
            if enc.wait() == 0:
                dec.wait()
                return
        except (BrokenPipeError, OSError):
            pass
        dec.kill()
        enc.kill()
        if qsv:
            print("Quick Sync encode failed; retrying with x264", flush=True)
    raise SystemExit("encode failed")


def preview(fmt, times):
    fx, c = FX(fmt), CFG[fmt]
    for t in times:
        dec = decoder(fmt, t, 1)
        nw, nh = NAT[fmt]
        rgb = np.frombuffer(dec.stdout.read(nw * nh * 3), np.uint8).reshape(nh, nw, 3)
        dec.wait()
        img = fx.frame(t, rgb)
        cv2.imwrite(str(SCR / f"fx-{fmt}-{t:g}.jpg"), cv2.cvtColor(img, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 88])
        print("wrote", SCR / f"fx-{fmt}-{t:g}.jpg", flush=True)


if __name__ == "__main__":
    fmt = sys.argv[1]
    if "--preview" in sys.argv:
        preview(fmt, [float(x) for x in sys.argv[sys.argv.index("--preview") + 1].split(",")])
    elif "--clip" in sys.argv:
        i = sys.argv.index("--clip")
        t0, d = float(sys.argv[i + 1]), float(sys.argv[i + 2])
        run(fmt, SCR / f"clip-{fmt}-{t0:g}.mp4", t0, d)
    else:
        run(fmt, OUT / f"kling-{fmt}-lyric-video-premium.mp4")
        print("done", flush=True)
