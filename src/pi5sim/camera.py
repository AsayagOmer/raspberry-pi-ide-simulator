"""Arducam IMX519 16 MP autofocus camera on CAM/DISP 0/1.

Frames come from the host webcam (OpenCV) when available, else a generated test pattern.
Focus is simulated: blur grows with the distance between the lens position and the
scene's in-focus position; autofocus sweeps the lens there in ~0.5 s.
"""
import base64
import json
import os
import tempfile
import threading
import time

import cv2
import numpy as np

SENSOR = (4656, 3496)
# (width, height, max fps) - the sensor modes rpicam-hello lists for the IMX519
MODES = [(1280, 720, 120.09), (1920, 1080, 60.05), (2328, 1748, 30.0), (3840, 2160, 18.0), (4656, 3496, 9.0)]
MANUAL, AUTO, CONTINUOUS = 0, 1, 2
SCENE_FOCUS = 2.0  # dioptres (scene at 0.5 m)
AF_SWEEP_S = 0.5
DT_PATH = "/base/axi/pcie@120000/rp1/i2c@88000/imx519@1a"


def mode_for(w, h):
    """Smallest sensor mode that covers the requested output size."""
    return next((m for m in MODES if m[0] >= w and m[1] >= h), MODES[-1])


def list_cameras_text():
    lines = ["Available cameras", "-----------------",
             f"0 : imx519 [{SENSOR[0]}x{SENSOR[1]} 10-bit RGGB] ({DT_PATH})"]
    for i, (w, h, fps) in enumerate(MODES):
        lead = "    Modes: 'SRGGB10_CSI2P' : " if i == 0 else " " * 29
        lines.append(f"{lead}{w}x{h} [{fps:.2f} fps]")
    return "\n".join(lines) + "\n"


