import sys
import os
import ctypes
import ctypes.wintypes as wintypes

if getattr(sys, 'frozen', False):
    sys.path.insert(0, os.path.dirname(sys.executable))
else:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import QApplication

from storage import init_db, is_first_run, get_last_unfinished_fragment
from monitor import WindowMonitor
from tray import TrayApp, _create_tray_icon


_INSTANCE_MUTEX_NAME = "Local\\DABIAN-afk.UsageTracker"


def _acquire_single_instance():
    """返回互斥量句柄；已有实例运行时返回 None。"""
    kernel32 = ctypes.windll.kernel32
    kernel32.CreateMutexW.restype = wintypes.HANDLE
    handle = kernel32.CreateMutexW(None, False, _INSTANCE_MUTEX_NAME)
    if not handle:
        return None
    if kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        kernel32.CloseHandle(handle)
        return None
    return handle


def main():
    instance_mutex = _acquire_single_instance()
    if instance_mutex is None:
        return

    init_db()
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setWindowIcon(_create_tray_icon())

    # 首次运行引导
    if is_first_run():
        from dashboard import _FirstRunWizard
        wizard = _FirstRunWizard()
        wizard.exec()

    # 崩溃恢复：检测上一次异常退出
    last = get_last_unfinished_fragment()
    if last:
        # 监控启动后会自动从当前时间重新开始计时
        # 上一次未结束的片段已写入 end_time，无需额外处理
        pass

    monitor = WindowMonitor(poll_interval=1.0)
    monitor.start()

    tray = TrayApp(monitor)
    tray.show()

    exit_code = app.exec()
    ctypes.windll.kernel32.CloseHandle(instance_mutex)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
