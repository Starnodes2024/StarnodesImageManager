#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Main window integration for enhanced search in StarImageBrowse
Contains functions to integrate the enhanced search into the main window.
"""

import logging
from datetime import datetime
from PyQt6.QtWidgets import QMessageBox, QMenu
from PyQt6.QtGui import QAction
from PyQt6.QtCore import Qt

from src.database.enhanced_search import EnhancedSearch
from src.ui.enhanced_search_panel import EnhancedSearchPanel
from src.ui.database_dimensions_update_dialog import DatabaseDimensionsUpdateDialog
from src.utils.image_dimensions_updater import ImageDimensionsUpdater

logger = logging.getLogger("StarImageBrowse.ui.main_window_search_integration")

def integrate_enhanced_search(main_window):
    """Integrate enhanced search functionality into the main window.
    
    Args:
        main_window: The main window instance to modify
    """
    try:
        # Create enhanced search instance and attach to db_manager
        # Make sure db_ops exists before trying to create EnhancedSearch
        if hasattr(main_window.db_manager, 'db_ops') and main_window.db_manager.db_ops:
            main_window.db_manager.enhanced_search = EnhancedSearch(main_window.db_manager.db_ops)
        else:
            logger.warning("Cannot create enhanced search: db_ops not available")
            return
        
        # Replace the search panel with the enhanced version
        if hasattr(main_window, 'search_panel') and main_window.search_panel:
            # Get the parent widget/layout
            search_panel_parent = main_window.search_panel.parent()
            
            # Create the enhanced search panel
            main_window.enhanced_search_panel = EnhancedSearchPanel(search_panel_parent)
            
            # Replace the old search panel in the layout
            if search_panel_parent:
                layout = search_panel_parent.layout()
                if layout:
                    # Find the search panel in the layout
                    for i in range(layout.count()):
                        if layout.itemAt(i).widget() == main_window.search_panel:
                            # Remove the old search panel
                            main_window.search_panel.setParent(None)
                            # Add the new search panel
                            layout.insertWidget(i, main_window.enhanced_search_panel)
                            break
            
            # Connect the search signal
            main_window.enhanced_search_panel.search_requested.connect(
                lambda params: handle_enhanced_search(main_window, params)
            )
            
            # Update the reference to use for searches going forward
            main_window.search_panel = main_window.enhanced_search_panel
            
            logger.info("Enhanced search panel integration complete")
        else:
            logger.warning("Could not find search panel to replace")
        
        # Add database dimensions update tool to the menu
        add_database_tools_to_menu(main_window)
        
    except Exception as e:
        logger.error(f"Error integrating enhanced search: {e}")
        QMessageBox.critical(
            main_window,
            "Enhanced Search Integration Error",
            f"An error occurred while integrating the enhanced search:\n{str(e)}",
            QMessageBox.StandardButton.Ok
        )

def add_database_tools_to_menu(main_window):
    """Add database tools to the main window menu.
    
    Args:
        main_window: The main window instance
    """
    try:
        # Check if we have the database menu
        if hasattr(main_window, 'menu_database'):
            menu_database = main_window.menu_database
            
            # Create a separator
            menu_database.addSeparator()
            
            # Add Database Maintenance action (comprehensive tool)
            maintenance_action = QAction("Database Maintenance", main_window)
            maintenance_action.setStatusTip("Comprehensive database maintenance, upgrade and optimization")
            maintenance_action.triggered.connect(
                lambda: show_database_maintenance_dialog(main_window)
            )
            menu_database.addAction(maintenance_action)
            
            logger.info("Added database maintenance tool to menu")
    except Exception as e:
        logger.error(f"Error adding database tools to menu: {e}")

def show_database_maintenance_dialog(main_window):
    """Show the comprehensive database maintenance dialog.
    
    Args:
        main_window: The main window instance
    """
    try:
        # Import required components
        from src.ui.database_maintenance_dialog import DatabaseMaintenanceDialog
        
        # Create the dialog
        dialog = DatabaseMaintenanceDialog(
            main_window, 
            main_window.db_manager, 
            main_window.db_manager.enhanced_search
        )
        
        # Show the dialog
        dialog.exec()
        
        # Refresh view after maintenance
        main_window.refresh_current_view()
        
    except Exception as e:
        logger.error(f"Error showing database maintenance dialog: {e}")
        show_error_message(
            main_window,
            "Error",
            f"An error occurred while showing the database maintenance dialog:\n{str(e)}"
        )

def show_dimensions_update_dialog(main_window):
    """Show the database dimensions update dialog.
    
    Args:
        main_window: The main window instance
    """
    try:
        # Create and show the dialog
        dialog = DatabaseDimensionsUpdateDialog(
            main_window, 
            main_window.db_manager, 
            main_window.db_manager.enhanced_search
        )
        dialog.exec()
        
        # Refresh the view after the update
        if hasattr(main_window, 'refresh_current_view'):
            main_window.refresh_current_view()
            
    except Exception as e:
        logger.error(f"Error showing dimensions update dialog: {e}")
        QMessageBox.critical(
            main_window,
            "Error",
            f"An error occurred while showing the dimensions update dialog:\n{str(e)}",
            QMessageBox.StandardButton.Ok
        )

def handle_enhanced_search(main_window, params):
    """Handle enhanced search request.
    
    Args:
        main_window: The main window instance
        params (dict): Search parameters from the enhanced search panel
    """
    try:
        logger.info(f"Enhanced search requested with params: {params}")
        
        # Determine the search scope
        scope = params.get('scope', 'folder')
        folder_id = None
        catalog_id = None
        
        if scope == 'folder':
            if hasattr(main_window, 'current_folder_id'):
                folder_id = main_window.current_folder_id
            else:
                logger.warning("No current folder selected for folder-scoped search")
                show_error_message(main_window, "No folder selected", 
                                 "Please select a folder before searching.")
                return
        elif scope == 'catalog':
            if hasattr(main_window, 'current_catalog_id'):
                catalog_id = main_window.current_catalog_id
            else:
                logger.warning("No current catalog selected for catalog-scoped search")
                show_error_message(main_window, "No catalog selected", 
                                 "Please select a catalog before searching.")
                return
        
        # Limit the number of results for 'all' scope to prevent memory issues
        if scope == 'all':
            # Add a reasonable limit for 'all images' search to prevent memory issues
            # 5000 is a good balance between showing enough results and performance
            max_results = 5000
            logger.info(f"Limiting 'all images' search to {max_results} results")
            results = main_window.db_manager.enhanced_search.search(
                params, folder_id=folder_id, catalog_id=catalog_id, limit=max_results
            )
            
            # Add a note about the limitation to the status message later
            results_limited = True
            total_count = main_window.db_manager.get_image_count()
        else:
            # For folder or catalog searches, no limit needed as they're already scoped
            results = main_window.db_manager.enhanced_search.search(
                params, folder_id=folder_id, catalog_id=catalog_id
            )
            results_limited = False
            total_count = len(results)
        
        # Update the thumbnail browser with results
        if hasattr(main_window, 'thumbnail_browser'):
            # Set a flag to indicate this is a search result
            main_window.thumbnail_browser.is_search_result = True
            
            # Store the search parameters for refresh
            main_window.thumbnail_browser.last_search_params = params
            main_window.thumbnail_browser.last_search_folder_id = folder_id
            main_window.thumbnail_browser.last_search_catalog_id = catalog_id
            
            # Update the view with search results
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
            
            # Create status message with limitation note if applicable
            if results_limited and scope == 'all':
                status_msg = f"Showing {len(results)} of {total_count} images matching {criteria_text} in {scope_text}"
                status_msg += " (results limited to prevent memory issues)"
            else:
                status_msg = f"Found {len(results)} images matching {criteria_text} in {scope_text}"
                
            if hasattr(main_window, 'status_bar'):
                main_window.status_bar.showMessage(status_msg)
            
            # Update window title with search info
            if hasattr(main_window, 'setWindowTitle'):
                base_title = "STARNODES Image Manager"
                if criteria_parts:
                    search_title = f"{base_title} - Search Results: {criteria_text}"
                    main_window.setWindowTitle(search_title)
        else:
            logger.warning("Thumbnail browser not found for displaying search results")
            
    except Exception as e:
        logger.error(f"Error in enhanced search: {e}")
        show_error_message(main_window, "Search Error", 
                         f"An error occurred during the search:\n{str(e)}")

def show_error_message(main_window, title, message):
    """Show an error message dialog.
    
    Args:
        main_window: The main window instance
        title (str): Error title
        message (str): Error message
    """
    QMessageBox.critical(
        main_window,
        title,
        message,
        QMessageBox.StandardButton.Ok
    )
