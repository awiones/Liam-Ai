
def handle_notepad_ai(self, user_input, mode="write"):
    """
    Handles AI-powered Notepad writing/appending for Liam.
    mode: "write" (write in/to notepad), "write_explicit" (write about/on), "append" (add/append to notepad), "remove" (clear notepad)
    Returns True if handled, False if fallback to manual input is needed.
    """
    import os
    import time
    import win32gui
    import win32con
    import win32com.client

    def ensure_notepad_foreground():
        # Always use the currently open Notepad window if available,
        # only open a new one if none is open.
        if self.notepad_hwnd is None or not win32gui.IsWindow(self.notepad_hwnd):
            if not self.open_notepad():
                self.speak("Could not open Notepad")
                return False
        else:
            # Bring existing Notepad window to front
            win32gui.ShowWindow(self.notepad_hwnd, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(self.notepad_hwnd)
            time.sleep(0.5)
        return True

    # --- Write in/to Notepad with topic ---
    if mode == "write":
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
        if topic_match:
            self.speak(f"I'll write about {topic_match} in Notepad.")
            try:
                model_name = "openai/gpt-4o" if os.environ.get("GITHUB_TOKEN") else "gpt-4o"
                response = self.client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {
                            "role": "system", 
                            "content": "You are Liam, an AI assistant. Generate informative, well-structured content about the requested topic. The content should be suitable for a Notepad document - clear, concise, and informative. Include a title and organize with paragraphs. Keep it under 500 words."
                        },
                        {
                            "role": "user",
                            "content": f"Write a short document about {topic_match}."
                        }
                    ],
                    max_tokens=800
                )
                generated_content = response.choices[0].message.content
                
                # First ensure Notepad is open and in foreground
                if not ensure_notepad_foreground():
                    self.speak("Could not open Notepad")
                    return True
                
                # Then write to it - use direct SendKeys approach for reliability
                shell = win32com.client.Dispatch("WScript.Shell")
                
                # Clear existing content
                shell.SendKeys("^a")  # Ctrl+A to select all
                time.sleep(0.1)
                shell.SendKeys("{DELETE}")  # Delete selected text
                time.sleep(0.1)
                
                # Write content in chunks
                chunk_size = 50  # Smaller chunks for more reliability
                for i in range(0, len(generated_content), chunk_size):
                    chunk = generated_content[i:i+chunk_size]
                    shell.SendKeys(chunk)
                    time.sleep(0.1)  # Slightly longer delay between chunks
                
                self.speak(f"I've written about {topic_match} in Notepad.")
            except Exception as e:
                print(f"ERROR: Content generation error: {str(e)}")
                self.speak(f"I had trouble generating content about {topic_match}.")
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
            
        self.speak(f"I'll write about {topic} in Notepad.")
        
        # First ensure Notepad is open and in foreground
        if not ensure_notepad_foreground():
            self.speak("Could not open Notepad")
            return True
            
        try:
            model_name = "openai/gpt-4o" if os.environ.get("GITHUB_TOKEN") else "gpt-4o"
            response = self.client.chat.completions.create(
                model=model_name,
                messages=[
                    {
                        "role": "system", 
                        "content": "You are Liam, an AI assistant. Generate informative, well-structured content about the requested topic. The content should be suitable for a Notepad document - clear, concise, and informative. Include a title and organize with paragraphs. Keep it under 500 words."
                    },
                    {
                        "role": "user",
                        "content": f"Write a short document about {topic}."
                    }
                ],
                max_tokens=800
            )
            generated_content = response.choices[0].message.content
            # Direct SendKeys approach for reliability
            shell = win32com.client.Dispatch("WScript.Shell")
            
            # Clear existing content
            shell.SendKeys("^a")  # Ctrl+A to select all
            time.sleep(0.1)
            shell.SendKeys("{DELETE}")  # Delete selected text
            time.sleep(0.1)
            
            # Write content in chunks
            chunk_size = 50  # Smaller chunks for more reliability
            for i in range(0, len(generated_content), chunk_size):
                chunk = generated_content[i:i+chunk_size]
                shell.SendKeys(chunk)
                time.sleep(0.1)  # Slightly longer delay between chunks
            
            self.speak(f"I've written about {topic} in Notepad.")
        except Exception as e:
            print(f"ERROR: Content generation error: {str(e)}")
            self.speak(f"I had trouble generating content about {topic}.")
        return True

    # --- Append to Notepad with topic ---
    if mode == "append":
        topic_match = None
        if "about" in user_input.lower():
            topic_index = user_input.lower().find("about")
            if topic_index != -1:
                topic_match = user_input[topic_index + 6:].strip()
        if topic_match:
            self.speak(f"I'll add information about {topic_match} to Notepad.")
            try:
                model_name = "openai/gpt-4o" if os.environ.get("GITHUB_TOKEN") else "gpt-4o"
                response = self.client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {
                            "role": "system", 
                            "content": "You are Liam, an AI assistant. Generate a paragraph of additional information about the requested topic. The content should be suitable to append to an existing document - clear, concise, and informative. Keep it under 200 words."
                        },
                        {
                            "role": "user",
                            "content": f"Write a paragraph with additional information about {topic_match}."
                        }
                    ],
                    max_tokens=400
                )
                generated_content = response.choices[0].message.content
                
                # First ensure Notepad is open and in foreground
                if not ensure_notepad_foreground():
                    self.speak("Could not open Notepad")
                    return True
                    
                # Direct SendKeys approach for reliability
                shell = win32com.client.Dispatch("WScript.Shell")
                
                # Move to end of document
                shell.SendKeys("^{END}")  # Ctrl+End to move to end
                time.sleep(0.1)
                
                # Add two newlines before appending
                shell.SendKeys("{ENTER}{ENTER}")
                time.sleep(0.1)
                
                # Write content in chunks
                chunk_size = 50  # Smaller chunks for more reliability
                for i in range(0, len(generated_content), chunk_size):
                    chunk = generated_content[i:i+chunk_size]
                    shell.SendKeys(chunk)
                    time.sleep(0.1)  # Slightly longer delay between chunks
                
                self.speak(f"I've added information about {topic_match} to Notepad.")
            except Exception as e:
                print(f"ERROR: Content generation error: {str(e)}")
                self.speak(f"I had trouble generating content about {topic_match}.")
            return True
        return False

    # --- Remove/Clear Notepad content ---
    if mode == "remove" or "remove" in user_input.lower() or "clear" in user_input.lower():
        # If user asks to remove or clear, clear the current Notepad window
        if ensure_notepad_foreground():
            # Direct SendKeys approach for reliability
            shell = win32com.client.Dispatch("WScript.Shell")
            
            # Clear existing content
            shell.SendKeys("^a")  # Ctrl+A to select all
            time.sleep(0.1)
            shell.SendKeys("{DELETE}")  # Delete selected text
            time.sleep(0.1)
            
            self.speak("I've cleared the Notepad content.")
        else:
            self.speak("Could not open Notepad")
        return True
