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
from ..waiting_sounds import WaitingSounds

try:
    import pyautogui
    HAVE_PYAUTOGUI = True
except ImportError:
    HAVE_PYAUTOGUI = False
    print("PyAutoGUI not available. Some fallback methods will be disabled.")

try:
    import soundfile as sf
    import sounddevice as sd
    HAVE_SOUND_LIBS = True
except ImportError:
    HAVE_SOUND_LIBS = False
    print("Sound libraries not available. Audio feedback will be disabled.")

PROJECT_ROOT = Path(__file__).parent.parent

# Utility functions for Notepad window handling
def ensure_notepad_window(instance, max_retries=3):
    """Ensures Notepad window is open and in the foreground. Returns (success, hwnd)"""
    for attempt in range(max_retries):
        try:
            if not hasattr(instance, 'notepad_hwnd') or instance.notepad_hwnd is None or not win32gui.IsWindow(instance.notepad_hwnd):
                if not hasattr(instance, 'open_notepad') or not instance.open_notepad():
                    if attempt == max_retries - 1:
                        return False, None
                    continue
            else:
                win32gui.ShowWindow(instance.notepad_hwnd, win32con.SW_RESTORE)
                win32gui.SetForegroundWindow(instance.notepad_hwnd)
                time.sleep(0.5)
            return True, instance.notepad_hwnd
        except Exception as e:
            print(f"Attempt {attempt + 1} to ensure Notepad window failed: {str(e)}")
            time.sleep(0.5)
            
            # Last attempt, try opening a new Notepad instance
            if attempt == max_retries - 1:
                try:
                    subprocess.Popen(['notepad.exe'])
                    time.sleep(1.0)
                    return True, win32gui.FindWindow("Notepad", None)
                except Exception as fallback_error:
                    print(f"Fallback Notepad launch failed: {str(fallback_error)}")
                    return False, None
    
    return False, None

def safe_send_keys(shell, text, retries=3, chunk_size=10):
    for attempt in range(retries):
        try:
            for i in range(0, len(text), chunk_size):
                chunk = text[i:i+chunk_size]
                shell.SendKeys(chunk)
                time.sleep(0.3)
            return True
        except Exception as e:
            print(f"SendKeys attempt {attempt+1} failed: {str(e)}")
            if attempt == retries - 1:
                return False
            time.sleep(1.0)
    return False

def write_to_notepad_clipboard(text):
    try:
        original_clipboard = None
        try:
            win32clipboard.OpenClipboard()
            if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_UNICODETEXT):
                original_clipboard = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
            win32clipboard.CloseClipboard()
        except Exception as e:
            print(f"Failed to backup clipboard: {str(e)}")
        
        try:
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardText(text, win32clipboard.CF_UNICODETEXT)
            win32clipboard.CloseClipboard()
        except Exception as e:
            print(f"Failed to set clipboard: {str(e)}")
            return False
        
        shell = win32com.client.Dispatch("WScript.Shell")
        shell.SendKeys("^a")
        time.sleep(0.3)
        shell.SendKeys("^v")
        time.sleep(0.5)
        
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
    if not HAVE_PYAUTOGUI:
        return False
        
    try:
        pyautogui.PAUSE = 0.7
        pyautogui.hotkey('ctrl', 'a')
        time.sleep(0.5)
        pyautogui.press('delete')
        time.sleep(0.5)
        
        chunk_size = 20
        for i in range(0, len(text), chunk_size):
            chunk = text[i:i+chunk_size]
            pyautogui.write(chunk, interval=0.02)
            time.sleep(0.4)
            
        return True
    except Exception as e:
        print(f"PyAutoGUI writing failed: {str(e)}")
        return False

def write_using_temp_file(text, notepad_hwnd):
    try:
        temp_file = os.path.join(os.environ['TEMP'], f'liam_notepad_content_{int(time.time())}.txt')
        with open(temp_file, 'w', encoding='utf-8') as f:
            f.write(text)
            
        if notepad_hwnd and win32gui.IsWindow(notepad_hwnd):
            try:
                win32gui.PostMessage(notepad_hwnd, win32con.WM_CLOSE, 0, 0)
                time.sleep(1.5)
            except Exception as e:
                print(f"Error closing Notepad: {str(e)}")
                
        subprocess.Popen(['notepad.exe', temp_file])
        time.sleep(1.0)
        return True
    except Exception as e:
        print(f"Temp file method failed: {str(e)}")
        return False

