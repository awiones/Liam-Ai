import os
import cv2
import time
import threading
import queue
import speech_recognition as sr
import pyttsx3
import base64
import subprocess
import platform
import re
from io import BytesIO
from PIL import Image
import numpy as np
from openai import OpenAI
from dotenv import load_dotenv
from modules import CameraManager
from modules.waiting_sounds import WaitingSounds 
from elevenlabs.client import ElevenLabs
from elevenlabs import play
import sounddevice as sd
import soundfile as sf
import random  
from modules.task_manager import TaskManager

from utils import print_banner, print_system_info, setup_logging
from config import config
from exceptions import *

# Platform-specific imports
if platform.system() == "Windows":
    try:
        import win32gui
        import win32con
        import win32api
        import win32com.client
        from modules.write.notepad import handle_notepad_ai, ensure_notepad_window, write_content_to_notepad, safe_send_keys
        WINDOWS_AVAILABLE = True
    except ImportError as e:
        print(f"Warning: Windows-specific modules not available: {e}")
        WINDOWS_AVAILABLE = False
else:
    WINDOWS_AVAILABLE = False

load_dotenv()

# Set up logging
logger = setup_logging(
    log_level=config.get("system", "log_level", "INFO"),
    log_file="liam_ai.log" if config.get("system", "enable_logging", False) else None
)

