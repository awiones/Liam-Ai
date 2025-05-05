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

    @property
    def is_active(self) -> bool:
        """Property to check if camera is currently active"""
        return self.camera_active

    @property
    def is_analyzing(self) -> bool:
        """Property to check if analysis is currently running"""
        return self.analysis_active

    def start_camera(self, with_analysis: bool = False):
        """Start the camera in a separate thread"""
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
        """Camera display loop running in separate thread"""
        print("DEBUG: Entered camera loop.")
        while self.camera_active and self.camera.isOpened():
            ret, frame = self.camera.read()
            if ret:
                # Store the current frame for analysis
                with self.frame_lock:
                    self.current_frame = frame.copy()
                
                # If analysis is active, draw face boxes and info
                display_frame = frame.copy()
                if self.display_with_analysis:
                    display_frame = self._draw_analysis_on_frame(display_frame)
                
                # Display the frame
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
