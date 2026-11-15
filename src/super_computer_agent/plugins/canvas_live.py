"""canvas_live.py - màn hình live dạng CANVAS BỀN VỮNG + lệnh delta (canvas_v7: scene recall, tuổi thọ ttl).
Khác pixel_grid (lưới màu dạng chữ): model nhận ẢNH THẬT, nhưng chỉ phần thay đổi sau keyframe đầu.
Chỉ có lợi với model tính token ảnh theo pixel (như Claude) và khi cuộc trò chuyện giữ lại các lượt trước.
Model tính theo số ảnh (Gemini) thì không lợi. Mặc định KHÔNG chạy gì cho tới khi gọi canvas_start."""
import os, sys, threading, time
import numpy as np
from PIL import Image

NAME = "canvas_live"
DESC = "Canvas live nén delta (v7): canvas_start/canvas_step/canvas_stop/canvas_status - keyframe 1 lần rồi chỉ gửi phần đổi (patch atlas, scroll, move, recall cảnh cũ)"
OUT = os.path.join(os.environ.get("SCA_OUTPUT_DIR", "outputs"), "canvas_live")
KEEP = 40          # số PNG giữ lại trên đĩa (ảnh chụp màn hình không tích tụ vô hạn)
T = 64
_S = dict(cd=None, n=0, size=None, max_side=1280, ttl=None, tot=0.0, keys=0, recalls=0, use_hwnd=False, tm={}, lock=threading.RLock())
_lib = {}

INSTR = (
    "CANVAS LIVE (v7): canvas_start() một lần, rồi canvas_step() mỗi khi cần nhìn màn hình. Lần đầu và mỗi lần đổi cảnh mới là KEY = ảnh đầy đủ "
    "(mở bằng view_image; thư mục ảnh do canvas_start báo, tên file ghi ngay ở dòng KEY/PATCH). Các lần sau chỉ là phần thay đổi: áp các dòng theo THỨ TỰ lên canvas trong đầu. "
    "KEY k7.png (lưu S0; ảnh này là S1): lưu canvas hiện tại thành cảnh S0, canvas mới = ảnh này (cảnh S1; không có ngoặc = keyframe đầu). "
    "RECALL a->b: lưu canvas hiện tại thành cảnh S<a>, rồi canvas = cảnh S<b> ở trạng thái lần cuối của nó (keyframe cũ + các delta sau đó); chỉ đúng khi cảnh đó còn trong ngữ cảnh, "
    "nếu không còn thì gọi canvas_start rồi canvas_step để lấy keyframe mới. "
    "SCROLL y0..y1 x0..x1 up dy: hàng y0..y1, cột x0..x1 dịch LÊN dy px (âm = xuống); phần hở được vá bởi PATCH sau đó. "
    "MOVE x,y,w,h from ox,oy: vùng (x,y,w,h) chép từ (x+ox, y+oy) của canvas hiện tại. "
    "DC tx,ty:v;...: ô 64px (tx,ty) cộng thêm giá trị màu v (r/g/b hoặc một số). "
    "PATCH a13.png <legend>: ảnh atlas gồm các mảnh xếp trái->phải, khe 1px, sang hàng mới khi đầy bề rộng 1568px, thứ tự trùng legend (các mục cách nhau bằng ';'). Mục 'tx,ty,s,wt' = dán mảnh vào ô (tx,ty) "
    "(px = tx*64, py = ty*64), rộng wt ô, cao 1 ô; mục 'px,py,s,w,h' = dán tại px,py, với w,h là kích thước TRONG atlas. s = hệ số đã thu nhỏ (s=4: mảnh nhỏ 4 lần, phóng to 4 lần khi dán). "
    "STALE: các ô có thể đã cũ, nên nhìn lại bằng canvas_crop(x,y,w,h) (ảnh thật của đúng vùng đó, rẻ hơn keyframe mới) hoặc canvas_start nếu cả cảnh đã cũ. "
    "Ảnh gần đúng (sai số nhỏ), cần đọc chính xác chữ/số nhỏ thì dùng canvas_crop (zoom 2-3 cho chữ rất nhỏ). canvas_stop khi xong.")


def ro(fn):
    fn.readonly = True
    return fn


