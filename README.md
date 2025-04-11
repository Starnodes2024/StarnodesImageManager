# STARNODES Image Manager v0.9.6

A modern image browser with AI-powered description generation and search capabilities.

## Overview

STARNODES Image Manager is a Windows application that allows you to manage and search your image collections using AI-generated descriptions and catalogs. The application scans your selected folders for images, generates thumbnails, and uses Ollama's vision models (like llava) to create descriptions of each image. You can then search your image collection using natural language queries based on these descriptions and organize them into custom catalogs independent of folder structure.

## Features

- **Intelligent Image Scanning**: Scans specified folders for PNG and JPEG images
- **Background Scanning**: Automatically scans for new images with configurable intervals
- **AI-Powered Descriptions**: Uses Ollama's vision models to create detailed descriptions of images
- **Structured AI Descriptions**: Descriptions include main colors, subject, and stylistic elements
- **Automatic Model Detection**: Automatically detects and uses available models on your Ollama server
- **Smart Model Selection**: Prioritizes vision models for better image descriptions
- **Fallback Mechanism**: Uses basic image analysis when Ollama is unavailable
- **Fast Thumbnail Browsing**: Browse thumbnails with a responsive grid layout
- **Enhanced Thumbnails**: Shows image dimensions (width×height) under each thumbnail
- **Catalogs**: Organize images by content type independent of folder structure
- **Image Counters**: Display of image counts for folders and catalogs in the side panel
- **Enhanced Unified Search**: Single search interface with multiple criteria and search scopes
- **Multi-Criteria Search**: Combine text, date range, and image dimensions in a single search
- **Dimension-Based Search**: Find images by width and height or aspect ratio
- **Dimension Presets**: Quick selection of common resolutions (HD, Full HD, 4K, etc.)
- **Multiple Search Scopes**: Search in current folder, current catalog, or all images
- **Direct All Images View**: Browse your entire image collection with efficient pagination
- **Natural Language Search**: Find images using meaningful search terms
- **Date-Based Search**: Find images by modification date range
- **Paginated Thumbnail Browsing**: Browse large collections efficiently with configurable pages (20-500 thumbnails per page)
- **Enhanced Folder Management**: Add multiple folders at once, quick-add button in folder panel
- **Image Operations**: Copy, open, edit descriptions, or delete images through a context menu
- **Export Options**: Export images as original/JPG/PNG with optional description text files and ComfyUI workflows
- **Database Backup**: Export and import database for backup and data transfer
- **Batch Operations**: Perform operations on multiple selected images at once
- **Batch Renaming**: Rename selected images with customizable patterns
- **Multiple Themes**: Choose from 12 different themes including a high-contrast accessibility option
- **Database Optimization**: Automatic database maintenance for optimal performance
- **Database Management**: Tools to optimize, repair, empty, and backup your database
- **Path Normalization**: Robust path handling to prevent file access issues
- **Fully Portable**: Runs from any folder or USB drive without installation

## Installation

STARNODES Image Manager is designed to be portable and easy to set up:

1. **Download the Repository**: Clone or download this repository
2. **Run Setup Script**: Execute `python setup_env.py` to create the Python virtual environment and install dependencies
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

## Organizing with Catalogs

1. Create a new catalog:
   - Right-click on any image and select "Add to Catalog" → "New Catalog..."
   - Enter a name and optional description for the catalog

2. Add images to catalogs:
   - Select one or more images
   - Right-click and choose "Add to Catalog" → [catalog name]

3. View catalog contents:
   - Click on a catalog name in the left panel (displays number of images in parentheses)
   - Browse all images assigned to that catalog

4. Remove images from catalogs:
   - While viewing a catalog, right-click on an image
   - Select "Remove from Catalog"
   
5. Upgrade existing database:
   - If you have an existing database, use Tools → Database → Upgrade Database for Catalogs
   - This will add catalog support without affecting your existing data

6. Update image dimensions in database:
   - Use Tools → Database → Update Image Dimensions
   - This will scan your image files and update width/height information in the database
   - Required for dimension-based searching

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
- View > All Images shows your complete collection with pagination
- Configure thumbnails per page (20, 50, 100, 200, or 500) to match your system capabilities

### Searching

1. Use the enhanced search panel to set up your search criteria:
   - **Text Search**: Enable the checkbox and enter search terms (e.g., "sunset beach", "dog playing")
   - **Date Range**: Enable the checkbox and select start/end dates
   - **Image Dimensions**: Enable the checkbox and specify width/height ranges or select a preset
2. Select your search scope:
   - **Current Folder**: Search only in the currently selected folder
   - **Current Catalog**: Search only in the currently selected catalog
   - **All Images**: Search across your entire collection
3. Click "Search" button to execute the search with all selected criteria
4. Browse the matching images in the thumbnail grid
5. The status bar will show how many images matched your search criteria

### Batch Operations

1. Select multiple images by holding Ctrl while clicking thumbnails
2. Right-click to access batch operations menu
3. Choose an operation (Generate AI Descriptions, Copy, Delete, Rename)

### Context Menu

Right-click on any thumbnail to access these options:

- **Copy to folder**: Copy the selected image(s) to another location
- **Export with options**: Export images with format, description, and workflow options
- **Add to Catalog**: Add the image to an existing catalog or create a new one
- **Remove from Catalog**: Remove the image from the current catalog (when viewing a catalog)
- **Open with...**: Open the image with your chosen application
- **Locate on disk**: Open file explorer at the image's location
- **Copy image to clipboard**: Copy the image to the system clipboard
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
