#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Search panel UI component for StarImageBrowse
Provides search functionality for finding images by description.
"""

import logging
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QPushButton, QCompleter
)
from PyQt6.QtCore import Qt, pyqtSignal, QStringListModel

logger = logging.getLogger("StarImageBrowse.ui.search_panel")

class SearchPanel(QWidget):
    """Panel for searching images by description."""
    
    search_requested = pyqtSignal(str)  # Signal emitted when search is requested
    
    def __init__(self, parent=None):
        """Initialize the search panel.
        
        Args:
            parent (QWidget, optional): Parent widget
        """
        super().__init__(parent)
        
        self.setup_ui()
    
    def setup_ui(self):
        """Set up the search panel UI."""
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Header
        header_label = QLabel("Search Images")
        header_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(header_label)
        
        # Search input layout
        search_layout = QHBoxLayout()
        
        # Search input field
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search by description...")
        self.search_input.returnPressed.connect(self.on_search)
        search_layout.addWidget(self.search_input)
        
        # Search button
        self.search_button = QPushButton("Search")
        self.search_button.clicked.connect(self.on_search)
        search_layout.addWidget(self.search_button)
        
        layout.addLayout(search_layout)
        
        # Search suggestions (will be populated later)
        self.completer = QCompleter()
        self.completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.search_input.setCompleter(self.completer)
        
        # Add some spacing
        layout.addSpacing(10)
        
        # Help text
        help_label = QLabel(
            "Enter keywords to search image descriptions. Examples:\n"
            "• \"sunset beach\"\n"
            "• \"dog playing\"\n"
            "• \"red car\""
        )
        help_label.setWordWrap(True)
        help_label.setStyleSheet("color: #666;")
        layout.addWidget(help_label)
        
        # Add stretch to push everything to the top
        layout.addStretch(1)
    
    def on_search(self):
        """Handle search button click or Enter key press."""
        query = self.search_input.text().strip()
        
        if query:
            # Emit search signal
            self.search_requested.emit(query)
            
            # Add to recent searches (could be implemented later)
    
    def set_search_suggestions(self, suggestions):
        """Set the search suggestions for autocomplete.
        
        Args:
            suggestions (list): List of search suggestions
        """
        model = QStringListModel()
        model.setStringList(suggestions)
        self.completer.setModel(model)
    
    def clear(self):
        """Clear the search input."""
        self.search_input.clear()
