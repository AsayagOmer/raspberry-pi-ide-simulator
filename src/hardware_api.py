import os
import time
import pygame
from components.raspberry_pi import RaspberryPi
from components.pirate_audio import PirateAudio
from components.usb_speaker import USBSpeaker

try:
    import sounddevice as sd
    import soundfile as sf
    RECORDING_ENABLED = True
except ImportError:
    RECORDING_ENABLED = False

class HardwareAPI:
    def __init__(self, app): 
        self.app = app
        
    def _find_active_pirate_audio(self):
        for c in self.app.components:
            if isinstance(c, PirateAudio) and isinstance(c.connected_to, RaspberryPi): return c
        return None
        
    def _find_active_speaker(self):
        for c in self.app.components:
            if isinstance(c, USBSpeaker) and isinstance(c.connected_to, RaspberryPi): return c
        return None

    def clear_screen(self):
        pa = self._find_active_pirate_audio()
        if pa: self.app.after(0, lambda: self.app.canvas.itemconfig(pa.screen_text, text=""))
        
    def display_text(self, text, color="white"):
        pa = self._find_active_pirate_audio()
        if pa: self.app.after(0, lambda: self.app.canvas.itemconfig(pa.screen_text, text=text, fill=color))
        
    def is_pressed(self, btn):
        return self.app.button_states.get(btn, False)
        
    def play_audio(self, filepath):
        spk = self._find_active_speaker()
        if not spk:
            self.app.after(0, lambda: self.app.log_console("ERROR: Playback failed. No USB Speaker connected to RPi!"))
            return False
        if os.path.exists(filepath):
            pygame.mixer.music.load(filepath)
            pygame.mixer.music.play()
            self.app.after(0, lambda: self.app.canvas.itemconfig(spk.status_text, text="Playing", fill="#4CAF50"))
            self.app.after(0, lambda p=filepath: self.app.log_console(f"Playing audio: {p}"))
            while pygame.mixer.music.get_busy(): time.sleep(0.1)
            self.app.after(0, lambda: self.app.canvas.itemconfig(spk.status_text, text="Connected", fill="#888"))
            return True
        else:
            self.app.after(0, lambda p=filepath: self.app.log_console(f"ERROR: Audio file '{p}' not found."))
            return False

    def record_audio(self, filepath, duration=3, fs=44100):
        pa = self._find_active_pirate_audio()
        if not pa:
            self.app.after(0, lambda: self.app.log_console("ERROR: Recording failed. Pirate Audio (Mic) not connected to RPi!"))
            return False
        if not RECORDING_ENABLED:
            self.app.after(0, lambda: self.app.log_console("ERROR: Sounddevice library not installed."))
            return False
        
        self.app.after(0, lambda: self.app.canvas.itemconfig(pa.screen_text, text="RECORDING...", fill="red"))
        self.app.after(0, lambda: self.app.log_console(f"Recording from Pirate Audio Mic for {duration}s..."))
        
        try:
            recording = sd.rec(int(duration * fs), samplerate=fs, channels=1)
            sd.wait()
            sf.write(filepath, recording, fs)
            self.app.after(0, lambda: self.app.canvas.itemconfig(pa.screen_text, text="Done", fill="white"))
            return True
        except Exception as e:
            self.app.after(0, lambda err=e: self.app.log_console(f"Recording error: {err}"))
            return False
