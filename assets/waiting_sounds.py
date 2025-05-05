import random
import threading
import sounddevice as sd
import soundfile as sf
import time

class WaitingSounds:
    def __init__(self):
        self.waiting_sounds = [
            'assets/sounds/waiting/uhhh.mp3',
            'assets/sounds/waiting/umm.mp3',
            'assets/sounds/waiting/erm.mp3'
        ]

    def play_single_waiting_sound(self):
        """Play two random waiting sounds in sequence with a gap in a background thread"""
        def play_sounds():
            try:
                # Try to play just one sound instead of two for quicker operations
                sound_file = random.choice(self.waiting_sounds)
                try:
                    data, fs = sf.read(sound_file)
                    sd.play(data, fs)
                    sd.wait()
                except Exception as e:
                    print(f"Error playing sound file {sound_file}: {e}")
            except Exception as e:
                print(f"Error in play_sounds: {e}")

        # Start in background thread
        thread = threading.Thread(target=play_sounds, daemon=True)
        thread.start()
        return thread  # Return thread in case caller needs to wait
