# STARNODES Image Manager v0.9.1 - Help Guide

## Introduction

STARNODES Image Manager is a Windows application that helps you organize, browse, and search your image collections using AI-powered descriptions. With an intuitive interface and advanced features, it makes managing large image collections simple and efficient.

## Getting Started

### First Launch

When you first launch the application, it will create a configuration file with default settings. From there, you can:

1. Add folders containing your images
2. Configure the Ollama server for AI descriptions
3. Select your preferred theme and visual options

### Adding Image Folders

1. Click the "Add Folder" button in the toolbar or select File → Add Folder
2. Choose a folder containing images in the file browser
3. The application will scan the folder and create thumbnails

### Managing Folders

- In the left panel, you can see all the folders you've added
- Right-click on a folder for options (Rescan, Remove)
- Click on a folder to view its images in the main thumbnail area

## Working with Images

### Viewing Images

- Browse thumbnails in the grid layout
- Double-click any thumbnail to open the image in your default viewer
- Select thumbnails by clicking on them (hold Ctrl for multiple selection)

### Searching Images

1. Enter descriptive terms in the search box (e.g., "sunset over mountains", "red car")
2. Click "Search" or press Enter
3. The results will show images matching your description

#### Date-Based Search

1. Enable the date range search by clicking the checkbox next to the date filters
2. Select a date range using the From and To date pickers
3. Click "Search" to find images modified within that date range
4. You can combine date search with text search for more specific results

### Context Menu Operations

Right-click on any thumbnail to access these options:

- **Open**: Open the image in your default viewer
- **Open With...**: Choose a specific application to open the image
- **Copy to Folder**: Copy the selected image(s) to another location
- **Generate AI Description**: Request an AI-generated description for the image
- **Edit Description**: View or modify the image description
- **Delete Description**: Remove the AI-generated description
- **Delete Image**: Remove the image from the database (with option to delete file)

## Batch Operations

You can perform operations on multiple selected images:

1. Select multiple images by holding Ctrl while clicking thumbnails
2. Right-click on any of the selected thumbnails
3. Choose from available batch operations:
   - Copy selected images to a folder
   - Generate AI descriptions for all selected images
   - Delete selected images
   - Delete descriptions for selected images
   - Rename selected images

### Batch Renaming

1. Select multiple images you want to rename
2. Right-click and choose "Rename Selected Images"
3. Enter a pattern for the new filenames
   - Use {n} for sequential numbering (1, 2, 3...)
   - Use {id} for image ID-based numbering
   - Use {ext} to reference the original file extension
   - Example: "vacation_{n}" becomes "vacation_1.jpg", "vacation_2.png", etc.
4. Click OK to start the renaming process

## Settings

Access the Settings dialog from the File menu to configure:

### AI Settings

- **Ollama Server URL**: The URL where your Ollama server is running (default: http://localhost:11434)
- **Model**: Select which Ollama model to use for descriptions (requires models installed on your Ollama server)
- **System Prompt**: Customize how AI describes images (default: "Describe this image concisely, start with main colors seperated by \" , \", then the main subject and key visual elements and style at the end.")
- **Processing Mode**: Choose to process only new images or all images when generating descriptions

### UI Settings

- **Theme**: Choose from 12 different themes:
  - Light
  - Dark
  - Blue
  - Purple
  - Red
  - Midnight Blue
  - Dark Forest
  - Dark Amber
  - Dark Rose
  - Dark Purple
  - Dark Cyan
  - Contrast (high-accessibility theme)
- **Thumbnail Size**: Adjust the size of thumbnails in the grid
- **Show Descriptions**: Toggle whether descriptions are shown under thumbnails

## Troubleshooting

### Ollama Connection Issues

- Ensure Ollama is installed and running on your system
- Check that the server URL in Settings is correct
- Verify that you have at least one vision model installed (like 'llava')

### Database Optimization

The application will automatically optimize the database for performance. If you experience slowdowns:

1. Go to File → Database Maintenance → Optimize Database
2. Follow the prompts to repair and optimize the database

### Path Issues

If you encounter "File not found" errors when working with images:

1. A path normalization utility is included to fix database path inconsistencies
2. Run the path fixer from the command line: `python src/utilities/path_fixer.py --db-path "path/to/your/database.db" --fix`
3. This will standardize all file paths in the database to use consistent separators

### Image Not Displaying

- Check that the image file still exists at the original location
- Try rescanning the folder from the folder context menu
- Ensure the image format is supported (JPEG, PNG)

## Keyboard Shortcuts

- **Ctrl+F**: Focus the search box
- **Ctrl+A**: Select all visible thumbnails
- **Delete**: Delete selected images (with confirmation)
- **F5**: Refresh the current view
- **Escape**: Clear selection
- **Ctrl+Click**: Select/deselect multiple individual thumbnails
- **Shift+Click**: Select a range of thumbnails

## Further Help

For more information or assistance, please visit the project GitHub repository:
https://github.com/Starnodes2024/STARNODES-Image-Manager

## License

STARNODES Image Manager is released under the MIT License.
Copyright (c) 2025 Starnodes2024
