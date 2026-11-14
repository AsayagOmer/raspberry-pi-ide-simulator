#!/usr/bin/env python3
"""
EcoCare - Hardware & Compatibility Test Suite for Raspberry Pi
Tests:
1. Audio devices detection (Microphone & Speaker)
2. Microphone capture test (up to 1 meter, SNR & dBFS calculation)
3. Speaker output test (75 dB tone & voice playback)
4. Power & Voltage stability check (vcgencmd throttled & 100% CPU stress test)
"""

import os
import sys
import time
import math
import wave
import subprocess
import multiprocessing
import numpy as np

try:
    import sounddevice as sd
except ImportError:
    print("❌ שגיאה: ספריית sounddevice חסרה. התקן בעזרת: sudo apt install -y python3-sounddevice")
    sys.exit(1)

SAMPLE_RATE = 16000
CHANNELS = 1
DTYPE = "int16"

NOISE_FILE = "hw_test_noise.wav"
SPEECH_FILE = "hw_test_speech_1m.wav"
TONE_FILE = "hw_test_tone_1khz.wav"


def run_cmd(cmd):
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return res.stdout.strip() or res.stderr.strip()


def analyze_wav(filename):
    with wave.open(filename, "rb") as wf:
        frames = wf.readframes(wf.getnframes())
    samples = np.frombuffer(frames, dtype=np.int16).astype(np.float64)
    if samples.size == 0:
        return 0.0, -100.0, 0.0
    peak = float(np.max(np.abs(samples)))
    rms = float(np.sqrt(np.mean(samples ** 2)))
    dbfs = 20.0 * math.log10(rms / 32768.0) if rms > 0 else -100.0
    return rms, dbfs, peak


def print_header(title):
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def test_step_0_devices():
    print_header("שלב 0: זיהוי התקני שמע מחוברים")
    print("🎙️ התקני הקלטה (arecord -l):")
    print(run_cmd("arecord -l") or "לא נמצאו")
    print("\n🔊 התקני השמעה (aplay -l):")
    print(run_cmd("aplay -l") or "לא נמצאו")


