#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Configuration manager for StarImageBrowse
Handles loading, saving, and accessing application configuration.
"""

import os
import sys
import json
import logging
from pathlib import Path

# Import cache configuration
from src.cache.cache_config import apply_cache_config

# Initialize logger
try:
    logger = logging.getLogger("StarImageBrowse.config")
except Exception as e:
    print(f"Warning: Could not initialize logger: {e}")
    logger = None

class ConfigManager:
    """Manages application configuration."""
    
    def __init__(self, config_dir=None, config_file="settings.json"):
        """Initialize the configuration manager.
        
        Args:
            config_dir (str, optional): Directory to store configuration files
            config_file (str, optional): Name of the main configuration file
        """
        # Check if we're running in portable mode
        self.is_portable = getattr(sys, 'frozen', False)
        
        # Set configuration directory
        if config_dir is None:
            if self.is_portable:
                # In portable mode, use a directory next to executable
                exe_dir = os.path.dirname(sys.executable)
                self.config_dir = os.path.join(exe_dir, "config")
                if logger:
                    logger.info(f"Using portable config directory: {self.config_dir}")
            else:
                # In development mode, use application directory
                self.config_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "config")
                if logger:
                    logger.info(f"Using development config directory: {self.config_dir}")
        else:
            self.config_dir = config_dir
            if logger:
                logger.info(f"Using specified config directory: {self.config_dir}")
        
        # Ensure directory exists
        os.makedirs(self.config_dir, exist_ok=True)
        
        # Set configuration file path
        self.config_file = os.path.join(self.config_dir, config_file)
        if logger:
            logger.info(f"Config file path: {self.config_file}")
        
        # Initialize configuration dictionary with defaults
        self.config = self._get_default_config()
        
        # Load existing configuration if available
        self.load()
        
        # Initialize cache configuration
        apply_cache_config(self)
        
        if logger:
            logger.info(f"Configuration manager initialized with file: {self.config_file}")
    
    def _get_default_config(self):
        """Get the default configuration.
        
        Returns:
            dict: Default configuration dictionary
        """
        # Base paths for configuration - different for portable vs development
        if self.is_portable:
            # In portable mode, use paths relative to the executable
            base_dir = os.path.dirname(sys.executable)
            data_dir = os.path.join(base_dir, "data")
            thumbnail_dir = os.path.join(data_dir, "thumbnails")
            log_dir = os.path.join(data_dir, "logs")
            db_path = os.path.join(data_dir, "image_database.db")
        else:
            # In development mode, use paths relative to the source code
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            data_dir = os.path.join(base_dir, "data")
            thumbnail_dir = os.path.join(data_dir, "thumbnails")
            # Use the standardized data/logs directory in all modes
            log_dir = os.path.join(data_dir, "logs")
            db_path = os.path.join(data_dir, "star_image_browse.db")
        
        # Make sure the directories exist
        os.makedirs(data_dir, exist_ok=True)
        os.makedirs(thumbnail_dir, exist_ok=True)
        os.makedirs(log_dir, exist_ok=True)
        
        # Log the important paths
        if logger:
            logger.info(f"Base directory: {base_dir}")
            logger.info(f"Data directory: {data_dir}")
            logger.info(f"Thumbnails directory: {thumbnail_dir}")
            logger.info(f"Log directory: {log_dir}")
            logger.info(f"Database path: {db_path}")
        
        return {
            "app": {
                "first_run": True,
                "window_width": 1200,
                "window_height": 800,
                "theme": "dark_purple"  # Updated default theme
            },
            "thumbnails": {
                "size": 200,
                "quality": 85,
                "path": thumbnail_dir  # Use the correctly determined path
            },
            "memory": {
                "max_pool_size": 100 * 1024 * 1024,  # 100MB default memory pool size
                "enable_memory_pool": True,          # Enable memory pooling
                "cleanup_interval": 60,             # Cleanup interval in seconds
                "debug_memory_usage": False         # Log detailed memory usage
            },
            
            "processing": {
                "num_workers": min(os.cpu_count() or 4, 8),  # Number of parallel workers
                "use_process_pool": True,         # Use process pool for CPU-bound tasks
                "max_batch_size": 50,            # Maximum batch size for processing
                "enable_parallel": True           # Enable parallel processing
            },
            
            "database": {
                "path": db_path  # Use the correctly determined path
            },
            "monitor": {
                "watch_folders": False,
                "scan_interval_minutes": 30
            },
            "ui": {
                "show_descriptions": True,
                "thumbnails_per_row": 0  # 0 = auto based on window size
            },
            "logging": {
                "path": log_dir  # Store logs in the correct location
            },
            "ollama": {
                "server_url": "http://localhost:11434",
                "model": "llava-phi3:latest",
                "system_prompt": "Describe this image concisely, start with main colors seperated by \" , \", then the main subject and key visual elements and style at the end."
            }
        }
    
    def load(self):
        """Load configuration from file."""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, "r") as f:
                    loaded_config = json.load(f)
                
                # Update configuration with loaded values
                self._update_dict(self.config, loaded_config)
                
                logger.info("Configuration loaded successfully")
                return True
            else:
                logger.info("Configuration file does not exist, using defaults")
                return False
        
        except (IOError, json.JSONDecodeError) as e:
            logger.error(f"Error loading configuration: {e}")
            return False
    
    def save(self):
        """Save configuration to file."""
        try:
            logger.info(f"Saving configuration to: {self.config_file}")  # ADDED for debug
            with open(self.config_file, "w") as f:
                json.dump(self.config, f, indent=4)
        
            logger.info("Configuration saved successfully")
            return True
        
        except IOError as e:
            logger.error(f"Error saving configuration: {e}")
            return False
    
    def _update_dict(self, target, source):
        """Recursively update a dictionary with values from another dictionary.
        
        Args:
            target (dict): Target dictionary to update
            source (dict): Source dictionary with new values
        """
        for key, value in source.items():
            if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                # Recursively update nested dictionaries
                self._update_dict(target[key], value)
            else:
                # Update value
                target[key] = value
    
    def get(self, section, key, default=None):
        """Get a configuration value.
        
        Args:
            section (str): Configuration section
            key (str): Configuration key
            default: Default value if key is not found
            
        Returns:
            Configuration value or default
        """
        try:
            return self.config[section][key]
        except (KeyError, TypeError):
            return default
    
    def set(self, section, key, value):
        """Set a configuration value.
        
        Args:
            section (str): Configuration section
            key (str): Configuration key
            value: Value to set
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if section not in self.config:
                self.config[section] = {}
            
            self.config[section][key] = value
            return True
        
        except Exception as e:
            logger.error(f"Error setting configuration value: {e}")
            return False
    
    def reset_to_defaults(self):
        """Reset configuration to default values."""
        self.config = self._get_default_config()
        self.save()
        
        logger.info("Configuration reset to defaults")
        return True
    
    def get_all(self):
        """Get the entire configuration dictionary.
        
        Returns:
            dict: Configuration dictionary
        """
        return self.config
        
    def has(self, section, key):
        """Check if a configuration key exists in a section.
        
        Args:
            section (str): Configuration section
            key (str): Configuration key
            
        Returns:
            bool: True if key exists in section, False otherwise
        """
        try:
            return section in self.config and key in self.config[section]
        except Exception as e:
            logger.error(f"Error checking configuration key: {e}")
            return False
