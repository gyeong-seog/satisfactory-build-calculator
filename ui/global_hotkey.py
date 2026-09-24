"""Small Windows global-hotkey wrapper with no third-party dependency."""

from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes
from collections.abc import Callable

from PySide6.QtCore import QAbstractNativeEventFilter, QCoreApplication, Qt, QTimer
from PySide6.QtGui import QKeySequence


WM_HOTKEY = 0x0312
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000
HOTKEY_ID = 0x5342


class _WindowsHotkeyFilter(QAbstractNativeEventFilter):
    def __init__(self, callback: Callable[[], None]):
        super().__init__()
        self._callback = callback

    def nativeEventFilter(self, event_type, message):
        if bytes(event_type) in (b"windows_generic_MSG", b"windows_dispatcher_MSG"):
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == WM_HOTKEY and int(msg.wParam) == HOTKEY_ID:
                QTimer.singleShot(0, self._callback)
        return False


class GlobalHotkeyManager:
    """Register one system-wide shortcut and route it into the Qt event loop."""

    def __init__(self, callback: Callable[[], None]):
        self.sequence = QKeySequence()
        self.last_error = ""
        self._registered = False
        self._enabled = sys.platform == "win32"
        self._filter = _WindowsHotkeyFilter(callback) if self._enabled else None
        if self._filter is not None:
            QCoreApplication.instance().installNativeEventFilter(self._filter)

    def register(self, sequence: QKeySequence) -> bool:
        self.last_error = ""
        native = self._to_native(sequence)
        if native is None:
            self.last_error = "invalid"
            return False

        old_sequence = QKeySequence(self.sequence)
        self.unregister()
        modifiers, virtual_key = native
        if not self._enabled:
            self.sequence = QKeySequence(sequence)
            return True

        if not ctypes.windll.user32.RegisterHotKey(
            None, HOTKEY_ID, modifiers | MOD_NOREPEAT, virtual_key
        ):
            if not old_sequence.isEmpty():
                self.register(old_sequence)
            self.last_error = "in_use"
            return False

        self._registered = True
        self.sequence = QKeySequence(sequence)
        return True

    def unregister(self) -> None:
        if self._registered and self._enabled:
            ctypes.windll.user32.UnregisterHotKey(None, HOTKEY_ID)
        self._registered = False

    def dispose(self) -> None:
        self.unregister()
        if self._filter is not None and QCoreApplication.instance() is not None:
            QCoreApplication.instance().removeNativeEventFilter(self._filter)

    @staticmethod
    def _to_native(sequence: QKeySequence) -> tuple[int, int] | None:
        if sequence.isEmpty() or sequence.count() != 1:
            return None
        combination = sequence[0]
        modifiers = combination.keyboardModifiers()
        native_modifiers = 0
        if modifiers & Qt.KeyboardModifier.ControlModifier:
            native_modifiers |= MOD_CONTROL
        if modifiers & Qt.KeyboardModifier.AltModifier:
            native_modifiers |= MOD_ALT
        if modifiers & Qt.KeyboardModifier.ShiftModifier:
            native_modifiers |= MOD_SHIFT
        if modifiers & Qt.KeyboardModifier.MetaModifier:
            native_modifiers |= MOD_WIN
        if native_modifiers == 0:
            return None

        key = combination.key()
        if Qt.Key.Key_A <= key <= Qt.Key.Key_Z or Qt.Key.Key_0 <= key <= Qt.Key.Key_9:
            virtual_key = int(key)
        elif Qt.Key.Key_F1 <= key <= Qt.Key.Key_F24:
            virtual_key = 0x70 + int(key - Qt.Key.Key_F1)
        else:
            virtual_key = {
                Qt.Key.Key_Space: 0x20,
                Qt.Key.Key_Tab: 0x09,
                Qt.Key.Key_Escape: 0x1B,
                Qt.Key.Key_Insert: 0x2D,
                Qt.Key.Key_Delete: 0x2E,
                Qt.Key.Key_Home: 0x24,
                Qt.Key.Key_End: 0x23,
                Qt.Key.Key_PageUp: 0x21,
                Qt.Key.Key_PageDown: 0x22,
            }.get(key)
        if virtual_key is None:
            return None
        return native_modifiers, virtual_key
