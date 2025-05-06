import cv2
import time
import base64
import threading
import traceback
from typing import Optional, Dict, List, Any
import numpy as np
from PIL import Image
import io
import sys

class CameraManager:
    def __init__(self):
        self.camera: Optional[cv2.VideoCapture] = None
        self.camera_active: bool = False
        self.camera_thread: Optional[threading.Thread] = None
        self.analysis_active: bool = False
        self.analysis_thread: Optional[threading.Thread] = None
        self.current_frame: Optional[np.ndarray] = None
        self.frame_lock = threading.Lock()
        self.last_analysis: Optional[Dict[str, Any]] = None
        self.analysis_interval: float = 1.0  # seconds between analyses
        self.analysis_error_count: int = 0
        self.max_analysis_errors: int = 5  # Stop analysis after this many consecutive errors
        self.face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        self.display_with_analysis: bool = False
        self.ai_vision_enabled: bool = False
        self.ai_vision_thread: Optional[threading.Thread] = None
        self.ai_vision_interval: float = 3.0  # seconds between sending frames to AI
        self.last_ai_frame_time: float = 0
        self.auto_narrate: bool = False
        self.speak_callback = None
        self.last_spoken_description = ""
        self.narration_interval: float = 6.0  # seconds between narrations
        self.last_narration_time: float = 0

    @property
    def is_active(self) -> bool:
        return self.camera_active

    @property
    def is_analyzing(self) -> bool:
        return self.analysis_active

    @property
    def is_ai_vision_enabled(self) -> bool:
        return self.ai_vision_enabled

    def start_camera(self, with_analysis: bool = False):
        if self.camera_active:
            print("DEBUG: Camera already active.")
            return False

        print("DEBUG: Attempting to open camera...")
        
        if self.camera:
            self.camera.release()
            
        camera_opened = False
        for camera_index in range(3):
            try:
                self.camera = cv2.VideoCapture(camera_index)
                if self.camera.isOpened():
                    camera_opened = True
                    print(f"DEBUG: Successfully opened camera at index {camera_index}")
                    break
                else:
                    self.camera.release()
            except Exception as e:
                print(f"DEBUG: Failed to open camera at index {camera_index}: {str(e)}")
                
        self.camera_active = camera_opened
        
        if not camera_opened:
            print("ERROR: Could not open any camera.")
            return False
        
        self.display_with_analysis = with_analysis
        self.camera_thread = threading.Thread(target=self._camera_loop)
        self.camera_thread.daemon = True
        self.camera_thread.start()
        print("DEBUG: Camera thread started.")
        
        return True

    def _camera_loop(self):
        print("DEBUG: Entered camera loop.")
        while self.camera_active and self.camera.isOpened():
            ret, frame = self.camera.read()
            if ret:
                with self.frame_lock:
                    self.current_frame = frame.copy()
                
                display_frame = frame.copy()
                if self.display_with_analysis:
                    display_frame = self._draw_analysis_on_frame(display_frame)
                
                try:
                    cv2.imshow('Liam Camera', display_frame)
                    cv2.waitKey(1)
                except Exception as e:
                    print(f"ERROR: Failed to display frame: {str(e)}")
            else:
                print("ERROR: Failed to read frame from camera.")
                break
        
        if self.camera:
            self.camera.release()
            print("DEBUG: Camera released.")
        cv2.destroyAllWindows()
        print("DEBUG: All OpenCV windows destroyed.")

    def _draw_analysis_on_frame(self, frame):
        if self.last_analysis and 'faces' in self.last_analysis:
            for (x, y, w, h) in self.last_analysis['faces']:
                cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
        
        return frame
    
    def stop_camera(self):
        print("DEBUG: Stopping camera...")
        self.camera_active = False
        
        self.stop_ai_vision()
        
        if self.camera_thread and self.camera_thread.is_alive():
            self.camera_thread.join(timeout=1.0)
            
        return True
    
    def set_auto_narrate(self, enabled: bool, speak_callback=None):
        self.auto_narrate = enabled
        if speak_callback is not None:
            self.speak_callback = speak_callback
        print(f"DEBUG: Auto narration {'enabled' if enabled else 'disabled'}")
        return True
    
    def start_ai_vision(self, client, conversation_history, speak_callback=None, auto_narrate=False):
        if self.ai_vision_enabled:
            print("DEBUG: AI vision already active.")
            return False
            
        if not self.camera_active or not self.camera or not self.camera.isOpened():
            print("ERROR: Cannot start AI vision without an active camera.")
            return False
            
        self.ai_vision_enabled = True
        self.ai_client = client
        self.conversation_history = conversation_history
        
        self.set_auto_narrate(auto_narrate, speak_callback)
        
        self.ai_vision_thread = threading.Thread(target=self._ai_vision_loop)
        self.ai_vision_thread.daemon = True
        self.ai_vision_thread.start()
        print("DEBUG: AI vision thread started.")
        
        return True
    
    def stop_ai_vision(self):
        print("DEBUG: Stopping AI vision...")
        self.ai_vision_enabled = False
        
        if self.ai_vision_thread and self.ai_vision_thread.is_alive():
            self.ai_vision_thread.join(timeout=1.0)
            
        return True
    
    def _ai_vision_loop(self):
        print("DEBUG: Entered AI vision loop.")
        
        while self.ai_vision_enabled and self.camera_active:
            current_time = time.time()
            
            if current_time - self.last_ai_frame_time >= self.ai_vision_interval:
                self.last_ai_frame_time = current_time
                
                try:
                    with self.frame_lock:
                        if self.current_frame is not None:
                            frame = self.current_frame.copy()
                        else:
                            time.sleep(0.1)
                            continue
                    
                    encoded_image = self._encode_frame_for_ai(frame)
                    
                    prompt_text = "What do you see in this image from my camera? Please describe what's happening briefly."
                    
                    vision_message = {
                        "role": "user", 
                        "content": [
                            {
                                "type": "text", 
                                "text": prompt_text
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{encoded_image}"
                                }
                            }
                        ]
                    }
                    
                    temp_conversation = [self.conversation_history[0], vision_message]
                    
                    if hasattr(self.ai_client, 'base_url'):
                        base_url_str = str(self.ai_client.base_url)
                        model_name = "openai/gpt-4o" if "github" in base_url_str or "models.github.ai" in base_url_str else "gpt-4o"
                    else:
                        model_name = "gpt-4o"
                    
                    response = self.ai_client.chat.completions.create(
                        model=model_name,
                        messages=temp_conversation,
                        max_tokens=150
                    )
                    
                    vision_description = response.choices[0].message.content
                    print(f"AI Vision: {vision_description}")
                    
                    if not self.last_analysis:
                        self.last_analysis = {}
                    
                    self.last_analysis['timestamp'] = time.time()
                    self.last_analysis['description'] = vision_description
                    
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    faces = self.face_cascade.detectMultiScale(
                        gray,
                        scaleFactor=1.1,
                        minNeighbors=5,
                        minSize=(30, 30)
                    )
                    self.last_analysis['faces'] = faces
                    
                    if self.auto_narrate and self.speak_callback:
                        if vision_description != self.last_spoken_description:
                            if current_time - self.last_narration_time >= 10:
                                self.speak_callback(f"I see: {vision_description}")
                                self.last_spoken_description = vision_description
                                self.last_narration_time = current_time
                    
                except Exception as e:
                    print(f"ERROR in AI vision loop: {str(e)}")
                    traceback.print_exc()
            
            time.sleep(0.1)
            
        print("DEBUG: Exited AI vision loop.")
    
    def _encode_frame_for_ai(self, frame):
        max_dim = 800
        height, width = frame.shape[:2]
        
        if max(height, width) > max_dim:
            if height > width:
                new_height = max_dim
                new_width = int(width * (max_dim / height))
            else:
                new_width = max_dim
                new_height = int(height * (max_dim / width))
                
            frame = cv2.resize(frame, (new_width, new_height))
        
        success, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if not success:
            raise ValueError("Failed to encode image")
            
        encoded_image = base64.b64encode(buffer).decode('utf-8')
        return encoded_image
    
    def get_latest_ai_description(self):
        if self.last_analysis and 'description' in self.last_analysis:
            return self.last_analysis['description']
        return None