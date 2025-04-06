#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Configuration manager for StarImageBrowse
Handles loading, saving, and accessing application configuration.
"""

import os
import json
import logging
from pathlib import Path

logger = logging.getLogger("StarImageBrowse.config")

class ConfigManager:
    """Manages application configuration."""
    
    def __init__(self, config_dir=None, config_file="settings.json"):
        """Initialize the configuration manager.
        
        Args:
            config_dir (str, optional): Directory to store configuration files
            config_file (str, optional): Name of the main configuration file
        """
        # Set configuration directory
        if config_dir is None:
            # Use application directory by default
            self.config_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "config")
        else:
            self.config_dir = config_dir
        
        # Ensure directory exists
        os.makedirs(self.config_dir, exist_ok=True)
        
        # Set configuration file path
        self.config_file = os.path.join(self.config_dir, config_file)
        
        # Initialize configuration dictionary with defaults
        self.config = self._get_default_config()
        
        # Load existing configuration if available
        self.load()
        
        logger.info(f"Configuration manager initialized with file: {self.config_file}")
    
    def _get_default_config(self):
        """Get the default configuration.
        
        Returns:
            dict: Default configuration dictionary
        """
        return {
            "app": {
                "first_run": True,
                "window_width": 1200,
                "window_height": 800,
                "theme": "system"  # Options: system, light, dark
            },
            "thumbnails": {
                "size": 200,
                "quality": 85
            },
            "ai": {
                "model_path": os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "model"),
                "device": "auto",  # Options: auto, cpu, cuda
                "batch_size": 1
            },
            "database": {
                "path": os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "star_image_browse.db")
            },
            "monitor": {
                "watch_folders": True,
                "scan_interval_minutes": 30
            },
            "ui": {
                "show_descriptions": True,
                "thumbnails_per_row": 0  # 0 = auto based on window size
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
