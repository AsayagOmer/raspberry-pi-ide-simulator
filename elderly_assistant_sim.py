import time
import requests

SERVER_URL = "http://localhost:8000"
INPUT_WAV = "input.wav"

# Clear the Pirate Audio LCD screen and show startup text
hardware.clear_screen()
hardware.display_text("Elderly Assistant\nStarting...", color="cyan")
print("Starting Elderly Assistant Simulator Script...")
time.sleep(1)

# 1. Check Server Connection
hardware.display_text("Checking Server...", color="yellow")
try:
    resp = requests.get(f"{SERVER_URL}/health", timeout=3)
    if resp.status_code == 200:
        hardware.display_text("Server OK!\nPress A to talk", color="green")
        print("Server connection successful.")
    else:
        hardware.display_text("Server Error!\nPress A anyway", color="red")
        print(f"Unexpected health response from server: {resp.status_code}")
except Exception as e:
    hardware.display_text("No Server!\nPress A anyway", color="orange")
    print(f"Server communication error (is it running?): {e}")

time.sleep(1)
hardware.display_text("Press A to talk", color="white")
print("Ready. Press 'A' on the Pirate Audio component to record.")

# 2. Main Event Loop
while True:
    # Wait for the user to press the 'A' button on the Pirate Audio Mic
    if hardware.is_pressed('A'):
        
        # 3. Record Audio
        hardware.display_text("Recording\n(5s)...", color="red")
        print("Recording started...")
        
        # This will use the Pirate Audio component in the simulator
        success = hardware.record_audio(INPUT_WAV, duration=5)
        
        if success:
            hardware.display_text("Sending...", color="yellow")
            print(f"Recording saved to: {INPUT_WAV}. Sending to server...")
            
            # 4. Send Audio to Server
            try:
                with open(INPUT_WAV, "rb") as audio_file:
                    files = {"audio": (INPUT_WAV, audio_file, "audio/wav")}
                    response = requests.post(f"{SERVER_URL}/audio", files=files, timeout=10)
                
                response.raise_for_status()
                data = response.json()
                print("Audio uploaded successfully. Server response:", data)
                
                hardware.display_text("Playing...", color="green")
                
                # NOTE: Since we don't have the real server's response.wav here, 
                # we'll play the recorded INPUT_WAV back through the USB speaker
                # to prove the full hardware pipeline works!
                print("Playing audio back through the USB speaker...")
                hardware.play_audio(INPUT_WAV)
                
                hardware.display_text("Done!\nPress A again", color="cyan")
                print("Playback finished.")
                
            except Exception as e:
                hardware.display_text("Send Failed!\nPlaying local...", color="red")
                print(f"Audio upload failed: {e}")
                
                # Still test the speaker even if the server is down
                print("Playing local audio back through the USB speaker...")
                hardware.play_audio(INPUT_WAV)
                
                time.sleep(2)
                hardware.display_text("Press A to talk", color="white")
                
        else:
            hardware.display_text("Record Failed", color="red")
            print("Recording failed. Is Pirate Audio attached?")
            time.sleep(2)
            hardware.display_text("Press A to talk", color="white")
            
        # Debounce the button press so we don't immediately trigger again
        while hardware.is_pressed('A'):
            time.sleep(0.1)
            
    time.sleep(0.1)
