"""EcoCare Voice Assistant Client (Low-Latency Continuous Loop).

Optimizations for Fast Query & Answer Round-Trip:
1. Smart 16kHz VAD Recording: Automatically stops 0.65s after you finish speaking (saves 1.5s-2.5s)
2. Persistent HTTP Keep-Alive Session: Reuses Tailscale TCP socket across turns
3. Header-First & skip_tts Fast Path: Starts neural TTS immediately from HTTP headers
4. Parallel Sentence-Pipelined Neural TTS (IPv4-optimized): Synthesizes & plays the first
   sentence immediately (~1.1s) while remaining sentences synthesize concurrently in the background!
"""

import os
import re
import sys
import time
import json
import socket
import asyncio
import logging
import threading
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

try:
    import requests
except ImportError:
    print("Error: 'requests' is required. Install via: pip install requests")
    sys.exit(1)

try:
    import edge_tts
    import soundfile as sf
    EDGE_TTS_AVAILABLE = True
except ImportError:
    EDGE_TTS_AVAILABLE = False

# Prefer IPv4 to avoid Windows IPv6 Happy-Eyeballs timeout (~0.9s saved on edge-tts WebSocket)
_orig_getaddrinfo = socket.getaddrinfo
_dns_cache = {}


def _fast_ipv4_getaddrinfo(host, port, family=0, *args, **kwargs):
    key = (host, port)
    if key in _dns_cache:
        return _dns_cache[key]
    try:
        res = _orig_getaddrinfo(host, port, socket.AF_INET, *args, **kwargs)
        _dns_cache[key] = res
        return res
    except Exception:
        return _orig_getaddrinfo(host, port, family, *args, **kwargs)


socket.getaddrinfo = _fast_ipv4_getaddrinfo

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("EcoCareClient")

# Load local .env if present (keeps personal Tailscale IP out of Git)
for _env_candidate in (".env", os.path.join("..", ".env")):
    if os.path.exists(_env_candidate):
        try:
            with open(_env_candidate, "r", encoding="utf-8") as _ef:
                for _line in _ef:
                    _line = _line.strip()
                    if _line and not _line.startswith("#") and "=" in _line:
                        _k, _v = _line.split("=", 1)
                        os.environ.setdefault(_k.strip(), _v.strip())
        except Exception:
            pass

# Configuration
DEFAULT_SERVER_URL = os.environ.get("ECOCARE_SERVER_URL", "http://127.0.0.1:8000")
INPUT_FILE = os.path.abspath("input.wav")
RESPONSE_FILE = os.path.abspath("response.wav")
RECORDING_DURATION = 4  # max seconds per turn (Smart VAD stops early after speech)
RECORDING_FS = 16000    # 16kHz native Whisper sample rate (64% smaller upload)
HEBREW_VOICE = os.environ.get("ECOCARE_VOICE", "he-IL-AvriNeural")
VOICE_RATE = os.environ.get("ECOCARE_VOICE_RATE", "+8%")

STOP_PHRASES = (
    "להתראות", "עצור", "תפסיק", "סיום", "ביי", "תודה ביי",
    "stop", "exit", "quit", "goodbye", "bye",
)


def is_stop_phrase(text: str) -> bool:
    """Return True if the transcribed user speech contains an exit/stop command."""
    if not text or text == "(unknown)":
        return False
    normalized = text.strip().lower()
    return any(phrase in normalized for phrase in STOP_PHRASES)


def chunk_sentences(text: str):
    """Split response into balanced sentence chunks so chunk 0 (~20-55 chars) plays while others synthesize in parallel."""
    cleaned = text.strip()
    if not cleaned:
        return []
    raw_sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", cleaned) if s.strip()]
    if len(raw_sentences) <= 1:
        return [cleaned]

    chunks = []
    current = ""
    for s in raw_sentences:
        if not current:
            current = s
        elif len(current) < 22:
            # Merge very short greeting ("שלום יעקב!") with the following sentence so chunk 0 is ~2.5s of audio
            current = f"{current} {s}"
        else:
            chunks.append(current)
            current = s
    if current:
        chunks.append(current)
    return chunks


def synthesize_clear_hebrew(text: str, output_wav_path: str, voice: str = HEBREW_VOICE) -> bool:
    """Synthesize natural, clear Hebrew speech using Microsoft Neural TTS (edge-tts)."""
    if not EDGE_TTS_AVAILABLE or not text or text == "(no text)":
        return False
    try:
        temp_mp3 = output_wav_path + ".mp3"
        communicate = edge_tts.Communicate(text, voice, rate=VOICE_RATE)
        asyncio.run(communicate.save(temp_mp3))
        data, samplerate = sf.read(temp_mp3)
        sf.write(output_wav_path, data, samplerate)
        try:
            os.remove(temp_mp3)
        except OSError:
            pass
        return True
    except Exception as e:
        logger.warning(f"Neural TTS fallback to server audio ({e})")
        return False


