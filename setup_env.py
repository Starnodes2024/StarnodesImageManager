#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Virtual environment setup script for StarImageBrowse
Creates and configures a Python virtual environment with all required dependencies.
"""

import os
import subprocess
import sys
import platform

def setup_virtual_environment():
    """Set up a virtual environment for the application."""
    print("StarImageBrowse Environment Setup")
    print("=================================")
    
    # Create virtual environment if it doesn't exist
    venv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "venv")
    if not os.path.exists(venv_path):
        print("Creating virtual environment...")
        try:
            subprocess.check_call([sys.executable, "-m", "venv", venv_path])
            print("Virtual environment created successfully.")
        except subprocess.CalledProcessError as e:
            print(f"Error creating virtual environment: {e}")
            return False
    else:
        print("Virtual environment already exists.")
    
    # Determine the pip executable path
    if platform.system() == "Windows":  # Windows
        pip_path = os.path.join(venv_path, "Scripts", "pip.exe")
        python_path = os.path.join(venv_path, "Scripts", "python.exe")
    else:  # Unix/Linux/Mac
        pip_path = os.path.join(venv_path, "bin", "pip")
        python_path = os.path.join(venv_path, "bin", "python")
    
    # Upgrade pip
    print("Upgrading pip...")
    try:
        subprocess.check_call([pip_path, "install", "--upgrade", "pip"])
    except subprocess.CalledProcessError as e:
        print(f"Error upgrading pip: {e}")
    
    # Install required packages
    print("Installing dependencies...")
    requirements = [
        "pillow",          # Image processing
        "pyqt6",           # GUI framework
        "watchdog",        # File system monitoring
        "torch",           # Deep learning framework (for AI model)
        "transformers",    # Hugging Face transformers for the AI model
        "numpy",           # Numerical processing
        "sqlalchemy",      # Database ORM
    ]
    
    for package in requirements:
        print(f"Installing {package}...")
        try:
            subprocess.check_call([pip_path, "install", package])
        except subprocess.CalledProcessError as e:
            print(f"Error installing {package}: {e}")
    
    # Create requirements.txt file
    print("Creating requirements.txt file...")
    with open("requirements.txt", "w") as f:
        for package in requirements:
            f.write(f"{package}\n")
    
    print("\nEnvironment setup complete!")
    print("\nTo activate the virtual environment:")
    if platform.system() == "Windows":
        print(f"    {venv_path}\\Scripts\\activate")
    else:
        print(f"    source {venv_path}/bin/activate")
    
    return True

if __name__ == "__main__":
    setup_virtual_environment()
