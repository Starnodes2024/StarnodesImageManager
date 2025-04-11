#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Date search worker for StarImageBrowse
Provides background processing for searching images by date range.
"""

import os
import logging
from datetime import datetime
from PIL import Image, ExifTags
from PyQt6.QtCore import QObject, pyqtSignal, QRunnable

logger = logging.getLogger("StarImageBrowse.ui.date_search_worker")

class DateSearchSignals(QObject):
    """Signals for date search tasks."""
    finished = pyqtSignal(list)  # Results list
    error = pyqtSignal(str)      # Error message
    progress = pyqtSignal(int, int, str)  # current, total, message

class DateSearchWorker(QRunnable):
    """Worker for searching images by date range in a background thread."""
    
    def __init__(self, db_manager, from_date, to_date):
        """Initialize the date search worker.
        
        Args:
            db_manager: Database manager instance
            from_date (datetime): Start date for the search
            to_date (datetime): End date for the search
        """
        super().__init__()
        self.db_manager = db_manager
        self.from_date = from_date
        self.to_date = to_date
        self.signals = DateSearchSignals()
        # Initialize cancelled as False - this will only be set to True by explicit cancellation
        self.cancelled = False
        
        # Log worker initialization
        logger.debug(f"Date search worker initialized: {from_date.date()} to {to_date.date()}")
        
    def cancel(self):
        """Cancel the search operation."""
        logger.debug("User explicitly canceled the date search operation")
        self.cancelled = True
        
    def run(self):
        """Run the date search operation using database-stored date information."""
        try:
            # Don't check for cancellation at the beginning since we just started
            # Start with no cancellation assumption
            
            # Initial progress update
            self.signals.progress.emit(0, 100, "Starting date range search...")
            
            logger.info(f"Searching for images between {self.from_date} and {self.to_date}")
            self.signals.progress.emit(10, 100, "Querying database for images in date range...")
            
            # Convert date objects to strings for SQLite
            from_date_str = self.from_date.strftime('%Y-%m-%d 00:00:00')
            to_date_str = self.to_date.strftime('%Y-%m-%d 23:59:59')
            
            # Only check for cancellation if the user has explicitly clicked the cancel button
            if self.cancelled:
                logger.info("Date search cancelled by user before database query")
                self.signals.error.emit("Search cancelled by user")
                return
            
            # Use the database to find images directly - much faster than file processing
            results = self.db_manager.get_images_by_date_range(from_date_str, to_date_str, limit=1000000)
            
            # Only check for cancellation if the user has explicitly clicked the cancel button
            if self.cancelled:
                logger.info("Date search cancelled by user after database query")
                self.signals.error.emit("Search cancelled by user")
                return
            
            # Completely avoid any progress update between initial and completion
            # Skip directly to completion to avoid any false cancellation triggers
            msg = f"Found {len(results)} images in date range"
            logger.debug(f"Date search completed: {msg}")
            
            # Only check for explicit user cancellation
            if self.cancelled:
                logger.info("Date search explicitly cancelled by user")
                self.signals.error.emit("Search cancelled by user")
                return
                
            # We found results, emit them directly - no further progress updates
            # This avoids any potential signal issues that might be triggering false cancellations
            self.signals.finished.emit(results)
            
        except Exception as e:
            logger.error(f"Error in date search: {e}")
            # Only emit error if we didn't explicitly cancel
            if not self.cancelled:
                self.signals.error.emit(str(e))
