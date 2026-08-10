import time
import threading
import ctypes
import ctypes.wintypes as wintypes
from datetime import datetime

import win32gui
import win32process
import psutil

from storage import (
    record_fragments_batch, get_ignored_apps, get_app_rules, get_setting,
)


# ── Idle 检测 ─────────────────────────────────────────────────

class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_uint),
        ("dwTime", ctypes.c_uint),
    ]


def _get_idle_seconds():
    lii = LASTINPUTINFO()
    lii.cbSize = ctypes.sizeof(lii)
    if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii)):
        return 0.0
    ctypes.windll.kernel32.GetTickCount.restype = wintypes.DWORD
    tick = ctypes.windll.kernel32.GetTickCount()
    return _idle_seconds_from_ticks(tick, lii.dwTime)


def _idle_seconds_from_ticks(current_tick, last_input_tick):
    """计算空闲秒数，并正确处理 DWORD 回绕。"""
    elapsed_ms = (int(current_tick) - int(last_input_tick)) & 0xFFFFFFFF
    return elapsed_ms / 1000.0


def _active_time_cutoff(now, idle_seconds, idle_threshold):
    """返回当前应用最多可以计时到的墙钟时间。"""
    if idle_seconds <= idle_threshold:
        return now
    return now - idle_seconds + idle_threshold


# ── 忽略的系统进程 ────────────────────────────────────────────

_IGNORED = {
    "searchui.exe", "shellexperiencehost.exe", "openwith.exe",
    "textinputhost.exe", "lockapp.exe", "applicationframehost.exe",
    "systemsettings.exe", "searchapp.exe", "startmenuexperiencehost.exe",
    "runtimebroker.exe", "sihost.exe", "fontdrvhost.exe",
    "dwm.exe", "csrss.exe",
}


# ── 监控主类 ──────────────────────────────────────────────────

class WindowMonitor:
    def __init__(self, poll_interval=1.0):
        self.poll_interval = poll_interval
        self._running = False
        self._paused = False
        self._thread = None

        self._last_hwnd = None
        self._last_app = None
        self._last_title = None
        self._last_exe = None
        self._last_start = None

        self._was_idle = False

        # 内存缓冲区，定期 flush 到 DB
        self._buffer = []
        self._buffer_lock = threading.Lock()
        self._flush_interval = 10.0  # 每 10 秒 flush 一次
        self._last_flush = time.time()

    @property
    def is_paused(self):
        return self._paused

    @property
    def idle_threshold(self):
        try:
            return int(get_setting("idle_threshold", "300"))
        except (ValueError, TypeError):
            return 300

    def start(self):
        self._running = True
        self._last_start = time.time()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        now = time.time()
        if self._was_idle:
            self._flush_idle(self._idle_start, now)
            self._was_idle = False
        else:
            idle_secs = _get_idle_seconds()
            self._flush_current(
                _active_time_cutoff(now, idle_secs, self.idle_threshold)
            )
        self._flush_to_db()

    def pause(self):
        if not self._paused:
            now = time.time()
            if self._was_idle:
                self._flush_idle(self._idle_start, now)
                self._was_idle = False
            else:
                idle_secs = _get_idle_seconds()
                self._flush_current(
                    _active_time_cutoff(now, idle_secs, self.idle_threshold)
                )
            self._flush_to_db()
            self._paused = True

    def resume(self):
        if self._paused:
            self._paused = False
            self._last_start = time.time()

    # ── 前台窗口检测（GetForegroundWindow） ─────────────────────

    def _get_active_window_info(self):
        """用 GetForegroundWindow 获取前台窗口信息。"""
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd or not win32gui.IsWindowVisible(hwnd):
            return None, None, None, None

        title = win32gui.GetWindowText(hwnd)
        if not title or len(title) < 2:
            return None, None, None, None

        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            proc = psutil.Process(pid)
            name = proc.name().lower()
            exe = proc.exe() or ""
        except (psutil.NoSuchProcess, psutil.AccessDenied, Exception):
            return None, None, None, None

        if name in _IGNORED:
            return None, None, None, None

        # 应用合并规则
        rules = get_app_rules()
        name = rules.get(name, name)

        return hwnd, name, title, exe

    # ── 缓冲区操作 ─────────────────────────────────────────────

    def _add_to_buffer(self, fragment):
        with self._buffer_lock:
            self._buffer.append(fragment)

    def _flush_to_db(self):
        """将缓冲区中的片段写入数据库。"""
        with self._buffer_lock:
            if not self._buffer:
                return
            batch = self._buffer[:]
            self._buffer.clear()
        record_fragments_batch(batch)

    # ── Flush ─────────────────────────────────────────────────

    def _flush_current(self, end_time=None):
        """将当前正在计时的片段 flush 到缓冲区。"""
        if self._last_app and self._last_start:
            end_time = time.time() if end_time is None else end_time
            duration = end_time - self._last_start
            if duration >= 0.5:
                start_iso = datetime.fromtimestamp(self._last_start).isoformat()
                end_iso = datetime.fromtimestamp(end_time).isoformat()
                ignored = get_ignored_apps()
                if self._last_app.lower() not in ignored:
                    self._add_to_buffer({
                        "app_name": self._last_app,
                        "window_title": self._last_title,
                        "exe_path": self._last_exe,
                        "start_time": start_iso,
                        "end_time": end_iso,
                        "duration": duration,
                        "is_idle": False,
                    })

    def _flush_idle(self, idle_start, idle_end):
        duration = idle_end - idle_start
        if duration >= 0.5:
            start_iso = datetime.fromtimestamp(idle_start).isoformat()
            end_iso = datetime.fromtimestamp(idle_end).isoformat()
            self._add_to_buffer({
                "app_name": self._last_app or "idle",
                "window_title": "idle",
                "exe_path": "",
                "start_time": start_iso,
                "end_time": end_iso,
                "duration": duration,
                "is_idle": True,
            })

    # ── 主循环 ────────────────────────────────────────────────

    def _loop(self):
        while self._running:
            if self._paused:
                time.sleep(self.poll_interval)
                continue

            idle_secs = _get_idle_seconds()
            idle_threshold = self.idle_threshold
            is_idle = idle_secs > idle_threshold
            now = time.time()

            if is_idle and not self._was_idle:
                # 刚进入 idle
                active_end = _active_time_cutoff(
                    now, idle_secs, idle_threshold
                )
                self._flush_current(active_end)
                self._idle_start = active_end
                self._was_idle = True

            elif not is_idle and self._was_idle:
                # 从 idle 恢复
                self._flush_idle(self._idle_start, now)
                self._was_idle = False
                self._last_start = now
                self._last_hwnd = None  # 强制重新检测窗口

            elif not is_idle:
                # 正常计时
                hwnd, app_name, title, exe = self._get_active_window_info()
                if hwnd and hwnd != self._last_hwnd:
                    self._flush_current()
                    self._last_hwnd = hwnd
                    self._last_app = app_name
                    self._last_title = title
                    self._last_exe = exe
                    self._last_start = time.time()

            # 定期 flush 缓冲区到 DB（空闲期间不 flush）
            if not self._was_idle and now - self._last_flush >= self._flush_interval:
                self._flush_current()
                self._flush_to_db()
                self._last_start = time.time()
                self._last_flush = now

            time.sleep(self.poll_interval)
