#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Pagination implementation for StarImageBrowse
Adds pagination to the thumbnail browser to handle large collections efficiently
"""

import logging
from PyQt6.QtWidgets import QPushButton, QLabel, QHBoxLayout
from PyQt6.QtCore import Qt

logger = logging.getLogger("StarImageBrowse.ui.pagination_implementation")

class PaginationMixin:
    """Mixin class to add pagination functionality to VirtualizedThumbnailBrowser"""
    
    def initialize_pagination(self):
        """Initialize pagination settings and controls"""
        # Add pagination settings
        self.page_size = 500  # Number of thumbnails per page
        self.current_page = 0
        self.total_items = 0
        self.total_pages = 0
        self.is_paginated = False
        
        # Create pagination controls
        self.create_pagination_controls()
        
    def create_pagination_controls(self):
        """Create pagination UI controls"""
        # Create pagination controls in the header_layout
        header_layout = self.header_frame.layout()
        
        # Previous page button
        self.prev_button = QPushButton("◀ Prev")
        self.prev_button.setFixedWidth(80)
        self.prev_button.clicked.connect(self.load_previous_page)
        self.prev_button.setVisible(False)
        header_layout.addWidget(self.prev_button)
        
        # Page information label
        self.page_info_label = QLabel("")
        self.page_info_label.setFixedWidth(120)
        self.page_info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.page_info_label.setVisible(False)
        header_layout.addWidget(self.page_info_label)
        
        # Next page button
        self.next_button = QPushButton("Next ▶")
        self.next_button.setFixedWidth(80)
        self.next_button.clicked.connect(self.load_next_page)
        self.next_button.setVisible(False)
        header_layout.addWidget(self.next_button)
        
    def update_pagination_controls(self):
        """Update the pagination controls based on current state"""
        # Only show pagination controls if we have multiple pages
        if self.is_paginated and self.total_pages > 1:
            self.prev_button.setVisible(True)
            self.next_button.setVisible(True)
            self.page_info_label.setVisible(True)
            
            # Update page info text
            self.page_info_label.setText(f"Page {self.current_page + 1} of {self.total_pages}")
            
            # Enable/disable buttons based on current page
            self.prev_button.setEnabled(self.current_page > 0)
            self.next_button.setEnabled(self.current_page < self.total_pages - 1)
        else:
            # Hide controls if no pagination
            self.prev_button.setVisible(False)
            self.next_button.setVisible(False)
            self.page_info_label.setVisible(False)
            
    def add_thumbnails_paginated(self, images, is_paginated=False, total_count=None):
        """Add thumbnails with pagination support
        
        Args:
            images (list): List of image dictionaries from the database
            is_paginated (bool): Whether this is part of a paginated result set
            total_count (int): Total count of items in the result set
        """
        # Update the list of all images
        self.all_images = images
        
        # Update pagination info if needed
        self.is_paginated = is_paginated
        if is_paginated:
            self.total_items = total_count
            self.total_pages = (total_count + self.page_size - 1) // self.page_size
            self.update_pagination_controls()
        else:
            # Hide pagination controls for non-paginated views
            self.prev_button.setVisible(False)
            self.next_button.setVisible(False)
            self.page_info_label.setVisible(False)
        
        # Update the grid widget with the new count
        self.grid.set_item_count(len(images))
        
    def load_next_page(self):
        """Load the next page of thumbnails"""
        if not self.is_paginated or self.current_page >= self.total_pages - 1:
            return
        
        # Increment page number
        self.current_page += 1
        
        # Calculate offset
        offset = self.current_page * self.page_size
        
        # Clear existing thumbnails
        self.thumbnails = {}
        self.selected_thumbnails = set()
        
        # Load the appropriate next page based on context
        if hasattr(self, 'current_search_query') and self.current_search_query is not None:
            # Search context
            images = self.db_manager.search_images(self.current_search_query, limit=self.page_size, offset=offset)
            self.all_images = images
            self.grid.set_item_count(len(images))
            self.status_message.emit(f"Showing page {self.current_page + 1} of {self.total_pages} for search '{self.current_search_query}'")
        elif hasattr(self, 'last_search_params') and self.last_search_params:
            # Enhanced search context
            params = self.last_search_params
            folder_id = getattr(self, 'last_search_folder_id', None)
            catalog_id = getattr(self, 'last_search_catalog_id', None)
            
            results = self.db_manager.enhanced_search.search(
                params, folder_id=folder_id, catalog_id=catalog_id, 
                limit=self.page_size, offset=offset
            )
            
            self.all_images = results
            self.grid.set_item_count(len(results))
            self.status_message.emit(f"Showing page {self.current_page + 1} of {self.total_pages} for search results")
        elif self.current_folder_id is not None:
            # Folder context
            images = self.db_manager.get_images_for_folder(self.current_folder_id, limit=self.page_size, offset=offset)
            self.all_images = images
            self.grid.set_item_count(len(images))
            folder_info = self.db_manager.get_folder_by_id(self.current_folder_id)
            folder_path = folder_info.get('path', 'Unknown') if folder_info else 'Unknown'
            self.status_message.emit(f"Showing page {self.current_page + 1} of {self.total_pages} for folder '{folder_path}'")
        elif self.current_catalog_id is not None:
            # Catalog context
            images = self.db_manager.get_images_for_catalog(self.current_catalog_id, limit=self.page_size, offset=offset)
            self.all_images = images
            self.grid.set_item_count(len(images))
            catalog_info = self.db_manager.get_catalog_by_id(self.current_catalog_id)
            catalog_name = catalog_info.get('name', 'Unknown') if catalog_info else 'Unknown'
            self.status_message.emit(f"Showing page {self.current_page + 1} of {self.total_pages} for catalog '{catalog_name}'")
            
        # Update pagination controls
        self.update_pagination_controls()
        
    def load_previous_page(self):
        """Load the previous page of thumbnails"""
        if not self.is_paginated or self.current_page <= 0:
            return
        
        # Decrement page number
        self.current_page -= 1
        
        # Calculate offset
        offset = self.current_page * self.page_size
        
        # Clear existing thumbnails
        self.thumbnails = {}
        self.selected_thumbnails = set()
        
        # Load the appropriate previous page based on context
        if hasattr(self, 'current_search_query') and self.current_search_query is not None:
            # Search context
            images = self.db_manager.search_images(self.current_search_query, limit=self.page_size, offset=offset)
            self.all_images = images
            self.grid.set_item_count(len(images))
            self.status_message.emit(f"Showing page {self.current_page + 1} of {self.total_pages} for search '{self.current_search_query}'")
        elif hasattr(self, 'last_search_params') and self.last_search_params:
            # Enhanced search context
            params = self.last_search_params
            folder_id = getattr(self, 'last_search_folder_id', None)
            catalog_id = getattr(self, 'last_search_catalog_id', None)
            
            results = self.db_manager.enhanced_search.search(
                params, folder_id=folder_id, catalog_id=catalog_id, 
                limit=self.page_size, offset=offset
            )
            
            self.all_images = results
            self.grid.set_item_count(len(results))
            self.status_message.emit(f"Showing page {self.current_page + 1} of {self.total_pages} for search results")
        elif self.current_folder_id is not None:
            # Folder context
            images = self.db_manager.get_images_for_folder(self.current_folder_id, limit=self.page_size, offset=offset)
            self.all_images = images
            self.grid.set_item_count(len(images))
            folder_info = self.db_manager.get_folder_by_id(self.current_folder_id)
            folder_path = folder_info.get('path', 'Unknown') if folder_info else 'Unknown'
            self.status_message.emit(f"Showing page {self.current_page + 1} of {self.total_pages} for folder '{folder_path}'")
        elif self.current_catalog_id is not None:
            # Catalog context
            images = self.db_manager.get_images_for_catalog(self.current_catalog_id, limit=self.page_size, offset=offset)
            self.all_images = images
            self.grid.set_item_count(len(images))
            catalog_info = self.db_manager.get_catalog_by_id(self.current_catalog_id)
            catalog_name = catalog_info.get('name', 'Unknown') if catalog_info else 'Unknown'
            self.status_message.emit(f"Showing page {self.current_page + 1} of {self.total_pages} for catalog '{catalog_name}'")
        
        # Update pagination controls
        self.update_pagination_controls()
        
def apply_pagination_to_enhanced_search(handle_enhanced_search_function):
    """Modify the handle_enhanced_search function to use pagination
    
    This function should be applied to the handle_enhanced_search function in main_window_search_integration.py
    to add pagination support for search results.
    """
    def pagination_wrapper(main_window, params):
        """Wrapper function that adds pagination to enhanced search results"""
        # Determine the search scope
        scope = params.get('scope', 'folder')
        folder_id = None
        catalog_id = None
        
        if scope == 'folder':
            if hasattr(main_window, 'current_folder_id'):
                folder_id = main_window.current_folder_id
            else:
                return
        elif scope == 'catalog':
            if hasattr(main_window, 'current_catalog_id'):
                catalog_id = main_window.current_catalog_id
            else:
                return
        
        # Initialize pagination parameters
        page_size = 500  # Number of items per page
        current_page = 0  # Start with first page
        offset = 0        # No offset for first page
        
        # Get total count first (without limit)
        total_count = main_window.db_manager.enhanced_search.count_results(
            params, folder_id=folder_id, catalog_id=catalog_id
        )
        
        # Get first page of results
        results = main_window.db_manager.enhanced_search.search(
            params, folder_id=folder_id, catalog_id=catalog_id,
            limit=page_size, offset=offset
        )
        
        # Check if results exceed page size (need pagination)
        is_paginated = total_count > page_size
        
        # Update the thumbnail browser with results
        if hasattr(main_window, 'thumbnail_browser'):
            # Set flags for search results
            main_window.thumbnail_browser.is_search_result = True
            main_window.thumbnail_browser.last_search_params = params
            main_window.thumbnail_browser.last_search_folder_id = folder_id
            main_window.thumbnail_browser.last_search_catalog_id = catalog_id
            
            # Make sure pagination is initialized
            if not hasattr(main_window.thumbnail_browser, 'is_paginated'):
                if hasattr(main_window.thumbnail_browser, 'initialize_pagination'):
                    main_window.thumbnail_browser.initialize_pagination()
            
            # Clear thumbnails and add new ones with pagination
            main_window.thumbnail_browser.clear_thumbnails()
            
            # Use paginated version if available
            if hasattr(main_window.thumbnail_browser, 'add_thumbnails_paginated'):
                main_window.thumbnail_browser.add_thumbnails_paginated(
                    results, is_paginated=is_paginated, total_count=total_count
                )
            else:
                # Fallback to standard add_thumbnails
                main_window.thumbnail_browser.add_thumbnails(results)
            
            # Set pagination properties if they exist
            if hasattr(main_window.thumbnail_browser, 'is_paginated'):
                main_window.thumbnail_browser.is_paginated = is_paginated
                main_window.thumbnail_browser.current_page = 0
                main_window.thumbnail_browser.total_items = total_count
                main_window.thumbnail_browser.total_pages = (total_count + page_size - 1) // page_size
                
                # Update pagination controls if available
                if hasattr(main_window.thumbnail_browser, 'update_pagination_controls'):
                    main_window.thumbnail_browser.update_pagination_controls()
            
            # Update status message
            criteria_parts = []
            if params.get('text_enabled', False) and params.get('text_query'):
                criteria_parts.append(f"text '{params['text_query']}'")
            if params.get('date_enabled', False):
                criteria_parts.append("date range")
            if params.get('dimensions_enabled', False):
                criteria_parts.append("image dimensions")
            
            criteria_text = " and ".join(criteria_parts) if criteria_parts else "all images"
            scope_text = "current folder" if scope == 'folder' else "current catalog" if scope == 'catalog' else "all images"
            
            if is_paginated:
                status_msg = f"Showing page 1 of {(total_count + page_size - 1) // page_size} ({len(results)} of {total_count} images) matching {criteria_text} in {scope_text}"
            else:
                status_msg = f"Found {len(results)} images matching {criteria_text} in {scope_text}"
                
            if hasattr(main_window, 'status_bar'):
                main_window.status_bar.showMessage(status_msg)
    
    return pagination_wrapper
