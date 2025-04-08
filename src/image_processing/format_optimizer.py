#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Image format optimizer for StarImageBrowse
Selects optimal image formats based on content type.
"""

import os
import logging
import numpy as np
from PIL import Image, ImageChops, ImageStat, UnidentifiedImageError
from typing import Tuple, Optional, Dict, Union, List

logger = logging.getLogger("StarImageBrowse.image_processing.format_optimizer")

class FormatOptimizer:
    """Optimizes image formats based on content type for better compression and quality."""
    
    def __init__(self, config_manager=None):
        """Initialize the format optimizer.
        
        Args:
            config_manager: Configuration manager instance
        """
        self.config_manager = config_manager
        
        # Default configuration
        self.webp_quality = 80
        self.jpeg_quality = 85
        self.png_compression = 6  # 0-9, higher is more compression but slower
        self.format_detection_enabled = True
        
        # Load configuration if provided
        if config_manager:
            self.webp_quality = config_manager.get("thumbnails", "webp_quality", 80)
            self.jpeg_quality = config_manager.get("thumbnails", "jpeg_quality", 85)
            self.png_compression = config_manager.get("thumbnails", "png_compression", 6)
            self.format_detection_enabled = config_manager.get("thumbnails", "format_detection_enabled", True)
            
        # Thresholds for format selection
        self.text_threshold = 0.15  # Threshold for text detection
        self.edge_threshold = 0.1   # Threshold for edge detection
        self.color_threshold = 5    # Threshold for color count (higher means more colors)
        
        logger.info(f"Format optimizer initialized with WebP quality={self.webp_quality}, "
                   f"JPEG quality={self.jpeg_quality}, PNG compression={self.png_compression}")
    
    def analyze_image_content(self, image: Image.Image) -> Dict[str, float]:
        """Analyze image content to determine the best format.
        
        Args:
            image: PIL Image object
            
        Returns:
            dict: Analysis results with metrics
        """
        try:
            # Convert to RGB if needed
            if image.mode not in ('RGB', 'RGBA'):
                image = image.convert('RGB')
            
            # Make a smaller version for analysis if the image is large
            analysis_size = (min(image.width, 500), min(image.height, 500))
            if image.size != analysis_size:
                analysis_img = image.resize(analysis_size, Image.Resampling.LANCZOS)
            else:
                analysis_img = image
            
            # Edge detection using Laplacian filter
            # Convert to grayscale
            gray_img = analysis_img.convert('L')
            
            # Simple edge detection by differencing
            h_edges = ImageChops.difference(
                ImageChops.offset(gray_img, 1, 0),
                ImageChops.offset(gray_img, -1, 0)
            )
            v_edges = ImageChops.difference(
                ImageChops.offset(gray_img, 0, 1),
                ImageChops.offset(gray_img, 0, -1)
            )
            
            # Combine horizontal and vertical edges
            edges = ImageChops.add(h_edges, v_edges)
            
            # Calculate edge ratio (how many edge pixels vs total)
            edge_stats = ImageStat.Stat(edges)
            edge_ratio = edge_stats.mean[0] / 255.0
            
            # Text detection based on edge distribution
            # Text typically has more high-frequency edges
            edge_histogram = edges.histogram()
            high_freq_edges = sum(edge_histogram[128:]) / sum(edge_histogram)
            
            # Color count approximation
            colors = analysis_img.getcolors(maxcolors=1000)
            if colors is None:
                color_count = 1000  # Lots of colors, more than 1000
            else:
                color_count = len(colors)
            color_count_ratio = color_count / 1000.0
            
            # Transparency check
            has_transparency = image.mode == 'RGBA' and any(
                pixel[3] < 255 for pixel in image.getdata(3)
            ) if 'A' in image.mode else False
            
            results = {
                'edge_ratio': edge_ratio,
                'high_freq_edges': high_freq_edges,
                'color_count_ratio': color_count_ratio,
                'has_transparency': has_transparency,
                'likely_text': high_freq_edges > self.text_threshold,
                'likely_photo': color_count_ratio > 0.5 and edge_ratio < self.edge_threshold
            }
            
            logger.debug(f"Image analysis results: {results}")
            return results
            
        except Exception as e:
            logger.error(f"Error analyzing image content: {e}")
            # Return default values
            return {
                'edge_ratio': 0,
                'high_freq_edges': 0,
                'color_count_ratio': 0,
                'has_transparency': False,
                'likely_text': False,
                'likely_photo': True  # Default to photo
            }
    
    def determine_optimal_format(self, image: Image.Image) -> Tuple[str, Dict]:
        """Determine the optimal format for an image based on its content.
        
        Args:
            image: PIL Image object
            
        Returns:
            tuple: (format_name, format_options)
        """
        if not self.format_detection_enabled:
            # If format detection is disabled, default to JPEG
            return 'JPEG', {'quality': self.jpeg_quality}
        
        try:
            # Analyze image content
            analysis = self.analyze_image_content(image)
            
            # Check for transparency first
            if analysis['has_transparency']:
                # WebP supports transparency and has good compression
                return 'WebP', {'quality': self.webp_quality, 'lossless': False}
            
            # Check if this is likely text/diagram content
            if analysis['likely_text']:
                # For text/diagrams, use PNG for better quality
                return 'PNG', {'compress_level': self.png_compression}
            
            # For photos, use WebP for better compression
            if analysis['likely_photo']:
                return 'WebP', {'quality': self.webp_quality, 'lossless': False}
            
            # Default to JPEG for all other cases
            return 'JPEG', {'quality': self.jpeg_quality}
            
        except Exception as e:
            logger.error(f"Error determining optimal format: {e}")
            # Default to JPEG for safety
            return 'JPEG', {'quality': self.jpeg_quality}
    
    def optimize_image(self, image: Image.Image, output_path: str) -> bool:
        """Save the image in the optimal format determined by content analysis.
        
        Args:
            image: PIL Image object
            output_path: Path to save the optimized image (extension will be changed if needed)
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Determine the optimal format
            format_name, format_options = self.determine_optimal_format(image)
            
            # Adjust output path extension based on format
            path_without_ext = os.path.splitext(output_path)[0]
            
            if format_name == 'WebP':
                final_path = f"{path_without_ext}.webp"
            elif format_name == 'PNG':
                final_path = f"{path_without_ext}.png"
            else:  # JPEG
                final_path = f"{path_without_ext}.jpg"
            
            # Save in the optimal format
            image.save(final_path, format=format_name, **format_options)
            
            logger.debug(f"Saved image in {format_name} format at {final_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error optimizing image format: {e}")
            # Fallback to simple JPEG save
            try:
                image.save(output_path, format='JPEG', quality=self.jpeg_quality)
                return True
            except Exception as fallback_error:
                logger.error(f"Fallback save also failed: {fallback_error}")
                return False
    
    def determine_best_format(self, image_path: str) -> str:
        """Determine the best format for an image based on its content (alias for backward compatibility).
        
        Args:
            image_path: Path to the image
            
        Returns:
            str: Best format name ('WebP', 'PNG', or 'JPEG')
        """
        try:
            # Open the image
            with Image.open(image_path) as img:
                # Use existing method to determine optimal format
                format_name, _ = self.determine_optimal_format(img)
                return format_name
        except Exception as e:
            logger.error(f"Error determining best format for {image_path}: {e}")
            # Default to JPEG for safety
            return 'JPEG'
    
    def batch_optimize_images(self, images: Dict[str, Image.Image], output_dir: str) -> Dict[str, str]:
        """Optimize multiple images in batch mode.
        
        Args:
            images: Dict mapping from image ID/name to PIL Image object
            output_dir: Directory to save optimized images
            
        Returns:
            dict: Mapping from original image ID/name to output path
        """
        results = {}
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        for image_id, image in images.items():
            # Generate output path
            output_path = os.path.join(output_dir, f"{image_id}_optimized.jpg")
            
            # Optimize and save
            if self.optimize_image(image, output_path):
                # Get the actual path that was saved (may have different extension)
                path_without_ext = os.path.splitext(output_path)[0]
                
                # Check which format was used
                if os.path.exists(f"{path_without_ext}.webp"):
                    results[image_id] = f"{path_without_ext}.webp"
                elif os.path.exists(f"{path_without_ext}.png"):
                    results[image_id] = f"{path_without_ext}.png"
                else:
                    results[image_id] = f"{path_without_ext}.jpg"
            else:
                results[image_id] = None
        
        return results
