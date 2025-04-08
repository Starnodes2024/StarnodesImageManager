#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Ollama batch processor for StarImageBrowse
Optimizes batch processing of images for Ollama API
"""

import os
import time
import base64
import logging
import requests
import threading
import concurrent.futures
from io import BytesIO
from PIL import Image
from queue import Queue, Empty

logger = logging.getLogger("StarImageBrowse.ai.ollama_batch_processor")

class AdaptiveBatch:
    """Track batch performance metrics and adapt size accordingly."""
    
    def __init__(self, initial_size=4, min_size=1, max_size=16):
        """Initialize batch metrics.
        
        Args:
            initial_size (int): Initial batch size
            min_size (int): Minimum batch size
            max_size (int): Maximum batch size
        """
        self.current_size = initial_size
        self.min_size = min_size
        self.max_size = max_size
        self.response_times = []
        self.max_response_times = 20  # Keep track of last N response times
        self.avg_time_per_item = None
        self.lock = threading.Lock()
        
    def record_batch_time(self, batch_size, elapsed_time):
        """Record metrics for a batch.
        
        Args:
            batch_size (int): Size of the batch
            elapsed_time (float): Time taken to process the batch in seconds
        """
        with self.lock:
            time_per_item = elapsed_time / batch_size
            self.response_times.append(time_per_item)
            
            # Keep only the last N response times
            if len(self.response_times) > self.max_response_times:
                self.response_times.pop(0)
            
            # Calculate average time per item
            self.avg_time_per_item = sum(self.response_times) / len(self.response_times)
            
            # Adjust batch size if we have enough data
            if len(self.response_times) >= 3:
                self._adjust_batch_size()
    
    def _adjust_batch_size(self):
        """Adjust batch size based on performance metrics."""
        # Check if the batch size needs adjustment
        current_avg = self.avg_time_per_item
        
        # If the last time is significantly worse than average, reduce batch size
        if self.response_times[-1] > current_avg * 1.5 and self.current_size > self.min_size:
            # Batch is too large, reduce size
            self.current_size = max(self.min_size, self.current_size - 1)
            logger.info(f"Reducing batch size to {self.current_size} due to slow response time")
        
        # If the last time is better than average, consider increasing batch size
        elif self.response_times[-1] < current_avg * 0.8 and self.current_size < self.max_size:
            # Batch is efficient, try increasing size
            self.current_size = min(self.max_size, self.current_size + 1)
            logger.info(f"Increasing batch size to {self.current_size} due to good response time")
    
    def get_batch_size(self):
        """Get the current recommended batch size.
        
        Returns:
            int: Current optimal batch size
        """
        with self.lock:
            return self.current_size
    
    def get_stats(self):
        """Get current batch statistics.
        
        Returns:
            dict: Batch statistics
        """
        with self.lock:
            return {
                "current_batch_size": self.current_size,
                "avg_time_per_item": self.avg_time_per_item,
                "samples": len(self.response_times)
            }


class OllamaBatchProcessor:
    """Process images in optimized batches using Ollama API."""
    
    def __init__(self, ollama_url, model_name, system_prompt, max_workers=4):
        """Initialize batch processor.
        
        Args:
            ollama_url (str): URL of the Ollama API
            model_name (str): Name of the model to use
            system_prompt (str): System prompt for image descriptions
            max_workers (int): Maximum number of concurrent worker threads
        """
        self.ollama_url = ollama_url
        self.model_name = model_name
        self.system_prompt = system_prompt
        self.max_workers = max_workers
        
        # Initialize adaptive batch sizing
        self.adaptive_batch = AdaptiveBatch()
        
        # Image preprocessing parameters
        self.max_image_size = 512  # Maximum size for image dimension
        self.image_quality = 85    # JPEG quality for compression
        
        # Compression level for different image types
        # Quality setting will be lower for larger images
        self.compression_levels = {
            "small": 85,   # < 0.5MB
            "medium": 75,  # 0.5MB - 2MB
            "large": 65    # > 2MB
        }
        
        logger.info(f"Initialized Ollama batch processor with model {model_name}")
    
    def preprocess_image(self, image_path):
        """Preprocess an image for efficient sending to Ollama.
        
        Args:
            image_path (str): Path to the image
            
        Returns:
            tuple: (base64_encoded_image, original_width, original_height) or None if preprocessing fails
        """
        try:
            # Open the image
            with Image.open(image_path) as img:
                # Store original dimensions
                original_width, original_height = img.width, img.height
                
                # Convert to RGB if needed (remove alpha channel)
                if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
                    background = Image.new("RGB", img.size, (255, 255, 255))
                    background.paste(img, mask=img.split()[3] if img.mode == 'RGBA' else None)
                    img = background
                elif img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # Resize if image is too large
                if img.width > self.max_image_size or img.height > self.max_image_size:
                    # Calculate new dimensions while preserving aspect ratio
                    if img.width > img.height:
                        new_width = self.max_image_size
                        new_height = int(img.height * (self.max_image_size / img.width))
                    else:
                        new_height = self.max_image_size
                        new_width = int(img.width * (self.max_image_size / img.height))
                    
                    # Resize the image
                    img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                    logger.debug(f"Resized image from {original_width}x{original_height} to {new_width}x{new_height}")
                
                # Determine appropriate compression level based on file size
                file_size_mb = os.path.getsize(image_path) / (1024 * 1024)
                
                if file_size_mb < 0.5:
                    quality = self.compression_levels["small"]
                elif file_size_mb < 2:
                    quality = self.compression_levels["medium"]
                else:
                    quality = self.compression_levels["large"]
                
                # Convert to base64
                buffered = BytesIO()
                img.save(buffered, format="JPEG", quality=quality)
                img_base64 = base64.b64encode(buffered.getvalue()).decode()
                
                return (img_base64, original_width, original_height)
                
        except Exception as e:
            logger.error(f"Error preprocessing image {image_path}: {e}")
            return None
    
    def process_batch(self, image_batch):
        """Process a batch of images with Ollama.
        
        Args:
            image_batch (list): List of tuples (image_id, image_path)
            
        Returns:
            dict: Dictionary mapping image_id to generated description or error
        """
        start_time = time.time()
        results = {}
        
        try:
            # Preprocess all images in the batch
            batch_data = []
            valid_ids = []
            
            for image_id, image_path in image_batch:
                processed = self.preprocess_image(image_path)
                if processed:
                    img_base64, width, height = processed
                    batch_data.append({
                        "id": image_id,
                        "path": image_path,
                        "base64": img_base64,
                        "width": width,
                        "height": height
                    })
                    valid_ids.append(image_id)
                else:
                    # Mark preprocessing failure
                    results[image_id] = {"success": False, "error": "Failed to preprocess image"}
            
            if not batch_data:
                logger.warning(f"No valid images to process in batch")
                return results
            
            # Process images in parallel using multiple Ollama API calls
            # For models that support batch processing of multiple images at once,
            # we could process them in a single call, but currently, we process each separately
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = {}
                for img_data in batch_data:
                    future = executor.submit(
                        self._process_single_image,
                        img_data["id"],
                        img_data["base64"],
                        img_data["path"]
                    )
                    futures[future] = img_data["id"]
                
                # Collect results
                for future in concurrent.futures.as_completed(futures):
                    image_id = futures[future]
                    try:
                        result = future.result()
                        results[image_id] = result
                    except Exception as e:
                        logger.error(f"Error processing image {image_id}: {e}")
                        results[image_id] = {"success": False, "error": str(e)}
            
            # Record batch processing time for adaptive batch sizing
            elapsed_time = time.time() - start_time
            self.adaptive_batch.record_batch_time(len(batch_data), elapsed_time)
            logger.info(f"Batch of {len(batch_data)} images processed in {elapsed_time:.2f} seconds")
            
            return results
            
        except Exception as e:
            logger.error(f"Error processing batch: {e}")
            # Mark all images as failed if not already in results
            for image_id, _ in image_batch:
                if image_id not in results:
                    results[image_id] = {"success": False, "error": f"Batch processing error: {str(e)}"}
            return results
    
    def _process_single_image(self, image_id, img_base64, image_path):
        """Process a single image with Ollama API.
        
        Args:
            image_id (int): ID of the image
            img_base64 (str): Base64-encoded image data
            image_path (str): Path to the original image (for logging)
            
        Returns:
            dict: Result dictionary with success status and description or error
        """
        try:
            # Send request to Ollama API
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.model_name,
                    "prompt": self.system_prompt,
                    "images": [img_base64],
                    "stream": False,
                    "options": {
                        "temperature": 0.7,
                        "num_predict": 200  # Limit response length for speed
                    }
                },
                timeout=30  # Increased timeout for image processing
            )
            
            if response.status_code == 200:
                result = response.json()
                description = result.get("response", "").strip()
                
                if description:
                    return {
                        "success": True,
                        "description": description
                    }
                else:
                    logger.warning(f"Ollama returned empty description for image {image_id}")
                    return {
                        "success": False,
                        "error": "Empty description returned"
                    }
            else:
                error_msg = f"API error: {response.status_code} - {response.text}"
                logger.error(f"Ollama API error for image {image_id}: {error_msg}")
                return {
                    "success": False,
                    "error": error_msg
                }
        
        except Exception as e:
            logger.error(f"Error in single image processing for {image_id}: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def process_queue(self, image_queue, result_callback=None, progress_callback=None, 
                      cancel_event=None):
        """Process a queue of images with batching.
        
        Args:
            image_queue (Queue): Queue of (image_id, image_path) tuples
            result_callback (callable): Callback function for results (image_id, result)
            progress_callback (callable): Callback function for progress updates (current, total)
            cancel_event (Event): Event to check for cancellation
            
        Returns:
            dict: Dictionary of all results
        """
        all_results = {}
        queue_size = image_queue.qsize()
        processed_count = 0
        
        logger.info(f"Starting batch processing of {queue_size} images")
        
        try:
            while not image_queue.empty():
                # Check for cancellation
                if cancel_event and cancel_event.is_set():
                    logger.info("Batch processing cancelled")
                    break
                
                # Get optimal batch size based on performance history
                batch_size = self.adaptive_batch.get_batch_size()
                batch = []
                
                # Collect batch from queue
                for _ in range(batch_size):
                    try:
                        item = image_queue.get_nowait()
                        batch.append(item)
                    except Empty:
                        break
                
                if not batch:
                    break
                
                # Process batch
                batch_results = self.process_batch(batch)
                
                # Update results and call callbacks
                for image_id, result in batch_results.items():
                    all_results[image_id] = result
                    
                    # Call result callback if provided
                    if result_callback:
                        result_callback(image_id, result)
                
                # Update progress
                processed_count += len(batch)
                if progress_callback:
                    progress_callback(processed_count, queue_size)
                
                # Log batch statistics
                stats = self.adaptive_batch.get_stats()
                logger.info(f"Processed {processed_count}/{queue_size} images - "
                          f"Current batch size: {stats['current_batch_size']}, "
                          f"Avg time per image: {stats.get('avg_time_per_item', 0):.2f}s")
        
        except Exception as e:
            logger.error(f"Error in batch queue processing: {e}")
        
        return all_results
