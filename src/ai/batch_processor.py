#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Batch processor for StarImageBrowse
Provides optimized batch processing for image descriptions
"""

import os
import logging
import time
from queue import Queue
from threading import Event

logger = logging.getLogger("StarImageBrowse.ai.batch_processor")

class BatchProcessor:
    """Provides optimized batch processing for large image collections."""
    
    def __init__(self, ai_processor, db_manager):
        """Initialize the batch processor.
        
        Args:
            ai_processor: AI image processor instance
            db_manager: Database manager instance
        """
        self.ai_processor = ai_processor
        self.db_manager = db_manager
        self.cancel_event = Event()
    
    def process_folder(self, folder_id, process_all=False, progress_callback=None):
        """Process images in a folder with optimized batching.
        
        Args:
            folder_id (int): ID of the folder to process
            process_all (bool): If True, process all images; if False, only process images without descriptions
            progress_callback (function, optional): Progress callback function
            
        Returns:
            dict: Processing results
        """
        if not self.db_manager:
            logger.error("No database manager available")
            return {"error": "No database manager available"}
        
        # Reset cancel event
        self.cancel_event.clear()
        
        # Get all images for the folder
        images = self.db_manager.get_images_for_folder(folder_id, limit=1000000)
        
        # Filter images that need processing
        images_to_process = []
        skipped_count = 0
        
        for image in images:
            if not process_all and image["ai_description"]:
                skipped_count += 1
            else:
                images_to_process.append(image)
        
        # Initialize results
        results = {
            "processed": 0,
            "failed": 0,
            "skipped": skipped_count,
            "total": len(images),
            "cancelled": False
        }
        
        total_to_process = len(images_to_process)
        logger.info(f"Batch processing {total_to_process} images in folder {folder_id} (skipping {skipped_count})")
        
        if total_to_process == 0:
            logger.info("No images need processing")
            if progress_callback:
                progress_callback(0, 0, "No images need processing")
            return results
        
        # Create lists of image paths and IDs for batch processing
        image_paths = []
        image_ids = []
        
        for image in images_to_process:
            image_ids.append(image["image_id"])
            image_paths.append(image["full_path"])
        
        # Check Ollama availability and use optimized batch processing if available
        if self.ai_processor.check_ollama_availability() and self.ai_processor.batch_processor:
            # Create a wrapper for the progress callback that includes a message
            def progress_wrapper(current, total):
                if progress_callback:
                    message = f"Processed {current} of {total} images"
                    try:
                        progress_callback(current, total, message)
                    except Exception as e:
                        logger.error(f"Error in progress callback: {e}")
            
            # Process with optimized batch processor
            logger.info("Using optimized batch processor for image descriptions")
            descriptions = self.ai_processor.batch_processor.process_queue(
                self._create_image_queue(image_ids, image_paths),
                result_callback=lambda img_id, result: self._update_description(
                    image_ids[img_id], result.get("description") if result.get("success") else None
                ),
                progress_callback=progress_wrapper,
                cancel_event=self.cancel_event
            )
            
            # Count processed and failed
            for image_id, image_path in zip(image_ids, image_paths):
                if self.cancel_event.is_set():
                    results["cancelled"] = True
                    break
                
                if self.db_manager.get_image_description(image_id):
                    results["processed"] += 1
                else:
                    results["failed"] += 1
        else:
            # Fall back to the traditional batch processing method
            logger.info("Using sequential batch processing for image descriptions")
            for i, (image_id, image_path) in enumerate(zip(image_ids, image_paths)):
                # Check for cancellation
                if self.cancel_event.is_set():
                    results["cancelled"] = True
                    break
                
                # Generate description
                description = self.ai_processor.generate_description(image_path)
                
                # Update database
                if description:
                    self._update_description(image_id, description)
                    results["processed"] += 1
                else:
                    results["failed"] += 1
                
                # Update progress
                if progress_callback:
                    try:
                        progress_callback(i + 1, total_to_process, 
                                         f"Processed {i + 1} of {total_to_process} images")
                    except Exception as e:
                        logger.error(f"Error in progress callback: {e}")
        
        # Log completion
        if results["cancelled"]:
            logger.info(f"Batch processing cancelled. Processed: {results['processed']}, Failed: {results['failed']}, Skipped: {results['skipped']}")
            if progress_callback:
                try:
                    progress_callback(results["processed"], total_to_process, "Processing cancelled")
                except Exception as e:
                    logger.error(f"Error in final progress callback: {e}")
        else:
            logger.info(f"Batch processing complete. Processed: {results['processed']}, Failed: {results['failed']}, Skipped: {results['skipped']}")
            if progress_callback:
                try:
                    progress_callback(total_to_process, total_to_process, "Processing complete")
                except Exception as e:
                    logger.error(f"Error in final progress callback: {e}")
        
        return results
    
    def process_selected_images(self, image_ids, progress_callback=None):
        """Process a selection of images with optimized batching.
        
        Args:
            image_ids (list): List of image IDs to process
            progress_callback (function, optional): Progress callback function
            
        Returns:
            dict: Processing results
        """
        if not self.db_manager:
            logger.error("No database manager available")
            return {"error": "No database manager available"}
        
        # Reset cancel event
        self.cancel_event.clear()
        
        # Get image data for all the IDs
        images_to_process = []
        for image_id in image_ids:
            # Check if image exists in DB (should always exist, but good practice)
            try:
                # Use the correct method name found in DatabaseManager
                image_data = self.db_manager.get_image_by_id(image_id)
                if not image_data:
                    logger.warning(f"Image ID {image_id} not found in DB, skipping.")
                    continue
            except Exception as db_err:
                logger.error(f"Error fetching image {image_id} from DB: {db_err}")
                continue
            
            # Extract full path
            images_to_process.append(image_data)
        
        # Initialize results
        results = {
            "processed": 0,
            "failed": 0,
            "total": len(images_to_process),
            "cancelled": False
        }
        
        total_to_process = len(images_to_process)
        logger.info(f"Batch processing {total_to_process} selected images")
        
        if total_to_process == 0:
            logger.info("No images to process")
            if progress_callback:
                progress_callback(0, 0, "No images to process")
            return results
        
        # Create lists of image paths and IDs for batch processing
        image_paths = []
        image_ids = []
        
        for image in images_to_process:
            image_ids.append(image["image_id"])
            image_paths.append(image["full_path"])
        
        # Check Ollama availability and use optimized batch processing if available
        if self.ai_processor.check_ollama_availability() and self.ai_processor.batch_processor:
            # Create a wrapper for the progress callback that includes a message
            def progress_wrapper(current, total):
                if progress_callback:
                    message = f"Processed {current} of {total} images"
                    try:
                        progress_callback(current, total, message)
                    except Exception as e:
                        logger.error(f"Error in progress callback: {e}")
            
            # Process with optimized batch processor
            logger.info("Using optimized batch processor for selected images")
            descriptions = self.ai_processor.batch_processor.process_queue(
                self._create_image_queue(image_ids, image_paths),
                result_callback=lambda img_id, result: self._update_description(
                    image_ids[img_id], result.get("description") if result.get("success") else None
                ),
                progress_callback=progress_wrapper,
                cancel_event=self.cancel_event
            )
            
            # Count processed and failed
            for image_id, image_path in zip(image_ids, image_paths):
                if self.cancel_event.is_set():
                    results["cancelled"] = True
                    break
                
                if self.db_manager.get_image_description(image_id):
                    results["processed"] += 1
                else:
                    results["failed"] += 1
        else:
            # Fall back to the traditional processing method
            logger.info("Using sequential processing for selected images")
            for i, (image_id, image_path) in enumerate(zip(image_ids, image_paths)):
                # Check for cancellation
                if self.cancel_event.is_set():
                    results["cancelled"] = True
                    break
                
                # Generate description
                description = self.ai_processor.generate_description(image_path)
                
                # Update database
                if description:
                    self._update_description(image_id, description)
                    results["processed"] += 1
                else:
                    results["failed"] += 1
                
                # Update progress
                if progress_callback:
                    try:
                        progress_callback(i + 1, total_to_process, 
                                         f"Processed {i + 1} of {total_to_process} images")
                    except Exception as e:
                        logger.error(f"Error in progress callback: {e}")
        
        # Log completion
        if results["cancelled"]:
            logger.info(f"Batch processing cancelled. Processed: {results['processed']}, Failed: {results['failed']}")
            if progress_callback:
                try:
                    progress_callback(results["processed"], total_to_process, "Processing cancelled")
                except Exception as e:
                    logger.error(f"Error in final progress callback: {e}")
        else:
            logger.info(f"Batch processing complete. Processed: {results['processed']}, Failed: {results['failed']}")
            if progress_callback:
                try:
                    progress_callback(total_to_process, total_to_process, "Processing complete")
                except Exception as e:
                    logger.error(f"Error in final progress callback: {e}")
        
        return results
    
    def cancel_processing(self):
        """Cancel the current batch processing operation."""
        logger.info("Cancelling batch processing operation")
        self.cancel_event.set()
    
    def _create_image_queue(self, image_ids, image_paths):
        """Create a queue of images for batch processing.
        
        Args:
            image_ids (list): List of image IDs
            image_paths (list): List of image paths
            
        Returns:
            Queue: Queue of (index, image_path) tuples
        """
        queue = Queue()
        for i, (image_id, image_path) in enumerate(zip(image_ids, image_paths)):
            queue.put((i, image_path))
        return queue
    
    def _update_description(self, image_id, description):
        """Update the image description in the database.
        
        Args:
            image_id (int): ID of the image
            description (str): Generated description
            
        Returns:
            bool: True if successful, False otherwise
        """
        if description:
            try:
                self.db_manager.update_image_description(image_id, ai_description=description)
                return True
            except Exception as e:
                logger.error(f"Error updating image description: {e}")
        return False