class AudioInterface:
    """Abstracts audio recording, playback, buttons, and display between Simulator and Physical Pi."""

    def __init__(self, hardware_api=None):
        self.hw = hardware_api

    def display(self, text: str, color: str = "white"):
        if self.hw and hasattr(self.hw, "display_text"):
            self.hw.display_text(text, color=color)
        else:
            logger.info(f"[DISPLAY] {text}")

    def clear_display(self):
        if self.hw and hasattr(self.hw, "clear_screen"):
            self.hw.clear_screen()

    def should_stop(self) -> bool:
        """Check if user pressed button X or Y on Pirate Audio to end the loop."""
        if self.hw and hasattr(self.hw, "is_pressed"):
            return bool(self.hw.is_pressed("X") or self.hw.is_pressed("Y"))
        return False

    def record(self, filepath: str, duration: int = RECORDING_DURATION) -> bool:
        if self.hw and hasattr(self.hw, "record_audio"):
            return self.hw.record_audio(filepath, duration=duration, fs=RECORDING_FS)

        # Standalone Smart VAD recording at 16kHz
        try:
            import numpy as np
            import sounddevice as sd
            import soundfile as sf
            block_dur = 0.08
            block_frames = int(RECORDING_FS * block_dur)
            max_blocks = max(1, int(duration / block_dur))
            chunks, rms_hist = [], []
            speech_started, speech_blocks, silent_blocks = False, 0, 0
            first_idx, last_idx = 0, 0

            logger.info(f"Listening (Smart VAD @ {RECORDING_FS}Hz, max {duration}s)...")
            with sd.InputStream(samplerate=RECORDING_FS, channels=1, dtype="float32", blocksize=block_frames) as stream:
                for idx in range(max_blocks):
                    chunk, _ = stream.read(block_frames)
                    chunks.append(chunk.copy())
                    rms = float(np.sqrt(np.mean(np.square(chunk))))
                    rms_hist.append(rms)
                    floor = min(rms_hist[:3]) if len(rms_hist) >= 2 else 0.005
                    thresh = max(0.012, min(0.045, floor * 2.8))
                    if rms >= thresh:
                        speech_blocks += 1
                        silent_blocks = 0
                        last_idx = idx
                        if not speech_started and speech_blocks >= 2:
                            speech_started = True
                            first_idx = max(0, idx - 3)
                    elif speech_started:
                        silent_blocks += 1
                        if silent_blocks >= 8 and idx >= 10:
                            break

            trimmed = chunks[max(0, first_idx - 2):min(len(chunks), last_idx + 4)] if speech_started else chunks
            sf.write(filepath, np.concatenate(trimmed, axis=0), RECORDING_FS, subtype="PCM_16")
            return True
        except Exception as e:
            logger.error(f"Recording error: {e}")
            return False

    def play(self, filepath: str) -> bool:
        if self.hw and hasattr(self.hw, "play_audio"):
            return self.hw.play_audio(filepath)

        try:
            import sounddevice as sd
            import soundfile as sf
            data, fs = sf.read(filepath)
            sd.play(data, fs)
            sd.wait()
            return True
        except Exception:
            try:
                import pygame
                if not pygame.mixer.get_init():
                    pygame.mixer.init()
                pygame.mixer.music.load(filepath)
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy():
                    time.sleep(0.05)
                return True
            except Exception as e:
                logger.error(f"Playback error: {e}")
                return False


