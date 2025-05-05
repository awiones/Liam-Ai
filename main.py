import os
import cv2
import time
import threading
import queue  # <-- Add this import
import speech_recognition as sr
import pyttsx3
import base64
import subprocess
import platform
import win32gui
import win32con
import win32api
import win32com.client
import re
from io import BytesIO
from PIL import Image
import numpy as np
from openai import OpenAI
from dotenv import load_dotenv
from assets import CameraManager
from assets.write import handle_notepad_ai
from assets.waiting_sounds import WaitingSounds  # Add this import
from elevenlabs.client import ElevenLabs
from elevenlabs import play
import sounddevice as sd
import soundfile as sf
import random  # Add at the top with other imports

from utils import print_banner, print_system_info  # <-- Add print_system_info import

load_dotenv()

def ensure_api_key():
    github_token = os.environ.get("GITHUB_TOKEN", "").strip()
    openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
    
    # Check if we already have a valid key
    if github_token:
        return github_token
    if openai_key:
        return openai_key
        
    # No valid key found, prompt user
    print("\nNo valid API key found in .env file.")
    print("Please enter your API key:")
    user_key = input("API Key: ").strip()
    if not user_key:
        print("No API key provided. Exiting.")
        exit(1)
        
    print("Is this a GitHub Copilot key or OpenAI key?")
    print("Type 'g' for GitHub Copilot, 'o' for OpenAI:")
    key_type = input("Key type [g/o]: ").strip().lower()
    
    if key_type not in ['g', 'o']:
        print("Invalid key type. Please restart and choose 'g' or 'o'.")
        exit(1)
        
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    with open(env_path, 'w') as f:  # Use 'w' to overwrite existing file
        if key_type == "g":
            f.write("GITHUB_TOKEN={}\n".format(user_key))
        else:
            f.write("OPENAI_API_KEY={}\n".format(user_key))

        # Preserve ELEVENLABS_API_KEY if it exists
        elevenlabs_key = os.environ.get("ELEVENLABS_API_KEY", "")
        if elevenlabs_key:
            f.write("ELEVENLABS_API_KEY={}\n".format(elevenlabs_key))
            
    print("\nAPI key saved to .env file.")
    print("Please restart the program to use the new key.")
    exit(0)

