import os
import time
import win32gui
import win32con
import win32com.client
import win32clipboard
import subprocess
import random
import threading
from pathlib import Path
from .waiting_sounds import WaitingSounds

# Try to import pyautogui as an alternative method
try:
    import pyautogui
    HAVE_PYAUTOGUI = True
except ImportError:
    HAVE_PYAUTOGUI = False
    print("PyAutoGUI not available. Some fallback methods will be disabled.")

# Try to import soundfile and sounddevice for audio playback
try:
    import soundfile as sf
    import sounddevice as sd
    HAVE_SOUND_LIBS = True
except ImportError:
    HAVE_SOUND_LIBS = False
    print("Sound libraries not available. Audio feedback will be disabled.")

# Get the project root directory
PROJECT_ROOT = Path(__file__).parent.parent

def safe_send_keys(shell, text, retries=3, chunk_size=10):
    """
    Helper function to safely send keys with retries and smaller chunks
    
    Args:
        shell: WScript.Shell object
        text: Text to send
        retries: Number of retry attempts
        chunk_size: Size of text chunks to send at once
        
    Returns:
        bool: True if successful, False otherwise
    """
    for attempt in range(retries):
        try:
            # Send text in smaller chunks with longer delays for reliability
            for i in range(0, len(text), chunk_size):
                chunk = text[i:i+chunk_size]
                shell.SendKeys(chunk)
                time.sleep(0.3)  # Longer delay between chunks for reliability
            return True
        except Exception as e:
            print(f"SendKeys attempt {attempt+1} failed: {str(e)}")
            if attempt == retries - 1:
                return False
            time.sleep(1.0)  # Longer delay between retries
    return False

def write_to_notepad_clipboard(text):
    """
    Fallback method using clipboard to write text
    
    Args:
        text: Text to write
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Store original clipboard content
        original_clipboard = None
        try:
            win32clipboard.OpenClipboard()
            if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_UNICODETEXT):
                original_clipboard = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
            win32clipboard.CloseClipboard()
        except Exception as e:
            print(f"Failed to backup clipboard: {str(e)}")
            # Continue anyway
        
        # Set new clipboard content
        try:
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardText(text, win32clipboard.CF_UNICODETEXT)
            win32clipboard.CloseClipboard()
        except Exception as e:
            print(f"Failed to set clipboard: {str(e)}")
            return False
        
        # Paste content
        shell = win32com.client.Dispatch("WScript.Shell")
        shell.SendKeys("^a")  # Select all existing text
        time.sleep(0.3)
        shell.SendKeys("^v")  # Paste
        time.sleep(0.5)
        
        # Restore original clipboard if available
        if original_clipboard:
            try:
                win32clipboard.OpenClipboard()
                win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardText(original_clipboard, win32clipboard.CF_UNICODETEXT)
                win32clipboard.CloseClipboard()
            except Exception as e:
                print(f"Failed to restore clipboard: {str(e)}")
        
        return True
    except Exception as e:
        print(f"Clipboard fallback failed: {str(e)}")
        return False

def write_with_pyautogui(text):
    """
    Alternative method using PyAutoGUI for writing text
    
    Args:
        text: Text to write
        
    Returns:
        bool: True if successful, False otherwise
    """
    if not HAVE_PYAUTOGUI:
        return False
        
    try:
        # Increase pause between actions for reliability
        pyautogui.PAUSE = 0.7
        
        # Select all existing text and delete it
        pyautogui.hotkey('ctrl', 'a')
        time.sleep(0.5)
        pyautogui.press('delete')
        time.sleep(0.5)
        
        # Type the new text in smaller chunks with longer pauses
        chunk_size = 20  # Smaller chunks for more reliability
        for i in range(0, len(text), chunk_size):
            chunk = text[i:i+chunk_size]
            pyautogui.write(chunk, interval=0.02)  # Slight delay between characters
            time.sleep(0.4)  # Longer pause between chunks
            
        return True
    except Exception as e:
        print(f"PyAutoGUI writing failed: {str(e)}")
        return False

def write_using_temp_file(text, notepad_hwnd):
    """
    Last resort method - Write to temp file and open in Notepad
    
    Args:
        text: Text to write
        notepad_hwnd: Handle to Notepad window
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Create a temporary file with unique name to avoid conflicts
        temp_file = os.path.join(os.environ['TEMP'], f'liam_notepad_content_{int(time.time())}.txt')
        with open(temp_file, 'w', encoding='utf-8') as f:
            f.write(text)
            
        # Close current Notepad instance if open
        if notepad_hwnd and win32gui.IsWindow(notepad_hwnd):
            try:
                win32gui.PostMessage(notepad_hwnd, win32con.WM_CLOSE, 0, 0)
                time.sleep(1.5)  # Give more time for Notepad to close
            except Exception as e:
                print(f"Error closing Notepad: {str(e)}")
                
        # Open the file with Notepad
        subprocess.Popen(['notepad.exe', temp_file])
        time.sleep(1.0)  # Give time for Notepad to open
        return True
    except Exception as e:
        print(f"Temp file method failed: {str(e)}")
        return False

