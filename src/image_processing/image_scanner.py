#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Image scanner for StarImageBrowse
Handles scanning directories for images and processing them.
"""

import os
import logging
import hashlib
import traceback
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

logger = logging.getLogger("StarImageBrowse.image_scanner")

class ImageScanner:
    """Scans directories for images and processes them."""
    
    def __init__(self, db_manager, thumbnail_generator, ai_processor=None, max_workers=4):
        """Initialize the image scanner.
        
        Args:
            db_manager: Database manager instance
            thumbnail_generator: Thumbnail generator instance
            ai_processor: AI image processor instance (optional)
            max_workers (int): Maximum number of worker threads
        """
        self.db_manager = db_manager
        self.thumbnail_generator = thumbnail_generator
        self.ai_processor = ai_processor
        self.max_workers = max_workers
        self.supported_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp'}
        
        logger.debug(f"Image scanner initialized with {max_workers} workers")
    
    def is_supported_image(self, file_path):
        """Check if a file is a supported image type.
        
        Args:
            file_path (str): Path to the file
            
        Returns:
            bool: True if the file is a supported image, False otherwise
        """
        try:
            # First check: file extension
            ext = Path(file_path).suffix.lower()
            is_supported_ext = ext in self.supported_extensions
            
            if not is_supported_ext:
                # Some image files might have wrong or missing extensions
                # Log this for debugging but continue with content-based checks
                logger.debug(f"Unsupported file extension: {file_path} (ext: {ext})")
                
                # If it's a file with no extension, we'll still try to check its content
                if ext == '':
                    logger.debug(f"File has no extension, will check content: {file_path}")
                else:
                    # If it has an unsupported extension, return False
                    return False
            
            # Second check: try to open with PIL to verify it's actually an image
            try:
                from PIL import Image, UnidentifiedImageError
                with Image.open(file_path) as img:
                    # Get the actual format detected by PIL
                    actual_format = img.format
                    if actual_format:
                        logger.debug(f"Image format detected: {file_path} (format: {actual_format})")
                        return True
                    else:
                        logger.warning(f"Unknown image format for file: {file_path}")
                        return False
            except UnidentifiedImageError:
                logger.warning(f"Not a valid image file (PIL cannot identify): {file_path}")
                return False
            except Exception as e:
                logger.warning(f"Error opening image with PIL: {file_path}, error: {str(e)}")
                # If the file extension is supported but PIL can't open it, it might be corrupted
                return False
                
        except Exception as e:
            logger.error(f"Error checking if file is a supported image: {file_path}, error: {str(e)}")
            return False
    
    def compute_file_hash(self, file_path):
        """Compute a hash for the file to detect duplicates.
        
        Args:
            file_path (str): Path to the file
            
        Returns:
            str: MD5 hash of the file, or None if hashing failed
        """
        try:
            hash_md5 = hashlib.md5()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except (IOError, OSError) as e:
            logger.error(f"Error computing hash for {file_path}: {e}")
            return None
    
    def process_image(self, folder_id, file_path):
        """Process a single image file.
        
        Args:
            folder_id (int): ID of the folder containing the image
            file_path (str): Path to the image file
            
        Returns:
            dict: Processing results
        """
        try:
            # Make sure the file exists
            if not os.path.exists(file_path):
                logger.warning(f"Image file does not exist: {file_path}")
                return {
                    "success": False, 
                    "error": "File does not exist", 
                    "filename": os.path.basename(file_path),
                    "file_path": file_path
                }
            
            # Check file size - skip empty files
            try:
                file_size = os.path.getsize(file_path)
                if file_size == 0:
                    logger.warning(f"Empty file (0 bytes): {file_path}")
                    return {
                        "success": False, 
                        "error": "Empty file (0 bytes)", 
                        "filename": os.path.basename(file_path),
                        "file_path": file_path
                    }
            except OSError as e:
                logger.error(f"Error getting file size for {file_path}: {e}")
                return {
                    "success": False, 
                    "error": f"Error getting file size: {str(e)}", 
                    "filename": os.path.basename(file_path),
                    "file_path": file_path
                }
            
            # Check if it's a supported image format
            if not self.is_supported_image(file_path):
                # Get file extension for better error reporting
                ext = Path(file_path).suffix.lower()
                logger.warning(f"Not a supported image file: {file_path} (extension: {ext})")
                return {
                    "success": False, 
                    "error": f"Not a supported image file (extension: {ext})", 
                    "filename": os.path.basename(file_path),
                    "file_path": file_path,
                    "extension": ext
                }
            
            # Get file information
            filename = os.path.basename(file_path)
            file_hash = self.compute_file_hash(file_path)
            if not file_hash:
                logger.warning(f"Failed to compute file hash: {file_path}")
                # Continue processing even without hash
            
            # Generate thumbnail
            try:
                thumbnail_path = self.thumbnail_generator.generate_thumbnail(file_path)
                if not thumbnail_path:
                    logger.warning(f"Failed to generate thumbnail for {file_path}")
            except Exception as e:
                logger.error(f"Error generating thumbnail for {file_path}: {e}")
                thumbnail_path = None
            
            # Generate AI description if AI processor is available
            ai_description = None
            if self.ai_processor:
                try:
                    ai_description = self.ai_processor.generate_description(file_path)
                except Exception as e:
                    logger.error(f"Error generating AI description for {file_path}: {e}")
            
            # Add to database
            try:
                image_id = self.db_manager.add_image(
                    folder_id=folder_id,
                    filename=filename,
                    full_path=file_path,
                    file_size=file_size,
                    file_hash=file_hash,
                    thumbnail_path=thumbnail_path,
                    ai_description=ai_description
                )
                
                if not image_id:
                    logger.warning(f"Failed to add image to database: {file_path}")
                    return {"success": False, "error": "Failed to add to database", "filename": filename}
                
            except Exception as e:
                logger.error(f"Database error when adding image {file_path}: {e}")
                return {"success": False, "error": f"Database error: {str(e)}", "filename": filename}
            
            return {
                "success": True,
                "image_id": image_id,
                "filename": filename,
                "thumbnail_path": thumbnail_path,
                "ai_description": ai_description is not None
            }
            
        except Exception as e:
            # Capture full exception information
            exc_info = sys.exc_info()
            logger.error(f"Error processing image {file_path}: {e}")
            logger.error(f"Exception details: {traceback.format_exception(*exc_info)}")
            return {"success": False, "error": str(e), "filename": os.path.basename(file_path)}
    
    def scan_folder(self, folder_id, folder_path, progress_callback=None):
        """Scan a folder for images and process them.
        
        Args:
            folder_id (int): ID of the folder to scan
            folder_path (str): Path to the folder
            progress_callback (function, optional): Progress callback function
            
        Returns:
            dict: Scan results with counts of processed, failed, and skipped images
        """
        try:
            if not os.path.exists(folder_path) or not os.path.isdir(folder_path):
                logger.error(f"Folder does not exist or is not a directory: {folder_path}")
                return {"error": "Folder does not exist or is not a directory"}
            
            logger.info(f"Starting scan of folder: {folder_path}")
            
            results = {
                "processed": 0,
                "failed": 0,
                "skipped": 0,
                "total": 0,
                "errors": []
            }
            
            # Find all image files recursively
            image_files = []
            for root, _, files in os.walk(folder_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    if self.is_supported_image(file_path):
                        image_files.append(file_path)
            
            results["total"] = len(image_files)
            logger.info(f"Found {results['total']} image files in {folder_path}")
            
            if results["total"] == 0:
                logger.warning(f"No image files found in folder: {folder_path}")
                # Update the last scan time for the folder anyway
                self.db_manager.update_folder_scan_time(folder_id)
                return results
            
            # Process images in parallel
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                future_to_path = {
                    executor.submit(self.process_image, folder_id, file_path): file_path
                    for file_path in image_files
                }
                
                completed = 0
                for future in future_to_path:
                    file_path = future_to_path[future]
                    try:
                        result = future.result()
                        if result.get("success", False):
                            results["processed"] += 1
                        else:
                            results["failed"] += 1
                            error_info = {
                                "file": os.path.basename(file_path),
                                "error": result.get("error", "Unknown error")
                            }
                            results["errors"].append(error_info)
                            logger.warning(f"Failed to process image {file_path}: {result.get('error')}")
                    except Exception as e:
                        # Capture and log the exception
                        exc_info = sys.exc_info()
                        logger.error(f"Exception processing image {file_path}: {e}")
                        logger.error(f"Exception details: {traceback.format_exception(*exc_info)}")
                        
                        results["failed"] += 1
                        error_info = {
                            "file": os.path.basename(file_path),
                            "error": str(e)
                        }
                        results["errors"].append(error_info)
                    
                    completed += 1
                    if progress_callback:
                        try:
                            progress_callback(completed, results["total"])
                        except Exception as e:
                            logger.error(f"Error in callback: {e}")
            
            # Update the last scan time for the folder
            try:
                self.db_manager.update_folder_scan_time(folder_id)
            except Exception as e:
                logger.error(f"Error updating folder scan time: {e}")
            
            logger.info(f"Folder scan complete: {folder_path}")
            logger.info(f"Processed: {results['processed']}, Failed: {results['failed']}, Total: {results['total']}")
            
            return results
            
        except Exception as e:
            # Capture and log the exception
            exc_info = sys.exc_info()
            logger.error(f"Error scanning folder {folder_path}: {e}")
            logger.error(f"Exception details: {traceback.format_exception(*exc_info)}")
            
            return {
                "processed": 0,
                "failed": 0,
                "skipped": 0,
                "total": 0,
                "errors": [{"file": "folder", "error": str(e)}],
                "error": str(e)
            }
    
    def scan_all_folders(self, progress_callback=None):
        """Scan all enabled folders for images.
        
        Args:
            progress_callback (function, optional): Progress callback function
            
        Returns:
            dict: Scan results with counts per folder
        """
        try:
            folders = self.db_manager.get_folders(enabled_only=True)
            
            results = {
                "folders_processed": 0,
                "folders_failed": 0,
                "total_processed": 0,
                "total_failed": 0,
                "details": {}
            }
            
            total_folders = len(folders)
            logger.info(f"Starting scan of {total_folders} folders")
            
            for folder in folders:
                folder_id = folder["folder_id"]
                folder_path = folder["path"]
                
                # Skip folders that don't exist
                if not os.path.exists(folder_path) or not os.path.isdir(folder_path):
                    logger.warning(f"Skipping non-existent folder: {folder_path}")
                    results["folders_failed"] += 1
                    continue
                
                # Scan the folder
                folder_results = self.scan_folder(folder_id, folder_path, progress_callback)
                
                if "error" in folder_results:
                    results["folders_failed"] += 1
                else:
                    results["folders_processed"] += 1
                    results["total_processed"] += folder_results["processed"]
                    results["total_failed"] += folder_results["failed"]
                
                results["details"][folder_path] = folder_results
            
            logger.info(f"All folders scanned. Processed: {results['total_processed']}, Failed: {results['total_failed']}")
            
            return results
            
        except Exception as e:
            # Capture and log the exception
            exc_info = sys.exc_info()
            logger.error(f"Error scanning all folders: {e}")
            logger.error(f"Exception details: {traceback.format_exception(*exc_info)}")
            
            return {
                "folders_processed": 0,
                "folders_failed": 0,
                "total_processed": 0,
                "total_failed": 0,
                "details": {},
                "error": str(e)
            }