class Liam:
    def __init__(self, api_key=None, voice_index=None):
        if not api_key or api_key.strip() == "":
            raise ValueError("No valid API key provided")
        
        github_token = os.environ.get("GITHUB_TOKEN")
        openai_key = os.environ.get("OPENAI_API_KEY")

        if github_token:
            self.api_key = github_token
            self.client = OpenAI(
                base_url="https://models.github.ai/inference",
                api_key=self.api_key,
            )
        else:
            self.api_key = api_key or openai_key
            if not self.api_key:
                raise ValueError("API key is required. Set it as an environment variable or pass it to the constructor.")
            self.client = OpenAI(
                api_key=self.api_key,
                base_url="https://api.openai.com/v1"
            )
        
        # Speech settings
        self.speak_with_pauses = True  # Enable natural pauses by default
        
        self.recognizer = sr.Recognizer()
        
        # Initialize text-to-speech settings
        self.use_elevenlabs = False
        self.elevenlabs_key = os.environ.get("ELEVENLABS_API_KEY")
        if self.elevenlabs_key:
            try:
                self.elevenlabs_client = ElevenLabs(api_key=self.elevenlabs_key)
                self.use_elevenlabs = True
                print("ElevenLabs TTS initialized successfully")
                
                # Cache for frequently used phrases
                self.voice_cache = {}
                
                # Create a queue for audio processing
                self.audio_queue = queue.Queue()
                self.audio_thread = threading.Thread(target=self._process_audio_queue, daemon=True)
                self.audio_thread.start()
                
            except Exception as e:
                print(f"ElevenLabs initialization failed: {e}")
                print("Falling back to Microsoft TTS")
                self.use_elevenlabs = False
        
        # Initialize Microsoft TTS as fallback
        self.engine = pyttsx3.init()
        self.engine.setProperty('rate', 150)  # Speed of speech
        
        # Get available voices and set a specific voice if requested
        voices = self.engine.getProperty('voices')
        
        # Set voice based on index or default to the first voice
        if voice_index is not None and 0 <= voice_index < len(voices):
            self.engine.setProperty('voice', voices[voice_index].id)
        else:
            # Try to find a more natural-sounding voice (often the second voice is better)
            # On Windows, voices[1] is often Microsoft David (male) or Microsoft Zira (female)
            default_voice_index = 1 if len(voices) > 1 else 0
            self.engine.setProperty('voice', voices[default_voice_index].id)
        
        # Adjust volume for more natural speech
        self.engine.setProperty('volume', 0.9)  # Volume (0.0 to 1.0)
        
        self.camera_manager = CameraManager()
        
        self.system_message = """
        You are Liam, a helpful AI assistant that can control a laptop's peripherals and applications.
        You can access the camera, open applications, create files, and execute various system commands.
        You can also write to Notepad and manipulate text files.
        You are friendly, helpful, and concise in your responses.
        Keep your responses brief and natural-sounding as they will be spoken aloud.
        """
        
        self.conversation_history = [{"role": "system", "content": self.system_message}]
        self.os_type = platform.system()
        self.notepad_hwnd = None
        
        # Add handle_notepad_ai as instance method
        self.handle_notepad_ai = lambda user_input, mode="write": handle_notepad_ai(self, user_input, mode)

        self.waiting_sounds = WaitingSounds()

        print("Liam AI initialized and ready to help!")
        self.speak("Hello, I'm Liam. How can I assist you today?")

    def _process_audio_queue(self):
        """Background thread to process audio queue"""
        while True:
            try:
                text, use_cache = self.audio_queue.get()
                if text:
                    self._generate_and_play_audio(text, use_cache)
                self.audio_queue.task_done()
            except Exception as e:
                print(f"Error in audio queue processing: {e}")
            time.sleep(0.1)

    def _generate_and_play_audio(self, text, use_cache=True):
        """Generate and play audio for the given text"""
        try:
            # Check cache first if enabled
            if use_cache and text in self.voice_cache:
                audio_data = self.voice_cache[text]
                play(audio_data)
                return

            # Use streaming for longer text to start playback faster
            if len(text) > 100:
                audio_stream = self.elevenlabs_client.generate(
                    text=text,
                    voice="Brian",
                    model="eleven_multilingual_v2",
                    stream=True
                )
                play(audio_stream)
            else:
                # For shorter text, generate and cache
                audio = self.elevenlabs_client.generate(
                    text=text,
                    voice="Brian",
                    model="eleven_multilingual_v2"
                )
                
                # Cache the audio for future use if it's a common phrase
                if use_cache and len(text) < 50:  # Only cache short phrases
                    self.voice_cache[text] = audio
                
                play(audio)
                
        except Exception as e:
            print(f"Error generating audio: {e}")

    def toggle_speech_pauses(self):
        """Toggle natural speech pauses on/off"""
        self.speak_with_pauses = not self.speak_with_pauses
        return self.speak_with_pauses
        
    def list_available_voices(self):
        """List all available voices and their properties"""
        voices = self.engine.getProperty('voices')
        voice_info = []
        
        for idx, voice in enumerate(voices):
            info = {
                "index": idx,
                "name": voice.name,
                "id": voice.id,
                "gender": voice.gender if hasattr(voice, 'gender') else "Unknown",
                "age": voice.age if hasattr(voice, 'age') else "Unknown",
                "languages": voice.languages if hasattr(voice, 'languages') else []
            }
            voice_info.append(info)
            
        return voice_info
    
    def change_voice(self, voice_index):
        """Change the voice to the specified index"""
        voices = self.engine.getProperty('voices')
        if 0 <= voice_index < len(voices):
            self.engine.setProperty('voice', voices[voice_index].id)
            print(f"Voice changed to: {voices[voice_index].name}")
            return True
        else:
            print(f"Invalid voice index. Please choose between 0 and {len(voices)-1}")
            return False

    def speak(self, text):
        print(f"Liam: {text}")
        
        if self.use_elevenlabs:
            try:
                # For very short responses, use pre-generation to reduce latency
                if len(text) < 20:
                    # Check if we have it cached already
                    if text in self.voice_cache:
                        play(self.voice_cache[text])
                        return
                    
                    # Generate and play immediately for very short text
                    audio = self.elevenlabs_client.generate(
                        text=text,
                        voice="Brian",
                        model="eleven_multilingual_v2"
                    )
                    self.voice_cache[text] = audio
                    play(audio)
                    return
                
                # For longer text, split into sentences and process in parallel
                if self.speak_with_pauses and len(text) > 50:
                    sentences = re.split(r'(?<=[.!?])\s+', text)
                    
                    # Start generating the first sentence immediately
                    if sentences:
                        first_sentence = sentences[0]
                        audio = self.elevenlabs_client.generate(
                            text=first_sentence,
                            voice="Brian",
                            model="eleven_multilingual_v2"
                        )
                        play(audio)
                        
                        # Queue the rest of the sentences
                        for sentence in sentences[1:]:
                            if sentence.strip():
                                self.audio_queue.put((sentence, True))
                        
                        return
                
                # For medium-length text, use streaming
                audio_stream = self.elevenlabs_client.generate(
                    text=text,
                    voice="Brian",
                    model="eleven_multilingual_v2",
                    stream=True
                )
                play(audio_stream)
                return
                
            except Exception as e:
                print(f"ElevenLabs TTS failed: {e}")
                print("Falling back to Microsoft TTS")
                self.use_elevenlabs = False
        
        # Fallback to Microsoft TTS
        if self.speak_with_pauses:
            sentences = re.split(r'(?<=[.!?])\s+', text)
            for sentence in sentences:
                if sentence.strip():
                    self.engine.say(sentence)
                    self.engine.runAndWait()
                    time.sleep(0.15)
        else:
            self.engine.say(text)
            self.engine.runAndWait()

    def listen(self):
        with sr.Microphone() as source:
            print("Listening...")
            self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
            try:
                audio = self.recognizer.listen(source, timeout=5)
                print("Processing speech...")
                text = self.recognizer.recognize_google(audio)
                print(f"You said: {text}")
                return text
            except sr.WaitTimeoutError:
                print("No speech detected")
                return None
            except sr.UnknownValueError:
                print("Could not understand audio")
                return None
            except sr.RequestError as e:
                print(f"Could not request results; {e}")
                return None

    def open_notepad(self):
        """Open Notepad and return the window handle"""
        try:
            # Play waiting sound while opening
            if self.use_elevenlabs:
                self.waiting_sounds.play_single_waiting_sound()
            
            # Start Notepad
            subprocess.Popen("notepad.exe")
            time.sleep(1)  # Wait for Notepad to open

            # Find Notepad window
            self.notepad_hwnd = win32gui.FindWindow("Notepad", None)
            if self.notepad_hwnd == 0:
                print("Could not find Notepad window")
                return False

            # Bring Notepad to front
            win32gui.ShowWindow(self.notepad_hwnd, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(self.notepad_hwnd)
            time.sleep(0.5)
            return True

        except Exception as e:
            print(f"Error opening Notepad: {e}")
            return False

    def write_to_notepad(self, text):
        """Write text directly to Notepad"""
        try:
            # Check if Notepad is already open
            if self.notepad_hwnd is None or not win32gui.IsWindow(self.notepad_hwnd):
                if not self.open_notepad():
                    self.speak("Could not open Notepad")
                    return False
            else:
                # Bring existing Notepad window to front
                win32gui.ShowWindow(self.notepad_hwnd, win32con.SW_RESTORE)
                win32gui.SetForegroundWindow(self.notepad_hwnd)
                time.sleep(0.5)

            # Create shell object
            shell = win32com.client.Dispatch("WScript.Shell")
            
            # Ensure Notepad has focus
            if win32gui.GetForegroundWindow() != self.notepad_hwnd:
                win32gui.SetForegroundWindow(self.notepad_hwnd)
                time.sleep(0.5)
            
            # Clear any existing text
            shell.SendKeys("^a")  # Ctrl+A to select all
            time.sleep(0.1)
            shell.SendKeys("{DELETE}")  # Delete selected text
            time.sleep(0.1)
            
            # Write the text in chunks to avoid issues with long text
            chunk_size = 100  # Send text in smaller chunks
            for i in range(0, len(text), chunk_size):
                chunk = text[i:i+chunk_size]
                shell.SendKeys(chunk)
                time.sleep(0.05)  # Small delay between chunks
            
            return True

        except Exception as e:
            print(f"Error writing to Notepad: {e}")
            return False

    def append_to_notepad(self, text):
        """Append text to existing Notepad content"""
        try:
            # Check if Notepad is already open
            if self.notepad_hwnd is None or not win32gui.IsWindow(self.notepad_hwnd):
                if not self.open_notepad():
                    self.speak("Could not open Notepad")
                    return False
            else:
                # Bring existing Notepad window to front
                win32gui.ShowWindow(self.notepad_hwnd, win32con.SW_RESTORE)
                win32gui.SetForegroundWindow(self.notepad_hwnd)
                time.sleep(0.5)

            # Create shell object
            shell = win32com.client.Dispatch("WScript.Shell")
            
            # Move to end of document
            shell.SendKeys("^{END}")  # Ctrl+End
            
            # Add a new line if needed
            shell.SendKeys("{ENTER}")
            
            # Write the text
            shell.SendKeys(text)
            return True

        except Exception as e:
            print(f"Error appending to Notepad: {e}")
            return False

    def clear_notepad(self):
        """Clear all text in Notepad"""
        try:
            # Check if Notepad is already open
            if self.notepad_hwnd is None or not win32gui.IsWindow(self.notepad_hwnd):
                if not self.open_notepad():
                    self.speak("Could not open Notepad")
                    return False
            else:
                # Bring existing Notepad window to front
                win32gui.ShowWindow(self.notepad_hwnd, win32con.SW_RESTORE)
                win32gui.SetForegroundWindow(self.notepad_hwnd)
                time.sleep(0.5)

            # Create shell object
            shell = win32com.client.Dispatch("WScript.Shell")
            
            # Select all text (Ctrl+A) and delete it
            shell.SendKeys("^a")
            time.sleep(0.1)
            shell.SendKeys("{DELETE}")
            return True

        except Exception as e:
            print(f"Error clearing Notepad: {e}")
            return False

    def save_notepad(self, filename=None):
        """Save the current Notepad content to a file"""
        try:
            # Check if Notepad is already open
            if self.notepad_hwnd is None or not win32gui.IsWindow(self.notepad_hwnd):
                self.speak("Notepad is not open")
                return False

            # Bring Notepad to front
            win32gui.ShowWindow(self.notepad_hwnd, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(self.notepad_hwnd)
            time.sleep(0.5)

            # Create shell object
            shell = win32com.client.Dispatch("WScript.Shell")
            
            # Press Ctrl+S to open save dialog
            shell.SendKeys("^s")
            time.sleep(1)  # Wait for save dialog
            
            # If filename is provided, type it
            if filename:
                shell.SendKeys(filename)
            
            # Press Enter to save
            shell.SendKeys("{ENTER}")
            time.sleep(0.5)
            
            # Handle potential "Replace" dialog
            try:
                # Find dialog by title
                replace_dialog = win32gui.FindWindow("#32770", "Confirm Save As")
                if replace_dialog:
                    # Press "Yes" to confirm replace
                    shell.SendKeys("{LEFT}")  # Focus on "Yes" button
                    shell.SendKeys("{ENTER}")
            except:
                pass
                
            return True

        except Exception as e:
            print(f"Error saving Notepad file: {e}")
            return False

    def process_command(self, user_input):
        """Process user command and get AI response"""
        if not user_input:
            return

        # Check for direct notepad commands first
        notepad_keywords = ["notepad", "write", "open notepad"]
        if any(keyword in user_input.lower() for keyword in notepad_keywords):
            try:
                if "write" in user_input.lower() or "write about" in user_input.lower():
                    self.handle_notepad_ai(user_input, "write")
                else:
                    success = self.open_notepad()
                    if success:
                        self.speak("I've opened Notepad for you.")
                    else:
                        self.speak("I had trouble opening Notepad.")
                return
            except Exception as e:
                print(f"Error handling notepad command: {e}")
                self.speak("I encountered an error while trying to work with Notepad.")
                return

        # Continue with normal AI response for other commands
        self.conversation_history.append({"role": "user", "content": user_input})
        
        try:
            # Play waiting sound before processing (non-blocking)
            if self.use_elevenlabs:
                self.waiting_sounds.play_single_waiting_sound()
            
            model_name = "openai/gpt-4o" if os.environ.get("GITHUB_TOKEN") else "gpt-4o"
            response = self.client.chat.completions.create(
                model=model_name,
                messages=self.conversation_history,
                max_tokens=150
            )
            ai_response = response.choices[0].message.content
            
            self.conversation_history.append({"role": "assistant", "content": ai_response})
            self.speak(ai_response)
            
        except Exception as e:
            error_msg = f"Sorry, I encountered an error: {str(e)}"
            self.speak(error_msg)

    def open_application(self, app_type):
        try:
            if self.os_type == "Windows":
                if app_type == "notebook":
                    self.open_notepad()
                    self.speak("Opening Notepad")
                elif app_type == "browser":
                    os.system("start \"\" https://www.google.com")
                    self.speak("Opening your default browser")
                elif app_type == "terminal":
                    subprocess.Popen("cmd.exe")
                    self.speak("Opening Command Prompt")
            elif self.os_type == "Darwin":
                if app_type == "notebook":
                    subprocess.Popen(["open", "-a", "TextEdit"])
                    self.speak("Opening TextEdit")
                elif app_type == "browser":
                    subprocess.Popen(["open", "https://www.google.com"])
                    self.speak("Opening your default browser")
                elif app_type == "terminal":
                    subprocess.Popen(["open", "-a", "Terminal"])
                    self.speak("Opening Terminal")
            elif self.os_type == "Linux":
                if app_type == "notebook":
                    for editor in ["gedit", "nano", "vim", "leafpad"]:
                        try:
                            subprocess.Popen([editor])
                            self.speak(f"Opening {editor}")
                            break
                        except:
                            continue
                elif app_type == "browser":
                    for browser in ["xdg-open https://www.google.com", "firefox", "google-chrome", "chromium-browser"]:
                        try:
                            subprocess.Popen(browser.split())
                            self.speak("Opening browser")
                            break
                        except:
                            continue
                elif app_type == "terminal":
                    for terminal in ["gnome-terminal", "konsole", "xterm"]:
                        try:
                            subprocess.Popen([terminal])
                            self.speak(f"Opening {terminal}")
                            break
                        except:
                            continue
            else:
                self.speak("I'm not sure how to open applications on your operating system.")
        except Exception as e:
            self.speak(f"I encountered an error while trying to open the application: {str(e)}")

    def create_text_file(self, user_input):
        try:
            self.speak("What would you like the file to be named?")
            time.sleep(0.5)
            filename = self.listen()
            
            if not filename:
                self.speak("I couldn't understand the filename. Please try again.")
                return
                
            if not filename.endswith('.txt'):
                filename += '.txt'
                
            self.speak("What content would you like to write to the file?")
            time.sleep(0.5)
            content = self.listen()
            
            if not content:
                self.speak("I couldn't understand the content. Please try again.")
                return
                
            with open(filename, 'w') as file:
                file.write(content)
                
            self.speak(f"I've created a file named {filename} with your content.")
            
        except Exception as e:
            self.speak(f"I encountered an error while creating the file: {str(e)}")

    def run(self):
        try:
            while True:
                user_input = self.listen()
                if user_input:
                    if "quit" in user_input.lower() or "exit" in user_input.lower() or "goodbye" in user_input.lower():
                        self.speak("Goodbye! Have a great day.")
                        break
                    self.process_command(user_input)
                time.sleep(0.1)
        finally:
            if self.camera_manager.is_active:
                self.camera_manager.stop_camera()


def main():
    try:
        print_banner()  # <-- Show banner at program start
        print_system_info()  # <-- Show system info at program start
        api_key = ensure_api_key()
        if not api_key or api_key.strip() == "":
            print("No valid API key found. Please restart the program.")
            exit(1)
        
        liam = Liam(api_key=api_key, voice_index=0)
        liam.run()
    except KeyboardInterrupt:
        print("\nExiting Liam AI...")
    except Exception as e:
        print(f"Error: {e}")
        exit(1)


if __name__ == "__main__":
    main()