class EcoCareClient:
    """Low-latency client for communicating with the EcoCare VM Server."""

    def __init__(self, server_url: str = DEFAULT_SERVER_URL, audio_interface: AudioInterface = None):
        self.server_url = server_url.rstrip("/")
        self.audio = audio_interface or AudioInterface()
        self.session = requests.Session()  # Persistent HTTP Keep-Alive connection
        self.last_user_text = ""
        self.last_response_text = ""

    def check_server(self) -> bool:
        """Verify the VM server is reachable and warm up the persistent TCP connection."""
        try:
            logger.info(f"Checking server connection at {self.server_url}...")
            resp = self.session.get(f"{self.server_url}/health", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                logger.info(f"Server reachable. Status: {data.get('status')}, Models Loaded: {data.get('models_loaded')}")
                return True
            return False
        except requests.RequestException as e:
            logger.error(f"Cannot connect to VM server: {e}")
            return False

    def reset_conversation(self):
        try:
            self.session.post(f"{self.server_url}/reset", timeout=5)
        except Exception:
            pass

    def process_turn_fast(self, input_path: str, output_path: str) -> bool:
        """Upload recorded audio, synthesize all sentence chunks in parallel, and play chunk 0 immediately."""
        try:
            t0 = time.time()
            with open(input_path, "rb") as f:
                files = {"audio": (os.path.basename(input_path), f, "audio/wav")}
                resp = self.session.post(
                    f"{self.server_url}/audio",
                    params={"skip_tts": "true"} if EDGE_TTS_AVAILABLE else None,
                    files=files,
                    timeout=30,
                    stream=True
                )

            if resp.status_code != 200:
                logger.error(f"Server error {resp.status_code}: {resp.text}")
                resp.close()
                return False

            self.last_user_text = urllib.parse.unquote(resp.headers.get("X-User-Text", "")) or "(unknown)"
            self.last_response_text = urllib.parse.unquote(resp.headers.get("X-Response-Text", "")) or "(no text)"
            try:
                timings = json.loads(resp.headers.get("X-Timings", "{}"))
            except Exception:
                timings = {}

            net_plus_server = round(time.time() - t0, 2)
            logger.info(f"STT: '{self.last_user_text}'")
            logger.info(f"LLM: '{self.last_response_text}'")
            logger.info(f"Server Timings: {timings} (Round-trip: {net_plus_server}s)")

            if EDGE_TTS_AVAILABLE and self.last_response_text and self.last_response_text != "(no text)":
                # Close server stream in background while immediately launching parallel sentence TTS
                threading.Thread(target=lambda r=resp: r.close(), daemon=True).start()

                chunks = chunk_sentences(self.last_response_text)
                chunk_paths = [
                    output_path if i == 0 else os.path.abspath(f"response_part_{i}.wav")
                    for i in range(len(chunks))
                ]

                tts_t0 = time.time()
                with ThreadPoolExecutor(max_workers=min(4, len(chunks))) as pool:
                    futures = [
                        pool.submit(synthesize_clear_hebrew, chunks[i], chunk_paths[i])
                        for i in range(len(chunks))
                    ]
                    if futures[0].result():
                        logger.info(f"First sentence ready in {round(time.time() - tts_t0, 2)}s — playing now!")
                        self.audio.display("Speaking...", color="green")
                        self.audio.play(chunk_paths[0])

                        for i in range(1, len(futures)):
                            if self.audio.should_stop():
                                break
                            if futures[i].result() and not self.audio.should_stop():
                                self.audio.play(chunk_paths[i])
                        return True

            # Fallback: save and play server WAV stream if edge-tts is unavailable
            with open(output_path, "wb") as out_f:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        out_f.write(chunk)
            self.audio.display("Speaking...", color="green")
            self.audio.play(output_path)
            return True

        except Exception as e:
            logger.error(f"Error during audio pipeline request: {e}")
            return False

    def run_turn(self, turn_num: int = 1) -> str:
        """Execute one fast voice turn. Returns 'continue', 'stop', or 'error'."""
        if self.audio.should_stop():
            return "stop"

        self.audio.display(f"Turn {turn_num}: Listening...", color="yellow")
        logger.info(f"=== Turn {turn_num} | Listening (Smart VAD) ===")
        if not self.audio.record(INPUT_FILE, duration=RECORDING_DURATION) or self.audio.should_stop():
            return "stop" if self.audio.should_stop() else "error"

        self.audio.display(f"Turn {turn_num}: Thinking...", color="cyan")
        if not self.process_turn_fast(INPUT_FILE, RESPONSE_FILE):
            self.audio.display("Server Error", color="red")
            return "error"

        if self.audio.should_stop() or is_stop_phrase(self.last_user_text):
            if is_stop_phrase(self.last_user_text):
                logger.info(f"Detected exit phrase ('{self.last_user_text}'). Ending session.")
            return "stop"

        return "continue"

    def run_loop(self):
        """Continuously run voice conversation turns until the user ends the session."""
        logger.info(
            "Starting fast continuous voice loop! "
            "To end: say 'להתראות'/'עצור'/'stop', press Button X/Y on Pirate Audio, or click '■ Stop'."
        )
        turn = 1
        try:
            while True:
                status = self.run_turn(turn_num=turn)
                if status == "stop":
                    logger.info("Voice assistant loop ended by user.")
                    self.audio.display("Goodbye! (Stopped)", color="white")
                    break
                elif status == "error":
                    time.sleep(0.5)
                    if self.audio.should_stop():
                        self.audio.display("Stopped", color="white")
                        break
                else:
                    turn += 1
                    self.audio.display("Ready (X/Y to Stop)", color="white")
                    for _ in range(3):
                        if self.audio.should_stop():
                            self.audio.display("Goodbye! (Stopped)", color="white")
                            return
                        time.sleep(0.08)
        except KeyboardInterrupt:
            logger.info("KeyboardInterrupt received. Exiting voice loop.")
            self.audio.display("Stopped", color="white")


def run_standalone():
    hw = globals().get("hardware", None)
    if hw is None:
        try:
            import hardware
            hw = hardware
        except ImportError:
            hw = None
    audio = AudioInterface(hardware_api=hw)
    client = EcoCareClient(audio_interface=audio)

    audio.display("EcoCare Starting...", color="cyan")
    if not client.check_server():
        audio.display("Server Offline", color="red")
        logger.error("Could not reach VM server. Ensure server.py is running on VM.")
        return

    client.reset_conversation()
    audio.display("EcoCare Ready", color="green")
    client.run_loop()


if __name__ == "__main__":
    run_standalone()
