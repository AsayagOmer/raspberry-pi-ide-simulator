import time
import sys
import threading
from professional_ide import ProfessionalSimulator

def run_test():
    try:
        app = ProfessionalSimulator()
        app.update() # Process initial events
        
        # Inject test code
        test_code = """
import time
hardware.clear_screen()
hardware.display_text("Test", color="red")
time.sleep(0.5)
print("Hello from test code!")
"""
        app.editor.delete("1.0", "end")
        app.editor.insert("end", test_code)
        
        # Run the code
        print("Running user code...")
        app.run_user_code()
        
        # Let the thread run and GUI update
        for i in range(20):
            app.update()
            time.sleep(0.1)
            
        print("Test finished successfully without crashing!")
        sys.exit(0)
    except Exception as e:
        print(f"Test failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    run_test()