def ensure_api_key():
    """Ensure a valid API key is available, with improved error handling and validation."""
    github_token = os.environ.get("GITHUB_TOKEN", "").strip()
    openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
    
    # Return existing valid keys
    if github_token and len(github_token) > 10:  # Basic validation
        return github_token
    if openai_key and len(openai_key) > 10:  # Basic validation
        return openai_key
        
    print("\n" + "="*50)
    print("🔑 API KEY CONFIGURATION")
    print("="*50)
    print("No valid API key found in .env file.")
    print("\nSupported providers:")
    print("  1. GitHub Copilot (recommended for free tier)")
    print("  2. OpenAI (requires paid account)")
    print("\nPlease enter your API key:")
    
    user_key = input("API Key: ").strip()
    if not user_key or len(user_key) < 10:
        print("❌ Invalid API key provided. Key must be at least 10 characters.")
        exit(1)
        
    print("\nWhich provider is this key for?")
    print("  [g] GitHub Copilot")
    print("  [o] OpenAI")
    key_type = input("Provider [g/o]: ").strip().lower()
    
    if key_type not in ['g', 'o']:
        print("❌ Invalid provider. Please restart and choose 'g' or 'o'.")
        exit(1)
        
    try:
        env_path = os.path.join(os.path.dirname(__file__), ".env")
        
        # Read existing .env content to preserve other variables
        existing_content = ""
        if os.path.exists(env_path):
            with open(env_path, 'r') as f:
                lines = f.readlines()
                # Filter out existing API keys
                existing_content = ''.join([
                    line for line in lines 
                    if not line.startswith(('GITHUB_TOKEN=', 'OPENAI_API_KEY='))
                ])
        
        with open(env_path, 'w') as f:
            f.write(existing_content)
            if key_type == "g":
                f.write(f"GITHUB_TOKEN={user_key}\n")
                print("✅ GitHub Copilot key saved.")
            else:
                f.write(f"OPENAI_API_KEY={user_key}\n")
                print("✅ OpenAI key saved.")

            # Preserve ElevenLabs key if it exists
            elevenlabs_key = os.environ.get("ELEVENLABS_API_KEY", "")
            if elevenlabs_key and "ELEVENLABS_API_KEY=" not in existing_content:
                f.write(f"ELEVENLABS_API_KEY={elevenlabs_key}\n")
                
    except Exception as e:
        print(f"❌ Error saving API key: {e}")
        exit(1)
            
    print("\n✅ Configuration saved successfully!")
    print("🔄 Please restart the program to use the new key.")
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
        
        self.speak_with_pauses = True
        
        self.recognizer = sr.Recognizer()
        
        self.use_elevenlabs = False
        self.elevenlabs_key = os.environ.get("ELEVENLABS_API_KEY")
        if self.elevenlabs_key:
            try:
                self.elevenlabs_client = ElevenLabs(api_key=self.elevenlabs_key)
                self.use_elevenlabs = True
                print("ElevenLabs TTS initialized successfully")
                
                self.voice_cache = {}
                
                self.audio_queue = queue.Queue()
                self.audio_thread = threading.Thread(target=self._process_audio_queue, daemon=True)
                self.audio_thread.start()
                
            except Exception as e:
                print(f"ElevenLabs initialization failed: {e}")
                print("Falling back to Microsoft TTS")
                self.use_elevenlabs = False
        
        self.engine = pyttsx3.init()
        self.engine.setProperty('rate', 150)
        
        voices = self.engine.getProperty('voices')
        
        if voice_index is not None and 0 <= voice_index < len(voices):
            self.engine.setProperty('voice', voices[voice_index].id)
        else:
            default_voice_index = 1 if len(voices) > 1 else 0
            self.engine.setProperty('voice', voices[default_voice_index].id)
        
        self.engine.setProperty('volume', 0.9)
        
        self.camera_manager = CameraManager()
        self.task_manager = TaskManager()
        
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
        
        self.handle_notepad_ai = lambda user_input, mode="write": handle_notepad_ai(self, user_input, mode)

        self.waiting_sounds = WaitingSounds()

        print("Liam AI initialized and ready to help!")
        self.speak("Hello, I'm Liam. How can I assist you today?")

    def _process_audio_queue(self):
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
        try:
            if use_cache and text in self.voice_cache:
                audio_data = self.voice_cache[text]
                play(audio_data)
                return

            if len(text) > 100:
                audio_stream = self.elevenlabs_client.generate(
                    text=text,
                    voice="Brian",
                    model="eleven_multilingual_v2",
                    stream=True
                )
                play(audio_stream)
            else:
                audio = self.elevenlabs_client.generate(
                    text=text,
                    voice="Brian",
                    model="eleven_multilingual_v2"
                )
                
                if use_cache and len(text) < 50:
                    self.voice_cache[text] = audio
                
                play(audio)
                
        except Exception as e:
            print(f"Error generating audio: {e}")

    def toggle_speech_pauses(self):
        self.speak_with_pauses = not self.speak_with_pauses
        return self.speak_with_pauses
        
    def list_available_voices(self):
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
                if len(text) < 20:
                    if text in self.voice_cache:
                        play(self.voice_cache[text])
                        return
                    
                    audio = self.elevenlabs_client.generate(
                        text=text,
                        voice="Brian",
                        model="eleven_multilingual_v2"
                    )
                    self.voice_cache[text] = audio
                    play(audio)
                    return
                
                if self.speak_with_pauses and len(text) > 50:
                    sentences = re.split(r'(?<=[.!?])\s+', text)
                    
                    if sentences:
                        first_sentence = sentences[0]
                        audio = self.elevenlabs_client.generate(
                            text=first_sentence,
                            voice="Brian",
                            model="eleven_multilingual_v2"
                        )
                        play(audio)
                        
                        for sentence in sentences[1:]:
                            if sentence.strip():
                                self.audio_queue.put((sentence, True))
                        
                        return
                
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
        if not WINDOWS_AVAILABLE:
            self.speak("Notepad functionality is only available on Windows.")
            return False
            
        try:
            if self.use_elevenlabs and hasattr(self, 'waiting_sounds'):
                self.waiting_sounds.play_single_waiting_sound()
            
            subprocess.Popen("notepad.exe")
            time.sleep(1)

            self.notepad_hwnd = win32gui.FindWindow("Notepad", None)
            if self.notepad_hwnd == 0:
                print("Could not find Notepad window")
                return False

            win32gui.ShowWindow(self.notepad_hwnd, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(self.notepad_hwnd)
            time.sleep(0.5)
            return True

        except Exception as e:
            print(f"Error opening Notepad: {e}")
            self.speak("I encountered an error while trying to open Notepad.")
            return False

    def write_to_notepad(self, text):
        success, hwnd = ensure_notepad_window(self)
        if not success:
            return False
            
        return write_content_to_notepad(text, hwnd)

    def append_to_notepad(self, text):
        success, hwnd = ensure_notepad_window(self)
        if not success:
            return False

        try:
            shell = win32com.client.Dispatch("WScript.Shell")
            shell.SendKeys("^{END}")
            shell.SendKeys("{ENTER}")
            return safe_send_keys(shell, text)
        except Exception as e:
            print(f"Error appending to Notepad: {e}")
            return False

    def clear_notepad(self):
        success, hwnd = ensure_notepad_window(self)
        if not success:
            return False

        try:
            shell = win32com.client.Dispatch("WScript.Shell")
            shell.SendKeys("^a")
            time.sleep(0.1)
            shell.SendKeys("{DELETE}")
            return True
        except Exception as e:
            print(f"Error clearing Notepad: {e}")
            return False

    def save_notepad(self, filename=None):
        try:
            if self.notepad_hwnd is None or not win32gui.IsWindow(self.notepad_hwnd):
                self.speak("Notepad is not open")
                return False

            win32gui.ShowWindow(self.notepad_hwnd, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(self.notepad_hwnd)
            time.sleep(0.5)

            shell = win32com.client.Dispatch("WScript.Shell")
            
            shell.SendKeys("^s")
            time.sleep(1)
            
            if filename:
                shell.SendKeys(filename)
            
            shell.SendKeys("{ENTER}")
            time.sleep(0.5)
            
            try:
                replace_dialog = win32gui.FindWindow("#32770", "Confirm Save As")
                if replace_dialog:
                    shell.SendKeys("{LEFT}")
                    shell.SendKeys("{ENTER}")
            except:
                pass
                
            return True

        except Exception as e:
            print(f"Error saving Notepad file: {e}")
            return False

    def process_command(self, user_input):
        """Process user commands with improved validation and security."""
        if not user_input or not isinstance(user_input, str):
            return
            
        # Sanitize input
        user_input = user_input.strip()
        if len(user_input) > 1000:  # Prevent extremely long inputs
            self.speak("Your command is too long. Please try a shorter command.")
            return
            
        # Log the command for debugging (without sensitive data)
        safe_input = user_input[:100] + "..." if len(user_input) > 100 else user_input
        print(f"Processing command: {safe_input}")

        task_manager_keywords = ["task manager", "list processes", "running processes", "what's running", 
                                "show processes", "system processes", "check processes", "active processes",
                                "cpu usage", "memory usage", "process information"]
                                
        if any(keyword in user_input.lower() for keyword in task_manager_keywords):
            try:
                intelligent_response = self.task_manager.analyze_user_query(user_input)
                
                if intelligent_response:
                    self.speak(intelligent_response)
                else:
                    self.speak("Checking the running processes on your system...")
                    
                    detail_level = 'normal'
                    if "detailed" in user_input.lower() or "details" in user_input.lower():
                        detail_level = 'detailed'
                    elif "brief" in user_input.lower() or "minimal" in user_input.lower():
                        detail_level = 'minimal'
                    
                    sort_by = 'cpu_percent'
                    if "memory" in user_input.lower():
                        sort_by = 'memory_percent'
                    elif "recent" in user_input.lower() or "new" in user_input.lower():
                        sort_by = 'created'
                    
                    limit = 10
                    if "all" in user_input.lower():
                        limit = 30
                    
                    description = self.task_manager.describe_processes(
                        limit=limit, 
                        sort_by=sort_by, 
                        detail_level=detail_level,
                        speak_summary=True
                    )
                    
                    self.speak(description)
                    full_description = self.task_manager.describe_processes(
                        limit=limit, 
                        sort_by=sort_by, 
                        detail_level=detail_level
                    )
                    print(full_description)
            except Exception as e:
                print(f"Error handling Task Manager command: {e}")
                self.speak("I encountered an error while trying to read the system processes.")
            return

        process_search_keywords = ["find process", "search process", "look for process", "is running", "find application"]
        if any(keyword in user_input.lower() for keyword in process_search_keywords):
            try:
                intelligent_response = self.task_manager.analyze_user_query(user_input)
                
                if intelligent_response:
                    self.speak(intelligent_response)
                    return
                    
                words = user_input.lower().split()
                search_terms = []
                
                for keyword in process_search_keywords:
                    if keyword in user_input.lower():
                        index = user_input.lower().find(keyword) + len(keyword)
                        search_terms = user_input[index:].strip().split()
                        break
                
                if search_terms:
                    search_term = ' '.join(search_terms)
                    self.speak(f"Searching for processes matching '{search_term}'...")
                    
                    matching_processes = self.task_manager.find_process_by_name(search_term)
                    
                    if matching_processes:
                        if len(matching_processes) == 1:
                            proc = matching_processes[0]
                            self.speak(f"I found 1 matching process: {proc.get('name')} (PID: {proc.get('pid')}), "
                                      f"using {proc.get('cpu_percent', 0):.1f}% CPU and {proc.get('memory_percent', 0):.1f}% memory.")
                        else:
                            self.speak(f"I found {len(matching_processes)} matching processes:")
                            for proc in matching_processes[:5]: 
                                self.speak(f"- {proc.get('name')} (PID: {proc.get('pid')}), "
                                         f"using {proc.get('cpu_percent', 0):.1f}% CPU and {proc.get('memory_percent', 0):.1f}% memory.")
                            
                            if len(matching_processes) > 5:
                                self.speak(f"...and {len(matching_processes) - 5} more matching processes.")
                    else:
                        self.speak(f"I couldn't find any processes matching '{search_term}'.")
                else:
                    self.speak("Please specify a process name to search for.")
            except Exception as e:
                print(f"Error handling process search command: {e}")
                self.speak("I encountered an error while searching for processes.")
            return

        # System resource usage command
        resource_keywords = ["system resources", "resource usage", "system usage", "cpu usage", "memory usage",
                           "system performance", "computer performance", "how is my system doing"]
        if any(keyword in user_input.lower() for keyword in resource_keywords):
            try:
                intelligent_response = self.task_manager.analyze_user_query(user_input)
                
                if intelligent_response:
                    self.speak(intelligent_response)
                    return
                    
                self.speak("Checking your system's resource usage...")
                
                resource_info = self.task_manager.get_system_resource_usage()
                
                response = (f"Your system is currently using {resource_info['cpu_percent']}% of CPU capacity. "
                           f"Memory usage is at {resource_info['memory']['percent']}%, with "
                           f"{resource_info['memory']['available'] / (1024 * 1024 * 1024):.1f} GB available. "
                           f"Your system disk is {resource_info['disk']['percent']}% full.")
                
                self.speak(response)
            except Exception as e:
                print(f"Error handling resource usage command: {e}")
                self.speak("I encountered an error while checking system resources.")
            return
            
        camera_on_keywords = ["open camera", "turn on camera", "start camera", "show camera"]
        camera_off_keywords = ["close camera", "turn off camera", "stop camera", "hide camera"]
        vision_keywords = ["see what's happening", "see what happened", "describe what you see", 
                            "access the camera", "what do you see", "look through the camera",
                            "camera vision", "see what's going on", "what is happening"]
        read_text_keywords = ["read text", "read what it says", "what does it say", 
                                "can you read", "read the text", "read the camera",
                                "make the ai read", "read what you see", "read about it",
                                "i need you to read this on the camera", "read this in the camera"]
        narrate_keywords = ["talk about what you see", "narrate what you see", 
                            "tell me what you see", "describe the camera", 
                            "make the ai talk", "talk what you see",
                            "speak what you see", "voice what you see"]
        stop_narrate_keywords = ["stop talking", "stop narrating", "stop describing", 
                                    "stop telling me", "be quiet", "silence",
                                    "stop auto narration", "turn off narration"]

        notepad_keywords = ["notepad", "write", "open notepad"]

        exit_keywords = ["quit", "exit", "goodbye"]

        if any(keyword in user_input.lower() for keyword in camera_on_keywords):
            try:
                self.speak("Sure! Opening the camera now.")
                started = self.camera_manager.start_camera()
                if started:
                    self.speak("The camera is now on.")
                else:
                    self.speak("I couldn't open the camera.")
            except Exception as e:
                print(f"Error handling camera command: {e}")
                self.speak("I encountered an error while trying to open the camera.")
            return

        if any(keyword in user_input.lower() for keyword in vision_keywords):
            try:
                if self.camera_manager.is_active:
                    self.speak("The camera is already on. Let me check what I can see.")
                else:
                    self.speak("I need to turn on the camera first.")
                    started = self.camera_manager.start_camera()
                    if not started:
                        self.speak("I couldn't open the camera.")
                        return
                    self.speak("Camera is now on.")
                
                if not self.camera_manager.is_ai_vision_enabled:
                    self.speak("Enabling my vision capabilities.")
                    self.camera_manager.start_ai_vision(self.client, self.conversation_history)
                    time.sleep(2)
                
                description = self.camera_manager.get_latest_ai_description()
                if description:
                    self.speak(f"Through the camera, I can see: {description}")
                else:
                    self.speak("I'm looking through the camera, but I'm still processing what I see. Please ask me again in a moment.")
            except Exception as e:
                print(f"Error handling AI vision command: {e}")
                self.speak("I encountered an error while trying to see through the camera.")
            return

        if "check camera" in user_input.lower() or "camera status" in user_input.lower():
            try:
                if self.camera_manager.is_active:
                    self.speak("The camera is currently on.")
                else:
                    self.speak("The camera is currently off.")
            except Exception as e:
                print(f"Error checking camera status: {e}")
                self.speak("I encountered an error while checking the camera's status.")
            return

        if any(keyword in user_input.lower() for keyword in read_text_keywords):
            try:
                if not self.camera_manager.is_active:
                    self.speak("I need to turn on the camera first.")
                    started = self.camera_manager.start_camera()
                    if not started:
                        self.speak("I couldn't open the camera.")
                        return
                    self.speak("Camera is now on.")
                
                if not self.camera_manager.is_ai_vision_enabled:
                    self.speak("Enabling my text recognition capabilities.")
                    self.camera_manager.start_ai_vision(
                        client=self.client, 
                        conversation_history=self.conversation_history,
                        speak_callback=self.speak,
                        auto_narrate=True,
                        ocr_enabled=True
                    )
                    self.speak("I'll now try to read any text I see through the camera.")
                    time.sleep(2)
                else:
                    self.camera_manager.enable_ocr(True)
                    self.camera_manager.set_auto_narrate(True, self.speak)
                    self.speak("I'll now try to read any text I see through the camera.")
                
                ocr_text = self.camera_manager.get_latest_ocr_text()
                if ocr_text:
                    self.speak(f"I can read the following text: {ocr_text}")
                else:
                    description = self.camera_manager.get_latest_ai_description()
                    if description and "text" in description.lower():
                        self.speak(f"The AI sees some text: {description}")
                    else:
                        self.speak("I don't see any clear text at the moment. I'll let you know if I recognize any text.")
                    
            except Exception as e:
                print(f"Error handling text recognition command: {e}")
                self.speak("I encountered an error while trying to read text from the camera.")
            return

        if any(keyword in user_input.lower() for keyword in narrate_keywords):
            try:
                if not self.camera_manager.is_active:
                    self.speak("I need to turn on the camera first.")
                    started = self.camera_manager.start_camera()
                    if not started:
                        self.speak("I couldn't open the camera.")
                        return
                    self.speak("Camera is now on.")
                
                if not self.camera_manager.is_ai_vision_enabled:
                    self.speak("Enabling my vision capabilities with auto-narration.")
                    self.camera_manager.start_ai_vision(
                        client=self.client, 
                        conversation_history=self.conversation_history,
                        speak_callback=self.speak,
                        auto_narrate=True
                    )
                    self.speak("I'll now automatically describe what I see through the camera.")
                else:
                    self.camera_manager.set_auto_narrate(True, self.speak)
                    self.speak("I'll now automatically describe what I see through the camera.")
                    
            except Exception as e:
                print(f"Error handling auto-narration command: {e}")
                self.speak("I encountered an error while trying to set up auto-narration.")
            return

        if any(keyword in user_input.lower() for keyword in stop_narrate_keywords):
            try:
                if self.camera_manager.is_ai_vision_enabled:
                    self.camera_manager.set_auto_narrate(False)
                    self.speak("I've turned off the auto-narration. I'll stop describing what I see.")
                else:
                    self.speak("I'm not currently narrating anything.")
            except Exception as e:
                print(f"Error handling stop narration command: {e}")
                self.speak("I encountered an error while trying to stop narration.")
            return

        if any(keyword in user_input.lower() for keyword in camera_off_keywords):
            try:
                if self.camera_manager.is_active:
                    self.camera_manager.stop_camera()
                    self.speak("I've turned off the camera.")
                else:
                    self.speak("The camera is already off.")
            except Exception as e:
                print(f"Error handling camera command: {e}")
                self.speak("I encountered an error while trying to close the camera.")
            return

        if any(keyword in user_input.lower() for keyword in notepad_keywords):
            success = self.open_notepad()
            if success:
                self.speak("I've opened Notepad for you.")
            else:
                self.speak("I had trouble opening Notepad.")
            return

        if "camera" in user_input.lower() or "see" in user_input.lower():
            try:
                if not self.camera_manager.is_active:
                    self.speak("The camera is not active. Let me turn it on for you.")
                    started = self.camera_manager.start_camera()
                    if not started:
                        self.speak("I couldn't open the camera.")
                        return
                    self.speak("The camera is now on.")
                
                if not self.camera_manager.is_ai_vision_enabled:
                    self.speak("Activating AI Vision to analyze the camera feed.")
                    self.camera_manager.start_ai_vision(self.client, self.conversation_history)
                    time.sleep(2)
                
                description = self.camera_manager.get_latest_ai_description()
                if description:
                    self.speak(f"Here's what I see: {description}")
                else:
                    self.speak("I'm still processing the camera feed. Please ask me again in a moment.")
            except Exception as e:
                print(f"Error handling camera or vision command: {e}")
                self.speak("I encountered an error while trying to use the camera or AI Vision.")
            return

        if "what do you see" in user_input.lower() or "describe" in user_input.lower():
            try:
                description = self.camera_manager.get_latest_ai_description()
                if description:
                    self.speak(f"Here's what I see: {description}")
                else:
                    self.speak("I'm still processing the camera feed. Please ask me again in a moment.")
            except Exception as e:
                print(f"Error handling description request: {e}")
                self.speak("I encountered an error while trying to describe the camera feed.")
            return

        self.conversation_history.append({"role": "user", "content": user_input})
        
        try:
            if self.use_elevenlabs and hasattr(self, 'waiting_sounds'):
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
        print_banner()
        print_system_info()
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