def write_content_to_notepad(content, notepad_hwnd=None):
    """
    Consolidated function to write content to notepad with multiple fallbacks
    
    Args:
        content: Text content to write
        notepad_hwnd: Handle to Notepad window
        
    Returns:
        bool: True if successful, False otherwise
    """
    # Track success of each method
    methods_tried = []
    
    try:
        # First try: Standard WScript.Shell approach
        try:
            shell = win32com.client.Dispatch("WScript.Shell")
            
            # Clear existing content
            shell.SendKeys("^a")  # Ctrl+A to select all
            time.sleep(0.3)
            shell.SendKeys("{DELETE}")  # Delete selected text
            time.sleep(0.3)
            
            # Try SendKeys with smaller chunks and more retries
            if safe_send_keys(shell, content, retries=4, chunk_size=10):
                return True
            methods_tried.append("WScript.Shell")
        except Exception as e:
            print(f"Error writing to Notepad with WScript.Shell: {str(e)}")
            methods_tried.append("WScript.Shell (failed)")
        
        # Second try: Clipboard method
        try:
            if write_to_notepad_clipboard(content):
                return True
            methods_tried.append("Clipboard")
        except Exception as e:
            print(f"Error writing to Notepad with clipboard: {str(e)}")
            methods_tried.append("Clipboard (failed)")
        
        # Third try: PyAutoGUI if available
        try:
            if HAVE_PYAUTOGUI and write_with_pyautogui(content):
                return True
            methods_tried.append("PyAutoGUI")
        except Exception as e:
            print(f"Error writing to Notepad with PyAutoGUI: {str(e)}")
            methods_tried.append("PyAutoGUI (failed)")
        
        # Last resort: Use temporary file method
        methods_tried.append("Temp file")
        if write_using_temp_file(content, notepad_hwnd):
            return True
            
        print(f"All writing methods failed. Methods tried: {', '.join(methods_tried)}")
        return False
    except Exception as e:
        print(f"Detailed writing error: {str(e)}")
        print(f"Methods tried before failure: {', '.join(methods_tried)}")
        return False

