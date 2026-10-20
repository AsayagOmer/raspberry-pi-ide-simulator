import os
import time
import pygame

from core.event_bus import EventBus

try:
    import numpy as np
    import sounddevice as sd
    import soundfile as sf
    RECORDING_ENABLED = True
except ImportError:
    RECORDING_ENABLED = False

class HardwareAPI:
    def __init__(self, app, rpi): 
        # App reference kept only for reading state (button_states, components)
        # Writes/Updates are sent entirely via EventBus
        self.app = app
        self.rpi = rpi
        self.stop_requested = False
        self._latched_buttons = set()
        
    def _find_active_pirate_audio(self):
        for c in self.app.components:
            if c.__class__.__name__ == "PirateAudio" and c.connected_to is self.rpi: return c
        return None
        
    def _find_active_speaker(self):
        for c in self.app.components:
            if c.__class__.__name__ == "USBSpeaker" and c.connected_to is self.rpi: return c
        return None

    def _poll_buttons(self):
        for btn, pressed in self.app.button_states.items():
            if pressed:
                self._latched_buttons.add(btn)

    def _wait_stream(self, duration_sec):
        """Wait for sounddevice stream while polling buttons and stop requests every 30ms."""
        end_time = time.time() + duration_sec + 0.05
        while time.time() < end_time:
            self._poll_buttons()
            if self.stop_requested or 'X' in self._latched_buttons or 'Y' in self._latched_buttons:
                if RECORDING_ENABLED:
                    try:
                        sd.stop()
                    except Exception:
                        pass
                return False
            try:
                stream = sd.get_stream()
                if stream is not None and not stream.active:
                    break
            except Exception:
                pass
            time.sleep(0.03)
        return not self.stop_requested

    def clear_screen(self):
        pa = self._find_active_pirate_audio()
        if pa: 
            EventBus.publish("UPDATE_CANVAS_TEXT", item=pa.screen_text, text="", color="white")
        
    def display_text(self, text, color="white"):
        pa = self._find_active_pirate_audio()
        if pa: 
            EventBus.publish("UPDATE_CANVAS_TEXT", item=pa.screen_text, text=text, color=color)
        
    def is_pressed(self, btn):
        self._poll_buttons()
        if btn in self._latched_buttons:
            self._latched_buttons.discard(btn)
            return True
        return self.app.button_states.get(btn, False)
        
    def play_audio(self, filepath):
        """Play an audio file. No path‑restriction – useful for demos."""
        if self.stop_requested:
            return False
        spk = self._find_active_speaker()
        if not spk:
            EventBus.publish("LOG_CONSOLE", text="ERROR: Playback failed. No USB Speaker plugged into RPi!")
            return False
            
        target_path = os.path.abspath(filepath)
        if os.path.exists(target_path):
            try:
                EventBus.publish("LOG_CONSOLE", text=f"Playing audio: {os.path.basename(target_path)}")
                if RECORDING_ENABLED:
                    data, fs = sf.read(target_path)
                    duration = len(data) / float(fs) if fs > 0 else 0
                    sd.play(data, fs)
                    self._wait_stream(duration)
                    return True
                else:
                    pygame.mixer.music.load(target_path)
                    pygame.mixer.music.play()
                    while pygame.mixer.music.get_busy():
                        self._poll_buttons()
                        if self.stop_requested or 'X' in self._latched_buttons or 'Y' in self._latched_buttons:
                            pygame.mixer.music.stop()
                            break
                        time.sleep(0.03)
                    return True
            except Exception as e:
                EventBus.publish("LOG_CONSOLE", text=f"ERROR: Playback failed – {e}")
                return False
        else:
            EventBus.publish("LOG_CONSOLE", text=f"ERROR: Audio file '{filepath}' not found.")
            return False

    def record_audio(self, filepath, duration=4, fs=16000):
        """Record audio with Smart VAD early-stop (stops 0.65s after speech ends)."""
        if self.stop_requested:
            return False
        pa = self._find_active_pirate_audio()
        if not pa:
            EventBus.publish("LOG_CONSOLE", text="ERROR: Recording failed. Pirate Audio (Mic) not plugged into RPi!")
            return False
        if not RECORDING_ENABLED:
            EventBus.publish("LOG_CONSOLE", text="ERROR: Sounddevice library not installed.")
            return False

        # Use 16kHz (Whisper's native sample rate) for 64% smaller upload and zero server resampling
        target_fs = 16000 if fs > 16000 else int(fs)
        block_dur = 0.08  # 80ms blocks
        block_frames = int(target_fs * block_dur)
        max_blocks = max(1, int(duration / block_dur))
        silence_blocks_limit = 8  # ~0.64s of trailing silence after speaking

        EventBus.publish("LOG_CONSOLE", text=f"Listening via Pirate Audio Mic (auto-stops after speech, max {duration}s)...")

        chunks = []
        rms_history = []
        speech_started = False
        speech_blocks = 0
        silent_blocks_after_speech = 0
        first_speech_idx = 0
        last_speech_idx = 0

        try:
            with sd.InputStream(samplerate=target_fs, channels=1, dtype="float32", blocksize=block_frames) as stream:
                for idx in range(max_blocks):
                    self._poll_buttons()
                    if self.stop_requested or 'X' in self._latched_buttons or 'Y' in self._latched_buttons:
                        return False

                    chunk, _ = stream.read(block_frames)
                    chunks.append(chunk.copy())
                    rms = float(np.sqrt(np.mean(np.square(chunk))))
                    rms_history.append(rms)

                    # Dynamic threshold based on initial ambient floor
                    ambient_floor = min(rms_history[:3]) if len(rms_history) >= 2 else 0.005
                    speech_thresh = max(0.012, min(0.045, ambient_floor * 2.8))
                    silence_thresh = speech_thresh * 0.75

                    if rms >= speech_thresh:
                        speech_blocks += 1
                        silent_blocks_after_speech = 0
                        last_speech_idx = idx
                        if not speech_started and speech_blocks >= 2:
                            speech_started = True
                            first_speech_idx = max(0, idx - 3)
                    elif speech_started:
                        silent_blocks_after_speech += 1
                        # Stop early once user has finished speaking and paused for ~0.64s
                        if silent_blocks_after_speech >= silence_blocks_limit and idx >= 10:
                            elapsed = round((idx + 1) * block_dur, 2)
                            EventBus.publish("LOG_CONSOLE", text=f"Speech end detected at {elapsed}s (saved {round(duration - elapsed, 2)}s)")
                            break

            if not chunks:
                return False

            # Trim excessive leading/trailing dead air if speech was detected
            if speech_started:
                start_b = max(0, first_speech_idx - 2)
                end_b = min(len(chunks), last_speech_idx + 4)
                trimmed = chunks[start_b:end_b] if end_b > start_b else chunks
            else:
                trimmed = chunks

            audio_data = np.concatenate(trimmed, axis=0)
            sf.write(filepath, audio_data, target_fs, subtype="PCM_16")
            return True
        except Exception as e:
            EventBus.publish("LOG_CONSOLE", text=f"Recording error: {e}")
            return False