class IMX519:
    def __init__(self, use_webcam=True):
        self.use_webcam = use_webcam and os.environ.get("PI5SIM_WEBCAM", "1") != "0"
        self.cap = None
        self.lock = threading.Lock()
        self.af_mode = CONTINUOUS
        self.lens = 0.0
        self.manual_lens = 1.0
        self.af_state = 0  # 0 idle, 1 scanning, 2 focused
        self._last = time.time()
        self.streaming = 0  # ref-count of active previews (CLI + scripts)
        self.source = "test pattern"

    # ---------- frame source ----------
    def _raw(self):
        if self.use_webcam:
            if self.cap is None:
                self.cap = cv2.VideoCapture(0, cv2.CAP_DSHOW) if os.name == "nt" else cv2.VideoCapture(0)
                if not self.cap.isOpened():
                    self.cap, self.use_webcam = None, False
            if self.cap is not None:
                ok, frame = self.cap.read()
                if ok:
                    self.source = "webcam"
                    return frame
        self.source = "test pattern"
        return self._pattern()

    @staticmethod
    def _pattern(w=1280, h=960):
        img = np.zeros((h, w, 3), np.uint8)
        bars = [(192, 192, 192), (0, 192, 192), (192, 192, 0), (0, 192, 0), (192, 0, 192), (0, 0, 192), (192, 0, 0)]
        for i, c in enumerate(bars):  # BGR colour bars
            img[: h * 2 // 3, i * w // 7:(i + 1) * w // 7] = c
        for x in range(0, w, 40):  # fine stripes show focus clearly
            img[h * 2 // 3:, x:x + 20] = 255
        t = time.time()
        cx = int(w / 2 + w / 3 * np.sin(t))
        cv2.circle(img, (cx, h // 3), 60, (255, 255, 255), -1)
        cv2.putText(img, "IMX519 TEST PATTERN", (30, 60), cv2.FONT_HERSHEY_SIMPLEX, 1.6, (0, 0, 0), 4)
        cv2.putText(img, time.strftime("%H:%M:%S"), (30, h - 30), cv2.FONT_HERSHEY_SIMPLEX, 1.4, (0, 0, 255), 3)
        return img

    def release(self):
        with self.lock:
            if self.cap is not None:
                self.cap.release()
                self.cap = None

    # ---------- focus ----------
    def _update_lens(self):
        now = time.time()
        dt, self._last = now - self._last, now
        if self.af_mode == MANUAL:
            self.lens, self.af_state = self.manual_lens, 0
        elif self.af_mode == CONTINUOUS:
            self.lens += (SCENE_FOCUS - self.lens) * min(1.0, dt / (AF_SWEEP_S / 2))
            self.af_state = 2 if abs(self.lens - SCENE_FOCUS) < 0.05 else 1

    def autofocus_cycle(self):
        """Sweep the lens to the in-focus position (blocks ~0.5 s like the real AF)."""
        self.af_state, start = 1, self.lens
        t0 = time.time()
        while (k := (time.time() - t0) / AF_SWEEP_S) < 1:
            self.lens = start + (SCENE_FOCUS - start) * k
            time.sleep(0.02)
        self.lens, self.af_state = SCENE_FOCUS, 2
        return True

    def set_controls(self, controls: dict):
        if "AfMode" in controls:
            self.af_mode = int(controls["AfMode"])
        if "LensPosition" in controls:
            self.manual_lens = float(controls["LensPosition"])
            self.af_mode = MANUAL
        if controls.get("AfTrigger") == 0:
            self.autofocus_cycle()

    def metadata(self):
        return {"LensPosition": round(self.lens, 3), "AfState": self.af_state, "AfMode": self.af_mode,
                "ExposureTime": 33333, "AnalogueGain": 1.0, "SensorTimestamp": time.monotonic_ns(),
                "FocusFoM": int(1000 / (1 + 4 * abs(self.lens - SCENE_FOCUS)))}

    # ---------- capture ----------
    def frame(self, w, h, channels=3):
        """BGR (or BGRX) frame at w x h with the current focus blur applied."""
        with self.lock:
            self._update_lens()
            raw = self._raw()
            sigma = abs(self.lens - SCENE_FOCUS) * 0.004 * raw.shape[1]
            if sigma > 0.3:
                raw = cv2.GaussianBlur(raw, (0, 0), sigma)
        img = cv2.resize(raw, (int(w), int(h)), interpolation=cv2.INTER_LINEAR)
        return cv2.cvtColor(img, cv2.COLOR_BGR2BGRA) if channels == 4 else img

    def capture_file(self, path, w=SENSOR[0], h=SENSOR[1]):
        os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
        ok, buf = cv2.imencode(os.path.splitext(path)[1] or ".jpg", self.frame(w, h))
        if ok:
            buf.tofile(path)  # imwrite cannot handle non-ASCII paths on Windows
        return bool(ok)

    def capture_array(self, w, h, channels=3):
        fd, path = tempfile.mkstemp(suffix=".npy")
        os.close(fd)
        np.save(path, self.frame(w, h, channels))
        return path

    def record(self, path, w, h, ms, cancel=None):
        fps = min(30.0, mode_for(w, h)[2])
        out = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), fps, (int(w), int(h)))
        n = 0
        t0 = time.time()
        while time.time() - t0 < ms / 1000 and not (cancel and cancel.is_set()):
            out.write(self.frame(w, h))
            n += 1
            time.sleep(max(0.0, t0 + n / fps - time.time()))
        out.release()
        return n

    def preview_jpeg(self):
        ok, buf = cv2.imencode(".jpg", self.frame(640, 480), [cv2.IMWRITE_JPEG_QUALITY, 70])
        return base64.b64encode(buf.tobytes()).decode() if ok else None


# ---------- user-script shims (written into .sim_env) ----------
LIBCAMERA_SHIM = '''
from enum import IntEnum

class controls:
    class AfModeEnum(IntEnum):
        Manual = 0
        Auto = 1
        Continuous = 2
    class AfTriggerEnum(IntEnum):
        Start = 0
        Cancel = 1
    class AfSpeedEnum(IntEnum):
        Normal = 0
        Fast = 1
    class AfRangeEnum(IntEnum):
        Normal = 0
        Macro = 1
        Full = 2

class Transform:
    def __init__(self, hflip=0, vflip=0):
        self.hflip, self.vflip = hflip, vflip
'''

PICAMERA2_SHIM = '''
"""Simulated picamera2 for the Arducam IMX519 (talks to the simulator through `hardware`)."""
import json, os, time
import numpy as np
from hardware import _send_cmd

_MODES = %(modes)r

class Picamera2:
    def __init__(self, camera_num=0):
        if not Picamera2.global_camera_info():
            raise IndexError("list index out of range")  # what picamera2 raises with no camera attached
        self.camera_num = camera_num
        self.camera_config = None
        self.started = False
        self.sensor_resolution = (4656, 3496)
        self.sensor_modes = [{"size": (w, h), "fps": f, "format": "SRGGB10_CSI2P", "bit_depth": 10} for w, h, f in _MODES]
        self.camera_properties = {"Model": "imx519", "PixelArraySize": self.sensor_resolution, "Location": 2}

    @staticmethod
    def global_camera_info():
        if _send_cmd("cam_info") != "imx519":
            return []
        return [{"Model": "imx519", "Location": 2, "Rotation": 0, "Id": %(dt)r, "Num": 0}]

    def _config(self, use, size, fmt, main, controls):
        main = dict(main or {})
        main.setdefault("size", size)
        main.setdefault("format", fmt)
        return {"use_case": use, "main": main, "controls": dict(controls or {})}

    def create_preview_configuration(self, main=None, controls=None, **kw):
        return self._config("preview", (640, 480), "XBGR8888", main, controls)

    def create_still_configuration(self, main=None, controls=None, **kw):
        return self._config("still", self.sensor_resolution, "BGR888", main, controls)

    def create_video_configuration(self, main=None, controls=None, **kw):
        return self._config("video", (1280, 720), "XBGR8888", main, controls)

    def configure(self, config=None):
        if isinstance(config, str):
            config = {"preview": self.create_preview_configuration, "still": self.create_still_configuration,
                      "video": self.create_video_configuration}[config]()
        self.camera_config = config or self.create_preview_configuration()
        if self.camera_config["controls"]:
            self.set_controls(self.camera_config["controls"])

    def start(self, config=None, show_preview=False):
        if config is not None or self.camera_config is None:
            self.configure(config)
        _send_cmd("cam_start")
        self.started = True

    def stop(self):
        if self.started:
            _send_cmd("cam_stop")
        self.started = False

    def close(self):
        self.stop()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def set_controls(self, controls):
        _send_cmd("cam_set_controls", json.dumps({k: (int(v) if hasattr(v, "value") else v) for k, v in controls.items()}))

    def autofocus_cycle(self, wait=True):
        return _send_cmd("cam_af_cycle") == "True"

    def _size(self):
        if self.camera_config is None:
            self.configure()
        return self.camera_config["main"]["size"]

    def capture_file(self, file_output, name="main", format=None, wait=None):
        w, h = self._size()
        return _send_cmd("cam_capture_file", os.path.abspath(file_output), w, h) == "True"

    def capture_array(self, name="main", wait=None):
        w, h = self._size()
        ch = 4 if self.camera_config["main"]["format"][0] in "XA" else 3
        path = _send_cmd("cam_capture_array", w, h, ch)
        arr = np.load(path)
        os.remove(path)
        return arr

    def capture_metadata(self, wait=None):
        return json.loads(_send_cmd("cam_metadata"))

    def start_and_capture_file(self, name="image.jpg", delay=1, show_preview=False, **kw):
        self.configure(self.create_still_configuration())
        self.start()
        time.sleep(delay)
        ok = self.capture_file(name)
        self.stop()
        return ok

    def start_and_record_video(self, output, encoder=None, duration=0, show_preview=False, **kw):
        w, h = self._size() if self.camera_config else (1920, 1080)
        return _send_cmd("cam_record", os.path.abspath(str(output)), w, h, int((duration or 5) * 1000)) == "True"
''' % {"modes": MODES, "dt": DT_PATH}


def attach(backend):
    """Wire the camera into the backend: HW_CMD handlers, shims, rpicam-* commands, preview stream."""
    cam = IMX519()
    backend.camera = cam
    wired = lambda: backend.links.get("imx519") in ("cam0", "cam1")

    def start(a, cwd):
        cam.streaming += 1
        return True

    def stop(a, cwd):
        cam.streaming = max(0, cam.streaming - 1)
        return True

    def need(fn):
        return lambda a, cwd: fn(a, cwd) if wired() else False

    backend.extra_files.update({"picamera2.py": PICAMERA2_SHIM, "libcamera.py": LIBCAMERA_SHIM})
    backend.extra_commands.update({
        "cam_info": lambda a, cwd: "imx519" if wired() else "",
        "cam_start": need(start),
        "cam_stop": stop,
        "cam_set_controls": need(lambda a, cwd: cam.set_controls(json.loads(a[0])) or True),
        "cam_af_cycle": need(lambda a, cwd: cam.autofocus_cycle()),
        "cam_metadata": need(lambda a, cwd: json.dumps(cam.metadata())),
        "cam_capture_file": need(lambda a, cwd: cam.capture_file(a[0], int(a[1]), int(a[2]))),
        "cam_capture_array": need(lambda a, cwd: cam.capture_array(int(a[0]), int(a[1]), int(a[2]))),
        "cam_record": need(lambda a, cwd: cam.record(a[0], int(a[1]), int(a[2]), int(a[3])) > 0),
    })

    def preview_loop():
        while True:
            if cam.streaming and wired():
                jpg = cam.preview_jpeg()
                if jpg:
                    backend.send(t="frame", jpg=jpg, source=cam.source, lens=round(cam.lens, 2), af=cam.af_state)
                time.sleep(0.2)
            else:
                if cam.cap is not None:
                    cam.release()  # turn the webcam light off when nothing previews
                time.sleep(0.25)
    threading.Thread(target=preview_loop, daemon=True).start()

    shell = backend.shell
    for name in ("rpicam-hello", "rpicam-still", "rpicam-jpeg", "rpicam-vid",
                 "libcamera-hello", "libcamera-still", "libcamera-jpeg", "libcamera-vid"):
        shell.commands[name] = (lambda n: lambda a: rpicam(shell, cam, wired, n.split("-")[1], a))(name)


def _opts(a):
    """Parse rpicam-style options: -o x, --width 1920, --immediate."""
    opts, i = {}, 0
    alias = {"-o": "output", "-t": "timeout", "-n": "nopreview"}
    while i < len(a):
        k = alias.get(a[i], a[i].lstrip("-"))
        if i + 1 < len(a) and not a[i + 1].startswith("-"):
            opts[k], i = a[i + 1], i + 2
        else:
            opts[k], i = True, i + 1
    return opts


def rpicam(shell, cam, wired, kind, a):
    o = _opts(a)
    if "list-cameras" in o:
        return shell.out(list_cameras_text() if wired() else "No cameras available!\n")
    if not wired():
        return shell.out("ERROR: *** no cameras available ***\n")
    defaults = {"hello": (640, 480), "vid": (640, 480)}.get(kind, SENSOR)
    w, h = int(o.get("width", defaults[0])), int(o.get("height", defaults[1]))
    ms = 0 if "immediate" in o else int(o.get("timeout", 5000))
    mode = mode_for(w, h)
    controls = {}
    if "autofocus-mode" in o:
        controls["AfMode"] = {"manual": MANUAL, "auto": AUTO, "continuous": CONTINUOUS}[o["autofocus-mode"]]
    if "lens-position" in o:
        controls["LensPosition"] = float(o["lens-position"])
    out = o.get("output")
    if kind in ("still", "jpeg", "vid") and not isinstance(out, str):
        return shell.out(f"ERROR: *** no output file specified (-o) ***\n")

    def job(cancel):
        cam.set_controls(controls)
        shell.out(f"Mode selection for {w}:{h}:12:P\n    SRGGB10_CSI2P,{mode[0]}x{mode[1]}/{mode[2]:.2f}\n")
        cam.streaming += 1
        try:
            if kind == "vid":
                n = cam.record(shell.resolve(out), w, h, ms or 5000, cancel)
                shell.out(f"Wrote {n} frames to {out}\n")
                return
            cancel.wait(ms / 1000)
            if cam.af_mode == AUTO:
                cam.autofocus_cycle()
            if kind in ("still", "jpeg") and not cancel.is_set():
                cam.capture_file(shell.resolve(out), w, h)
                shell.out(f"Still capture image received ({w}x{h}, lens {cam.lens:.2f})\n")
        finally:
            cam.streaming = max(0, cam.streaming - 1)
    return shell.run_async(job)
