# STARNODES Image Manager v0.9.5

A modern image browser with AI-powered description generation and search capabilities.

## Overview

STARNODES Image Manager is a Windows application that allows you to manage and search your image collections using AI-generated descriptions. The application scans your selected folders for images, generates thumbnails, and uses Ollama's vision models (like llava) to create descriptions of each image. You can then search your image collection using natural language queries based on these descriptions.

## Features

- **Intelligent Image Scanning**: Scans specified folders for PNG and JPEG images
- **AI-Powered Descriptions**: Uses Ollama's vision models to create detailed descriptions of images
- **Structured AI Descriptions**: Descriptions include main colors, subject, and stylistic elements
- **Automatic Model Detection**: Automatically detects and uses available models on your Ollama server
- **Smart Model Selection**: Prioritizes vision models for better image descriptions
- **Fallback Mechanism**: Uses basic image analysis when Ollama is unavailable
- **Fast Thumbnail Browsing**: Browse thumbnails with a responsive grid layout
- **Context-Aware Search**: Search only within the current folder or across all folders
- **Natural Language Search**: Find images using meaningful search terms
- **Date-Based Search**: Find images by modification date range
- **All Images View**: Browse your complete image collection across all folders
- **Enhanced Folder Management**: Add multiple folders at once, quick-add button in folder panel
- **Image Operations**: Copy, open, edit descriptions, or delete images through a context menu
- **Batch Operations**: Perform operations on multiple selected images at once
- **Batch Renaming**: Rename selected images with customizable patterns
- **Multiple Themes**: Choose from 12 different themes including a high-contrast accessibility option
- **Database Optimization**: Automatic database maintenance for optimal performance
- **Path Normalization**: Robust path handling to prevent file access issues
- **Fully Portable**: Runs from any folder or USB drive without installation

## Installation

STARNODES Image Manager is designed to be portable and easy to set up:

1. **Download the Repository**: Clone or download this repository
2. **Run Setup Script**: Execute `setup_env.py` to create the Python virtual environment and install dependencies
3. **Launch the Application**: Run `main.py` to start the application or use StartApp.bat

```powershell
# Clone the repository (or download and extract the ZIP)
git clone https://github.com/Starnodes2024/STARNODES-Image-Manager.git
cd STARNODES-Image-Manager

# Run the setup script to create virtual environment and install dependencies
python setup_env.py

# Start the application
python main.py
```

## Requirements

- Windows operating system
- Python 3.8 or higher
- Ollama server running locally or on a network (for AI-powered descriptions)
- At least one vision model installed on your Ollama server (llava recommended)
- Basic image analysis available as fallback when Ollama is unavailable

## Usage

### Adding Folders

1. Click the "Add Folder" button in the toolbar
2. Select a folder containing images
3. The application will scan the folder and generate thumbnails

### Browsing Images

- Navigate folders in the left panel
- View thumbnails in the main grid layout
- Click a thumbnail to select it
- Double-click to open the image
- Use "All Images" view to see your complete collection

### Searching

1. Enter search terms in the search box (e.g., "sunset beach", "dog playing")
2. Click "Search" or press Enter
3. Browse the matching images in the thumbnail grid
4. Use date range search to find images by modification date

### Batch Operations

1. Select multiple images by holding Ctrl while clicking thumbnails
2. Right-click to access batch operations menu
3. Choose an operation (Generate AI Descriptions, Copy, Delete, Rename)

### Context Menu

Right-click on any thumbnail to access these options:

- **Copy to folder**: Copy the selected image(s) to another location
- **Open with...**: Open the image with your chosen application
- **Generate AI description**: Generate or regenerate an AI description
- **Edit description**: View or edit the AI-generated description
- **Delete description**: Remove the AI-generated description
- **Delete image**: Remove the image from the database (option to delete the file too)
- **Batch operations**: Access batch operations for multiple selected images

## Customization

You can customize application settings by editing the `config/settings.json` file:

- Thumbnail size and quality
- AI model settings
- UI preferences
- Monitoring options

## Development

STARNODES Image Manager is built with:

- **Python**: Core programming language
- **PyQt6**: Modern UI framework
- **SQLite**: Lightweight database
- **Pillow**: Image processing
- **Ollama API**: Integration with local LLM vision models for image descriptions
- **NumPy**: For fallback image analysis

The application architecture separates concerns into these key modules:

- **Database**: Stores image information and descriptions
- **Image Processing**: Handles scanning and thumbnail generation
- **AI**: Manages the vision model and description generation
- **UI**: Provides the user interface components

## License

[MIT License](LICENSE)
