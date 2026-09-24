import os
import time
import pygame
from components.raspberry_pi import RaspberryPi
from components.pirate_audio import PirateAudio
from components.usb_speaker import USBSpeaker
from event_bus import EventBus

try:
    import sounddevice as sd
    import soundfile as sf
    RECORDING_ENABLED = True
except ImportError:
    RECORDING_ENABLED = False

class HardwareAPI:
    def __init__(self, app): 
        # App reference kept only for reading state (button_states, components)
        # Writes/Updates are sent entirely via EventBus
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
        if pa: 
            EventBus.publish("UPDATE_CANVAS_TEXT", item=pa.screen_text, text="", color="white")
        
    def display_text(self, text, color="white"):
        pa = self._find_active_pirate_audio()
        if pa: 
            EventBus.publish("UPDATE_CANVAS_TEXT", item=pa.screen_text, text=text, color=color)
        
    def is_pressed(self, btn):
        return self.app.button_states.get(btn, False)
        
    def play_audio(self, filepath):
        """Play an audio file. No path‑restriction – useful for demos."""
        spk = self._find_active_speaker()
        if not spk:
            EventBus.publish("LOG_CONSOLE", text="ERROR: Playback failed. No USB Speaker plugged into RPi!")
            return False
            
        target_path = os.path.abspath(filepath)
        if os.path.exists(target_path):
            try:
                pygame.mixer.music.load(target_path)
                pygame.mixer.music.play()
                EventBus.publish("LOG_CONSOLE", text=f"Playing audio: {target_path}")
                while pygame.mixer.music.get_busy():
                    time.sleep(0.1)
                return True
            except Exception as e:
                EventBus.publish("LOG_CONSOLE", text=f"ERROR: Playback failed – {e}")
                return False
        else:
            EventBus.publish("LOG_CONSOLE", text=f"ERROR: Audio file '{filepath}' not found.")
            return False

    def record_audio(self, filepath, duration=3, fs=44100):
        pa = self._find_active_pirate_audio()
        if not pa:
            EventBus.publish("LOG_CONSOLE", text="ERROR: Recording failed. Pirate Audio (Mic) not plugged into RPi!")
            return False
        if not RECORDING_ENABLED:
            EventBus.publish("LOG_CONSOLE", text="ERROR: Sounddevice library not installed.")
            return False
        
        EventBus.publish("UPDATE_CANVAS_TEXT", item=pa.screen_text, text="RECORDING...", color="red")
        EventBus.publish("LOG_CONSOLE", text=f"Recording from Pirate Audio Mic for {duration}s...")
        
        try:
            recording = sd.rec(int(duration * fs), samplerate=fs, channels=1)
            sd.wait()
            sf.write(filepath, recording, fs)
            EventBus.publish("UPDATE_CANVAS_TEXT", item=pa.screen_text, text="Done", color="white")
            return True
        except Exception as e:
            EventBus.publish("LOG_CONSOLE", text=f"Recording error: {e}")
            return False
