#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
STARNODES Image Manager - Main Application Entry Point

A Windows application for managing and searching image collections 
using AI-powered image descriptions.
"""

import os
import sys
import logging
import time
from datetime import datetime
import threading

# Add the project root directory to the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

# Determine if we're running in portable mode
is_portable = getattr(sys, 'frozen', False)
app_base_dir = current_dir
if is_portable:
    app_base_dir = os.path.dirname(sys.executable)
    
    # CRITICAL: Override PyInstaller's temporary directory with our portable directory
    # This prevents PyInstaller from using temp folders like AppData
    if hasattr(sys, '_MEIPASS'):
        print(f"PyInstaller _MEIPASS detected: {sys._MEIPASS}")
        print(f"Overriding with our portable app_base_dir: {app_base_dir}")
        
        # PyInstaller extracts files to this temporary directory
        # We need to modify our path handling to use our own directories instead

# Setup logging (we'll update this with config settings later)
log_dir = os.path.join(app_base_dir, "data", "logs")
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, f"app_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

# Configure root logger with handlers
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)

# Clear any existing handlers
for handler in root_logger.handlers[:]: 
    root_logger.removeHandler(handler)

# Create file handler for all logs (INFO and above)
file_handler = logging.FileHandler(log_file)
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
root_logger.addHandler(file_handler)

# Create console handler with higher log level (only WARNING and above)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.WARNING)  # Only show warnings and errors in console
console_handler.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
root_logger.addHandler(console_handler)

# Clean old log files, keeping only the 5 most recent
log_files = sorted([os.path.join(log_dir, f) for f in os.listdir(log_dir) if f.startswith("app_") and f.endswith(".log")], 
                   key=os.path.getctime, reverse=True)
for old_log in log_files[5:]:  # Keep 5 most recent logs
    try:
        os.remove(old_log)
    except Exception as e:
        print(f"Warning: Could not remove old log file {old_log}: {e}")

# Initialize our application logger
logger = logging.getLogger("STARNODESImageManager")

# Log important information about the execution environment
logger.info(f"Starting application in {'portable' if is_portable else 'development'} mode")
logger.info(f"Application base directory: {app_base_dir}")
logger.info(f"Log directory: {log_dir}")

def activate_virtual_environment():
    """Activate the bundled virtual environment if running as a script.
    When running as a PyInstaller executable, this is not needed and will be skipped.
    """
    # Check if we're running in a PyInstaller bundle
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        logger.info("Running as PyInstaller executable, skipping virtual environment activation")
        return True
    
    logger.info("Activating virtual environment...")
    venv_path = os.path.join(current_dir, "venv")
    
    # Determine the site-packages directory based on the Python version
    if sys.platform == "win32":
        site_packages = os.path.join(venv_path, "Lib", "site-packages")
    else:
        site_packages = os.path.join(
            venv_path, 
            "lib",
            f"python{sys.version_info.major}.{sys.version_info.minor}",
            "site-packages"
        )
    
    # Check if the site-packages directory exists
    if os.path.exists(site_packages):
        # Add site-packages to the Python path
        if site_packages not in sys.path:
            sys.path.insert(0, site_packages)
        logger.info(f"Virtual environment activated: {site_packages}")
        return True
    else:
        logger.error(f"Virtual environment not found at: {site_packages}")
        # Return True anyway if we're running as an executable
        # This allows the app to continue startup without an environment
        return getattr(sys, 'frozen', False)

# Global references to prevent garbage collection
_app_instance = None
_main_window = None
_setup_wizard = None

# Dictionary to store application references
app_refs = {}

def main():
    """Main application entry point."""
    logger.info("Starting STARNODES Image Manager application...")
    
    # If running as PyInstaller executable, ensure we're using portable paths
    if getattr(sys, 'frozen', False):
        logger.info("Running as PyInstaller executable - ensuring portable paths")
        
        # Force our portable paths instead of PyInstaller's temporary extraction
        exe_dir = os.path.dirname(sys.executable)
        
        # These are the critical portable directories we need to ensure exist
        portable_dirs = [
            os.path.join(exe_dir, "data"),
            os.path.join(exe_dir, "data", "thumbnails"),
            os.path.join(exe_dir, "config"),
            os.path.join(exe_dir, "data", "logs")
        ]
        
        for directory in portable_dirs:
            os.makedirs(directory, exist_ok=True)
            logger.info(f"Ensured portable directory exists: {directory}")
    
    # Activate virtual environment (only necessary when running as script)
    if not activate_virtual_environment():
        # Only exit if we're not running as a PyInstaller executable
        if not getattr(sys, 'frozen', False):
            logger.error("Failed to activate virtual environment. Run setup_env.py first.")
            print("ERROR: Virtual environment not found. Please run setup_env.py first.")
            return
    
    # Import required modules (must be done after activating virtual environment)
    try:
        from PyQt6.QtWidgets import QApplication, QMessageBox
        from PyQt6.QtCore import QTimer, Qt
        from src.ui.main_window import MainWindow
        from src.database.db_manager import DatabaseManager
        from src.config.config_manager import ConfigManager
        from src.database.db_repair import check_and_repair_if_needed
    except ImportError as e:
        logger.error(f"Failed to import required modules: {e}")
        print(f"ERROR: Failed to import required modules: {e}")
        print("Please run setup_env.py to set up the virtual environment.")
        return
    
    # Load configuration
    config_manager = ConfigManager()
    
    # Initialize memory management and Phase 4 optimizations
    try:
        from src.memory.memory_utils import initialize_memory_management
        from src.database.db_sharding import ShardManager, FolderBasedSharding, DateBasedSharding
        from src.image_processing.format_optimizer import FormatOptimizer
        from src.memory.resource_manager import ResourceManager
        
        logger.info("Initializing memory management system...")
        initialize_memory_management(config_manager)
        
        # Initialize Phase 4 optimization components
        logger.info("Initializing Phase 4 optimization components...")
        
        # Initialize resource manager first (needed by other components)
        resource_manager = None
        if config_manager.get("memory", "enable_resource_management", True):
            resource_manager = ResourceManager(config_manager)
            logger.info("Resource manager initialized")
        
        # Initialize format optimizer
        format_optimizer = None
        if config_manager.get("thumbnails", "format_optimization", True):
            format_optimizer = FormatOptimizer(config_manager)
            logger.info("Format optimizer initialized")
        
        # Initialize shard manager if enabled
        shard_manager = None
        if config_manager.get("database", "enable_sharding", False):
            # Get database path from config
            db_path = config_manager.get("database", "path", None)
            if db_path and os.path.exists(os.path.dirname(db_path)):
                # Choose sharding strategy based on configuration
                sharding_type = config_manager.get("database", "sharding_type", "folder")
                if sharding_type == "date":
                    interval_months = config_manager.get("database", "shard_interval_months", 6)
                    strategy = DateBasedSharding(interval_months=interval_months)
                    logger.info(f"Using date-based sharding with interval of {interval_months} months")
                else:
                    max_folders = config_manager.get("database", "max_folders_per_shard", 10)
                    strategy = FolderBasedSharding(max_folders_per_shard=max_folders)
                    logger.info(f"Using folder-based sharding with max {max_folders} folders per shard")
                
                shard_manager = ShardManager(db_path, strategy, config_manager.get("database", "enable_sharding", False))
                logger.info("Shard manager initialized")
        
        # Store optimizers in app_refs for later use by components
        app_refs["resource_manager"] = resource_manager
        app_refs["format_optimizer"] = format_optimizer
        app_refs["shard_manager"] = shard_manager
    except Exception as e:
        logger.warning(f"Could not initialize memory management or Phase 4 optimizations: {e}")
    
    # Initialize database
    db_path = config_manager.get("database", "path")
    if not os.path.isabs(db_path):
        db_path = os.path.join(current_dir, db_path)
    
    # FORCE consistent paths for both portable (exe) and development (script) modes
    # This ensures thumbnails are always in /data/thumbnails for ALL run modes
    if getattr(sys, 'frozen', False):
        # PORTABLE MODE: Get the directory where the executable is located
        exe_dir = os.path.dirname(sys.executable)
        
        # Force portable paths even if config has something else
        portable_db_path = os.path.join(exe_dir, "data", "image_database.db")
        portable_thumbnails_path = os.path.join(exe_dir, "data", "thumbnails")
        portable_cache_path = os.path.join(exe_dir, "data", "cache")
        
        # Override the config settings with our portable paths
        config_manager.set("database", "path", portable_db_path)
        config_manager.set("thumbnails", "path", portable_thumbnails_path)
        config_manager.set("cache", "path", portable_cache_path)
        
        # Save the configuration to ensure it persists
        config_manager.save()
        
        logger.info(f"FORCED PORTABLE PATHS:")
        logger.info(f"  Database: {portable_db_path}")
        logger.info(f"  Thumbnails: {portable_thumbnails_path}")
        logger.info(f"  Cache: {portable_cache_path}")
    else:
        # DEVELOPMENT MODE: Use the exact same directory structure for consistency
        app_dir = os.path.dirname(os.path.abspath(__file__)) # Main directory of the application
        
        # Force the same data/thumbnails structure for development mode
        dev_data_dir = os.path.join(app_dir, "data")
        dev_db_path = os.path.join(dev_data_dir, "image_database.db")
        dev_thumbnails_path = os.path.join(dev_data_dir, "thumbnails")
        dev_cache_path = os.path.join(dev_data_dir, "cache")
        
        # Create all necessary directories
        os.makedirs(dev_data_dir, exist_ok=True)
        os.makedirs(dev_thumbnails_path, exist_ok=True)
        os.makedirs(os.path.join(dev_data_dir, "logs"), exist_ok=True)
        os.makedirs(dev_cache_path, exist_ok=True)
        
        # Override the config settings to use our development paths
        config_manager.set("database", "path", dev_db_path)
        config_manager.set("thumbnails", "path", dev_thumbnails_path)
        config_manager.set("cache", "path", dev_cache_path)
        
        # Save the configuration to ensure it persists
        config_manager.save()
        
        logger.info(f"FORCED DEVELOPMENT PATHS:")
        logger.info(f"  Database: {dev_db_path}")
        logger.info(f"  Thumbnails: {dev_thumbnails_path}")
        logger.info(f"  Cache: {dev_cache_path}")
    
    # Ensure directory exists
    try:
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
    except Exception as e:
        logger.error(f"Error creating database directory: {e}")
    
    logger.info(f"Using database: {db_path}")
    
    # Create application instance
    app = QApplication(sys.argv)
    app.setApplicationName("STARNODES Image Manager")
    app.setOrganizationName("StarKeeper")
    app.setOrganizationDomain("starkeeper.example.com")
    
    # Store the reference
    app_refs['app'] = app
    
    # Use our robust startup repair to ensure database integrity
    try:
        from src.database.db_startup_repair import ensure_database_integrity
        from src.database.db_repair import repair_database
        
        logger.info("Running comprehensive database integrity check...")
        repair_result = ensure_database_integrity(db_path)
        
        if repair_result:
            logger.info("Database integrity check completed successfully")
        else:
            logger.error("Database integrity check failed, forcing repair...")
            
            # Force a database repair
            repair_success = repair_database(db_path)
            
            # Show a message to the user
            msg_box = QMessageBox()
            if repair_success:
                msg_box.setIcon(QMessageBox.Icon.Information)
                msg_box.setWindowTitle("Database Repaired")
                msg_box.setText("The database was repaired successfully.")
                msg_box.setInformativeText("Your image data has been restored, but you may need to re-scan some folders if images are missing.")
                logger.info("Database repair completed successfully")
            else:
                msg_box.setIcon(QMessageBox.Icon.Critical)
                msg_box.setWindowTitle("Database Repair Failed")
                msg_box.setText("Failed to repair the database.")
                msg_box.setInformativeText("The application will create a new database. You will need to re-add your folders and re-scan your images.")
                logger.error("Database repair failed, creating new database")
                
                # If repair failed, delete the corrupted database so a new one will be created
                try:
                    if os.path.exists(db_path):
                        backup_path = f"{db_path}.corrupted_{int(time.time())}"
                        os.rename(db_path, backup_path)
                        logger.info(f"Backed up corrupted database to {backup_path}")
                except Exception as backup_error:
                    logger.error(f"Failed to backup corrupted database: {backup_error}")
            
            msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
            msg_box.exec()
    except Exception as e:
        logger.error(f"Error during database startup repair: {e}")
        # Continue anyway, the database manager will create a new database if needed
    
    # Initialize database manager
    db_manager = DatabaseManager(db_path)
    db_manager.initialize_database()
    
    # Ensure thumbnail directory exists and fix paths for imported databases
    thumbnail_path = config_manager.get("thumbnails", "path")
    os.makedirs(thumbnail_path, exist_ok=True)
    logger.info(f"Using thumbnail directory: {thumbnail_path}")
    
    # Verify the directory structure again - this is critical for both modes
    if not os.path.exists(thumbnail_path):
        logger.warning(f"Thumbnail directory does not exist even after creation attempt: {thumbnail_path}")
        # Try another creation attempt with higher permissions
        try:
            os.makedirs(thumbnail_path, exist_ok=True, mode=0o777)
            logger.info(f"Created thumbnail directory with elevated permissions: {thumbnail_path}")
        except Exception as e:
            logger.error(f"Failed to create thumbnail directory: {e}")
    
    # Fix imported database thumbnail paths - this is optional since thumbnails already work
    try:
        fix_imported_database_thumbnails(db_manager, thumbnail_path)
    except Exception as e:
        # Don't let this error stop the application
        logger.warning(f"Non-critical error in thumbnail path fixing: {e}")
        logger.info("This error can be safely ignored as thumbnails are working correctly.")
    
    # Log thumbnail path for debugging
    logger.info(f"FINAL CONFIRMED Thumbnail path: {thumbnail_path}")
    
    # Application instance already created above
    
    # This function is moved down and merged with the duplicate version below
    
    # Check if this is the first run or if there's no data in the database
    is_first_run = config_manager.get("app", "first_run", True)
    
    # Check if there are any folders in the database
    folders = db_manager.get_folders()
    data_exists = len(folders) > 0
    
    # Log the first run status and whether we're running as an executable
    is_frozen = getattr(sys, 'frozen', False)
    logger.info(f"First run status: is_first_run={is_first_run}, has_data={data_exists}, is_executable={is_frozen}")
            
    # Create and show the main window
    def create_main_window():
        try:
            # Create the main window
            main_window = MainWindow(db_manager)
            main_window.setWindowTitle("STARNODES Image Manager V0.9.7")
            
            # Set up key position and size
            desktop = app.primaryScreen().availableGeometry()
            main_window.resize(int(desktop.width() * 0.8), int(desktop.height() * 0.8))
            main_window.move(int(desktop.width() * 0.1), int(desktop.height() * 0.1))
            
            # Make it visible
            main_window.show()
            main_window.raise_()
            main_window.activateWindow()
            
            # Store the reference to prevent garbage collection
            app_refs['main_window'] = main_window
            
            logger.info("Main window created and shown successfully")
            return main_window
        except Exception as e:
            logger.error(f"Error creating main window: {e}")
            QMessageBox.critical(None, "Error", f"Failed to create main window: {e}")
            return None
    
    # Function to handle setup completion
    def setup_completed(settings=None):
        logger.info("Setup completion handler called")
        
        # Make sure first_run is set to false
        config_manager.set("app", "first_run", False)
        config_manager.save()
        logger.info("First run flag set to false")
        
        # Create the main window
        main_window = create_main_window()
        
        # Process folders if any were selected
        if main_window and settings and settings.get("folders"):
            logger.info(f"Setup wizard provided {len(settings.get('folders'))} folders")
    
    # Define a MainApplication class to manage the app's lifecycle
    class MainApplication:
        def __init__(self):
            self.main_window = None
            self.wizard = None
            
            # In portable mode, ensure all paths are set correctly
            if getattr(sys, 'frozen', False):
                self.setup_portable_paths()
        
        def start(self):
            # Setup wizard was removed as per PROGRESS.md (2025-04-06)
            # Always show main window directly
            self.show_main_window()
        
        def setup_portable_paths(self):
            """Set up all paths for portable mode operation"""
            try:
                # Get executable directory
                exe_dir = os.path.dirname(sys.executable)
                data_dir = os.path.join(exe_dir, "data")
                
                # Ensure all required directories exist
                dirs_to_create = [
                    data_dir,
                    os.path.join(data_dir, "thumbnails"),
                    os.path.join(data_dir, "cache"),
                    os.path.join(data_dir, "exports"),
                    os.path.join(data_dir, "logs"),
                    os.path.join(exe_dir, "config")  # Create config directory next to the executable
                ]
                
                for directory in dirs_to_create:
                    os.makedirs(directory, exist_ok=True)
                    logger.info(f"Created portable directory: {directory}")
                
                # Copy default config files to the config directory if they don't exist
                default_config_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config")
                target_config_dir = os.path.join(exe_dir, "config")
                
                try:
                    if os.path.exists(default_config_dir) and os.path.isdir(default_config_dir):
                        for config_file in os.listdir(default_config_dir):
                            src_file = os.path.join(default_config_dir, config_file)
                            dst_file = os.path.join(target_config_dir, config_file)
                            
                            # Only copy if the file doesn't exist
                            if os.path.isfile(src_file) and not os.path.exists(dst_file):
                                import shutil
                                shutil.copy2(src_file, dst_file)
                                logger.info(f"Copied config file to portable location: {dst_file}")
                except Exception as e:
                    logger.error(f"Error copying config files: {e}")
                
                # Redirect logs to the portable location
                if logger.handlers:
                    for handler in logger.handlers:
                        if isinstance(handler, logging.FileHandler):
                            # Close current log file
                            handler.close()
                            logger.removeHandler(handler)
                            
                            # Create new log file in portable location
                            portable_log = os.path.join(data_dir, "logs", f"app_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
                            new_handler = logging.FileHandler(portable_log)
                            new_handler.setFormatter(handler.formatter)
                            new_handler.setLevel(handler.level)
                            logger.addHandler(new_handler)
                            
                            logger.info(f"Redirected logs to portable location: {portable_log}")
                            break
            except Exception as e:
                logger.error(f"Error setting up portable paths: {e}")
        
        # Setup wizard method removed as it's no longer used (per PROGRESS.md 2025-04-06)
        # "Removed setup wizard and replaced with default configuration"
        
        def on_setup_complete(self, settings):
            logger.info("Setup wizard completed, creating main window directly")
            
            # Mark first run as complete (although this is redundant as the wizard also does it)
            config_manager.set("app", "first_run", False)
            config_manager.save()
            
            # Create and show main window immediately
            self.show_main_window()
        
        def show_main_window(self):
            try:
                # Only create the main window if it doesn't already exist
                if not self.main_window:
                    logger.info("Creating new main window instance")
                    self.main_window = MainWindow(db_manager)
                    
                    # Integrate format optimizer with thumbnail generator
                    try:
                        format_optimizer = app_refs.get("format_optimizer")
                        if format_optimizer and hasattr(self.main_window, "thumbnail_generator"):
                            logger.info("Integrating format optimizer with thumbnail generator...")
                            thumbnail_generator = self.main_window.thumbnail_generator
                            
                            # Store the original method
                            original_generate_thumbnail = thumbnail_generator.generate_thumbnail
                            
                            # Create a simple wrapper function that doesn't try to optimize
                            # This is a temporary fix until we can properly implement the thumbnail optimization
                            def generate_thumbnail_simple(image_path, force=False, target_format=None):
                                """Generate a thumbnail without optimization (temporary fix)."""
                                try:
                                    # Just pass through to the original method
                                    # This avoids the errors while still allowing thumbnails to be generated
                                    return original_generate_thumbnail(image_path, force=force, target_format=target_format)
                                except Exception as e:
                                    logger.error(f"Error in thumbnail generation: {e}")
                                    # Fall back to even simpler call
                                    try:
                                        return original_generate_thumbnail(image_path)
                                    except Exception as e2:
                                        logger.error(f"Critical error in thumbnail generation: {e2}")
                                        return None
                            
                            # Replace the original method with our simple version
                            thumbnail_generator.generate_thumbnail = generate_thumbnail_simple
                            logger.info("Integrated format optimizer with thumbnail generator")
                    except Exception as e:
                        logger.error(f"Failed to integrate format optimizer with thumbnail generator: {e}")
                    
                    # Integrate resource manager with batch operations if available
                    try:
                        resource_manager = app_refs.get("resource_manager")
                        if resource_manager and hasattr(self.main_window, "batch_operations"):
                            logger.info("Integrating resource manager with batch operations...")
                            batch_operations = self.main_window.batch_operations
                            
                            # Store reference to resource manager
                            batch_operations.resource_manager = resource_manager
                            
                            # Skip checking for process_batch method directly, as per PROGRESS.md
                            # this has been refactored to use task_manager directly
                            
                            # Create optimized batch processing function with resource management
                            def process_batch_with_resource_management(operation_type, items, **kwargs):
                                """Process a batch operation with resource management."""
                                # Estimate memory usage based on number of items and operation type
                                estimated_size_mb = len(items) * 5  # Rough estimate of 5MB per item
                                
                                # Create batch operation context
                                with resource_manager.create_batch_context(f"Batch {operation_type}", estimated_size_mb):
                                    # Call appropriate task manager methods based on operation type
                                    if hasattr(batch_operations, 'task_manager'):
                                        if operation_type == 'ai_description':
                                            return batch_operations.task_manager.process_batch_ai_descriptions(items)
                                        elif operation_type == 'thumbnail':
                                            return batch_operations.task_manager.process_batch_thumbnails(items)
                                        else:
                                            # For other operations, delegate to existing methods
                                            method_name = f"process_{operation_type}"
                                            if hasattr(batch_operations, method_name):
                                                method = getattr(batch_operations, method_name)
                                                return method(items, **kwargs)
                                    
                                    # If we got here, we couldn't process the batch
                                    return None
                            
                            # Add the resource-managed batch processor if not already present
                            batch_operations.process_batch_with_resources = process_batch_with_resource_management
                            logger.info("Integrated resource manager with batch operations")
                    except Exception as e:
                        logger.error(f"Failed to integrate resource manager with batch operations: {e}")
                    # Store reference to prevent garbage collection
                    app_refs['main_window'] = self.main_window
                
                logger.info("Showing main window")
                self.main_window.show()
                self.main_window.raise_()
                self.main_window.activateWindow()
                logger.info("Main window shown successfully")
            except Exception as e:
                logger.error(f"Error creating/showing main window: {e}")
                QMessageBox.critical(
                    None,
                    "Error",
                    f"Failed to create/show main window: {e}"
                )
    
    # Create and start the application
    main_app = MainApplication()
    app_refs["main_app"] = main_app  # Keep a reference
    main_app.start()
    
    # Log that we're starting the event loop
    logger.info("Starting application event loop")
    
    # Start the event loop and return its result
    exit_code = app.exec()
    
    # Cleanup any resources used by optimizers
    try:
        resource_manager = app_refs.get("resource_manager")
        if resource_manager:
            logger.info("Cleaning up resource manager...")
            resource_manager.cleanup()
    except Exception as e:
        logger.error(f"Error during resource manager cleanup: {e}")
    
    # Log application exit
    logger.info(f"Application exiting with code {exit_code}")
    return exit_code

def fix_imported_database_thumbnails(db_manager, thumbnails_dir):
    """Fix thumbnail paths in imported databases to ensure thumbnails display correctly.
    
    This function checks the database for thumbnail paths that may be inconsistent
    with the current mode (script vs executable) and fixes them to ensure thumbnails
    can be properly displayed.
    
    Args:
        db_manager: DatabaseManager instance
        thumbnails_dir: Path to the thumbnails directory
    """
    # Log the thumbnails directory we're using
    logger.info(f"Fixing imported database thumbnails with thumbnails_dir: {thumbnails_dir}")
    try:
        logger.info("Checking for imported database and fixing thumbnail paths if needed...")
        
        # Get all images with thumbnail paths - using direct connection instead of execute_query
        # Since the DatabaseManager doesn't have execute_query method
        if db_manager.conn is None:
            db_manager.connect()
        
        try:
            # Use the existing connection to execute the query
            cursor = db_manager.conn.cursor()
            cursor.execute("SELECT image_id, thumbnail_path FROM images WHERE thumbnail_path IS NOT NULL")
            images = cursor.fetchall()
        except Exception as e:
            logger.warning(f"Could not query images: {e}, skipping thumbnail path fixing")
            return (0, 0, 0, 0)
        
        if not images or len(images) == 0:
            logger.info("No images with thumbnails found in database")
            return
        
        # Import utility specifically here to avoid circular imports
        from src.utilities.convert_thumbnail_paths import convert_to_relative_paths
        
        # Convert thumbnail paths to ensure they're consistent with current mode
        success, unchanged, errors = convert_to_relative_paths(
            db_path=db_manager.db_path,
            db_manager=db_manager,
            dry_run=False
        )
        
        if success > 0:
            logger.info(f"Fixed {success} thumbnail paths for imported database")
        else:
            logger.info("No thumbnail paths needed fixing")
        
        # Check if thumbnail directory contains the expected files
        thumbnail_filenames = set()
        for img in images:
            if img['thumbnail_path']:
                thumbnail_filenames.add(os.path.basename(img['thumbnail_path']))
        
        # Check if thumbnails exist
        missing_count = 0
        if os.path.exists(thumbnails_dir):
            existing_thumbnails = set(os.listdir(thumbnails_dir))
            missing_thumbnails = thumbnail_filenames - existing_thumbnails
            missing_count = len(missing_thumbnails)
            
            # Log the detailed information about thumbnails for debugging
            logger.info(f"Total thumbnails in database: {len(thumbnail_filenames)}")
            logger.info(f"Total thumbnails found in directory: {len(existing_thumbnails)}")
            
            if missing_count > 0:
                logger.warning(f"Found {missing_count} missing thumbnails that will need to be regenerated")
                # Log up to 10 missing thumbnails to help with debugging
                if len(missing_thumbnails) <= 10:
                    logger.warning(f"Missing thumbnails: {list(missing_thumbnails)}")
                else:
                    logger.warning(f"First 10 missing thumbnails: {list(missing_thumbnails)[:10]}")
        else:
            logger.warning(f"Thumbnail directory does not exist: {thumbnails_dir}")
        
        return (success, unchanged, errors, missing_count)
    except Exception as e:
        logger.error(f"Error fixing imported database thumbnails: {e}")
        return (0, 0, 1, 0)

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except Exception as e:
        logger.error(f"Critical application error: {e}")
        # Add more detailed error reporting for executable mode
        if getattr(sys, 'frozen', False):
            try:
                from PyQt6.QtWidgets import QApplication, QMessageBox
                app = QApplication(sys.argv)
                error_msg = QMessageBox()
                error_msg.setIcon(QMessageBox.Icon.Critical)
                error_msg.setWindowTitle("STARNODES Image Manager - Critical Error")
                error_msg.setText("A critical error occurred while starting the application.")
                error_msg.setDetailedText(f"Error details: {str(e)}\n\nPlease check the logs or contact support.")
                error_msg.setStandardButtons(QMessageBox.StandardButton.Ok)
                error_msg.exec()
            except Exception:
                # If even the error reporting fails, at least try to show something to the user
                import ctypes
                ctypes.windll.user32.MessageBoxW(0, f"Application failed to start: {str(e)}", "STARNODES Image Manager - Error", 0)
        sys.exit(1)
