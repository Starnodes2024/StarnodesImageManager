#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Background scanner for StarImageBrowse
Provides a background worker that periodically scans folders for new images.
"""

import os
import time
import logging
import threading
from datetime import datetime, timedelta
from PyQt6.QtCore import QObject, pyqtSignal

logger = logging.getLogger("StarImageBrowse.processing.background_scanner")

class BackgroundScannerSignals(QObject):
    """Signals for the background scanner."""
    
    scan_started = pyqtSignal(str)  # Emitted when a scan starts (folder_path)
    scan_progress = pyqtSignal(str, int, int)  # Emitted during scan (folder_path, current, total)
    scan_completed = pyqtSignal(str, dict)  # Emitted when a scan completes (folder_path, results)
    scan_error = pyqtSignal(str, str)  # Emitted on scan error (folder_path, error_message)
    
class BackgroundScanner:
    """Background scanner that periodically checks for new images."""
    
    def __init__(self, image_scanner, db_manager, config_manager):
        """Initialize the background scanner.
        
        Args:
            image_scanner: Image scanner instance
            db_manager: Database manager instance
            config_manager: Configuration manager instance
        """
        self.image_scanner = image_scanner
        self.db_manager = db_manager
        self.config_manager = config_manager
        
        # Create signals object
        self.signals = BackgroundScannerSignals()
        
        # Initialize state
        self.running = False
        self.scan_thread = None
        self.scan_interval = self.config_manager.get("scanning", "background_interval_minutes", 30)
        self.enabled = self.config_manager.get("scanning", "enable_background_scanning", False)
        self.last_scan_time = datetime.now() - timedelta(minutes=self.scan_interval)  # Force scan on first check
        
        logger.info(f"Background scanner initialized (enabled: {self.enabled}, interval: {self.scan_interval} minutes)")
    
    def start(self):
        """Start the background scanner."""
        if self.running:
            logger.warning("Background scanner is already running")
            return
            
        if not self.enabled:
            logger.info("Background scanner is disabled in settings")
            return
            
        self.running = True
        self.scan_thread = threading.Thread(target=self._scanner_worker, daemon=True)
        self.scan_thread.start()
        
        logger.info("Background scanner started")
    
    def stop(self):
        """Stop the background scanner."""
        if not self.running:
            logger.warning("Background scanner is not running")
            return
            
        self.running = False
        if self.scan_thread and self.scan_thread.is_alive():
            # Wait for thread to terminate (with timeout)
            self.scan_thread.join(timeout=2.0)
            
        logger.info("Background scanner stopped")
    
    def _scanner_worker(self):
        """Worker function that runs in the background thread."""
        logger.debug("Scanner worker thread started")
        
        while self.running:
            try:
                # Check if it's time to scan
                current_time = datetime.now()
                elapsed_minutes = (current_time - self.last_scan_time).total_seconds() / 60
                
                if elapsed_minutes >= self.scan_interval:
                    # Time to scan
                    logger.info(f"Starting background scan after {elapsed_minutes:.1f} minutes")
                    self._scan_all_folders()
                    self.last_scan_time = current_time
                    
                # Sleep before next check (check every minute if we should scan)
                # This allows the scanner to respond more quickly to stop requests
                for _ in range(min(60, self.scan_interval * 60 // 10)):
                    if not self.running:
                        break
                    time.sleep(0.1)  # 100ms
            
            except Exception as e:
                logger.error(f"Error in background scanner worker: {e}")
                # Wait a bit before retrying
                time.sleep(5)
    
    def _scan_all_folders(self):
        """Scan all enabled folders for new images."""
        try:
            # Get enabled folders
            folders = self.db_manager.get_folders(enabled_only=True)
            
            # Skip if no folders to scan
            if not folders:
                logger.info("No folders to scan")
                return
                
            # Process each folder
            total_new_images = 0
            total_errors = 0
            
            for folder in folders:
                folder_id = folder["folder_id"]
                folder_path = folder["path"]
                
                # Skip folders that don't exist
                if not os.path.exists(folder_path) or not os.path.isdir(folder_path):
                    logger.warning(f"Background scan: Skipping non-existent folder: {folder_path}")
                    continue
                
                # Skip folders that were scanned recently (within the last hour)
                last_scan_time = folder.get("last_scan_time")
                if last_scan_time:
                    try:
                        # Parse the last scan time from the database
                        if isinstance(last_scan_time, str):
                            last_scan_time = datetime.fromisoformat(last_scan_time.replace("Z", "+00:00"))
                        
                        # Check if it was scanned within the last hour
                        elapsed_hours = (datetime.now() - last_scan_time).total_seconds() / 3600
                        if elapsed_hours < 1:
                            logger.debug(f"Background scan: Skipping recently scanned folder: {folder_path} ({elapsed_hours:.1f} hours ago)")
                            continue
                    except Exception as e:
                        logger.warning(f"Error parsing last scan time: {e}")
                
                # Emit started signal
                self.signals.scan_started.emit(folder_path)
                
                try:
                    # Define a progress callback
                    def progress_callback(current, total):
                        self.signals.scan_progress.emit(folder_path, current, total)
                    
                    # Scan the folder
                    results = self.image_scanner.scan_folder(folder_id, folder_path, progress_callback)
                    
                    # Update statistics
                    processed = results.get("processed", 0)
                    total_new_images += processed
                    errors = len(results.get("errors", []))
                    total_errors += errors
                    
                    # Log the results
                    logger.info(f"Background scan results for {folder_path}: {processed} new images, {errors} errors")
                    
                    # Emit completed signal
                    self.signals.scan_completed.emit(folder_path, results)
                    
                except Exception as e:
                    logger.error(f"Error scanning folder in background: {folder_path} - {e}")
                    total_errors += 1
                    self.signals.scan_error.emit(folder_path, str(e))
            
            # Log overall results
            logger.info(f"Background scan complete: {total_new_images} new images, {total_errors} errors")
            
        except Exception as e:
            logger.error(f"Error in background scanner: {e}")
    
    def update_settings(self):
        """Update settings from the config manager."""
        # Get latest settings
        self.scan_interval = self.config_manager.get("scanning", "background_interval_minutes", 30)
        new_enabled = self.config_manager.get("scanning", "enable_background_scanning", False)
        
        # Handle enable/disable changes
        if new_enabled != self.enabled:
            self.enabled = new_enabled
            
            if self.enabled and not self.running:
                # Start the scanner if newly enabled
                self.start()
            elif not self.enabled and self.running:
                # Stop the scanner if newly disabled
                self.stop()
        
        logger.info(f"Background scanner settings updated (enabled: {self.enabled}, interval: {self.scan_interval} minutes)")
