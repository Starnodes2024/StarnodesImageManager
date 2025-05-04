#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Thumbnail browser factory for StarImageBrowse
Creates the appropriate thumbnail browser implementation based on settings
"""

import logging
from .thumbnail_browser import ThumbnailBrowser

logger = logging.getLogger("StarImageBrowse.ui.thumbnail_browser_factory")

def create_thumbnail_browser(db_manager, config_manager, parent=None, language_manager=None):
    """Create the appropriate thumbnail browser based on configuration settings.
    
    Args:
        db_manager: Database manager instance
        config_manager: Configuration manager instance
        parent: Parent widget
        language_manager: Language manager instance for translations
        
    Returns:
        A thumbnail browser instance
    """
    # Always use standard thumbnail browser for better visual appearance
    # This fixes selection highlight issues and provides a more consistent experience
    
    # Log collection size for informational purposes
    collection_size = db_manager.get_image_count()
    logger.info(f"Creating standard thumbnail browser for collection ({collection_size} images)")
    
    # Always return the standard thumbnail browser
    logger.info("Using standard thumbnail browser")
    # Create the thumbnail browser with language manager if provided
    browser = ThumbnailBrowser(db_manager, parent)
    
    # Set language manager explicitly to ensure translations work
    if language_manager:
        browser.language_manager = language_manager
        logger.info(f"Language manager set for thumbnail browser: {language_manager.current_language}")
    
    return browser
