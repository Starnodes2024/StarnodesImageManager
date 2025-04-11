#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Pagination for Standard Thumbnail Browser in StarImageBrowse
Adds pagination controls to handle large image collections efficiently
"""

import logging
from PyQt6.QtWidgets import QPushButton, QLabel, QHBoxLayout, QWidget
from PyQt6.QtCore import Qt

logger = logging.getLogger("StarImageBrowse.ui.thumbnail_browser_pagination")

class ThumbnailBrowserPagination:
    """
    Helper class to add pagination to the standard ThumbnailBrowser.
    This implementation loads just 500 thumbnails at a time to prevent memory issues.
    """
    
    def __init__(self, thumbnail_browser):
        """Initialize pagination for the thumbnail browser
        
        Args:
            thumbnail_browser: The ThumbnailBrowser instance to add pagination to
        """
        self.browser = thumbnail_browser
        
        # Add pagination settings with configurable page size
        # Default to 200 thumbnails per page (with options for 20, 50, 100, 200, 500)
        
        # Get page size from config if available
        default_page_size = 200
        if hasattr(self.browser, 'db_manager') and hasattr(self.browser.db_manager, 'config_manager'):
            # Try to get from config manager
            config_manager = self.browser.db_manager.config_manager
            if config_manager:
                page_size = config_manager.get_setting('thumbnails_per_page', default_page_size)
                self.browser.page_size = int(page_size)
            else:
                self.browser.page_size = default_page_size
        else:
            self.browser.page_size = default_page_size
        self.browser.current_page = 0
        self.browser.total_items = 0
        self.browser.total_pages = 0
        self.browser.is_paginated = False
        
        # Create and add pagination controls
        self.add_pagination_controls()
        
    def add_pagination_controls(self):
        """Add pagination controls to the browser's header"""
        # Find the header frame and its layout
        if not hasattr(self.browser, 'header_frame'):
            # Create a header frame if it doesn't exist
            from PyQt6.QtWidgets import QFrame
            self.browser.header_frame = QFrame()
            self.browser.header_frame.setFrameShape(QFrame.Shape.StyledPanel)
            self.browser.header_frame.setMaximumHeight(40)
            header_layout = QHBoxLayout(self.browser.header_frame)
            header_layout.setContentsMargins(10, 5, 10, 5)
            
            # Add header label
            self.browser.header_label = QLabel()
            self.browser.header_label.setStyleSheet("font-weight: bold;")
            header_layout.addWidget(self.browser.header_label)
            
            # Add the header frame to the main layout
            main_layout = self.browser.layout()
            main_layout.insertWidget(0, self.browser.header_frame)
        else:
            # Get the existing header layout
            header_layout = self.browser.header_frame.layout()
        
        # Create pagination controls
        self.browser.prev_button = QPushButton("◀ Prev")
        self.browser.prev_button.setFixedWidth(80)
        self.browser.prev_button.clicked.connect(self.load_previous_page)
        self.browser.prev_button.setVisible(False)
        header_layout.addWidget(self.browser.prev_button)
        
        self.browser.page_info_label = QLabel("")
        self.browser.page_info_label.setFixedWidth(120)
        self.browser.page_info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.browser.page_info_label.setVisible(False)
        header_layout.addWidget(self.browser.page_info_label)
        
        self.browser.next_button = QPushButton("Next ▶")
        self.browser.next_button.setFixedWidth(80)
        self.browser.next_button.clicked.connect(self.load_next_page)
        self.browser.next_button.setVisible(False)
        header_layout.addWidget(self.browser.next_button)
        
        # Add page size selection
        from PyQt6.QtWidgets import QComboBox
        self.browser.page_size_combo = QComboBox()
        self.browser.page_size_combo.addItems(["20", "50", "100", "200", "500"])
        
        # Set the default value based on current page size
        if self.browser.page_size == 20:
            self.browser.page_size_combo.setCurrentIndex(0)
        elif self.browser.page_size == 50:
            self.browser.page_size_combo.setCurrentIndex(1)
        elif self.browser.page_size == 100:
            self.browser.page_size_combo.setCurrentIndex(2)
        elif self.browser.page_size == 200:
            self.browser.page_size_combo.setCurrentIndex(3)
        elif self.browser.page_size == 500:
            self.browser.page_size_combo.setCurrentIndex(4)
        else:
            # Default to 200
            self.browser.page_size_combo.setCurrentIndex(3)
            self.browser.page_size = 200
        
        # Add a label
        page_size_label = QLabel("Per page:")
        header_layout.addWidget(page_size_label)
        
        # Connect the combo box to update the page size
        self.browser.page_size_combo.currentIndexChanged.connect(self.on_page_size_changed)
        header_layout.addWidget(self.browser.page_size_combo)
    
    def update_pagination_controls(self):
        """Update the pagination controls based on current state"""
        # Only show pagination controls if we have multiple pages
        if self.browser.is_paginated and self.browser.total_pages > 1:
            self.browser.prev_button.setVisible(True)
            self.browser.next_button.setVisible(True)
            self.browser.page_info_label.setVisible(True)
            self.browser.page_size_combo.setVisible(True)
            
            # Update page info text
            self.browser.page_info_label.setText(f"Page {self.browser.current_page + 1} of {self.browser.total_pages}")
            
            # Enable/disable buttons based on current page
            self.browser.prev_button.setEnabled(self.browser.current_page > 0)
            self.browser.next_button.setEnabled(self.browser.current_page < self.browser.total_pages - 1)
        else:
            # Hide controls if no pagination
            self.browser.prev_button.setVisible(False)
            self.browser.next_button.setVisible(False)
            self.browser.page_info_label.setVisible(False)
            
            # Always show the page size combo
            self.browser.page_size_combo.setVisible(True)
    
    def load_next_page(self):
        """Load the next page of thumbnails"""
        if not self.browser.is_paginated or self.browser.current_page >= self.browser.total_pages - 1:
            return
        
        # Increment page number
        self.browser.current_page += 1
        
        # Calculate offset
        offset = self.browser.current_page * self.browser.page_size
        
        # Clear existing thumbnails
        self.browser.clear_thumbnails()
        
        # Load the appropriate next page based on context
        if hasattr(self.browser, 'current_search_query') and self.browser.current_search_query is not None:
            # Search context
            images = self.browser.db_manager.search_images(
                self.browser.current_search_query, 
                limit=self.browser.page_size, 
                offset=offset
            )
            self.browser.add_thumbnails(images)
            self.browser.status_message.emit(
                f"Showing page {self.browser.current_page + 1} of {self.browser.total_pages} "
                f"for search '{self.browser.current_search_query}'"
            )
        elif hasattr(self.browser, 'last_search_params') and self.browser.last_search_params:
            # Enhanced search context
            params = self.browser.last_search_params
            folder_id = getattr(self.browser, 'last_search_folder_id', None)
            catalog_id = getattr(self.browser, 'last_search_catalog_id', None)
            
            results = self.browser.db_manager.enhanced_search.search(
                params, folder_id=folder_id, catalog_id=catalog_id, 
                limit=self.browser.page_size, offset=offset
            )
            
            self.browser.add_thumbnails(results)
            self.browser.status_message.emit(
                f"Showing page {self.browser.current_page + 1} of {self.browser.total_pages} "
                f"for search results"
            )
        elif self.browser.current_folder_id is not None:
            # Folder context
            images = self.browser.db_manager.get_images_for_folder(
                self.browser.current_folder_id,
                limit=self.browser.page_size, 
                offset=offset
            )
            self.browser.add_thumbnails(images)
            folder_info = self.browser.db_manager.get_folder_by_id(self.browser.current_folder_id)
            folder_path = folder_info.get('path', 'Unknown') if folder_info else 'Unknown'
            self.browser.status_message.emit(
                f"Showing page {self.browser.current_page + 1} of {self.browser.total_pages} "
                f"for folder '{folder_path}'"
            )
        elif self.browser.current_catalog_id is not None:
            # Catalog context
            images = self.browser.db_manager.get_images_for_catalog(
                self.browser.current_catalog_id,
                limit=self.browser.page_size, 
                offset=offset
            )
            self.browser.add_thumbnails(images)
            catalog_info = self.browser.db_manager.get_catalog_by_id(self.browser.current_catalog_id)
            catalog_name = catalog_info.get('name', 'Unknown') if catalog_info else 'Unknown'
            self.browser.status_message.emit(
                f"Showing page {self.browser.current_page + 1} of {self.browser.total_pages} "
                f"for catalog '{catalog_name}'"
            )
            
        # Update pagination controls
        self.update_pagination_controls()
        
    def on_page_size_changed(self, index):
        """Handle change in page size
        
        Args:
            index (int): Index of the selected page size in the combo box
        """
        # Get the new page size
        page_sizes = [20, 50, 100, 200, 500]
        new_page_size = page_sizes[index]
        
        # Only proceed if the page size has changed
        if new_page_size == self.browser.page_size:
            return
        
        # Store the new page size
        old_page_size = self.browser.page_size
        self.browser.page_size = new_page_size
        
        # Save to config if available
        if hasattr(self.browser, 'db_manager') and hasattr(self.browser.db_manager, 'config_manager'):
            config_manager = self.browser.db_manager.config_manager
            if config_manager:
                config_manager.set_setting('thumbnails_per_page', new_page_size)
        
        # Recalculate pagination
        if self.browser.is_paginated and self.browser.total_items > 0:
            # Calculate new total pages
            self.browser.total_pages = (self.browser.total_items + new_page_size - 1) // new_page_size
            
            # Adjust current page to show approximately the same items
            if old_page_size > 0:  # Avoid division by zero
                # Calculate the first item index in the old view
                first_item_index = self.browser.current_page * old_page_size
                # Calculate new page number to show that item
                self.browser.current_page = first_item_index // new_page_size
            
            # Make sure current page is valid
            self.browser.current_page = min(self.browser.current_page, self.browser.total_pages - 1)
            self.browser.current_page = max(0, self.browser.current_page)
            
            # Refresh the current view
            if hasattr(self.browser, 'refresh'):
                self.browser.refresh()
            else:
                # Manually reload based on context
                offset = self.browser.current_page * new_page_size
                
                # Clear current thumbnails
                self.browser.clear_thumbnails()
                
                # Load appropriate data based on context
                self._reload_current_view(offset)
            
            # Update pagination controls
            self.update_pagination_controls()
    
    def _reload_current_view(self, offset):
        """Reload the current view with the current page size and offset
        
        Args:
            offset (int): Offset to use for loading data
        """
        # Determine what we're currently viewing and reload it
        if hasattr(self.browser, 'current_search_query') and self.browser.current_search_query is not None:
            # Search context
            images = self.browser.db_manager.search_images(
                self.browser.current_search_query, 
                limit=self.browser.page_size, 
                offset=offset
            )
            self.browser.add_thumbnails(images)
        elif hasattr(self.browser, 'last_search_params') and self.browser.last_search_params:
            # Enhanced search context
            params = self.browser.last_search_params
            folder_id = getattr(self.browser, 'last_search_folder_id', None)
            catalog_id = getattr(self.browser, 'last_search_catalog_id', None)
            
            results = self.browser.db_manager.enhanced_search.search(
                params, folder_id=folder_id, catalog_id=catalog_id, 
                limit=self.browser.page_size, offset=offset
            )
            
            self.browser.add_thumbnails(results)
        elif hasattr(self.browser, 'all_images_view') and self.browser.all_images_view:
            # All Images view
            images = self.browser.db_manager.get_all_images(
                limit=self.browser.page_size,
                offset=offset
            )
            self.browser.add_thumbnails(images)
        elif self.browser.current_folder_id is not None:
            # Folder context
            images = self.browser.db_manager.get_images_for_folder(
                self.browser.current_folder_id,
                limit=self.browser.page_size, 
                offset=offset
            )
            self.browser.add_thumbnails(images)
        elif self.browser.current_catalog_id is not None:
            # Catalog context
            images = self.browser.db_manager.get_images_for_catalog(
                self.browser.current_catalog_id,
                limit=self.browser.page_size, 
                offset=offset
            )
            self.browser.add_thumbnails(images)
    
    def load_previous_page(self):
        """Load the previous page of thumbnails"""
        if not self.browser.is_paginated or self.browser.current_page <= 0:
            return
        
        # Decrement page number
        self.browser.current_page -= 1
        
        # Calculate offset
        offset = self.browser.current_page * self.browser.page_size
        
        # Clear existing thumbnails
        self.browser.clear_thumbnails()
        
        # Load the appropriate previous page based on context
        if hasattr(self.browser, 'current_search_query') and self.browser.current_search_query is not None:
            # Search context
            images = self.browser.db_manager.search_images(
                self.browser.current_search_query,
                limit=self.browser.page_size, 
                offset=offset
            )
            self.browser.add_thumbnails(images)
            self.browser.status_message.emit(
                f"Showing page {self.browser.current_page + 1} of {self.browser.total_pages} "
                f"for search '{self.browser.current_search_query}'"
            )
        elif hasattr(self.browser, 'last_search_params') and self.browser.last_search_params:
            # Enhanced search context
            params = self.browser.last_search_params
            folder_id = getattr(self.browser, 'last_search_folder_id', None)
            catalog_id = getattr(self.browser, 'last_search_catalog_id', None)
            
            results = self.browser.db_manager.enhanced_search.search(
                params, folder_id=folder_id, catalog_id=catalog_id, 
                limit=self.browser.page_size, offset=offset
            )
            
            self.browser.add_thumbnails(results)
            self.browser.status_message.emit(
                f"Showing page {self.browser.current_page + 1} of {self.browser.total_pages} "
                f"for search results"
            )
        elif self.browser.current_folder_id is not None:
            # Folder context
            images = self.browser.db_manager.get_images_for_folder(
                self.browser.current_folder_id,
                limit=self.browser.page_size, 
                offset=offset
            )
            self.browser.add_thumbnails(images)
            folder_info = self.browser.db_manager.get_folder_by_id(self.browser.current_folder_id)
            folder_path = folder_info.get('path', 'Unknown') if folder_info else 'Unknown'
            self.browser.status_message.emit(
                f"Showing page {self.browser.current_page + 1} of {self.browser.total_pages} "
                f"for folder '{folder_path}'"
            )
        elif self.browser.current_catalog_id is not None:
            # Catalog context
            images = self.browser.db_manager.get_images_for_catalog(
                self.browser.current_catalog_id,
                limit=self.browser.page_size, 
                offset=offset
            )
            self.browser.add_thumbnails(images)
            catalog_info = self.browser.db_manager.get_catalog_by_id(self.browser.current_catalog_id)
            catalog_name = catalog_info.get('name', 'Unknown') if catalog_info else 'Unknown'
            self.browser.status_message.emit(
                f"Showing page {self.browser.current_page + 1} of {self.browser.total_pages} "
                f"for catalog '{catalog_name}'"
            )
        
        # Update pagination controls
        self.update_pagination_controls()


