#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Path normalization utility for StarImageBrowse
Fixes inconsistent path separators in the database and provides path utilities
"""

import os
import logging
import sys
import sqlite3
from pathlib import Path

# Add the parent directory to the path so we can import our modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

logger = logging.getLogger("StarImageBrowse.utilities.path_fixer")

class PathFixer:
    """Utility to fix path issues in the database and provide path normalization functions."""
    
    def __init__(self, db_path=None):
        """Initialize the path fixer.
        
        Args:
            db_path (str, optional): Path to the database file
        """
        # Use a default database path if not provided
        if not db_path:
            db_path = os.path.join(os.path.expanduser("~"), "STARNODES_ImageManager.db")
            
        self.db_path = db_path
        logger.info(f"Path fixer initialized with database: {db_path}")
        
    @staticmethod
    def normalize_path(path):
        """Normalize a file path to use consistent separators.
        
        Args:
            path (str): The path to normalize
            
        Returns:
            str: Normalized path using the OS-specific separator
        """
        if not path:
            return path
            
        # First convert to standard form with forward slashes
        normalized = os.path.normpath(path.replace('\\', '/'))
        # Then convert to os-specific path format
        return os.path.normpath(normalized)
        
    def fix_database_paths(self, dry_run=True):
        """Fix all paths in the database to use consistent separators.
        
        Args:
            dry_run (bool): If True, just report issues without fixing
            
        Returns:
            dict: Statistics about the fix operation
        """
        logger.info(f"Scanning database for path issues (dry_run={dry_run})")
        
        stats = {
            "processed": 0,
            "fixed": 0,
            "errors": 0,
            "skipped": 0
        }
        
        try:
            # Connect directly to the database
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Get all images from the database
            cursor.execute("SELECT image_id, filename, full_path FROM images")
            images = cursor.fetchall()
            stats["processed"] = len(images)
            
            logger.info(f"Found {len(images)} images in database")
            # Show a sample of paths for debugging
            if len(images) > 0:
                sample_size = min(5, len(images))
                logger.info("Sample paths from database:")
                for i in range(sample_size):
                    logger.info(f"  Image {images[i]['image_id']}: {images[i]['full_path']}")
            
            for image in images:
                try:
                    image_id = image["image_id"]
                    filename = image["filename"]
                    current_path = image["full_path"]
                    
                    # Normalize the path
                    normalized_path = self.normalize_path(current_path)
                    
                    # Check if the path needs to be fixed
                    if normalized_path != current_path:
                        logger.info(f"Found path to fix: ID={image_id}")
                        logger.info(f"  Old: '{current_path}'")
                        logger.info(f"  New: '{normalized_path}'")
                        logger.info(f"  Difference: '{''.join(c1 if c1 == c2 else f'[{c1}->{c2}]' for c1, c2 in zip(current_path, normalized_path if len(normalized_path) <= len(current_path) else normalized_path[:len(current_path)])) + ('' if len(normalized_path) <= len(current_path) else normalized_path[len(current_path):])}")
                        
                        # Try to check if the normalized path exists
                        exists = os.path.exists(normalized_path)
                        logger.info(f"  Path exists: {exists}")
                        
                        if not dry_run:
                            # Update the path in the database
                            update_cursor = conn.cursor()
                            update_cursor.execute(
                                "UPDATE images SET full_path = ? WHERE image_id = ?",
                                (normalized_path, image_id)
                            )
                            
                            if update_cursor.rowcount > 0:
                                stats["fixed"] += 1
                                logger.info(f"  Fixed successfully")
                            else:
                                stats["errors"] += 1
                                logger.warning(f"  Failed to update path in database")
                    else:
                        stats["skipped"] += 1
                        if image_id % 50 == 0:  # Log periodically to show progress
                            logger.debug(f"Checking path: {image_id} - {current_path} - Already normalized")
                        
                except Exception as e:
                    stats["errors"] += 1
                    logger.error(f"Error processing image ID {image_id}: {e}")
            
            # Commit changes if not a dry run
            if not dry_run:
                conn.commit()
                logger.info("All changes committed to database")
                
        except Exception as e:
            logger.error(f"Database error: {e}")
            stats["errors"] += 1
            
        finally:
            if 'conn' in locals():
                conn.close()
                
        logger.info(f"Path fix scan completed: {stats}")
        return stats
        
    def fix_single_image_path(self, image_id, dry_run=False):
        """Fix the path for a single image.
        
        Args:
            image_id (int): ID of the image to fix
            dry_run (bool): If True, just report issues without fixing
            
        Returns:
            bool: True if successful or no fix needed, False otherwise
        """
        try:
            # Get the image from the database
            image = self.db_manager.get_image_by_id(image_id)
            if not image:
                logger.warning(f"Image not found with ID: {image_id}")
                return False
                
            current_path = image["full_path"]
            
            # Normalize the path
            normalized_path = self.normalize_path(current_path)
            
            # Check if the path needs to be fixed
            if normalized_path != current_path:
                logger.info(f"Found path to fix: ID={image_id}")
                logger.info(f"  Old: '{current_path}'")
                logger.info(f"  New: '{normalized_path}'")
                
                # Try to check if the normalized path exists
                exists = os.path.exists(normalized_path)
                logger.info(f"  Path exists: {exists}")
                
                if not dry_run:
                    # Update the path in the database
                    filename = os.path.basename(normalized_path)
                    success = self.db_manager.update_image_path(image_id, filename, normalized_path)
                    
                    if success:
                        logger.info(f"  Fixed successfully")
                        return True
                    else:
                        logger.warning(f"  Failed to update path in database")
                        return False
            else:
                logger.info(f"Path already normalized for image ID: {image_id}")
                return True
                
        except Exception as e:
            logger.error(f"Error fixing path for image ID {image_id}: {e}")
            return False
            
    def find_similar_paths(self, path):
        """Find similar paths that might match the given path with different separators.
        
        Args:
            path (str): The path to find similar paths for
            
        Returns:
            list: List of similar paths that exist on disk
        """
        try:
            dirname = os.path.dirname(path)
            basename = os.path.basename(path)
            
            # Ensure the directory exists
            if not os.path.exists(dirname):
                logger.warning(f"Directory doesn't exist: {dirname}")
                return []
                
            # List files in the directory
            files = os.listdir(dirname)
            
            # Find similar filenames
            if '.' in basename:
                name_part, ext = basename.rsplit('.', 1)
                similar_files = [f for f in files if f.startswith(name_part) and f.endswith(ext)]
            else:
                similar_files = [f for f in files if f.startswith(basename)]
                
            # Convert to full paths
            similar_paths = [os.path.join(dirname, f) for f in similar_files]
            
            return similar_paths
            
        except Exception as e:
            logger.error(f"Error finding similar paths for {path}: {e}")
            return []

def run_path_fixer():
    """Run the path fixer as a standalone utility."""
    import argparse
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Fix path issues in StarImageBrowse database')
    parser.add_argument('--fix', action='store_true', help='Actually fix issues (default is dry run)')
    parser.add_argument('--db-path', type=str, help='Path to the database file')
    
    args = parser.parse_args()
    
    # Determine database path
    db_path = args.db_path
    if not db_path:
        # Try to detect default database location
        default_paths = [
            os.path.join(os.path.expanduser("~"), "STARNODES_ImageManager.db"),
            os.path.join(os.path.expanduser("~"), "Documents", "STARNODES_ImageManager.db"),
            os.path.join(os.getcwd(), "STARNODES_ImageManager.db")
        ]
        
        for path in default_paths:
            if os.path.exists(path):
                db_path = path
                logger.info(f"Found database at: {db_path}")
                break
                
        if not db_path:
            logger.error("Database path not specified and could not find default database")
            logger.error("Please specify database path with --db-path argument")
            return
    
    # Run the path fixer
    fixer = PathFixer(db_path)
    
    logger.info(f"Starting database path scan and fix (dry_run={not args.fix})")
    stats = fixer.fix_database_paths(not args.fix)
    logger.info(f"Path fix complete: {stats}")
    logger.info(f"Run with --fix to actually apply the changes" if not args.fix else "All changes applied")

if __name__ == "__main__":
    run_path_fixer()
