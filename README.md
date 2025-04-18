# STARNODES Image Manager v1.0.0

## Quick Start

**Ready-to-use portable version**: Extract `SIM_Windows_App.zip` to any location and run `STARNODES Image Manager.exe`

## What is STARNODES Image Manager?

STARNODES Image Manager is a Windows application that helps you organize, search, and manage your image collections. It works with both local images and those generated by AI tools.

### Key Features

- **AI-Powered Search**: Find images using natural language descriptions
- **Smart Organization**: Create catalogs to group images by content, regardless of folder location
- **Batch Operations**: Select multiple images for renaming, copying, or exporting
- **Multi-Criteria Search**: Find images by text description, date, or dimensions
- **Dimension Presets**: Quickly find images matching standard resolutions (HD, 4K, etc.)
- **Multiple Themes**: Choose from 12 different visual styles

## Known Bugs in 1.0.0
-when importing a database from a backup merge isn´t working at the moment. please use option: remove

## Getting Started

### Portable Version (Recommended)

1. **Download**: Get the `SIM_Windows_App.zip` file
2. **Extract**: Unzip to any location (even a USB drive)
3. **Run**: Launch `STARNODES Image Manager.exe`

### Developer Version

If you prefer to run from source code:

1. **Setup**: Run `python setup_env.py` to create the environment and install dependencies
2. **Launch**: Start with `python main.py` or use `StartApp.bat`

### First Steps

1. Add folders containing your images using the + button in the Folders panel
2. Set up Ollama for AI descriptions (optional but recommended)
3. Browse, search, and organize your images

## Need Help?

See the full documentation in HELP.md for detailed instructions.

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
  watch https://ollama.com/ for more Info. 
  Recommended model (every ollama vision model works): ollama run llava-phi3
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