def _load():
    if not _lib:
        try:
            import cv2
        except Exception as e:
            raise RuntimeError(f"không nạp được opencv-python ({e})") from e
        from ..licensing import LicenseError, license_slot
        try:
            cm = license_slot()
            cm.__enter__()
        except LicenseError as e:
            raise RuntimeError(f"canvas_v7/canvas_delta2 là module proprietary, cần license key hợp lệ: {e}") from e
        else:
            import atexit
            atexit.register(cm.__exit__, None, None, None)
        try:
            from ..canvas._compiled import canvas_v7, canvas_delta2
        except Exception as e:
            raise RuntimeError(f"không nạp được canvas_v7/canvas_delta2 ({e})") from e
        _lib.update(cv2=cv2, v7=canvas_v7, d2=canvas_delta2)
    return _lib


def _tm(name, t0):
    """Cộng dồn thời gian (ms) của một giai đoạn: [tổng, số lần, lớn nhất]."""
    ms = (time.time() - t0) * 1000.0
    a = _S["tm"].setdefault(name, [0.0, 0, 0.0]); a[0] += ms; a[1] += 1; a[2] = max(a[2], ms)


def _hwnd():
    """hwnd cửa sổ đang ở trên cùng (chỉ làm gợi ý thứ tự thử cảnh); None nếu không lấy được."""
    try:
        import ctypes
        h = int(ctypes.windll.user32.GetForegroundWindow())
        return h or None
    except Exception:
        return None


