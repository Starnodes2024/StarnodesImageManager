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

# Add the project root directory to the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

# Setup logging
log_dir = os.path.join(current_dir, "logs")
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, f"app_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
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
            main_window.setWindowTitle("STARNODES Image Manager")
            
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
            # Show setup wizard if needed, otherwise show main window directly
            if is_first_run or not data_exists:
                self.show_setup_wizard()
            else:
                self.show_main_window()
        
        def show_setup_wizard(self):
            try:
                # Import wizard
                from src.ui.setup_wizard import SetupWizard
                
                # Create wizard
                logger.info("Creating setup wizard")
                self.wizard = SetupWizard(db_manager)
                
                # Connect signals
                self.wizard.setup_complete.connect(self.on_setup_complete)
                
                # Show the wizard
                logger.info("Showing setup wizard")
                self.wizard.show()
                
            except Exception as e:
                logger.error(f"Error showing setup wizard: {e}")
                # Fallback to main window
                self.show_main_window()
        
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