def write_content_to_notepad(content, notepad_hwnd=None):
    methods_tried = []
    
    try:
        try:
            shell = win32com.client.Dispatch("WScript.Shell")
            shell.SendKeys("^a")
            time.sleep(0.3)
            shell.SendKeys("{DELETE}")
            time.sleep(0.3)
            
            if safe_send_keys(shell, content, retries=4, chunk_size=10):
                return True
            methods_tried.append("WScript.Shell")
        except Exception as e:
            print(f"Error writing to Notepad with WScript.Shell: {str(e)}")
            methods_tried.append("WScript.Shell (failed)")
        
        try:
            if write_to_notepad_clipboard(content):
                return True
            methods_tried.append("Clipboard")
        except Exception as e:
            print(f"Error writing to Notepad with clipboard: {str(e)}")
            methods_tried.append("Clipboard (failed)")
        
        try:
            if HAVE_PYAUTOGUI and write_with_pyautogui(content):
                return True
            methods_tried.append("PyAutoGUI")
        except Exception as e:
            print(f"Error writing to Notepad with PyAutoGUI: {str(e)}")
            methods_tried.append("PyAutoGUI (failed)")
        
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
    waiting_thread = None
    if getattr(self, 'use_elevenlabs', False) and hasattr(self, 'waiting_sounds'):
        waiting_thread = self.waiting_sounds.play_single_waiting_sound()

    def ensure_notepad_foreground():
        sound_thread = None
        if getattr(self, 'use_elevenlabs', False) and hasattr(self, 'waiting_sounds'):
            sound_thread = self.waiting_sounds.play_single_waiting_sound()
            
        if not hasattr(self, 'notepad_hwnd') or self.notepad_hwnd is None or not win32gui.IsWindow(self.notepad_hwnd):
            if not hasattr(self, 'open_notepad') or not self.open_notepad():
                self.speak("Could not open Notepad")
                return False
        else:
            try:
                win32gui.ShowWindow(self.notepad_hwnd, win32con.SW_RESTORE)
                win32gui.SetForegroundWindow(self.notepad_hwnd)
                time.sleep(0.7)
            except Exception as e:
                print(f"Error bringing Notepad to foreground: {str(e)}")
                if hasattr(self, 'open_notepad'):
                    self.open_notepad()
                else:
                    subprocess.Popen(['notepad.exe'])
                    time.sleep(1.0)
        
        if sound_thread:
            sound_thread.join(timeout=2.0)
            
        return True

    def extract_topic(user_input):
        topic_match = None
        
        if "about" in user_input.lower():
            topic_index = user_input.lower().find("about")
            if topic_index != -1:
                topic_match = user_input[topic_index + 6:].strip()
                
        if not topic_match and "on" in user_input.lower():
            topic_index = user_input.lower().find("on")
            if topic_index != -1 and topic_index + 3 < len(user_input):
                potential_topic = user_input[topic_index + 3:].strip()
                if len(potential_topic) > 2:
                    topic_match = potential_topic
                    
        return topic_match

    def generate_content(topic, is_append=False):
        try:
            model_name = "openai/gpt-4o" if os.environ.get("GITHUB_TOKEN") else "gpt-4o"
            
            if is_append:
                system_message = "You are Liam, an AI assistant. Generate a paragraph of additional information about the requested topic. The content should be suitable to append to an existing document - clear, concise, and informative. Keep it under 200 words."
                user_message = f"Write a paragraph with additional information about {topic}."
                max_tokens = 400
            else:
                system_message = "You are Liam, an AI assistant. Generate informative, well-structured content about the requested topic. The content should be suitable for a Notepad document - clear, concise, and informative. Include a title and organize with paragraphs. Keep it under 500 words."
                user_message = f"Write a short document about {topic}."
                max_tokens = 800
            
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

    if mode == "write":
        topic_match = extract_topic(user_input)
        if topic_match:
            self.speak(f"I'll write about {topic_match} in Notepad.")
            
            generated_content = generate_content(topic_match)
            if not generated_content:
                self.speak(f"I had trouble generating content about {topic_match}.")
                return True
                
            if not ensure_notepad_foreground():
                return True
            
            success = False
            try:
                print("Trying built-in write_to_notepad method...")
                if hasattr(self, 'write_to_notepad'):
                    success = self.write_to_notepad(generated_content)
            except Exception as e:
                print(f"Error writing to Notepad with built-in method: {str(e)}")
            
            if not success:
                print("Trying enhanced write_content_to_notepad function...")
                success = write_content_to_notepad(generated_content, getattr(self, 'notepad_hwnd', None))
                
            if success:
                self.speak(f"I've written about {topic_match} in Notepad.")
            else:
                self.speak("I had trouble writing to Notepad.")
                
            return True
        return False

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
            
        self.speak(f"I'll write about {topic} in Notepad.")
        
        generated_content = generate_content(topic)
        if not generated_content:
            self.speak(f"I had trouble generating content about {topic}.")
            return True
            
        if not ensure_notepad_foreground():
            return True
            
        success = False
        try:
            if hasattr(self, 'write_to_notepad'):
                success = self.write_to_notepad(generated_content)
        except Exception as e:
            print(f"Error with built-in write method: {str(e)}")
        
        if not success:
            success = write_content_to_notepad(generated_content, getattr(self, 'notepad_hwnd', None))
        
        if success:
            self.speak(f"I've written about {topic} in Notepad.")
        else:
            self.speak("I had trouble writing to Notepad.")
            
        return True

    if mode == "append":
        topic_match = extract_topic(user_input)
        if topic_match:
            self.speak(f"I'll add information about {topic_match} to Notepad.")
            
            generated_content = generate_content(topic_match, is_append=True)
            if not generated_content:
                self.speak(f"I had trouble generating content about {topic_match}.")
                return True
                
            if not ensure_notepad_foreground():
                return True
                
            success = False
            try:
                if hasattr(self, 'append_to_notepad'):
                    success = self.append_to_notepad(generated_content)
            except Exception as e:
                print(f"Built-in append failed: {str(e)}")
            
            if not success:
                try:
                    shell = win32com.client.Dispatch("WScript.Shell")
                    shell.SendKeys("^{END}")
                    time.sleep(0.3)
                    shell.SendKeys("{ENTER}{ENTER}")
                    time.sleep(0.3)
                    
                    success = safe_send_keys(shell, generated_content, retries=4, chunk_size=10)
                        
                    if not success and HAVE_PYAUTOGUI:
                        pyautogui.hotkey('ctrl', 'end')
                        time.sleep(0.3)
                        pyautogui.press('enter', presses=2)
                        time.sleep(0.3)
                        
                        chunk_size = 20
                        for i in range(0, len(generated_content), chunk_size):
                            chunk = generated_content[i:i+chunk_size]
                            pyautogui.write(chunk, interval=0.02)
                            time.sleep(0.4)
                            
                        success = True
                        
                except Exception as e:
                    print(f"Append fallbacks failed: {str(e)}")
                    success = False
                
            if success:
                self.speak(f"I've added information about {topic_match} to Notepad.")
            else:
                self.speak(f"I had trouble adding content about {topic_match} to Notepad.")
                
            return True
        return False

    if mode == "remove" or "remove" in user_input.lower() or "clear" in user_input.lower():
        if ensure_notepad_foreground():
            success = False
            
            try:
                if hasattr(self, 'clear_notepad'):
                    success = self.clear_notepad()
            except Exception as e:
                print(f"Built-in clear failed: {str(e)}")
                
            if not success:
                try:
                    shell = win32com.client.Dispatch("WScript.Shell")
                    shell.SendKeys("^a")
                    time.sleep(0.3)
                    shell.SendKeys("{DELETE}")
                    time.sleep(0.3)
                    
                    success = True
                except Exception as e:
                    print(f"Clear fallback failed: {str(e)}")
                    
                    if not success and HAVE_PYAUTOGUI:
                        try:
                            pyautogui.hotkey('ctrl', 'a')
                            time.sleep(0.5)
                            pyautogui.press('delete')
                            success = True
                        except Exception as e:
                            print(f"PyAutoGUI clear failed: {str(e)}")
            
            if success:
                self.speak("I've cleared the Notepad content.")
            else:
                self.speak("I had trouble clearing the Notepad content.")
        else:
            self.speak("Could not open Notepad")
            
        return True
        
    return False