def _grab():
    import mss
    M = getattr(mss, "MSS", None) or mss.mss
    with M() as s:
        raw = s.grab(s.monitors[1])
    return np.asarray(Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX"))


def _small(f):
    """Ảnh xám rất nhỏ (160x96) để so sánh nhanh 'màn đang đổi hay đã yên'."""
    return _lib["cv2"].resize(_lib["cv2"].cvtColor(f, _lib["cv2"].COLOR_RGB2GRAY), (160, 96), interpolation=_lib["cv2"].INTER_AREA).astype(np.float32)


SETTLE_THR = 0.8   # sai khác TB (mức xám, ảnh 160x96) từ đó coi là 'đang đổi'
SETTLE_GAP = 0.06  # giây giữa hai lần chụp khi chờ yên


def _grab_settled():
    """Chụp; nếu so với khung cuối ở bước trước màn ĐANG ĐỔI thì chờ tới khi yên (tối đa settle_ms) rồi mới trả khung.
    Màn tĩnh: không tốn thêm gì. Tránh mã hóa các khung chuyển cảnh/hiệu ứng giữa chừng (nguyên nhân KEY/RECALL thừa, độ trễ không ổn định)."""
    t0 = time.time(); fr = _grab(); _tm("grab", t0)
    lim = _S.get("settle_ms", 0) / 1000.0
    sm = _small(fr); prev = _S.get("prev_small")
    if lim > 0 and prev is not None and float(np.abs(sm - prev).mean()) > SETTLE_THR:
        t1 = time.time(); n = 0
        while time.time() - t1 < lim:
            time.sleep(SETTLE_GAP); f2 = _grab(); s2 = _small(f2); n += 1
            done = float(np.abs(s2 - sm).mean()) <= SETTLE_THR * .25
            fr, sm = f2, s2
            if done: break
        _tm("settle", t1); _S["settles"] = _S.get("settles", 0) + 1
    _S["prev_small"] = sm
    return fr


def _prep(f):
    H, W = f.shape[:2]; m = _S["max_side"]
    if max(H, W) > m:
        k = m / max(H, W)
        f = _lib["cv2"].resize(f, (max(8, round(W * k)), max(8, round(H * k))), interpolation=_lib["cv2"].INTER_AREA)
    return np.ascontiguousarray(f)


PNG_LEVEL = 1   # v10: PNG vẫn không mất mát; mức 1 nhanh hơn mức mặc định 6 (~9 ms/keyframe 1280x768), file to hơn ~30% trên đĩa (số token ảnh tính theo pixel nên không đổi)


def _u8(a):
    """-> uint8, giống hệt np.clip(a,0,255).round().astype(np.uint8) (đã kiểm: ngẫu nhiên, đúng .5, giá trị biên) nhưng ~5x nhanh với canvas float32 (cv2.add saturate + làm tròn half-to-even)."""
    a = np.asarray(a)
    if a.dtype == np.uint8: return a
    if a.dtype == np.float32 and a.ndim == 3 and a.shape[2] == 3 and "cv2" in _lib:
        return _lib["cv2"].add(a, 0, dtype=_lib["cv2"].CV_8U)
    return np.clip(a, 0, 255).round().astype(np.uint8)


def _save_png(a, name):
    os.makedirs(OUT, exist_ok=True)
    p = os.path.join(OUT, name)
    im = a if isinstance(a, Image.Image) else Image.fromarray(_u8(a))
    im.save(p, compress_level=PNG_LEVEL)
    for old in sorted((f for f in os.listdir(OUT) if f.endswith(".png")), key=lambda f: os.path.getmtime(os.path.join(OUT, f)))[:-KEEP]:
        try: os.remove(os.path.join(OUT, old))
        except OSError: pass
    return os.path.abspath(p)


def _dir():
    return os.path.abspath(OUT)


def _fnum(x):
    return ("%.1f" % x).rstrip("0").rstrip(".") if x == x else "0"


def serialize(ops, n):
    """Chuỗi op của v7 -> (các dòng văn bản theo thứ tự, danh sách bản ghi có cấu trúc cho kiểm thử)."""
    d2 = _lib["d2"]; lines = []; recs = []; i = 0
    while i < len(ops):
        o = ops[i]; k = o[0]
        if k == "key":
            p = _save_png(o[1], f"k{n}.png"); frm = o[2] if len(o) > 3 else None; new = o[3] if len(o) > 3 else None
            lines.append(f"KEY {os.path.basename(p)}" + (f" (lưu S{frm}; ảnh này là S{new})" if frm is not None else ""))
            recs.append(("key", p, frm, new)); i += 1
        elif k == "recall":
            lines.append(f"RECALL S{o[1]}->S{o[2]}")
            recs.append(("recall", o[1], o[2])); i += 1
        elif k == "scroll":
            (y0, y1, x0, x1), dy = o[1], int(o[2])
            lines.append(f"SCROLL {y0}..{y1} {x0}..{x1} up {dy}")
            recs.append(("scroll", (y0, y1, x0, x1), dy)); i += 1
        elif k == "move":
            (x0, y0, w, h), ox, oy = o[1], int(o[2]), int(o[3])
            lines.append(f"MOVE {x0},{y0},{w},{h} from {ox:+d},{oy:+d}")
            recs.append(("move", (x0, y0, w, h), ox, oy)); i += 1
        elif k == "dc":
            grp = []
            while i < len(ops) and ops[i][0] == "dc":
                v = np.round(np.ravel(np.asarray(ops[i][3], float)), 1).tolist(); grp.append((int(ops[i][2]), int(ops[i][1]), v)); i += 1
            lines.append("DC " + ";".join(f"{tx},{ty}:" + "/".join(_fnum(x) for x in v) for tx, ty, v in grp))
            recs.append(("dc", grp))
        elif k == "patch":
            grp = []
            while i < len(ops) and ops[i][0] == "patch":
                grp.append(ops[i]); i += 1
            im, leg = d2.to_atlas(grp, T)
            p = _save_png(im, f"a{n}.png" if not any(r[0] == "patch" for r in recs) else f"a{n}_{len(recs)}.png")
            lines.append(f"PATCH {os.path.basename(p)} {leg}")
            recs.append(("patch", p, leg))
        else:
            lines.append(f"? lệnh lạ {k}"); recs.append(("unknown", k)); i += 1
    return lines, recs


def start(max_side=1280, ttl_tok=0, use_hwnd=False, settle_ms=400):
    with _S["lock"]:
        L = _load()
        _S.update(cd=L["v7"].CanvasDelta(ttl_tok=(int(ttl_tok) if ttl_tok and ttl_tok > 0 else None)), n=0, size=None, ttl=(int(ttl_tok) if ttl_tok and ttl_tok > 0 else None),
                  max_side=max(256, min(int(max_side), 2560)), tot=0.0, keys=0, recalls=0, use_hwnd=bool(use_hwnd), tm={},
                  settle_ms=max(0, min(int(settle_ms), 2000)), prev_small=None, settles=0)
        return (f"canvas bật: cạnh dài tối đa {_S['max_side']}px, ttl_tok={_S['ttl']}, use_hwnd={_S['use_hwnd']}, settle_ms={_S['settle_ms']}. Ảnh nằm trong thư mục {_dir()} (view_image <thư mục>\\<tên file ghi ở dòng KEY/PATCH>). "
                "Gọi canvas_step để lấy keyframe đầu.")


def step_frame(frame, hint=None):
    """Một bước trên khung đã có (tool canvas_step dùng khung chụp màn hình; kiểm thử dùng khung giả). hint: khóa cảnh gợi ý (hwnd)."""
    with _S["lock"]:
        L = _load()
        t1 = time.time(); f = _prep(frame); _tm("prep", t1)
        if _S["cd"] is None or _S["size"] != f.shape:
            _S["cd"] = L["v7"].CanvasDelta(ttl_tok=_S["ttl"]); _S["size"] = f.shape
        cd = _S["cd"]; t0 = time.time()
        ops, cost = cd.step(f, hint=hint); ms = (time.time() - t0) * 1000; _tm("enc", t0)
        _S["n"] += 1; n = _S["n"]; _S["tot"] += cost
        _S["keys"] += sum(o[0] == "key" for o in ops); _S["recalls"] += sum(o[0] == "recall" for o in ops)
        t2 = time.time(); lines, recs = serialize(ops, n); _tm("ser", t2)
        stale = sorted(map(str, getattr(cd, "stale", [])))[:30]
        head = f"#{n} ~{cost:.0f}tok S{getattr(cd, 'cur', 0)}"
        if not lines: lines = ["(không đổi)"]
        if stale: lines.append("STALE (có thể đã cũ): " + ",".join(stale) + (" ..." if len(getattr(cd, "stale", [])) > 30 else ""))
        return "\n".join([head] + lines), recs, cd


def crop(x, y, w, h, zoom=1, scale=1.0, max_tok=0):
    """Cắt vùng (x,y,w,h) theo TỌA ĐỘ CANVAS (hệ ảnh KEY/PATCH) từ màn hình thật NGAY LÚC NÀY, ở độ phân giải gốc.
    Không đụng trạng thái canvas (không làm lệch delta). Trả (thông điệp, đường dẫn)."""
    _load(); fr = _grab(); RH, RW = fr.shape[:2]
    sz = _S["size"]
    if sz is not None: CH, CW = sz[0], sz[1]
    else:
        m = _S["max_side"]; k = min(1.0, m / max(RH, RW)); CH, CW = round(RH * k), round(RW * k)
    sx, sy = RW / CW, RH / CH
    x0 = max(0, int(x * sx)); y0 = max(0, int(y * sy)); x1 = min(RW, int((x + w) * sx)); y1 = min(RH, int((y + h) * sy))
    if x1 - x0 < 4 or y1 - y0 < 4:
        return "vùng ngoài màn hình hoặc quá nhỏ", None
    a = fr[y0:y1, x0:x1]; z = max(1, min(int(zoom), 4))
    sc = max(0.2, min(float(scale or 1.0), 1.0))
    if max_tok and max_tok > 0 and z == 1:
        sc = min(sc, max(0.2, (max_tok * 750.0 / (a.shape[0] * a.shape[1])) ** 0.5))
    if sc < 0.999 and z == 1:
        a = _lib["cv2"].resize(a, (max(4, round(a.shape[1] * sc)), max(4, round(a.shape[0] * sc))), interpolation=_lib["cv2"].INTER_AREA)
    if z > 1: a = _lib["cv2"].resize(a, (a.shape[1] * z, a.shape[0] * z), interpolation=_lib["cv2"].INTER_CUBIC)
    _S["ncrop"] = _S.get("ncrop", 0) + 1
    p = _save_png(a, f"c{_S['ncrop']}.png")
    return f"CROP c{_S['ncrop']}.png {a.shape[1]}x{a.shape[0]}px ~{a.shape[0] * a.shape[1] / 750:.0f}tok (canvas {x},{y},{w},{h}; zoom {z}; scale {sc:.2f})", p


def stop():
    with _S["lock"]:
        msg = f"canvas dừng: {_S['n']} bước, ~{_S['tot']:.0f} tok ước lượng, {_S['keys']} keyframe, {_S['recalls']} recall"
        _S.update(cd=None, size=None); return msg


def apply(ctx):
    ctx.instructions(lambda: INSTR)

    @ctx.tool
    def canvas_start(max_side: int = 1280, ttl_tok: int = 0, use_hwnd: bool = False, settle_ms: int = 400) -> str:
        """Bật canvas live (v7). max_side: cạnh dài tối đa px của ảnh gửi (thu nhỏ từ màn thật). ttl_tok>0: tuổi thọ tính theo token ngữ cảnh của cuộc trò chuyện; cảnh/keyframe cũ hơn mức này bị coi là có thể đã quên (làm mới keyframe, bỏ recall). 0 = tắt tuổi thọ. use_hwnd=True: dùng hwnd cửa sổ trên cùng để thử cảnh liên quan trước và dừng sớm khi đã đủ rẻ (nhanh hơn khi đổi cảnh; nhầm chỉ tốn token, không sai ảnh). settle_ms: nếu màn đang đổi (hiệu ứng, chuyển tab) thì chờ yên tối đa ngần này ms rồi mới chụp (0 = tắt; màn tĩnh không tốn thêm). Gọi lại sẽ đặt lại canvas."""
        return start(max_side, ttl_tok, use_hwnd, settle_ms)

    @ctx.tool
    @ro
    def canvas_step() -> str:
        """Chụp màn hình chính và trả các lệnh delta so với lần trước (KEY/RECALL/SCROLL/MOVE/DC/PATCH + ảnh atlas để view_image). Tự bật nếu chưa gọi canvas_start."""
        if _S["cd"] is None:
            start(_S["max_side"], _S["ttl"] or 0, _S["use_hwnd"], _S.get("settle_ms", 400))
        fr = _grab_settled()
        return step_frame(fr, _hwnd() if _S["use_hwnd"] else None)[0]

    @ctx.tool
    @ro
    def canvas_status() -> str:
        """Tổng số bước, token ước lượng đã gửi, số keyframe/recall và thời gian từng giai đoạn (chụp / thu nhỏ / mã hóa / ghi PNG, ms TB/lớn nhất) của phiên canvas hiện tại."""
        tm = "; ".join(f"{k} {v[0] / max(v[1], 1):.0f}/{v[2]:.0f}" for k, v in _S["tm"].items())
        at = getattr(_S["cd"], "attempts", None)
        return (f"bước {_S['n']}, ~{_S['tot']:.0f} tok ước lượng, keyframe {_S['keys']}, recall {_S['recalls']}, ttl_tok={_S['ttl']}, use_hwnd={_S['use_hwnd']}, "
                f"lần thử cảnh cũ {at}, chờ yên {_S.get('settles', 0)} lần (settle_ms={_S.get('settle_ms', 0)}), bật={_S['cd'] is not None}\nms TB/max: {tm or '-'}")

    @ctx.tool
    @ro
    def canvas_crop(x: int, y: int, w: int, h: int, zoom: int = 1, scale: float = 1.0, max_tok: int = 0) -> str:
        """Ảnh CHÍNH XÁC của vùng (x,y,w,h) (tọa độ canvas, như trong KEY/PATCH) từ màn hình thật lúc này, độ phân giải gốc, không qua nén. Dùng khi cần đọc chữ nhỏ hoặc kiểm vùng STALE; tốn token đúng bằng diện tích vùng. zoom 1-4 phóng to chữ nhỏ. Để GIẢM token: scale (0.2-1.0, thu nhỏ ảnh, 0.67 ~ ngang canvas, token giảm theo scale^2) hoặc max_tok (tự chọn scale để ảnh không vượt ngần này token; chỉ khi zoom=1). Chỉ cắt đúng vùng cần đọc. Không làm lệch canvas_step."""
        return crop(x, y, w, h, zoom, scale, max_tok)[0]

    @ctx.tool
    def canvas_stop() -> str:
        """Dừng canvas live và giải phóng bộ nhớ."""
        return stop()