# Helper function to apply pagination to the standard ThumbnailBrowser
def enable_pagination_for_browser(thumbnail_browser):
    """Apply pagination to a ThumbnailBrowser instance
    
    Args:
        thumbnail_browser: The ThumbnailBrowser instance to add pagination to
        
    Returns:
        The pagination controller instance
    """
    pagination = ThumbnailBrowserPagination(thumbnail_browser)
    
    # Enhance the set_folder method with pagination
    original_set_folder = thumbnail_browser.set_folder
    
    def set_folder_with_pagination(folder_id):
        """Enhanced set_folder method with pagination support"""
        # Reset pagination state
        thumbnail_browser.current_page = 0
        
        # Get folder info
        folder_info = thumbnail_browser.db_manager.get_folder_by_id(folder_id)
        if not folder_info:
            return
            
        # Store folder ID and clear search query
        thumbnail_browser.current_folder_id = folder_id
        if hasattr(thumbnail_browser, 'current_catalog_id'):
            thumbnail_browser.current_catalog_id = None
        if hasattr(thumbnail_browser, 'current_search_query'):
            thumbnail_browser.current_search_query = None
        
        # Get total image count for the folder
        total_count = thumbnail_browser.db_manager.get_image_count_for_folder(folder_id)
        
        # Determine if pagination is needed
        if total_count > thumbnail_browser.page_size:
            # Enable pagination
            thumbnail_browser.is_paginated = True
            thumbnail_browser.total_items = total_count
            thumbnail_browser.total_pages = (total_count + thumbnail_browser.page_size - 1) // thumbnail_browser.page_size
            
            # Get first page only
            images = thumbnail_browser.db_manager.get_images_for_folder(
                folder_id, 
                limit=thumbnail_browser.page_size, 
                offset=0
            )
            
            # Clear thumbnails and add first page
            thumbnail_browser.clear_thumbnails()
            thumbnail_browser.add_thumbnails(images)
            
            # Update folder info display
            folder_path = folder_info.get('path', 'Unknown')
            if hasattr(thumbnail_browser, 'header_label'):
                thumbnail_browser.header_label.setText(f"Folder: {folder_path} ({total_count} images)")
            
            # Update status
            thumbnail_browser.status_message.emit(
                f"Showing page 1 of {thumbnail_browser.total_pages} "
                f"({len(images)} of {total_count} images) from folder '{folder_path}'"
            )
            
            # Update pagination controls
            pagination.update_pagination_controls()
        else:
            # No pagination needed for small folders
            thumbnail_browser.is_paginated = False
            
            # Use the original method for small folders
            original_set_folder(folder_id)
    
    # Replace the original method with our enhanced version
    thumbnail_browser.set_folder = set_folder_with_pagination
    
    # Now enhance the add_thumbnails method for enhanced search
    original_handle_enhanced_search = None
    if hasattr(thumbnail_browser, 'main_window') and hasattr(thumbnail_browser.main_window, 'handle_enhanced_search'):
        original_handle_enhanced_search = thumbnail_browser.main_window.handle_enhanced_search
        
        def handle_enhanced_search_with_pagination(main_window, params):
            """Enhanced search handler with pagination support"""
            # Determine the search scope
            scope = params.get('scope', 'folder')
            folder_id = None
            catalog_id = None
            
            if scope == 'folder':
                if hasattr(main_window, 'current_folder_id'):
                    folder_id = main_window.current_folder_id
                else:
                    return original_handle_enhanced_search(main_window, params)
            elif scope == 'catalog':
                if hasattr(main_window, 'current_catalog_id'):
                    catalog_id = main_window.current_catalog_id
                else:
                    return original_handle_enhanced_search(main_window, params)
            
            # Get total count for pagination
            total_count = main_window.db_manager.enhanced_search.count_results(
                params, folder_id=folder_id, catalog_id=catalog_id
            )
            
            # Reset pagination state
            thumbnail_browser.current_page = 0
            
            # Determine if pagination is needed
            if total_count > thumbnail_browser.page_size:
                # Enable pagination
                thumbnail_browser.is_paginated = True
                thumbnail_browser.total_items = total_count
                thumbnail_browser.total_pages = (total_count + thumbnail_browser.page_size - 1) // thumbnail_browser.page_size
                
                # Get first page only
                results = main_window.db_manager.enhanced_search.search(
                    params, folder_id=folder_id, catalog_id=catalog_id,
                    limit=thumbnail_browser.page_size, offset=0
                )
                
                # Update the thumbnail browser with results
                if hasattr(main_window, 'thumbnail_browser'):
                    # Set flags for search results
                    main_window.thumbnail_browser.is_search_result = True
                    main_window.thumbnail_browser.last_search_params = params
                    main_window.thumbnail_browser.last_search_folder_id = folder_id
                    main_window.thumbnail_browser.last_search_catalog_id = catalog_id
                    
                    # Clear and add new thumbnails
                    main_window.thumbnail_browser.clear_thumbnails()
                    main_window.thumbnail_browser.add_thumbnails(results)
                    
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
                    
                    status_msg = f"Showing page 1 of {thumbnail_browser.total_pages} ({len(results)} of {total_count} images) matching {criteria_text} in {scope_text}"
                    if hasattr(main_window, 'status_bar'):
                        main_window.status_bar.showMessage(status_msg)
                    
                    # Update pagination controls
                    pagination.update_pagination_controls()
            else:
                # No pagination needed for small result sets
                thumbnail_browser.is_paginated = False
                
                # Use the original method for small result sets
                original_handle_enhanced_search(main_window, params)
        
        # Replace the original method with our enhanced version if it exists
        if original_handle_enhanced_search:
            main_window = thumbnail_browser.main_window if hasattr(thumbnail_browser, 'main_window') else None
            if main_window:
                main_window.handle_enhanced_search = handle_enhanced_search_with_pagination
    
    return pagination
