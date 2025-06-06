#!/usr/bin/env python3
"""
Setup script for Liam AI Assistant.
"""

import os
import sys
import platform
import subprocess
import shutil
from pathlib import Path

def check_python_version():
    """Check if Python version is compatible."""
    if sys.version_info < (3, 8):
        print("❌ Error: Python 3.8 or higher is required.")
        print(f"Current version: {sys.version}")
        return False
    print(f"✅ Python version: {sys.version}")
    return True

def install_dependencies():
    """Install required dependencies."""
    print("\n📦 Installing dependencies...")
    
    try:
        # Upgrade pip first
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "pip"])
        
        # Install requirements
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        
        # Platform-specific installations
        if platform.system() == "Windows":
            print("🪟 Installing Windows-specific dependencies...")
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", "pipwin"])
                subprocess.check_call([sys.executable, "-m", "pipwin", "install", "pyaudio"])
            except subprocess.CalledProcessError:
                print("⚠️  Warning: Could not install PyAudio via pipwin. You may need to install it manually.")
        
        print("✅ Dependencies installed successfully!")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Error installing dependencies: {e}")
        return False

def create_directories():
    """Create necessary directories."""
    print("\n📁 Creating directories...")
    
    directories = [
        "logs",
        "modules/sounds/waiting",
        "temp"
    ]
    
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
        print(f"✅ Created: {directory}")

def setup_environment():
    """Set up environment configuration."""
    print("\n⚙️  Setting up environment...")
    
    env_file = Path(".env")
    if not env_file.exists():
        print("Creating .env file template...")
        with open(env_file, "w") as f:
            f.write("# Liam AI Configuration\n")
            f.write("# Add your API keys here\n\n")
            f.write("# GitHub Copilot Token (recommended)\n")
            f.write("# GITHUB_TOKEN=your_github_token_here\n\n")
            f.write("# OpenAI API Key (alternative)\n")
            f.write("# OPENAI_API_KEY=your_openai_key_here\n\n")
            f.write("# ElevenLabs API Key (optional, for premium voice)\n")
            f.write("# ELEVENLABS_API_KEY=your_elevenlabs_key_here\n")
        print("✅ Created .env template file")
    else:
        print("✅ .env file already exists")

def check_system_requirements():
    """Check system requirements."""
    print("\n🔍 Checking system requirements...")
    
    # Check for microphone
    try:
        import sounddevice as sd
        devices = sd.query_devices()
        input_devices = [d for d in devices if d['max_input_channels'] > 0]
        if input_devices:
            print("✅ Microphone detected")
        else:
            print("⚠️  Warning: No microphone detected")
    except:
        print("⚠️  Warning: Could not check for microphone")
    
    # Check for camera
    try:
        import cv2
        cap = cv2.VideoCapture(0)
        if cap.isOpened():
            print("✅ Camera detected")
            cap.release()
        else:
            print("⚠️  Warning: No camera detected")
    except:
        print("⚠️  Warning: Could not check for camera")

def create_launcher_script():
    """Create launcher script."""
    print("\n🚀 Creating launcher script...")
    
    if platform.system() == "Windows":
        launcher_content = f"""@echo off
cd /d "{os.getcwd()}"
python main.py
pause
"""
        with open("start_liam.bat", "w") as f:
            f.write(launcher_content)
        print("✅ Created start_liam.bat")
    else:
        launcher_content = f"""#!/bin/bash
cd "{os.getcwd()}"
python3 main.py
"""
        with open("start_liam.sh", "w") as f:
            f.write(launcher_content)
        os.chmod("start_liam.sh", 0o755)
        print("✅ Created start_liam.sh")

def main():
    """Main setup function."""
    print("🤖 Liam AI Assistant Setup")
    print("=" * 40)
    
    # Check Python version
    if not check_python_version():
        return False
    
    # Install dependencies
    if not install_dependencies():
        return False
    
    # Create directories
    create_directories()
    
    # Setup environment
    setup_environment()
    
    # Check system requirements
    check_system_requirements()
    
    # Create launcher script
    create_launcher_script()
    
    print("\n🎉 Setup completed successfully!")
    print("\n📋 Next steps:")
    print("1. Edit the .env file and add your API keys")
    print("2. Run 'python main.py' or use the launcher script")
    print("3. Follow the voice prompts to configure Liam AI")
    
    return True

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n❌ Setup interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Setup failed with error: {e}")
        sys.exit(1)