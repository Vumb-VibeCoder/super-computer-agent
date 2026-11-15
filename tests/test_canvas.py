import numpy as np

from _engine import require_engine

require_engine("super_computer_agent.canvas._compiled.canvas_v7")

from super_computer_agent.licensing import license_slot  # noqa: E402

with license_slot():
    from super_computer_agent.canvas._compiled import canvas_v7 as v7  # noqa: E402

H, W = 192, 256


def scene(seed):
    r = np.random.default_rng(seed)
    f = np.zeros((H, W, 3), np.uint8)
    f[:] = r.integers(30, 220, 3)
    for _ in range(12):
        y, x = r.integers(0, H - 30), r.integers(0, W - 40)
        f[y:y + r.integers(8, 30), x:x + r.integers(10, 40)] = r.integers(0, 255, 3)
    return f


def test_key_delta_and_recall_rebuild_the_screen():
    a, b = scene(1), scene(2)
    a2 = a.copy()
    a2[40:60, 50:90] = (250, 10, 10)
    cd, dec = v7.CanvasDelta(), v7.Decoder()
    keycost = H * W / v7.PX
    kinds = []
    for f in (a, a, a2, b, a2):
        ops, cost = cd.step(f)
        canvas = np.clip(dec.feed(ops), 0, 255)[:H, :W]
        # the canvas is an approximation by design (patches are down-scaled): mean error must stay tiny
        assert np.abs(canvas - f.astype(float)).mean() < 0.5
        kinds.append((ops[0][0] if ops else None, cost))
    assert kinds[0][0] == "key"
    assert kinds[1] == (None, 0.0)                    # identical frame: nothing is sent
    assert kinds[2][0] != "key" and kinds[2][1] < 0.2 * keycost   # small change: cheap delta
    assert kinds[3][0] == "key"                       # new scene: keyframe
    assert kinds[4][0] == "recall" and kinds[4][1] < 0.2 * keycost  # back to a known scene: recall, not a keyframe
