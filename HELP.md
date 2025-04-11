# STARNODES Image Manager v0.9.6 - Help Guide

## Introduction

STARNODES Image Manager is a Windows application that helps you organize, browse, and search your image collections using AI-powered descriptions and catalogs. With an intuitive interface and advanced features, it makes managing large image collections simple and efficient.

This application supports both folder-based organization and content-based catalogs, allowing you to manage your images in multiple ways simultaneously.

## Getting Started

### First Launch

When you first launch the application, it will create a configuration file with default settings. From there, you can:

1. Add folders containing your images
2. Configure the Ollama server for AI descriptions
3. Select your preferred theme and visual options

### Adding Image Folders

1. Click the "+" button next to "Folders" in the left panel, or select File → Add Folder
2. Choose one or multiple folders containing images in the file browser
   - Hold Ctrl while clicking to select multiple non-adjacent folders
   - Hold Shift to select a range of folders
3. The application will automatically detect and skip any folders that have already been added
4. You'll be prompted to scan the newly added folders to create thumbnails
5. Once scanned, the folder will show the number of contained images in parentheses

### Managing Folders

- In the left panel, you can see all the folders you've added
- Right-click on a folder for options (Rescan, Remove)
- Click on a folder to view its images in the main thumbnail area
- Use the folder quick-add button (+) to add multiple folders at once
- Select parent/child folders intelligently with automatic filtering

### Managing Catalogs

- Catalogs allow you to organize images by content type (animals, landscapes, etc.) independent of folder structure
- In the left panel, you can see your created catalogs in the Catalogs section
- Each catalog shows the number of images it contains in parentheses (e.g., "Animals (24)")
- Click on a catalog to view all images assigned to that catalog
- Right-click on a catalog for options (Remove)
- Add images to catalogs using the context menu on thumbnails
- Remove images from catalogs using the "Remove from Catalog" context menu option

### Upgrading Database for Catalogs

If you're using an older version of the database that doesn't support catalogs:

1. Go to Tools → Database → Upgrade Database for Catalogs
2. Confirm the operation when prompted
3. Your database will be updated to support the Catalogs feature without affecting your existing data
4. Once upgraded, you can start using the catalog features immediately

## Working with Images

### Viewing Images

- Browse thumbnails in the grid layout
- Each thumbnail displays the filename and exact image dimensions in pixels (e.g., 1024×768)
- Double-click any thumbnail to open the image in your default viewer
- Select thumbnails by clicking on them (hold Ctrl for multiple selection)
- Folder and catalog counts show the exact number of images they contain

### Pagination System

- Thumbnail browser automatically uses pagination for efficient memory management
- Configure how many thumbnails to show per page using the dropdown in the bottom navigation bar
- Choose from 20, 50, 100, 200 (default), or 500 thumbnails per page
- Navigation controls show current page, total pages, and thumbnail count information
- Use "Previous" and "Next" buttons to navigate between pages

### All Images View

- Access from the View menu by selecting "All Images"
- Shows your entire image collection with efficient pagination
- Images are loaded in batches according to your pagination settings
- Perfect for browsing your complete collection without memory issues
- Automatically adjusts to your selected thumbnails-per-page setting

### Enhanced Unified Search

The application features a comprehensive search system that allows you to find images using multiple criteria simultaneously:

#### Search Criteria

1. **Text Search**:
   - Enable the checkbox next to "Search by text"
   - Enter descriptive terms in the search box (e.g., "sunset over mountains", "red car")
   - The search uses advanced full-text search to find relevant images

2. **Date Range Search**:
   - Enable the checkbox next to "Search by date modified"
   - Select a date range using the From and To date pickers
   - Find images that were modified within the specified date range

3. **Image Dimensions Search**:
   - Enable the checkbox next to "Search by image size"
   - Specify minimum and maximum width and height in pixels
   - Choose from dimension presets in the dropdown menu:
     - HD (1280×720)
     - Full HD (1920×1080)
     - 4K (3840×2160)
     - 8K (7680×4320)
     - Square (width = height)
     - Portrait (height > width)
     - Landscape (width > height)
     - Custom (manual specifications)

#### Search Scope Selection

Choose where to search by selecting one of these options:

1. **Current Folder**: Search only within the currently selected folder
2. **Current Catalog**: Search only within the currently selected catalog
3. **All Images**: Search across your entire image collection with pagination

#### Combining Search Criteria

- Enable multiple search criteria simultaneously by checking their respective boxes
- For example, search for "sunset" images taken in July 2025 with Full HD resolution
- The search will find images matching ALL selected criteria (logical AND)
- The status bar shows how many images matched your combined search

#### Using the Search Tool

1. Configure your search criteria by enabling desired options
2. Select your search scope
3. Click the "Search" button to execute the search
4. Results are displayed in the thumbnail grid
5. Clear search parameters with the "Clear" option

#### Updating Image Dimensions

To enable dimension-based searching, image dimensions must be stored in the database:

1. Go to Tools → Database → Update Image Dimensions
2. Choose to update all images or just the current folder
3. The application will scan your image files and update width/height information
4. This process only needs to be done once for your existing images
5. New images added to the database will automatically have dimensions recorded

### Context Menu Operations

Right-click on any thumbnail to access these options:

- **Open**: Open the image in your default viewer
- **Open With...**: Choose a specific application to open the image
- **Copy to Folder**: Copy the selected image(s) to another location
- **Export with Options**: Export the image with format, description, and workflow options
- **Add to Catalog**: Add the image to an existing catalog or create a new one
- **Remove from Catalog**: Remove the image from the current catalog (only visible when viewing a catalog)
- **Locate on Disk**: Open File Explorer at the image's location
- **Copy Image to Clipboard**: Copy the image to the system clipboard
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
   - Export selected images with format, description, and workflow options
   - Add selected images to catalog
   - Remove selected images from current catalog (when viewing a catalog)
   - Generate AI descriptions for all selected images
   - Delete selected images (from database or disk)
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

### Background Scanning

- **Enable Background Scanning**: Toggle automatic scanning for new images
- **Scan Interval**: Set how often the application checks for new images (in minutes)
- **Notification**: Receive alerts when new images are found

## File Operations

### Exporting Images

1. Select one or more images to export
2. Right-click and choose "Export with options..."
3. In the Export Options dialog, select:
   - **Format**: Original format, JPEG, or PNG
   - **Description Export**: Include description as text file, or export description only
   - **ComfyUI Workflow Export**: Export embedded workflow data as JSON file
   - **Destination**: Select where to save the exported files
4. Click OK to begin the export process

### Database Management

#### Exporting the Database

1. Go to Tools → Database → Export Database
2. Select a location and filename for the database backup
3. The application will create a complete copy of your database

#### Importing a Database

1. Go to Tools → Database → Import Database
2. Select a previously exported database file
3. Choose from two import modes:
   - **Merge**: Add new folders and images from the import to your existing database
   - **Replace**: Completely replace your current database with the imported one
4. Follow the prompts to complete the import process

#### Database Maintenance

1. Empty Database: File → Folder Management → Empty Database
2. Optimize & Repair: Tools → Database → Optimize & Repair Database
3. Upgrade Database for Catalogs: Tools → Database → Upgrade Database for Catalogs
4. Update Image Dimensions: Tools → Database → Update Image Dimensions

## Troubleshooting

### Ollama Connection Issues

- Ensure Ollama is installed and running on your system
- Check that the server URL in Settings is correct
- Verify that you have at least one vision model installed (like 'llava')

### Database Optimization

The application will automatically optimize the database for performance. If you experience slowdowns:

1. Go to Tools → Database → Optimize & Repair Database
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
