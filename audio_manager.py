import ctypes
import os


SOUND_FILES = {
    "bgm": "bgm.mp3",
    "drop": "drop.mp3",
    "drop-perfect": "drop-perfect.mp3",
}


class SoundPlayer:
    def __init__(self, sound_dir=None):
        self.enabled = os.name == "nt"
        self.aliases = {}
        self.sound_dir = sound_dir or os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "assets",
            "sound",
        )
        self._mci = None

        if self.enabled:
            self._mci = ctypes.windll.winmm.mciSendStringW
            self._mci.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint, ctypes.c_void_p]
            self._mci.restype = ctypes.c_uint
            self.load()

    def send(self, command):
        if not self.enabled or self._mci is None:
            return False
        return self._mci(command, None, 0, None) == 0

    def load(self):
        for sound_name, filename in SOUND_FILES.items():
            path = os.path.join(self.sound_dir, filename)
            if not os.path.isfile(path):
                continue

            alias = f"skyscraper_{sound_name.replace('-', '_')}"
            media_type = "mpegvideo" if filename.lower().endswith(".mp3") else "waveaudio"
            self.send(f"close {alias}")
            if self.send(f'open "{path}" type {media_type} alias {alias}'):
                self.aliases[sound_name] = alias

    def play_bgm(self):
        alias = self.aliases.get("bgm")
        if alias is None:
            return

        self.send(f"stop {alias}")
        self.send(f"seek {alias} to start")
        self.send(f"play {alias} repeat")

    def play_effect(self, sound_name):
        alias = self.aliases.get(sound_name)
        if alias is None:
            return

        self.send(f"stop {alias}")
        self.send(f"seek {alias} to start")
        self.send(f"play {alias}")

    def stop_all(self):
        for alias in self.aliases.values():
            self.send(f"stop {alias}")
            self.send(f"close {alias}")
        self.aliases.clear()
