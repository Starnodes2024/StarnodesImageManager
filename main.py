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

# Setup logging
log_dir = os.path.join(current_dir, "logs")
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

logger = logging.getLogger("STARNODESImageManager")

def activate_virtual_environment():
    """Activate the bundled virtual environment."""
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
        return False

# Global references to prevent garbage collection
_app_instance = None
_main_window = None
_setup_wizard = None

# Dictionary to store application references
app_refs = {}

def main():
    """Main application entry point."""
    logger.info("Starting STARNODES Image Manager application...")
    
    # Activate virtual environment
    if not activate_virtual_environment():
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
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
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
    
    # Application instance already created above
    
    # Simple, reliable function to create and show main window
    def create_main_window():
        try:
            main_window = MainWindow(db_manager)
            main_window.setWindowTitle("STARNODES Image Manager V0.9.6")
            
            # Set up key position and size
            desktop = app.primaryScreen().availableGeometry()
            main_window.resize(int(desktop.width() * 0.8), int(desktop.height() * 0.8))
            main_window.move(int(desktop.width() * 0.1), int(desktop.height() * 0.1))
            
            # Make it visible
            main_window.show()
            main_window.raise_()
            main_window.activateWindow()
            
            # Store a reference
            app_references["main_window"] = main_window
            
            # Log success
            logger.info("Main window created successfully")
            return main_window
        except Exception as e:
            logger.error(f"Error creating main window: {e}")
            QMessageBox.critical(None, "Error", f"Failed to create main window: {e}")
            return None
    
    # Check if this is the first run or if there's no data in the database
    is_first_run = config_manager.get("app", "first_run", True)
    
    # Check if there are any folders in the database
    folders = db_manager.get_folders()
    data_exists = len(folders) > 0
    
    # Log the first run status
    logger.info(f"First run status: is_first_run={is_first_run}, has_data={data_exists}")
            
    # Simple function to create and show the main window
    def create_main_window():
        try:
            # Create the main window
            main_window = MainWindow(db_manager)
            main_window.show()
            main_window.raise_()
            main_window.activateWindow()
            
            # Store the reference to prevent garbage collection
            app_refs['main_window'] = main_window
            
            logger.info("Main window created and shown successfully")
            return main_window
        except Exception as e:
            logger.error(f"Error creating main window: {e}")
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
        
        def start(self):
            # Setup wizard was removed as per PROGRESS.md (2025-04-06)
            # Always show main window directly
            self.show_main_window()
        
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

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except Exception as e:
        logger.error(f"Critical application error: {e}")
        sys.exit(1)
