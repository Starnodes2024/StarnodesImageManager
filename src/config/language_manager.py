#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Language manager for StarImageBrowse
Handles loading and applying translations.
"""

import os
import json
import logging
from pathlib import Path

logger = logging.getLogger("StarImageBrowse.config.language_manager")

class LanguageManager:
    """Manages language translations for the application."""
    
    def __init__(self, config_manager):
        """Initialize the language manager.
        
        Args:
            config_manager: Configuration manager instance
        """
        self.config_manager = config_manager
        self.translations = {}
        self.current_language = None
        self.default_language = "en_GB"
        
        # Load the selected language
        self.load_language()
    
    def get_language_dir(self):
        """Get the path to the language directory."""
        import sys
        
        # Check if we're running in portable mode (PyInstaller executable)
        is_portable = getattr(sys, 'frozen', False)
        
        if is_portable:
            # Use the executable directory for portable mode
            exe_dir = os.path.dirname(sys.executable)
            return os.path.join(exe_dir, "data", "lang")
        else:
            # For development mode, use the path relative to this file
            app_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            return os.path.join(app_dir, "data", "lang")
    
    def get_available_languages(self):
        """Get a list of available languages.
        
        Returns:
            list: List of dictionaries with language information
        """
        languages = []
        lang_dir = self.get_language_dir()
        
        # Check if the directory exists
        if not os.path.exists(lang_dir):
            logger.warning(f"Language directory not found: {lang_dir}")
            # Add English as fallback
            languages.append({"name": "English (UK)", "code": "en_GB"})
            return languages
        
        # Get all JSON files in the directory
        language_files = [f for f in os.listdir(lang_dir) if f.endswith(".json")]
        
        # If no language files found, add English as fallback
        if not language_files:
            logger.warning("No language files found in the language directory")
            languages.append({"name": "English (UK)", "code": "en_GB"})
            return languages
        
        # Add each language to the list
        for lang_file in language_files:
            try:
                with open(os.path.join(lang_dir, lang_file), "r", encoding="utf-8") as f:
                    lang_data = json.load(f)
                    languages.append({
                        "name": lang_data.get("language", os.path.splitext(lang_file)[0]),
                        "code": lang_data.get("code", os.path.splitext(lang_file)[0]),
                        "file": lang_file
                    })
            except Exception as e:
                logger.error(f"Error loading language file {lang_file}: {e}")
        
        return languages
    
    def load_language(self, language_code=None):
        """Load a language file.
        
        Args:
            language_code (str, optional): Language code to load. If None, load from config.
        
        Returns:
            bool: True if language was loaded successfully, False otherwise
        """
        # If no language code provided, get from config
        if language_code is None:
            language_code = self.config_manager.get("ui", "language", self.default_language)
        
        # If same as current language, do nothing
        if language_code == self.current_language and self.translations:
            return True
        
        # Get the language file path
        lang_dir = self.get_language_dir()
        lang_file = os.path.join(lang_dir, f"{language_code}.json")
        
        # Check if the file exists
        if not os.path.exists(lang_file):
            logger.warning(f"Language file not found: {lang_file}")
            # If not the default language, try to load the default
            if language_code != self.default_language:
                logger.info(f"Falling back to default language: {self.default_language}")
                return self.load_language(self.default_language)
            else:
                # If default language file not found, create empty translations
                self.translations = {}
                self.current_language = self.default_language
                return False
        
        # Load the language file
        try:
            with open(lang_file, "r", encoding="utf-8") as f:
                lang_data = json.load(f)
                self.translations = lang_data.get("translations", {})
                self.current_language = language_code
                logger.info(f"Loaded language: {language_code}")
                return True
        except Exception as e:
            logger.error(f"Error loading language file {lang_file}: {e}")
            # If not the default language, try to load the default
            if language_code != self.default_language:
                logger.info(f"Falling back to default language: {self.default_language}")
                return self.load_language(self.default_language)
            else:
                # If default language file not found, create empty translations
                self.translations = {}
                self.current_language = self.default_language
                return False
    
    def get_translation(self, section, key, default=None):
        """Get a translation for a key.
        
        Args:
            section (str): Section in the translations
            key (str): Key in the section
            default (str, optional): Default value if translation not found
        
        Returns:
            str: Translated string or default value
        """
        # If no translations loaded, return default
        if not self.translations:
            return default if default is not None else key
        
        # Get the section
        section_data = self.translations.get(section, {})
        
        # Get the translation
        translation = section_data.get(key)
        
        # If translation not found, return default or key
        if translation is None:
            return default if default is not None else key
        
        return translation
    
    def translate(self, section, key, default=None):
        """Alias for get_translation."""
        return self.get_translation(section, key, default)
