import os
import cv2
import time
import threading
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
from assets import CameraManager, handle_notepad_ai

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
        self.engine = pyttsx3.init()
        
        # Configure voice settings
        self.engine.setProperty('rate', 150)  # Speed of speech
        
        # Get available voices and set a specific voice if requested
        voices = self.engine.getProperty('voices')
        
        # Print available voices for reference
        print("Available voices:")
        for idx, voice in enumerate(voices):
            print(f"Voice {idx}: {voice.name} ({voice.id})")
            print(f"  - Gender: {voice.gender if hasattr(voice, 'gender') else 'Unknown'}")
            print(f"  - Age: {voice.age if hasattr(voice, 'age') else 'Unknown'}")
            print(f"  - Languages: {voice.languages if hasattr(voice, 'languages') else 'Unknown'}")
        
        # Set voice based on index or default to the first voice
        if voice_index is not None and 0 <= voice_index < len(voices):
            self.engine.setProperty('voice', voices[voice_index].id)
            print(f"Using voice: {voices[voice_index].name}")
        else:
            # Try to find a more natural-sounding voice (often the second voice is better)
            # On Windows, voices[1] is often Microsoft David (male) or Microsoft Zira (female)
            default_voice_index = 1 if len(voices) > 1 else 0
            self.engine.setProperty('voice', voices[default_voice_index].id)
            print(f"Using default voice: {voices[default_voice_index].name}")
        
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
        
        print("Liam AI initialized and ready to help!")
        self.speak("Hello, I'm Liam. How can I assist you today?")

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
        
        if self.speak_with_pauses:
            # Split text into sentences for more natural pauses
            sentences = re.split(r'(?<=[.!?])\s+', text)
            for sentence in sentences:
                if sentence.strip():
                    self.engine.say(sentence)
                    self.engine.runAndWait()
                    # Add a tiny pause between sentences
                    time.sleep(0.15)
        else:
            # Original behavior
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
                
        # Camera commands
        if "camera on" in user_input.lower() or "turn on camera" in user_input.lower() or "open camera" in user_input.lower():
            with_analysis = "analyze" in user_input.lower() or "recognition" in user_input.lower() or "detect" in user_input.lower()
            self.speak("Opening the camera now.")
            if self.camera_manager.start_camera(with_analysis=with_analysis):
                if with_analysis:
                    self.speak("Camera is now on with face analysis enabled. I can detect faces, emotions, age, and gender.")
                else:
                    self.speak("Camera is now on and I can access it if you need me to take a photo or describe the scene.")
            else:
                self.speak("I can't access your camera. Please make sure it's connected and not used by another app.")
            return
        elif "start analysis" in user_input.lower() or "begin analysis" in user_input.lower() or "analyze faces" in user_input.lower() or "face analysis" in user_input.lower() or "play analysis" in user_input.lower():
            if not self.camera_manager.is_active:
                self.speak("Camera is not on. Turning it on first.")
                if not self.camera_manager.start_camera():
                    self.speak("Failed to start camera.")
                    return
                time.sleep(1)
            
            self.speak("Starting face analysis. I'll detect faces and show information about age, gender, and emotion.")
            if self.camera_manager.start_analysis():
                self.speak("Face analysis is now active.")
            else:
                self.speak("Face analysis is already running or couldn't be started.")
            return
        elif "stop analysis" in user_input.lower() or "end analysis" in user_input.lower():
            if self.camera_manager.stop_analysis():
                self.speak("Face analysis stopped.")
            else:
                self.speak("Face analysis is not currently running.")
            return
        elif "who do you see" in user_input.lower() or "who is there" in user_input.lower() or "detect people" in user_input.lower():
            if not self.camera_manager.is_active:
                self.speak("Opening the camera with face analysis.")
                if not self.camera_manager.start_camera(with_analysis=True):
                    self.speak("Failed to start camera.")
                    return
                time.sleep(1.5)
            elif not self.camera_manager.is_analyzing:
                self.speak("Starting face analysis.")
                self.camera_manager.start_analysis()
                time.sleep(1.5)
                
            analysis = self.camera_manager.get_latest_analysis()
            if analysis:
                try:
                    if isinstance(analysis, list) and len(analysis) > 0:
                        faces_info = []
                        for face in analysis:
                            gender = face.get('gender', 'unknown')
                            age = face.get('age', 'unknown')
                            emotion = face.get('dominant_emotion', 'neutral')
                            faces_info.append(f"a {age} year old {gender} who appears {emotion}")
                        
                        if faces_info:
                            if len(faces_info) == 1:
                                self.speak(f"I can see {faces_info[0]}.")
                            else:
                                people_list = ", ".join(faces_info[:-1]) + " and " + faces_info[-1]
                                self.speak(f"I can see {len(faces_info)} people: {people_list}.")
                        else:
                            self.speak("I can see faces but couldn't determine details.")
                    else:
                        self.speak("I can see a person but couldn't analyze their details.")
                except Exception as e:
                    print(f"ERROR: Analysis processing error: {str(e)}")
                    self.speak("I detected faces but had trouble processing the analysis.")
            else:
                self.speak("I don't see any people in the camera view right now.")
            return
        elif "camera off" in user_input.lower() or "turn off camera" in user_input.lower() or "close camera" in user_input.lower():
            if self.camera_manager.stop_camera():
                self.speak("Camera turned off.")
            else:
                self.speak("Camera is already off.")
            return
        elif "take photo" in user_input.lower() or "take picture" in user_input.lower() or "capture image" in user_input.lower():
            if not self.camera_manager.is_active:
                self.speak("Camera is not on. Turning it on first.")
                if not self.camera_manager.start_camera():
                    self.speak("Failed to start camera.")
                    return
                time.sleep(1)

            filename = f"liam_photo_{time.strftime('%Y%m%d_%H%M%S')}.jpg"
            if self.camera_manager.take_photo(filename):
                self.speak(f"Photo taken and saved as {filename}")
            else:
                self.speak("Failed to capture image.")
            return
        elif "what do you see" in user_input.lower() or "describe what you see" in user_input.lower() or "what's happening" in user_input.lower() or "what happening" in user_input.lower():
            if not self.camera_manager.is_active:
                self.speak("Opening the camera to see what's happening.")
                if not self.camera_manager.start_camera():
                    self.speak("Failed to start camera.")
                    return
                time.sleep(1.5)

            self.speak("Analyzing what I see...")
            jpg_as_text = self.camera_manager.get_frame_base64()
            
            if jpg_as_text:
                try:
                    model_name = "openai/gpt-4o" if os.environ.get("GITHUB_TOKEN") else "gpt-4o"
                    response = self.client.chat.completions.create(
                        model=model_name,
                        messages=[
                            {
                                "role": "system", 
                                "content": "You are Liam, an AI assistant that can see through a camera. Describe what you see in the image concisely and accurately. Focus on people, activities, objects, and any notable events. Keep your description conversational and helpful."
                            },
                            {
                                "role": "user",
                                "content": [
                                    {"type": "text", "text": "What do you see in this camera feed? Describe what's happening."},
                                    {
                                        "type": "image_url",
                                        "image_url": {"url": f"data:image/jpeg;base64,{jpg_as_text}"}
                                    }
                                ]
                            }
                        ],
                        max_tokens=150
                    )
                    description = response.choices[0].message.content
                    self.speak(description)
                except Exception as e:
                    print(f"ERROR: Vision API error: {str(e)}")
                    self.speak("I can see through the camera, but I'm having trouble analyzing what I see right now.")
            else:
                self.speak("I'm having trouble capturing an image from the camera.")
            return

        # Enhanced Notepad commands with topic generation
        elif "open notepad" in user_input.lower():
            if self.open_notepad():
                self.speak("Notepad is now open.")
            else:
                self.speak("I had trouble opening Notepad.")
            return
        elif "write in notepad" in user_input.lower() or "write to notepad" in user_input.lower():
            # Use helper for AI topic/content
            if handle_notepad_ai(self, user_input, mode="write"):
                return
            # fallback to traditional behavior
            self.speak("What would you like me to write?")
            time.sleep(0.5)
            note_content = self.listen()
            if note_content:
                if self.write_to_notepad(note_content):
                    self.speak("I've written your text in Notepad.")
                else:
                    self.speak("I had trouble writing to Notepad.")
            else:
                self.speak("I couldn't understand what to write.")
            return
        elif "write about" in user_input.lower() or "write on" in user_input.lower():
            if handle_notepad_ai(self, user_input, mode="write_explicit"):
                return
            # fallback if no topic found
            self.speak("I couldn't understand what topic you want me to write about.")
            return
        elif "add to notepad" in user_input.lower() or "append to notepad" in user_input.lower():
            if handle_notepad_ai(self, user_input, mode="append"):
                return
            # fallback to traditional behavior
            self.speak("What would you like me to add?")
            time.sleep(0.5)
            note_content = self.listen()
            if note_content:
                if self.append_to_notepad(note_content):
                    self.speak("I've added your text to Notepad.")
                else:
                    self.speak("I had trouble adding to Notepad.")
            else:
                self.speak("I couldn't understand what to add.")
            return
        elif "clear notepad" in user_input.lower() or "erase notepad" in user_input.lower():
            if self.clear_notepad():
                self.speak("I've cleared the Notepad content.")
            else:
                self.speak("I had trouble clearing Notepad.")
            return
        elif "save notepad" in user_input.lower():
            self.speak("What would you like to name the file?")
            time.sleep(0.5)
            filename = self.listen()
            
            if filename:
                if not filename.lower().endswith('.txt'):
                    filename += '.txt'
                if self.save_notepad(filename):
                    self.speak(f"I've saved the Notepad content as {filename}.")
                else:
                    self.speak("I had trouble saving the Notepad file.")
            else:
                self.speak("I couldn't understand the filename.")
            return
        elif "dictate to notepad" in user_input.lower() or "take dictation" in user_input.lower():
            self.speak("I'm ready to take dictation. Say 'stop dictation' when you're finished.")
            
            # Open Notepad if not already open
            if self.notepad_hwnd is None or not win32gui.IsWindow(self.notepad_hwnd):
                if not self.open_notepad():
                    self.speak("Could not open Notepad")
                    return
            
            dictation_active = True
            while dictation_active:
                dictated_text = self.listen()
                if not dictated_text:
                    continue
                    
                if "stop dictation" in dictated_text.lower() or "end dictation" in dictated_text.lower():
                    dictation_active = False
                    self.speak("Dictation complete.")
                else:
                    if self.append_to_notepad(dictated_text + " "):
                        print(f"Added to notepad: {dictated_text}")
                    else:
                        self.speak("I had trouble adding that to Notepad.")
                        dictation_active = False
            return

        # Add a specific handler for "brighten the notepad" or similar commands
        elif any(phrase in user_input.lower() for phrase in ["brighten the notepad", "right in the notepad", "write in notepad about"]):
            # Extract topic after "about" if present
            topic = None
            if "about" in user_input.lower():
                topic_index = user_input.lower().find("about")
                if topic_index != -1:
                    topic = user_input[topic_index + 6:].strip()
            
            if topic:
                # Create a modified input that handle_notepad_ai can process
                modified_input = f"write about {topic}"
                if handle_notepad_ai(self, modified_input, mode="write_explicit"):
                    return
            
            # Fallback
            self.speak("I couldn't understand what to write in Notepad.")
            return
            
        # Voice commands
        elif "change voice" in user_input.lower() or "switch voice" in user_input.lower():
            voices = self.list_available_voices()
            voice_list = ""
            for v in voices:
                voice_list += f"Voice {v['index']}: {v['name']}\n"
            
            self.speak("Here are the available voices. Which one would you like to use? Please say the number.")
            print("\nAvailable voices:")
            print(voice_list)
            
            time.sleep(0.5)
            voice_choice = self.listen()
            if voice_choice and voice_choice.isdigit():
                voice_index = int(voice_choice)
                if self.change_voice(voice_index):
                    self.speak("I've changed my voice. How does this sound?")
                else:
                    self.speak("That voice number is not available. Please try again with a valid number.")
            else:
                self.speak("I couldn't understand which voice number you want. Please try again.")
            return
        elif "list voices" in user_input.lower() or "show voices" in user_input.lower() or "available voices" in user_input.lower():
            voices = self.list_available_voices()
            self.speak(f"I have {len(voices)} voices available. Here they are:")
            for v in voices:
                print(f"Voice {v['index']}: {v['name']} ({v['gender']})")
            self.speak("You can say 'change voice' to select a different voice.")
            return
        elif "toggle pauses" in user_input.lower() or "toggle speech pauses" in user_input.lower() or "natural pauses" in user_input.lower():
            enabled = self.toggle_speech_pauses()
            if enabled:
                self.speak("Natural speech pauses are now enabled. I'll speak with more natural rhythm and pauses between sentences.")
            else:
                self.speak("Natural speech pauses are now disabled. I'll speak without pauses between sentences.")
            return
            
        # Other application commands
        elif "open browser" in user_input.lower() or "open chrome" in user_input.lower() or "open firefox" in user_input.lower() or "open safari" in user_input.lower():
            self.open_application("browser")
            return
        elif "open terminal" in user_input.lower() or "open command prompt" in user_input.lower() or "open cmd" in user_input.lower():
            self.open_application("terminal")
            return
        elif "write file" in user_input.lower() or "create file" in user_input.lower() or "create document" in user_input.lower():
            self.create_text_file(user_input)
            return
            
        self.conversation_history.append({"role": "user", "content": user_input})
        
        try:
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