def handle_notepad_ai(self, user_input, mode="write"):
    """
    Handles AI-powered Notepad writing/appending for Liam.
    
    Args:
        self: The Liam instance
        user_input: User's input text
        mode: Operation mode - "write" (write in/to notepad), "write_explicit" (write about/on), 
              "append" (add/append to notepad), "remove" (clear notepad)
              
    Returns:
        bool: True if handled, False if fallback to manual input is needed.
    """
    # Add waiting sound at the start of writing operations
    waiting_thread = None
    if hasattr(self, 'use_elevenlabs') and self.use_elevenlabs and hasattr(self, 'waiting_sounds'):
        waiting_thread = self.waiting_sounds.play_single_waiting_sound()

    def ensure_notepad_foreground():
        """Helper function to ensure Notepad is open and in foreground"""
        # Play waiting sound when opening/focusing Notepad
        sound_thread = None
        if hasattr(self, 'use_elevenlabs') and self.use_elevenlabs and hasattr(self, 'waiting_sounds'):
            sound_thread = self.waiting_sounds.play_single_waiting_sound()
            
        # Always use the currently open Notepad window if available,
        # only open a new one if none is open.
        if not hasattr(self, 'notepad_hwnd') or self.notepad_hwnd is None or not win32gui.IsWindow(self.notepad_hwnd):
            if not hasattr(self, 'open_notepad') or not self.open_notepad():
                self.speak("Could not open Notepad")
                return False
        else:
            # Bring existing Notepad window to front
            try:
                win32gui.ShowWindow(self.notepad_hwnd, win32con.SW_RESTORE)
                win32gui.SetForegroundWindow(self.notepad_hwnd)
                time.sleep(0.7)  # Give more time for window to come to foreground
            except Exception as e:
                print(f"Error bringing Notepad to foreground: {str(e)}")
                # Try to open a new Notepad instance if we can't bring the existing one to foreground
                if hasattr(self, 'open_notepad'):
                    self.open_notepad()
                else:
                    subprocess.Popen(['notepad.exe'])
                    time.sleep(1.0)
        
        # Wait for sound thread to complete if it exists
        if sound_thread:
            sound_thread.join(timeout=2.0)
            
        return True

    # --- Extract topic from user input ---
    def extract_topic(user_input):
        """Helper function to extract topic from user input"""
        topic_match = None
        
        # Check for "about" pattern
        if "about" in user_input.lower():
            topic_index = user_input.lower().find("about")
            if topic_index != -1:
                topic_match = user_input[topic_index + 6:].strip()
                
        # Check for "on" pattern if "about" wasn't found
        if not topic_match and "on" in user_input.lower():
            topic_index = user_input.lower().find("on")
            if topic_index != -1 and topic_index + 3 < len(user_input):
                potential_topic = user_input[topic_index + 3:].strip()
                if len(potential_topic) > 2:  # Ensure it's a meaningful topic
                    topic_match = potential_topic
                    
        return topic_match

    # --- Generate content using OpenAI ---
    def generate_content(topic, is_append=False):
        """Helper function to generate content using OpenAI"""
        try:
            # Determine which model to use
            model_name = "openai/gpt-4o" if os.environ.get("GITHUB_TOKEN") else "gpt-4o"
            
            # Set system message based on whether we're appending or writing new content
            if is_append:
                system_message = "You are Liam, an AI assistant. Generate a paragraph of additional information about the requested topic. The content should be suitable to append to an existing document - clear, concise, and informative. Keep it under 200 words."
                user_message = f"Write a paragraph with additional information about {topic}."
                max_tokens = 400
            else:
                system_message = "You are Liam, an AI assistant. Generate informative, well-structured content about the requested topic. The content should be suitable for a Notepad document - clear, concise, and informative. Include a title and organize with paragraphs. Keep it under 500 words."
                user_message = f"Write a short document about {topic}."
                max_tokens = 800
            
            # Make API call
            response = self.client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_message}
                ],
                max_tokens=max_tokens
            )
            
            return response.choices[0].message.content
        except Exception as e:
            print(f"ERROR: Content generation error: {str(e)}")
            return None

    # --- Write in/to Notepad with topic ---
    if mode == "write":
        topic_match = extract_topic(user_input)
        if topic_match:
            # Fix: Remove the double "in Notepad" in the spoken message
            self.speak(f"I'll write about {topic_match} in Notepad.")
            
            # Generate content
            generated_content = generate_content(topic_match)
            if not generated_content:
                self.speak(f"I had trouble generating content about {topic_match}.")
                return True
                
            # First ensure Notepad is open and in foreground
            if not ensure_notepad_foreground():
                return True
            
            # Try using Liam's built-in write_to_notepad method
            success = False
            try:
                print("Trying built-in write_to_notepad method...")
                if hasattr(self, 'write_to_notepad'):
                    success = self.write_to_notepad(generated_content)
            except Exception as e:
                print(f"Error writing to Notepad with built-in method: {str(e)}")
            
            # If built-in method failed, fallback to our enhanced method
            if not success:
                print("Trying enhanced write_content_to_notepad function...")
                success = write_content_to_notepad(generated_content, getattr(self, 'notepad_hwnd', None))
                
            # Provide feedback to user
            if success:
                self.speak(f"I've written about {topic_match} in Notepad.")
            else:
                self.speak("I had trouble writing to Notepad.")
                
            return True
        return False

    # --- Write about/on (explicit) ---
    if mode == "write_explicit":
        topic = None
        if "write about" in user_input.lower():
            topic_index = user_input.lower().find("write about")
            if topic_index != -1:
                topic = user_input[topic_index + 12:].strip()
        elif "write on" in user_input.lower():
            topic_index = user_input.lower().find("write on")
            if topic_index != -1:
                topic = user_input[topic_index + 9:].strip()
        if not topic:
            return False
            
        # Fix: Remove the double "in Notepad" in the spoken message
        self.speak(f"I'll write about {topic} in Notepad.")
        
        # Generate content
        generated_content = generate_content(topic)
        if not generated_content:
            self.speak(f"I had trouble generating content about {topic}.")
            return True
            
        # First ensure Notepad is open and in foreground
        if not ensure_notepad_foreground():
            return True
            
        # Try built-in method first
        success = False
        try:
            if hasattr(self, 'write_to_notepad'):
                success = self.write_to_notepad(generated_content)
        except Exception as e:
            print(f"Error with built-in write method: {str(e)}")
        
        # Fallback to enhanced method
        if not success:
            success = write_content_to_notepad(generated_content, getattr(self, 'notepad_hwnd', None))
        
        # Provide feedback to user
        if success:
            self.speak(f"I've written about {topic} in Notepad.")
        else:
            self.speak("I had trouble writing to Notepad.")
            
        return True

    # --- Append to Notepad with topic ---
    if mode == "append":
        topic_match = extract_topic(user_input)
        if topic_match:
            self.speak(f"I'll add information about {topic_match} to Notepad.")
            
            # Generate content for appending
            generated_content = generate_content(topic_match, is_append=True)
            if not generated_content:
                self.speak(f"I had trouble generating content about {topic_match}.")
                return True
                
            # First ensure Notepad is open and in foreground
            if not ensure_notepad_foreground():
                return True
                
            # Try built-in append method first
            success = False
            try:
                if hasattr(self, 'append_to_notepad'):
                    success = self.append_to_notepad(generated_content)
            except Exception as e:
                print(f"Built-in append failed: {str(e)}")
            
            # If built-in method failed, try direct approach for append
            if not success:
                try:
                    # Direct SendKeys approach for reliability
                    shell = win32com.client.Dispatch("WScript.Shell")
                    
                    # Move to end of document
                    shell.SendKeys("^{END}")  # Ctrl+End to move to end
                    time.sleep(0.3)
                    
                    # Add two newlines before appending
                    shell.SendKeys("{ENTER}{ENTER}")
                    time.sleep(0.3)
                    
                    # Try standard SendKeys first
                    success = safe_send_keys(shell, generated_content, retries=4, chunk_size=10)
                        
                    # If that fails, try PyAutoGUI if available
                    if not success and HAVE_PYAUTOGUI:
                        pyautogui.hotkey('ctrl', 'end')  # Move to end of document
                        time.sleep(0.3)
                        pyautogui.press('enter', presses=2)  # Add two newlines
                        time.sleep(0.3)
                        
                        # Write in smaller chunks
                        chunk_size = 20
                        for i in range(0, len(generated_content), chunk_size):
                            chunk = generated_content[i:i+chunk_size]
                            pyautogui.write(chunk, interval=0.02)
                            time.sleep(0.4)
                            
                        success = True
                        
                except Exception as e:
                    print(f"Append fallbacks failed: {str(e)}")
                    success = False
                
            # Provide feedback to user
            if success:
                self.speak(f"I've added information about {topic_match} to Notepad.")
            else:
                self.speak(f"I had trouble adding content about {topic_match} to Notepad.")
                
            return True
        return False

    # --- Remove/Clear Notepad content ---
    if mode == "remove" or "remove" in user_input.lower() or "clear" in user_input.lower():
        # If user asks to remove or clear, clear the current Notepad window
        if ensure_notepad_foreground():
            success = False
            
            # Try built-in clear method first
            try:
                if hasattr(self, 'clear_notepad'):
                    success = self.clear_notepad()
            except Exception as e:
                print(f"Built-in clear failed: {str(e)}")
                
            # If built-in method failed, try direct approach
            if not success:
                try:
                    # Direct SendKeys approach for reliability
                    shell = win32com.client.Dispatch("WScript.Shell")
                    
                    # Clear existing content
                    shell.SendKeys("^a")  # Ctrl+A to select all
                    time.sleep(0.3)
                    shell.SendKeys("{DELETE}")  # Delete selected text
                    time.sleep(0.3)
                    
                    success = True
                except Exception as e:
                    print(f"Clear fallback failed: {str(e)}")
                    
                    # Try PyAutoGUI as last resort
                    if not success and HAVE_PYAUTOGUI:
                        try:
                            pyautogui.hotkey('ctrl', 'a')
                            time.sleep(0.5)
                            pyautogui.press('delete')
                            success = True
                        except Exception as e:
                            print(f"PyAutoGUI clear failed: {str(e)}")
            
            # Provide feedback to user
            if success:
                self.speak("I've cleared the Notepad content.")
            else:
                self.speak("I had trouble clearing the Notepad content.")
        else:
            self.speak("Could not open Notepad")
            
        return True
        
    # If we get here, we didn't handle the request
    return False
