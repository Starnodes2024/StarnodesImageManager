#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
All Images View functionality for StarImageBrowse
Direct implementation of view_all_images method for the MainWindow class.
This is patched directly into the MainWindow class during initialization.
"""

import logging
from PyQt6.QtWidgets import QApplication, QMessageBox

logger = logging.getLogger("StarImageBrowse.ui.main_window_all_images")

def view_all_images(self):
    """Display all images in the database with pagination"""
    try:
        # Update the thumbnail browser UI to show we're loading
        # This ensures UI responsiveness during loading
        self.status_bar.showMessage("Loading all images...")
        QApplication.processEvents()  # Process events to update the UI
        
        # Initialize database extensions if needed
        if not hasattr(self.db_manager, 'get_all_images_count'):
            logger.info("Initializing database extensions for view_all_images")
            from src.database.db_operations_extension import extend_db_operations
            extend_db_operations(self.db_manager)
        
        # Get total count of images for pagination
        total_count = self.db_manager.get_all_images_count()
        
        # Clear any previous search or folder selection
        if hasattr(self.thumbnail_browser, 'current_folder_id'):
            self.thumbnail_browser.current_folder_id = None
        if hasattr(self.thumbnail_browser, 'current_catalog_id'):
            self.thumbnail_browser.current_catalog_id = None
        if hasattr(self.thumbnail_browser, 'current_search_query'):
            self.thumbnail_browser.current_search_query = None
        if hasattr(self.thumbnail_browser, 'last_search_params'):
            self.thumbnail_browser.last_search_params = None
        
        # Set flag to indicate this is the "All Images" view
        self.thumbnail_browser.all_images_view = True
        
        # Reset pagination to first page
        self.thumbnail_browser.current_page = 0
        
        # Get the page size from pagination if available
        page_size = 200  # Default
        if hasattr(self.thumbnail_browser, 'page_size'):
            page_size = self.thumbnail_browser.page_size
        
        # Enable pagination
        self.thumbnail_browser.is_paginated = True
        self.thumbnail_browser.total_items = total_count
        self.thumbnail_browser.total_pages = (total_count + page_size - 1) // page_size
        
        # Get first page of images
        images = self.db_manager.get_all_images(limit=page_size, offset=0)
        
        # Clear thumbnails and add the first page
        self.thumbnail_browser.clear_thumbnails()
        self.thumbnail_browser.add_thumbnails(images)
        
        # Update header with count
        if hasattr(self.thumbnail_browser, 'header_label'):
            self.thumbnail_browser.header_label.setText(f"All Images ({total_count} total)")
        
        # Update status
        page_count = (total_count + page_size - 1) // page_size
        if page_count > 1:
            self.status_bar.showMessage(
                f"Showing page 1 of {page_count} ({len(images)} of {total_count} images)"
            )
        else:
            self.status_bar.showMessage(f"Showing all {len(images)} images")
            
        # Update pagination controls if available
        if hasattr(self.thumbnail_browser, 'thumbnail_pagination') and \
           hasattr(self.thumbnail_browser.thumbnail_pagination, 'update_pagination_controls'):
            self.thumbnail_browser.thumbnail_pagination.update_pagination_controls()
            
        # Update window title
        if hasattr(self, 'setWindowTitle'):
            self.setWindowTitle("Star Image Browse - All Images")
            
    except Exception as e:
        logger.error(f"Error viewing all images: {e}")
        QMessageBox.critical(
            self,
            "Error",
            f"An error occurred while loading all images:\n{str(e)}",
            QMessageBox.StandardButton.Ok
        )
