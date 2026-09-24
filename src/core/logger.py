import os
import datetime

def log_event(text: str):
    """Log major IDE and hardware events to the event.log file."""
    os.makedirs("logs", exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(os.path.join("logs", "event.log"), "a") as f:
        f.write(f"[{timestamp}] {text}\n")