def test_step_1_microphone():
    print_header("בדיקה 1: תקינות מיקרופון ממרחק 1 מטר")
    
    print("\n[1/2] מדידת רעש רקע (Noise Floor) למשך 2 שניות...")
    print(">> אנא שמור על שקט מוחלט בחדר.")
    time.sleep(1)
    
    rec_noise = sd.rec(int(2 * SAMPLE_RATE), samplerate=SAMPLE_RATE, channels=CHANNELS, dtype=DTYPE)
    sd.wait()
    with wave.open(NOISE_FILE, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(rec_noise.tobytes())
    
    _, noise_dbfs, _ = analyze_wav(NOISE_FILE)
    print(f"   רצפת רעש: {noise_dbfs:.1f} dBFS")

    print("\n[2/2] הקלטת דיבור ממרחק 1 מטר למשך 5 שניות.")
    print(">> התרחק כ-1 מטר מהמיקרופון.")
    input("לחץ [Enter] כשאתה מוכן בעמדה...")

    print("🎙️ מקליט כעת (5 שניות) - דבר כעת בקול רגיל וברור...")
    rec_speech = sd.rec(int(5 * SAMPLE_RATE), samplerate=SAMPLE_RATE, channels=CHANNELS, dtype=DTYPE)
    sd.wait()
    with wave.open(SPEECH_FILE, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(rec_speech.tobytes())
    
    speech_rms, speech_dbfs, speech_peak = analyze_wav(SPEECH_FILE)
    snr_db = speech_dbfs - noise_dbfs
    peak_pct = (speech_peak / 32768.0) * 100.0

    print("\n--- תוצאות בדיקת מיקרופון ---")
    print(f"עוצמת דיבור (RMS)  : {speech_dbfs:.1f} dBFS (Peak: {peak_pct:.1f}%)")
    print(f"רצפת רעש (Noise)    : {noise_dbfs:.1f} dBFS")
    print(f"יחס אות לרעש (SNR)  : {snr_db:.1f} dB")

    if speech_rms < 15:
        print("❌ כישלון: לא נקלט אות מהמיקרופון (בדוק חיבור או השתקה ב-alsamixer).")
    elif snr_db >= 10.0 and speech_dbfs > -45.0:
        print("✅ תקין: המיקרופון קולט דיבור ממרחק 1 מטר בצורה ברורה!")
    else:
        print("⚠️ גבולי: האות חלש יחסית ממרחק 1 מטר. מומלץ להגביר עוצמה ב-alsamixer (F4 -> Capture).")


def test_step_2_speaker():
    print_header("בדיקה 2: תקינות רמקול ועוצמת שמע (75 dB)")
    
    # פתיחת ווליום ב-ALSA
    for ctrl in ["Master", "PCM", "Speaker", "Headphone"]:
        subprocess.run(f"amixer sset '{ctrl}' 100% unmute", shell=True, capture_output=True)

    # יצירת צליל 1kHz
    t = np.linspace(0, 4, int(SAMPLE_RATE * 4), endpoint=False)
    tone = (0.95 * 32767 * np.sin(2 * np.pi * 1000 * t)).astype(np.int16)

    print("🔊 שלב א': השמעת צליל בדיקה (1kHz) למשך 4 שניות בעוצמה מלאה.")
    print(">> שים לב: פתח אפליקציית מד דציבלים בטלפון מול הרמקול כדי לוודא הגעה ל-75dB.")
    input("לחץ [Enter] להפעלת הצליל...")

    loopback = sd.playrec(tone.reshape(-1, 1), samplerate=SAMPLE_RATE, channels=CHANNELS, dtype=DTYPE)
    sd.wait()

    loop_rms = float(np.sqrt(np.mean(loopback.astype(np.float64) ** 2)))
    loop_dbfs = 20.0 * math.log10(loop_rms / 32768.0) if loop_rms > 0 else -100.0
    est_spl = 94.0 + loop_dbfs

    print(f"עוצמה שנקלטה במיקרופון : {loop_dbfs:.1f} dBFS (אומדן משוער: ~{est_spl:.1f} dB SPL)")
    if loop_dbfs > -30:
        print("✅ הרמקול מפיק צליל חזק וברור!")
    else:
        print("⚠️ עוצמת השמע נמוכה. בדוק חיבורים או הגברות ב-alsamixer.")

    if os.path.exists(SPEECH_FILE):
        print("\n🔊 שלב ב': השמעה חוזרת של הקלטת הדיבור שלך ממרחק 1 מטר...")
        with wave.open(SPEECH_FILE, "rb") as wf:
            data = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16)
        sd.play(data, SAMPLE_RATE)
        sd.wait()
        print("✅ השמעה הסתיימה.")


def test_step_3_power():
    print_header("בדיקה 3: צריכת מתח ויציבות ספק כוח")

    def read_metrics():
        throttled = run_cmd("vcgencmd get_throttled")
        v_core = run_cmd("vcgencmd measure_volts core")
        temp = run_cmd("vcgencmd measure_temp")
        pmic = run_cmd("vcgencmd pmic_read_adc")
        ext5v = ""
        for line in pmic.splitlines():
            if "EXT5V_V" in line:
                ext5v = line.strip()
                break
        return throttled, v_core, temp, ext5v

    print("[1] בדיקה במצב מנוחה (Idle):")
    t_idle, v_idle, temp_idle, ext5v_idle = read_metrics()
    print(f"   טמפרטורה : {temp_idle}")
    print(f"   מתח ליבה : {v_idle}")
    if ext5v_idle:
        print(f"   מתח 5V   : {ext5v_idle}")
    print(f"   סטטוס    : {t_idle}")

    print("\n[2] מריץ בדיקת מאמץ (100% CPU על כל הליבות) למשך 5 שניות...")
    def burn(d):
        end = time.time() + d
        x = 0.001
        while time.time() < end:
            x = math.sqrt(x * x + 1.2345)

    procs = [multiprocessing.Process(target=burn, args=(5,)) for _ in range(multiprocessing.cpu_count())]
    for p in procs:
        p.start()
    time.sleep(3.5)
    t_load, v_load, temp_load, ext5v_load = read_metrics()
    for p in procs:
        p.join()

    print(f"   טמפרטורה בשיא עומס : {temp_load}")
    print(f"   מתח ליבה בשיא עומס : {v_load}")
    if ext5v_load:
        print(f"   מתח 5V בשיא עומס   : {ext5v_load}")
    print(f"   סטטוס Throttled    : {t_load}")

    # פיענוח
    if "=" in t_load:
        val = int(t_load.split("=")[1], 16)
        if val == 0:
            print("\n✅ תקין לחלוטין (0x0): אין שום נפילת מתח (Under-voltage) גם תחת עומס מלא!")
        else:
            print(f"\n⚠️ התראה: זוהו דגלי Throttling (קוד: {hex(val)}):")
            if val & 0x1:
                print("   - התרחשה נפילת מתח כעת (מתח נמוך מ-4.63V!)")
            if val & 0x50000:
                print("   - התרחשה נפילת מתח בעבר מאז ההדלקה.")
            if val & 0x8:
                print("   - הגבלת טמפרטורה (מעבד חם מדי).")
    else:
        print(f"\nℹ️ פקודת vcgencmd: {t_load}")


def main():
    print("=" * 60)
    print("   EcoCare - סקריפט בדיקת חומרה (מיקרופון, רמקול, מתח)")
    print("=" * 60)
    test_step_0_devices()
    test_step_1_microphone()
    test_step_2_speaker()
    test_step_3_power()
    print_header("כל הבדיקות הסתיימו!")


if __name__ == "__main__":
    main()
