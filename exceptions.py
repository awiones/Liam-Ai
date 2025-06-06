"""
Custom exceptions for Liam AI Assistant.
"""

class LiamAIException(Exception):
    """Base exception for Liam AI."""
    pass

class ConfigurationError(LiamAIException):
    """Raised when there's a configuration error."""
    pass

class APIKeyError(LiamAIException):
    """Raised when API key is invalid or missing."""
    pass

class CameraError(LiamAIException):
    """Raised when camera operations fail."""
    pass

class AudioError(LiamAIException):
    """Raised when audio operations fail."""
    pass

class NotepadError(LiamAIException):
    """Raised when Notepad operations fail."""
    pass

class PlatformNotSupportedError(LiamAIException):
    """Raised when trying to use platform-specific features on unsupported platforms."""
    pass

class InputValidationError(LiamAIException):
    """Raised when user input validation fails."""
    pass

class AIServiceError(LiamAIException):
    """Raised when AI service calls fail."""
    pass