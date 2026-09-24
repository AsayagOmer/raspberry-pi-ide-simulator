import pygame
import sys
import os

# Emulating Pirate Audio HAT
# Screen: 240x240 LCD (ST7789)
# Buttons: A, B, X, Y (Mapped to keyboard A, B, X, Y)
# Audio: Handled by pygame.mixer simulating USB Speaker / Pirate Audio DAC

# Constants
SCREEN_WIDTH = 240
SCREEN_HEIGHT = 240
FPS = 30

class PirateAudioEmulator:
    def __init__(self):
        pygame.init()
        pygame.mixer.init() # Simulates USB Speaker / Pirate Audio DAC
        
        # Set up the display
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Pirate Audio / RPi 4 Simulator")
        self.clock = pygame.time.Clock()
        
        # Default font
        self.font = pygame.font.SysFont(None, 24)
        
        # State
        self.running = True
        self.current_text = "Press A, B, X, or Y"
        
    def play_sound(self, sound_file):
        """Simulates sending audio to the Mini USB Speaker / DAC"""
        if os.path.exists(sound_file):
            try:
                pygame.mixer.music.load(sound_file)
                pygame.mixer.music.play()
                self.current_text = f"Playing: {os.path.basename(sound_file)}"
            except Exception as e:
                self.current_text = "Audio error!"
                print(f"Error playing sound: {e}")
        else:
            self.current_text = "Sound file not found!"
            print(f"File {sound_file} does not exist.")

    def stop_sound(self):
        pygame.mixer.music.stop()
        self.current_text = "Audio Stopped"

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                
            elif event.type == pygame.KEYDOWN:
                # Map keyboard to Pirate Audio buttons
                if event.key == pygame.K_a:
                    print("Button A pressed")
                    self.current_text = "Button A Pressed"
                    # Add your Button A logic here
                    
                elif event.key == pygame.K_b:
                    print("Button B pressed")
                    self.current_text = "Button B Pressed"
                    # Add your Button B logic here
                    
                elif event.key == pygame.K_x:
                    print("Button X pressed")
                    self.current_text = "Button X Pressed"
                    # Add your Button X logic here
                    
                elif event.key == pygame.K_y:
                    print("Button Y pressed")
                    self.current_text = "Button Y Pressed"
                    # Add your Button Y logic here

    def update_display(self):
        # Clear screen (Pirate audio has a black background by default)
        self.screen.fill((0, 0, 0))
        
        # Draw UI
        text_surface = self.font.render(self.current_text, True, (255, 255, 255))
        text_rect = text_surface.get_rect(center=(SCREEN_WIDTH/2, SCREEN_HEIGHT/2))
        self.screen.blit(text_surface, text_rect)
        
        # Draw button hints
        hint_font = pygame.font.SysFont(None, 18)
        hints = [
            ("A", (10, 10)),
            ("B", (10, 210)),
            ("X", (220, 10)),
            ("Y", (220, 210))
        ]
        for text, pos in hints:
            surf = hint_font.render(text, True, (100, 100, 100))
            self.screen.blit(surf, pos)
            
        pygame.display.flip()

    def run(self):
        print("Starting Pirate Audio Simulator...")
        print("Use your keyboard keys A, B, X, Y to simulate the HAT buttons.")
        
        while self.running:
            self.handle_events()
            self.update_display()
            self.clock.tick(FPS)
            
        pygame.quit()
        sys.exit()

if __name__ == "__main__":
    emulator = PirateAudioEmulator()
    emulator.run()
