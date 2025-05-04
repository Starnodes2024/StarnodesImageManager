#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Main window language integration for StarImageBrowse
Handles applying translations to the main window UI.
"""

import logging

logger = logging.getLogger("StarImageBrowse.ui.main_window_language")

def apply_language_to_main_window(main_window, language_manager):
    """Apply translations to the main window UI.
    
    Args:
        main_window: Main window instance
        language_manager: Language manager instance
    """
    try:
        logger.info(f"Applying language: {language_manager.current_language}")
        
        # Store the language manager in the main window
        main_window.language_manager = language_manager
        
        # Apply translations to menus
        apply_menu_translations(main_window, language_manager)
        
        # Apply translations to panels
        apply_panel_translations(main_window, language_manager)
        
        # Apply translations to other UI elements
        apply_other_ui_translations(main_window, language_manager)
        
        logger.info("Language applied successfully")
    except Exception as e:
        logger.error(f"Error applying language: {e}")

def apply_menu_translations(main_window, language_manager):
    """Apply translations to menus.
    
    Args:
        main_window: Main window instance
        language_manager: Language manager instance
    """
    # File menu
    if hasattr(main_window, 'file_menu'):
        main_window.file_menu.setTitle(language_manager.translate('main', 'file_menu', 'File'))
        
        # File menu actions
        if hasattr(main_window, 'add_folder_action'):
            main_window.add_folder_action.setText(language_manager.translate('file_menu', 'add_folder', 'Add Folder'))
        
        if hasattr(main_window, 'scan_folder_action'):
            main_window.scan_folder_action.setText(language_manager.translate('file_menu', 'scan_folder', 'Scan Folder'))
        
        if hasattr(main_window, 'remove_folder_action'):
            main_window.remove_folder_action.setText(language_manager.translate('file_menu', 'remove_folder', 'Remove Folder'))
        
        if hasattr(main_window, 'export_action'):
            main_window.export_action.setText(language_manager.translate('file_menu', 'export_images', 'Export Images'))
        
        if hasattr(main_window, 'exit_action'):
            main_window.exit_action.setText(language_manager.translate('file_menu', 'exit', 'Exit'))
    
    # Edit menu
    if hasattr(main_window, 'edit_menu'):
        main_window.edit_menu.setTitle(language_manager.translate('main', 'edit_menu', 'Edit'))
        
        # Edit menu actions
        if hasattr(main_window, 'copy_action'):
            main_window.copy_action.setText(language_manager.translate('edit_menu', 'copy', 'Copy'))
        
        if hasattr(main_window, 'copy_to_clipboard_action'):
            main_window.copy_to_clipboard_action.setText(language_manager.translate('edit_menu', 'copy_to_clipboard', 'Copy to Clipboard'))
        
        if hasattr(main_window, 'locate_on_disk_action'):
            main_window.locate_on_disk_action.setText(language_manager.translate('edit_menu', 'locate_on_disk', 'Locate on Disk'))
        
        if hasattr(main_window, 'delete_action'):
            main_window.delete_action.setText(language_manager.translate('edit_menu', 'delete', 'Delete'))
    
    # View menu
    if hasattr(main_window, 'view_menu'):
        main_window.view_menu.setTitle(language_manager.translate('main', 'view_menu', 'View'))
        
        # View menu actions
        if hasattr(main_window, 'all_images_action'):
            main_window.all_images_action.setText(language_manager.translate('view_menu', 'all_images', 'All Images'))
        
        if hasattr(main_window, 'refresh_action'):
            main_window.refresh_action.setText(language_manager.translate('view_menu', 'refresh', 'Refresh'))
    
    # Tools menu
    if hasattr(main_window, 'tools_menu'):
        main_window.tools_menu.setTitle(language_manager.translate('main', 'tools_menu', 'Tools'))
        
        # Tools menu actions
        if hasattr(main_window, 'settings_action'):
            main_window.settings_action.setText(language_manager.translate('tools_menu', 'settings', 'Settings'))
        
        if hasattr(main_window, 'database_menu'):
            main_window.database_menu.setTitle(language_manager.translate('tools_menu', 'database', 'Database'))
        
        if hasattr(main_window, 'generate_descriptions_action'):
            main_window.generate_descriptions_action.setText(language_manager.translate('tools_menu', 'generate_descriptions', 'Generate Descriptions'))
    
    # Help menu
    if hasattr(main_window, 'help_menu'):
        main_window.help_menu.setTitle(language_manager.translate('main', 'help_menu', 'Help'))
        
        # Help menu actions
        if hasattr(main_window, 'about_action'):
            main_window.about_action.setText(language_manager.translate('help_menu', 'about', 'About'))
        
        if hasattr(main_window, 'help_action'):
            main_window.help_action.setText(language_manager.translate('help_menu', 'help', 'Help'))

def apply_panel_translations(main_window, language_manager):
    """Apply translations to panels and call retranslateUi on all panels supporting it."""
    # Folder panel
    if hasattr(main_window, 'folder_panel'):
        if hasattr(main_window.folder_panel, 'header_label'):
            main_window.folder_panel.header_label.setText(language_manager.translate('folder_panel', 'title', 'Folders'))
        if hasattr(main_window.folder_panel, 'add_button'):
            main_window.folder_panel.add_button.setText(language_manager.translate('folder_panel', 'add', '+'))
            main_window.folder_panel.add_button.setToolTip(language_manager.translate('folder_panel', 'add', 'Add'))
        if hasattr(main_window.folder_panel, 'retranslateUi'):
            main_window.folder_panel.retranslateUi()
    # Catalog panel
    if hasattr(main_window, 'catalog_panel'):
        if hasattr(main_window.catalog_panel, 'header_label'):
            main_window.catalog_panel.header_label.setText(language_manager.translate('catalog_panel', 'title', 'Catalogs'))
        if hasattr(main_window.catalog_panel, 'add_button'):
            main_window.catalog_panel.add_button.setText(language_manager.translate('catalog_panel', 'add', '+'))
            main_window.catalog_panel.add_button.setToolTip(language_manager.translate('catalog_panel', 'add', 'Add'))
        if hasattr(main_window.catalog_panel, 'retranslateUi'):
            main_window.catalog_panel.retranslateUi()
    # Metadata panel
    if hasattr(main_window, 'metadata_panel'):
        if hasattr(main_window.metadata_panel, 'set_language_manager'):
            main_window.metadata_panel.set_language_manager(language_manager)
        elif hasattr(main_window.metadata_panel, 'retranslateUi'):
            main_window.metadata_panel.retranslateUi()
    # Enhanced search panel
    if hasattr(main_window, 'enhanced_search_panel'):
        if hasattr(main_window.enhanced_search_panel, 'set_language_manager'):
            main_window.enhanced_search_panel.set_language_manager(language_manager)
        elif hasattr(main_window.enhanced_search_panel, 'retranslateUi'):
            main_window.enhanced_search_panel.retranslateUi()
    # Search panel
    if hasattr(main_window, 'search_panel'):
        if hasattr(main_window.search_panel, 'header_label'):
            main_window.search_panel.header_label.setText(language_manager.translate('search', 'title', 'Search'))
        if hasattr(main_window.search_panel, 'search_button'):
            main_window.search_panel.search_button.setText(language_manager.translate('search', 'search_button', 'Search'))
        if hasattr(main_window.search_panel, 'clear_button'):
            main_window.search_panel.clear_button.setText(language_manager.translate('search', 'clear_button', 'Clear'))
        if hasattr(main_window.search_panel, 'retranslateUi'):
            main_window.search_panel.retranslateUi()

def apply_other_ui_translations(main_window, language_manager):
    """Apply translations to other UI elements.
    
    Args:
        main_window: Main window instance
        language_manager: Language manager instance
    """
    # Window title
    main_window.setWindowTitle(language_manager.translate('main', 'title', 'StarImageBrowse'))
    
    # Other UI elements can be added here as needed

def on_language_changed(main_window, language_code):
    """Handle language change event.
    
    Args:
        main_window: Main window instance
        language_code: New language code
    """
    try:
        # Load the new language
        main_window.language_manager.load_language(language_code)
        
        # Clear and rebuild the menu bar to ensure all menu items update
        if hasattr(main_window, 'menuBar') and callable(main_window.menuBar):
            main_window.menuBar().clear()
            if hasattr(main_window, 'setup_menus') and callable(main_window.setup_menus):
                main_window.setup_menus()
        # Apply translations to panels and other UI
        apply_language_to_main_window(main_window, main_window.language_manager)
        
        logger.info(f"Language changed to: {language_code}")
    except Exception as e:
        logger.error(f"Error changing language: {e}")
