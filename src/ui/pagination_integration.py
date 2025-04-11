#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Pagination integration for StarImageBrowse
Integrates pagination into the main application
"""

import logging
from .thumbnail_browser_pagination import enable_pagination_for_browser

logger = logging.getLogger("StarImageBrowse.ui.pagination_integration")

def integrate_pagination(main_window):
    """
    Integrate pagination features into the main window
    
    Args:
        main_window: The main application window
    """
    # Check if we have a thumbnail browser
    if not hasattr(main_window, 'thumbnail_browser'):
        logger.warning("No thumbnail browser found to add pagination to")
        return False
    
    try:
        # Enable pagination for the thumbnail browser
        pagination = enable_pagination_for_browser(main_window.thumbnail_browser)
        
        # Store the pagination controller in the main window for future reference
        main_window.thumbnail_pagination = pagination
        
        # Check if enhanced_search attribute exists before attempting to use it
        has_enhanced_search = hasattr(main_window.db_manager, 'enhanced_search') and main_window.db_manager.enhanced_search is not None
        
        # Add a DB manager method to count search results if needed and enhanced_search exists
        if has_enhanced_search and not hasattr(main_window.db_manager.enhanced_search, 'count_results'):
            def count_results(self, params, folder_id=None, catalog_id=None):
                """Count results without fetching all records"""
                # Build a similar query as search but with COUNT()
                conn = self.db_ops.db.get_connection()
                if not conn:
                    return 0
                
                try:
                    # Build query parts similar to search method
                    query_parts = []
                    query_params = []
                    
                    # Base query depends on scope
                    if folder_id is not None:
                        base_query = "SELECT COUNT(*) FROM images WHERE folder_id = ?"
                        query_params.append(folder_id)
                    elif catalog_id is not None:
                        base_query = """
                            SELECT COUNT(i.image_id) FROM images i
                            JOIN image_catalog_mapping m ON i.image_id = m.image_id
                            WHERE m.catalog_id = ?
                        """
                        query_params.append(catalog_id)
                    else:
                        base_query = "SELECT COUNT(*) FROM images WHERE 1=1"
                    
                    # Add text search
                    if params.get('text_enabled', False) and params.get('text_query'):
                        query_text = params['text_query'].strip()
                        if query_text:
                            like_pattern = f"%{query_text}%"
                            query_parts.append("(ai_description LIKE ? OR user_description LIKE ? OR filename LIKE ?)")
                            query_params.extend([like_pattern, like_pattern, like_pattern])
                    
                    # Add date range
                    if params.get('date_enabled', False):
                        date_from = params.get('date_from')
                        date_to = params.get('date_to')
                        
                        if date_from and date_to:
                            query_parts.append("last_modified_date BETWEEN ? AND ?")
                            query_params.append(date_from)
                            query_params.append(date_to)
                    
                    # Add dimensions
                    if params.get('dimensions_enabled', False):
                        # Add a condition to filter only images that have dimensions stored
                        query_parts.append("(width IS NOT NULL AND height IS NOT NULL)")
                        
                        # Apply dimension filters
                        min_width = params.get('min_width')
                        max_width = params.get('max_width')
                        min_height = params.get('min_height')
                        max_height = params.get('max_height')
                        
                        if min_width is not None and min_width > 0:
                            query_parts.append("width >= ?")
                            query_params.append(min_width)
                        
                        if max_width is not None and max_width < 10000:
                            query_parts.append("width <= ?")
                            query_params.append(max_width)
                        
                        if min_height is not None and min_height > 0:
                            query_parts.append("height >= ?")
                            query_params.append(min_height)
                        
                        if max_height is not None and max_height < 10000:
                            query_parts.append("height <= ?")
                            query_params.append(max_height)
                    
                    # Combine all parts
                    final_query = base_query
                    if query_parts:
                        final_query += " AND " + " AND ".join(query_parts)
                    
                    # Execute count query
                    cursor = conn.execute(final_query, tuple(query_params))
                    count = cursor.fetchone()[0]
                    
                    return count
                
                except Exception as e:
                    logger.error(f"Error counting search results: {e}")
                    return 0
            
            # Add the count_results method to EnhancedSearch
            import types
            # Only add the method if enhanced_search exists
            if has_enhanced_search:
                main_window.db_manager.enhanced_search.count_results = types.MethodType(
                    count_results, main_window.db_manager.enhanced_search
                )
        
        # Add method to get folder image count if it doesn't exist
        if not hasattr(main_window.db_manager, 'get_image_count_for_folder'):
            def get_image_count_for_folder(self, folder_id):
                """Get the number of images in a folder"""
                conn = self.db.get_connection()
                if not conn:
                    return 0
                
                try:
                    cursor = conn.execute(
                        "SELECT COUNT(*) FROM images WHERE folder_id = ?", 
                        (folder_id,)
                    )
                    count = cursor.fetchone()[0]
                    return count
                except Exception as e:
                    logger.error(f"Error counting folder images: {e}")
                    return 0
            
            # Add the get_image_count_for_folder method to DB manager
            import types
            main_window.db_manager.get_image_count_for_folder = types.MethodType(
                get_image_count_for_folder, main_window.db_manager
            )
        
        logger.info("Pagination successfully integrated")
        return True
        
    except Exception as e:
        logger.error(f"Error integrating pagination: {e}")
        return False
