#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
AI image processor for StarImageBrowse
Handles image description generation using image analysis and future Ollama integration.
"""

import os
import logging
import torch
import numpy as np
import requests
import base64
from io import BytesIO
from PIL import Image, UnidentifiedImageError
from queue import Queue
from threading import Thread, Event
import time

logger = logging.getLogger("StarImageBrowse.ai")

class AIImageProcessor:
    """Processes images to generate descriptions using basic image analysis.
    Future implementation will use Ollama for AI-powered descriptions.
    """
    
    def __init__(self, db_manager=None, batch_size=1):
        """Initialize the AI image processor.
        
        Args:
            db_manager: Database manager instance for storing generated descriptions
            batch_size (int): Batch size for inference
        """
        self.db_manager = db_manager
        self.batch_size = batch_size
        
        # Processing queue for background processing
        self.queue = Queue()
        self.processing_thread = None
        self.stop_event = Event()
        
        # Load Ollama configuration from config manager if available
        from src.config.config_manager import ConfigManager
        config = ConfigManager()
        
        # Ollama configuration
        self.ollama_url = config.get("ollama", "server_url", "http://localhost:11434")
        self.ollama_model = config.get("ollama", "model", "")
        
        # If no model is specified, try to find an available one
        if not self.ollama_model:
            try:
                # Try to get available models
                import requests
                response = requests.get(f"{self.ollama_url}/api/tags", timeout=5)
                if response.status_code == 200:
                    models_data = response.json()
                    models = [model['name'] for model in models_data.get('models', [])]
                    
                    # Look for vision models first
                    vision_models = [m for m in models if 'llava' in m.lower() or 'bakllava' in m.lower() or 'vision' in m.lower()]
                    if vision_models:
                        self.ollama_model = vision_models[0]
                        logger.info(f"Selected vision model: {self.ollama_model}")
                    elif models:
                        # Just use the first available model
                        self.ollama_model = models[0]
                        logger.info(f"No vision models found, using: {self.ollama_model}")
                    else:
                        logger.warning("No models found on Ollama server")
            except Exception as e:
                logger.error(f"Error getting available Ollama models: {e}")
        
        if self.ollama_model:
            logger.info(f"AI image processor initialized with Ollama model: {self.ollama_model}")
        else:
            logger.warning("AI image processor initialized without a specified Ollama model")
    
    def check_ollama_availability(self):
        """Check if Ollama server is available.
        
        Returns:
            bool: True if Ollama is available, False otherwise
        """
        try:
            # Check if the Ollama server is running and the model is available
            logger.info(f"Checking Ollama availability at {self.ollama_url}...")
            
            # Make an HTTP request to the Ollama API to check version
            response = requests.get(f"{self.ollama_url}/api/version", timeout=5)
            if response.status_code != 200:
                logger.warning(f"Ollama server not available: Status code {response.status_code}")
                return False
                
            # Check if the model is available
            response = requests.get(f"{self.ollama_url}/api/tags", timeout=5)
            if response.status_code != 200:
                logger.warning(f"Ollama models not available: Status code {response.status_code}")
                return False
                
            # Check if our model is in the list
            models_data = response.json()
            models = [model['name'] for model in models_data.get('models', [])]
            
            if self.ollama_model not in models:
                logger.warning(f"Model {self.ollama_model} not found in available models: {models}")
                return False
                
            logger.info(f"Ollama server available with model {self.ollama_model}")
            return True
            
        except Exception as e:
            logger.error(f"Error checking Ollama availability: {e}")
            return False
    
    def _generate_with_ollama(self, image):
        """Generate a description for an image using Ollama.
        
        Args:
            image (PIL.Image): Image to process
            
        Returns:
            str: Generated description or None if generation failed
        """
        try:
            logger.info(f"Generating description with Ollama model {self.ollama_model}...")
            
            # Resize image for faster processing if it's too large
            max_size = 512  # Maximum dimension for faster processing
            if image.width > max_size or image.height > max_size:
                # Calculate new dimensions while preserving aspect ratio
                if image.width > image.height:
                    new_width = max_size
                    new_height = int(image.height * (max_size / image.width))
                else:
                    new_height = max_size
                    new_width = int(image.width * (max_size / image.height))
                
                # Resize the image
                image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
                logger.debug(f"Resized image to {new_width}x{new_height} for faster processing")
            
            # Convert image to base64 with optimized quality
            buffered = BytesIO()
            image.save(buffered, format="JPEG", quality=85)  # Reduced quality for smaller payload
            img_str = base64.b64encode(buffered.getvalue()).decode()
            
            # Prepare the prompt - simplified for faster processing
            prompt = "Describe this image concisely, focusing on the main subject and key visual elements."
            
            # Send request to Ollama with optimized parameters
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.ollama_model,
                    "prompt": prompt,
                    "images": [img_str],
                    "stream": False,
                    "options": {"temperature": 0.7, "num_predict": 200}  # Limit response length for speed
                },
                timeout=30  # Increased timeout for image processing
            )
            
            # Parse response
            if response.status_code == 200:
                result = response.json()
                description = result.get("response", "")
                
                # Clean up the description
                description = description.strip()
                
                if description:
                    logger.info("Successfully generated description with Ollama")
                    return description
                else:
                    logger.warning("Ollama returned empty description")
                    return None
            else:
                logger.error(f"Error from Ollama API: {response.status_code} - {response.text}")
                return None
            
        except Exception as e:
            logger.error(f"Error generating description with Ollama: {e}")
            return None
    
    def unload_model(self):
        """Unload the AI model to free memory."""
        # This method is kept for compatibility with existing code
        # but doesn't do anything in the current implementation
        
        # Force garbage collection just in case
        import gc
        gc.collect()
        
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        
        logger.info("No model to unload in current implementation")
    
    def _analyze_image(self, image):
        """Analyze an image to generate a basic description based on image properties.
        
        Args:
            image (PIL.Image): Image to analyze
            
        Returns:
            str: Generated description
        """
        try:
            # Convert PIL image to numpy array
            img_array = np.array(image)
            
            # Calculate basic image statistics
            avg_brightness = np.mean(img_array) / 255.0
            
            # Calculate color variance (approximation of saturation)
            if len(img_array.shape) == 3 and img_array.shape[2] >= 3:  # Color image
                r, g, b = img_array[:,:,0], img_array[:,:,1], img_array[:,:,2]
                color_variance = np.std([np.mean(r), np.mean(g), np.mean(b)]) / 255.0
            else:  # Grayscale image
                color_variance = 0.0
            
            # Get image dimensions
            height, width = img_array.shape[0], img_array.shape[1]
            aspect_ratio = width / height
            
            # Generate a basic description based on image characteristics
            description = "Image analysis: "
            
            # Brightness description
            if avg_brightness > 0.7:
                description += "A bright image, possibly outdoors or well-lit scene. "
            elif avg_brightness < 0.3:
                description += "A dark image, possibly a night scene or low-light environment. "
            else:
                description += "An image with moderate lighting. "
                
            # Color description
            if color_variance > 0.1:
                description += "Contains vibrant or contrasting colors. "
            else:
                description += "Contains mostly uniform or muted colors. "
            
            # Aspect ratio description
            if aspect_ratio > 1.2:
                description += "Landscape orientation. "
            elif aspect_ratio < 0.8:
                description += "Portrait orientation. "
            else:
                description += "Square-like proportions. "
            
            # Add a note about the fallback solution
            description += "(This is an automated analysis based on image properties. AI-generated descriptions will be available in a future update.)"
            
            return description.strip()
            
        except Exception as e:
            logger.error(f"Error analyzing image: {e}")
            return "Unable to analyze image due to an error."
    
    def _process_image(self, image):
        """Process a single image to generate a description.
        
        Args:
            image (PIL.Image): Image to process
            
        Returns:
            str: Generated description or None if processing failed
        """
        try:
            # First try to use Ollama if available
            if self.check_ollama_availability():
                logger.info("Ollama is available, attempting to generate description")
                ollama_description = self._generate_with_ollama(image)
                if ollama_description:
                    logger.info("Successfully generated description with Ollama")
                    return ollama_description
                else:
                    logger.warning("Ollama description generation failed, falling back to basic analysis")
            else:
                logger.info("Ollama not available, using fallback image analysis")
            
            # Fall back to basic image analysis if Ollama is not available or fails
            logger.info("Using basic image analysis for description generation")
            return self._analyze_image(image)
            
        except Exception as e:
            logger.error(f"Error processing image with AI: {e}")
            return None
    
    def generate_description(self, image_path):
        """Generate a description for an image.
        
        Args:
            image_path (str): Path to the image
            
        Returns:
            str: Generated description or None if generation failed
        """
        try:
            # Check if we can use the thumbnail instead of the full image for faster processing
            thumbnail_path = None
            try:
                # Try to find the thumbnail path by replacing the image directory with the thumbnails directory
                base_dir = os.path.dirname(os.path.dirname(image_path))  # Go up one level from image directory
                rel_path = os.path.relpath(image_path, base_dir)
                potential_thumbnail = os.path.join(base_dir, "thumbnails", rel_path)
                
                if os.path.exists(potential_thumbnail):
                    thumbnail_path = potential_thumbnail
                    logger.debug(f"Using existing thumbnail for faster processing: {thumbnail_path}")
            except Exception as e:
                logger.warning(f"Error finding thumbnail path: {e}")
                thumbnail_path = None
            
            # Load the image (thumbnail if available, otherwise original)
            try:
                if thumbnail_path:
                    image = Image.open(thumbnail_path).convert("RGB")
                    logger.debug(f"Using thumbnail for {image_path}")
                else:
                    image = Image.open(image_path).convert("RGB")
            except (UnidentifiedImageError, OSError) as e:
                logger.error(f"Error opening image {image_path}: {e}")
                return None
            
            # Process the image
            description = self._process_image(image)
            
            if description:
                logger.debug(f"Generated description for {image_path}: {description[:50]}...")
            else:
                logger.warning(f"Failed to generate description for {image_path}")
            
            return description
            
        except Exception as e:
            logger.error(f"Error generating description for {image_path}: {e}")
            import traceback
            logger.error(f"Detailed error: {traceback.format_exc()}")
            return None
    
    def add_to_queue(self, image_id, image_path):
        """Add an image to the processing queue.
        
        Args:
            image_id (int): ID of the image in the database
            image_path (str): Path to the image
            
        Returns:
            bool: True if added to queue, False otherwise
        """
        try:
            self.queue.put((image_id, image_path))
            
            # Start the processing thread if it's not running
            if self.processing_thread is None or not self.processing_thread.is_alive():
                self.start_processing_thread()
            
            return True
            
        except Exception as e:
            logger.error(f"Error adding image to queue: {e}")
            return False
    
    def start_processing_thread(self):
        """Start the background processing thread."""
        self.stop_event.clear()
        self.processing_thread = Thread(target=self._process_queue, daemon=True)
        self.processing_thread.start()
        logger.info("Started AI processing thread")
    
    def stop_processing_thread(self):
        """Stop the background processing thread."""
        if self.processing_thread and self.processing_thread.is_alive():
            self.stop_event.set()
            self.processing_thread.join(timeout=5)
            logger.info("Stopped AI processing thread")
    
    def _process_queue(self):
        """Process images in the queue until stopped."""
        try:
            # No need to load a model in the current implementation
            
            while not self.stop_event.is_set():
                try:
                    # Get an item from the queue with a timeout
                    try:
                        image_id, image_path = self.queue.get(timeout=1)
                    except:
                        # No items in the queue, check if we should stop
                        if self.stop_event.is_set():
                            break
                        continue
                    
                    # Generate description
                    description = self.generate_description(image_path)
                    
                    # Update the database if we have a description and db_manager
                    if description and self.db_manager:
                        self.db_manager.update_image_description(image_id, ai_description=description)
                    
                    # Mark the task as done
                    self.queue.task_done()
                    
                except Exception as e:
                    logger.error(f"Error in processing thread: {e}")
                    # Sleep briefly to avoid tight loops in case of persistent errors
                    time.sleep(1)
            
            # No model to unload in the current implementation
            pass
            
        except Exception as e:
            logger.error(f"Fatal error in processing thread: {e}")
        
        logger.info("AI processing thread exited")
    
    def batch_process_folder(self, folder_id, process_all=False, progress_callback=None, batch_size=5):
        """Process images in a folder with the AI model.
        
        Args:
            folder_id (int): ID of the folder to process
            process_all (bool): If True, process all images; if False, only process images without descriptions
            progress_callback (function, optional): Progress callback function
            batch_size (int): Number of images to process in each batch for better performance
            
        Returns:
            dict: Processing results
        """
        if not self.db_manager:
            logger.error("No database manager available")
            return {"error": "No database manager available"}
        
        # Get all images for the folder
        images = self.db_manager.get_images_for_folder(folder_id, limit=10000)
        
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
            "total": len(images)
        }
        
        total_to_process = len(images_to_process)
        logger.info(f"Batch processing {total_to_process} images in folder {folder_id} (skipping {skipped_count})")
        
        if total_to_process == 0:
            logger.info("No images need processing")
            if progress_callback:
                progress_callback(0, 0, "No images need processing")
            return results
        
        # Process images in batches for better performance
        for batch_start in range(0, total_to_process, batch_size):
            batch_end = min(batch_start + batch_size, total_to_process)
            current_batch = images_to_process[batch_start:batch_end]
            batch_num = batch_start // batch_size + 1
            total_batches = (total_to_process + batch_size - 1) // batch_size
            
            logger.info(f"Processing batch {batch_num}/{total_batches} with {len(current_batch)} images")
            
            # Update progress at batch start
            if progress_callback:
                try:
                    progress_callback(batch_start, total_to_process, 
                                     f"Processing batch {batch_num} of {total_batches}")
                except Exception as e:
                    logger.error(f"Error in progress callback: {e}")
            
            # Process each image in the batch
            for i, image in enumerate(current_batch):
                image_id = image["image_id"]
                image_path = image["full_path"]
                
                # Try to use thumbnail for faster processing
                description = self.generate_description(image_path)
                
                if description:
                    # Update the database
                    self.db_manager.update_image_description(image_id, ai_description=description)
                    results["processed"] += 1
                else:
                    results["failed"] += 1
                
                # Update progress within batch
                if progress_callback:
                    try:
                        current_progress = batch_start + i + 1
                        progress_callback(current_progress, total_to_process, 
                                         f"Processed {current_progress} of {total_to_process} images")
                    except Exception as e:
                        logger.error(f"Error in progress callback: {e}")
        
        # Final update
        if progress_callback:
            try:
                progress_callback(total_to_process, total_to_process, "Processing complete")
            except Exception as e:
                logger.error(f"Error in final progress callback: {e}")
        
        logger.info(f"Batch processing complete. Processed: {results['processed']}, Failed: {results['failed']}, Skipped: {results['skipped']}")
        
        return results
