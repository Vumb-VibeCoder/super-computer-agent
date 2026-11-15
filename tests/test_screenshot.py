import os
import time

from PIL import Image

from super_computer_agent import screenshot


def test_save_writes_png_and_prunes(monkeypatch):
    monkeypatch.setattr(screenshot, "grab", lambda: Image.new("RGB", (32, 16), "red"))
    d = screenshot.out_dir()
    os.makedirs(d)
    for i in range(5):
        p = os.path.join(d, f"screenshot_{i}.png")
        Image.new("RGB", (4, 4)).save(p)
        os.utime(p, (time.time() - 100 + i, time.time() - 100 + i))
    path = screenshot.save(keep=3)
    assert os.path.isfile(path) and Image.open(path).size == (32, 16)
    left = sorted(os.listdir(d))
    assert len(left) == 3 and os.path.basename(path) in left


def test_save_to_explicit_path_does_not_prune(monkeypatch, tmp_path):
    monkeypatch.setattr(screenshot, "grab", lambda: Image.new("RGB", (8, 8)))
    target = tmp_path / "sub" / "shot.png"
    assert screenshot.save(str(target)) == str(target)
    assert target.is_file()
