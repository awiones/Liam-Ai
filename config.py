"""
Configuration management for Liam AI Assistant.
"""

import os
import json
import platform
from typing import Dict, Any, Optional
from pathlib import Path

class LiamConfig:
    """Configuration manager for Liam AI with validation and defaults."""
    
    DEFAULT_CONFIG = {
        "audio": {
            "speech_rate": 150,
            "volume": 0.9,
            "voice_index": 1,
            "use_elevenlabs": True,
            "elevenlabs_voice": "Brian",
            "elevenlabs_model": "eleven_multilingual_v2",
            "speak_with_pauses": True
        },
        "camera": {
            "default_width": 640,
            "default_height": 480,
            "default_fps": 30,
            "ai_vision_interval": 3.0,
            "narration_interval": 6.0,
            "max_analysis_errors": 5
        },
        "ai": {
            "max_tokens": 150,
            "conversation_history_limit": 20,
            "github_model": "openai/gpt-4o",
            "openai_model": "gpt-4o"
        },
        "system": {
            "log_level": "INFO",
            "enable_waiting_sounds": True,
            "notepad_retry_attempts": 3,
            "command_timeout": 30
        },
        "security": {
            "max_input_length": 1000,
            "sanitize_inputs": True,
            "log_commands": True
        }
    }
    
    def __init__(self, config_file: Optional[str] = None):
        """Initialize configuration manager."""
        self.config_file = config_file or self._get_default_config_path()
        self.config = self.DEFAULT_CONFIG.copy()
        self.load_config()
    
    def _get_default_config_path(self) -> str:
        """Get the default configuration file path."""
        return os.path.join(os.path.dirname(__file__), "liam_config.json")
    
    def load_config(self) -> None:
        """Load configuration from file, creating defaults if needed."""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    user_config = json.load(f)
                    self._merge_config(user_config)
            else:
                # Create default config file
                self.save_config()
        except Exception as e:
            print(f"Warning: Could not load config file {self.config_file}: {e}")
            print("Using default configuration.")
    
    def _merge_config(self, user_config: Dict[str, Any]) -> None:
        """Merge user configuration with defaults."""
        for section, values in user_config.items():
            if section in self.config and isinstance(values, dict):
                self.config[section].update(values)
            else:
                self.config[section] = values
    
    def save_config(self) -> bool:
        """Save current configuration to file."""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=4)
            return True
        except Exception as e:
            print(f"Error saving config file {self.config_file}: {e}")
            return False
    
    def get(self, section: str, key: str, default: Any = None) -> Any:
        """Get a configuration value."""
        return self.config.get(section, {}).get(key, default)
    
    def set(self, section: str, key: str, value: Any) -> None:
        """Set a configuration value."""
        if section not in self.config:
            self.config[section] = {}
        self.config[section][key] = value
    
    def get_audio_config(self) -> Dict[str, Any]:
        """Get audio configuration."""
        return self.config.get("audio", {})
    
    def get_camera_config(self) -> Dict[str, Any]:
        """Get camera configuration."""
        return self.config.get("camera", {})
    
    def get_ai_config(self) -> Dict[str, Any]:
        """Get AI configuration."""
        return self.config.get("ai", {})
    
    def get_system_config(self) -> Dict[str, Any]:
        """Get system configuration."""
        return self.config.get("system", {})
    
    def get_security_config(self) -> Dict[str, Any]:
        """Get security configuration."""
        return self.config.get("security", {})
    
    def validate_config(self) -> bool:
        """Validate configuration values."""
        try:
            # Validate audio settings
            audio = self.get_audio_config()
            if not (50 <= audio.get("speech_rate", 150) <= 300):
                print("Warning: speech_rate should be between 50 and 300")
            
            if not (0.0 <= audio.get("volume", 0.9) <= 1.0):
                print("Warning: volume should be between 0.0 and 1.0")
            
            # Validate camera settings
            camera = self.get_camera_config()
            if camera.get("ai_vision_interval", 3.0) < 1.0:
                print("Warning: ai_vision_interval should be at least 1.0 seconds")
            
            # Validate security settings
            security = self.get_security_config()
            if security.get("max_input_length", 1000) < 100:
                print("Warning: max_input_length should be at least 100 characters")
            
            return True
        except Exception as e:
            print(f"Configuration validation error: {e}")
            return False
    
    def reset_to_defaults(self) -> None:
        """Reset configuration to defaults."""
        self.config = self.DEFAULT_CONFIG.copy()
        self.save_config()
    
    def __str__(self) -> str:
        """String representation of configuration."""
        return json.dumps(self.config, indent=2)

# Global configuration instance
config = LiamConfig()