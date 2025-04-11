#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Background scanner for StarImageBrowse
Periodically scans monitored folders for new images
"""

import os
import time
import logging
import threading
from datetime import datetime
from PyQt6.QtCore import QObject, pyqtSignal

from ..database.db_operations import DatabaseOperations
from ..utils.image_utils import is_supported_image

logger = logging.getLogger("StarImageBrowse.scanner.background_scanner")


class BackgroundScannerSignals(QObject):
    """Signals for the background scanner."""
    scan_started = pyqtSignal()
    scan_completed = pyqtSignal(int, int)  # (new_images_count, folders_scanned)
    scan_error = pyqtSignal(str)  # error message

class BackgroundScanner:
    """Background scanner that periodically checks for new images in monitored folders."""
    
    def __init__(self, image_scanner=None, db_manager=None, config_manager=None, interval_minutes=15):
        """Initialize the background scanner.
        
        Args:
            image_scanner: Optional image scanner instance (for compatibility with MainWindow)
            db_manager (DatabaseOperations): Database manager instance
            config_manager: Optional config manager instance (for compatibility with MainWindow)
            interval_minutes (int): Scan interval in minutes
        """
        self.image_scanner = image_scanner  # Not used, for compatibility
        self.db_manager = db_manager
        self.config_manager = config_manager  # Not used, for compatibility
        self.interval_minutes = interval_minutes
        self.running = False
        self.thread = None
        self._stop_event = threading.Event()
        self._last_scan_time = None
        
        # Initialize signals
        self.signals = BackgroundScannerSignals()
        
    def start(self):
        """Start the background scanner."""
        if self.running:
            logger.warning("Background scanner is already running")
            return
            
        self.running = True
        self._stop_event.clear()
        self.thread = threading.Thread(target=self._scan_loop, daemon=True)
        self.thread.start()
        logger.info(f"Background scanner started with interval: {self.interval_minutes} minutes")
        
    def stop(self):
        """Stop the background scanner."""
        if not self.running:
            return
            
        self._stop_event.set()
        if self.thread:
            self.thread.join(timeout=1.0)
        self.running = False
        logger.info("Background scanner stopped")
        
    def set_interval(self, minutes):
        """Set the scan interval.
        
        Args:
            minutes (int): Scan interval in minutes
        """
        self.interval_minutes = max(1, minutes)  # Minimum 1 minute
        logger.info(f"Background scanner interval set to {self.interval_minutes} minutes")
        
    def update_settings(self):
        """Update scanner settings from configuration manager.
        
        This method is called when settings are changed in the application.
        It reads the new settings from the config manager and updates the scanner accordingly.
        """
        if self.config_manager is None:
            logger.warning("Cannot update settings: No config manager available")
            return
            
        try:
            # Update scan interval from config
            interval = self.config_manager.get("scanner", "interval_minutes", 15)
            if interval != self.interval_minutes:
                self.set_interval(interval)
                logger.info(f"Updated background scanner interval to {interval} minutes")
                
            # Restart the scanner if it's running to apply new settings
            if self.running:
                logger.info("Restarting background scanner to apply new settings")
                self.stop()
                self.start()
                
        except Exception as e:
            logger.error(f"Error updating background scanner settings: {e}")
        
    def _scan_loop(self):
        """Main scanning loop."""
        # Run first scan immediately
        self._scan_folders()
        
        while not self._stop_event.is_set():
            # Sleep for the configured interval, checking periodically if we should stop
            for _ in range(int(self.interval_minutes * 60 / 5)):  # Check every 5 seconds
                if self._stop_event.is_set():
                    return
                time.sleep(5)
                
            # Run a scan if we haven't been stopped
            if not self._stop_event.is_set():
                self._scan_folders()
    
    def _scan_folders(self):
        """Scan all monitored folders for new images."""
        logger.info("Starting background scan for new images")
        self._last_scan_time = datetime.now()
        
        # Emit scan started signal
        self.signals.scan_started.emit()
        
        try:
            # Get all monitored folders from the database
            folders = self.db_manager.get_all_folders()
            
            total_new_images = 0
            total_folders = 0
            
            for folder in folders:
                # Skip folders that don't exist
                folder_path = folder.get('path')
                if not folder_path or not os.path.exists(folder_path):
                    continue
                    
                # Count new images found
                new_images = self._scan_folder(folder_path, folder.get('folder_id'))
                total_new_images += new_images
                
                if new_images > 0:
                    total_folders += 1
            
            if total_new_images > 0:
                logger.info(f"Background scan complete: Found {total_new_images} new images in {total_folders} folders")
            else:
                logger.info("Background scan complete: No new images found")
                
            # Emit scan completed signal
            self.signals.scan_completed.emit(total_new_images, total_folders)
            
        except Exception as e:
            error_msg = f"Error during background scan: {str(e)}"
            logger.error(error_msg)
            # Emit scan error signal
            self.signals.scan_error.emit(error_msg)
    
    def _scan_folder(self, folder_path, folder_id):
        """Scan a single folder for new images.
        
        Args:
            folder_path (str): Path to the folder
            folder_id (int): ID of the folder in the database
            
        Returns:
            int: Number of new images found and added
        """
        if not os.path.exists(folder_path):
            logger.warning(f"Folder does not exist: {folder_path}")
            return 0
            
        # Get existing images for this folder
        existing_images = {}
        db_images = self.db_manager.get_images_in_folder(folder_id)
        
        for img in db_images:
            # Map by filename for quick lookup
            existing_images[os.path.basename(img.get('full_path', ''))] = img
        
        # Counter for new images
        new_images_count = 0
        
        # Scan folder for new images
        try:
            for filename in os.listdir(folder_path):
                # Skip if already in database
                if filename in existing_images:
                    continue
                    
                file_path = os.path.join(folder_path, filename)
                
                # Skip non-files and unsupported formats
                if not os.path.isfile(file_path) or not is_supported_image(file_path):
                    continue
                
                # Try to add to database
                try:
                    self.db_manager.add_image(file_path, folder_id)
                    new_images_count += 1
                    logger.debug(f"Background scanner: Added new image: {file_path}")
                except Exception as e:
                    logger.error(f"Error adding image to database: {file_path} - {e}")
        
        except Exception as e:
            logger.error(f"Error scanning folder {folder_path}: {e}")
        
        return new_images_count
    
    @property
    def last_scan_time(self):
        """Get the time of the last scan.
        
        Returns:
            datetime: Time of the last scan, or None if no scan has been performed
        """
        return self._last_scan_time
