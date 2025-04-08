#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Virtualized grid for efficient thumbnail display
Handles large collections by only creating widgets for visible thumbnails
"""

import logging
from PyQt6.QtWidgets import (
    QWidget, QScrollArea, QVBoxLayout, QHBoxLayout, QGridLayout, 
    QLabel, QSizePolicy, QFrame
)
from PyQt6.QtCore import Qt, QSize, QRect, QTimer, pyqtSignal, QEvent

logger = logging.getLogger("StarImageBrowse.ui.virtualized_grid")

class VirtualizedGridWidget(QScrollArea):
    """
    A scrollable virtualized grid that only renders visible items.
    """
    
    # Signal emitted when the visible range changes
    range_changed = pyqtSignal(int, int)  # start_index, end_index
    
    def __init__(self, parent=None):
        """Initialize the virtualized grid widget.
        
        Args:
            parent (QWidget, optional): Parent widget
        """
        super().__init__(parent)
        
        # Settings
        self.item_width = 220   # Width of each thumbnail widget
        self.item_height = 300  # Height of each thumbnail widget
        self.h_spacing = 10     # Horizontal spacing between items
        self.v_spacing = 10     # Vertical spacing between items
        self.items_per_row = 4  # Default items per row
        self.margin = 10        # Margin around the grid
        
        # Internal data
        self.total_items = 0       # Total number of items in the dataset
        self.visible_range = (0, 0)  # Currently visible range (start_index, end_index)
        self.visible_widgets = {}   # Dictionary of visible widgets {index: widget}
        self.recycled_widgets = []  # List of widgets available for recycling
        self.item_provider = None   # Function that provides widgets for specific indices
        
        # Setup UI
        self.setup_ui()
        
    def setup_ui(self):
        """Set up the virtualized grid UI."""
        # Set up the scroll area
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # Create the container widget
        self.container = QWidget()
        self.setWidget(self.container)
        
        # Set up the layout
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(self.margin, self.margin, self.margin, self.margin)
        
        # Content area will have absolute positioning of child widgets
        self.content = QWidget()
        self.content.setLayout(QVBoxLayout())
        self.content.layout().setContentsMargins(0, 0, 0, 0)
        self.container_layout.addWidget(self.content)
        
        # Enable mouse tracking for hover effects
        self.setMouseTracking(True)
        
        # Set up a timer for scroll efficiency (prevents too many updates)
        self.scroll_timer = QTimer(self)
        self.scroll_timer.setSingleShot(True)
        self.scroll_timer.timeout.connect(self.update_visible_range)
        
        # Connect to scrollbar changes
        self.verticalScrollBar().valueChanged.connect(self.on_scroll)
        
        # Install event filter for resize events
        self.viewport().installEventFilter(self)
        
    def set_item_provider(self, provider_func):
        """Set the function that provides widgets for specific indices.
        
        Args:
            provider_func: Function that takes an index and returns a widget
        """
        self.item_provider = provider_func
        
    def set_items_per_row(self, count):
        """Set the number of items per row.
        
        Args:
            count (int): Number of items per row
        """
        if count != self.items_per_row:
            self.items_per_row = max(1, count)  # Ensure at least 1 item per row
            self.layout_items()
    
    def set_total_items(self, count):
        """Set the total number of items in the dataset.
        
        Args:
            count (int): Total number of items
        """
        if count != self.total_items:
            logger.debug(f"Setting total items to {count}")
            self.total_items = count
            self.layout_items()
            self.update_visible_range()
    
    def get_visible_range(self):
        """Get the current visible range.
        
        Returns:
            tuple: (start_index, end_index) of visible items
        """
        return self.visible_range
    
    def layout_items(self):
        """Update the layout based on current size and item count."""
        if self.total_items == 0:
            # Resize content height to 0 if no items
            self.content.setMinimumHeight(0)
            return
        
        # Calculate the total number of rows
        rows = (self.total_items + self.items_per_row - 1) // self.items_per_row
        
        # Calculate the total height of the content
        total_height = rows * (self.item_height + self.v_spacing) + self.margin
        
        # Set the content height
        self.content.setMinimumHeight(total_height)
        
        # Update the visible range
        self.update_visible_range()
    
    def on_scroll(self):
        """Handle scroll events."""
        # Use a timer to prevent too many updates
        self.scroll_timer.start(50)  # 50ms delay
    
    def update_visible_range(self):
        """Update the range of visible items based on scroll position."""
        if self.total_items == 0 or not self.item_provider:
            return
            
        # Get the visible rectangle
        visible_rect = self.viewport().rect()
        scroll_pos = self.verticalScrollBar().value()
        
        # Translate to content coordinates
        visible_rect.translate(0, scroll_pos)
        
        # Calculate the visible range
        row_height = self.item_height + self.v_spacing
        
        # Add buffer rows above and below for smoother scrolling
        buffer_rows = 1
        first_visible_row = max(0, (visible_rect.top() - buffer_rows * row_height) // row_height)
        last_visible_row = min((self.total_items - 1) // self.items_per_row, 
                              (visible_rect.bottom() + buffer_rows * row_height) // row_height)
        
        # Calculate the first and last visible indices
        first_visible_index = first_visible_row * self.items_per_row
        last_visible_index = min(self.total_items - 1, 
                                (last_visible_row + 1) * self.items_per_row - 1)
        
        # Check if the range has changed
        if self.visible_range != (first_visible_index, last_visible_index):
            old_range = self.visible_range
            self.visible_range = (first_visible_index, last_visible_index)
            
            # Emit signal for range change
            self.range_changed.emit(first_visible_index, last_visible_index)
            
            # Update the visible widgets
            self.update_visible_widgets()
            
    def update_visible_widgets(self):
        """Update the visible widgets based on the current visible range."""
        if not self.item_provider:
            return
            
        start_index, end_index = self.visible_range
        
        # Determine which indices are newly visible and which are no longer visible
        currently_visible = set(range(start_index, end_index + 1))
        previously_visible = set(self.visible_widgets.keys())
        
        to_add = currently_visible - previously_visible
        to_remove = previously_visible - currently_visible
        
        # Recycle widgets that are no longer visible
        for index in to_remove:
            widget = self.visible_widgets.pop(index)
            widget.hide()
            self.recycled_widgets.append(widget)
        
        # Add new widgets for newly visible indices
        for index in to_add:
            if index < 0 or index >= self.total_items:
                continue
                
            # Get a widget (new or recycled)
            if self.recycled_widgets:
                widget = self.recycled_widgets.pop()
            else:
                # Create a new placeholder widget
                widget = QFrame(self.content)
                widget.setFixedSize(self.item_width, self.item_height)
            
            # Position the widget
            row = index // self.items_per_row
            col = index % self.items_per_row
            
            x = col * (self.item_width + self.h_spacing)
            y = row * (self.item_height + self.v_spacing)
            
            widget.setGeometry(x, y, self.item_width, self.item_height)
            
            # Update the widget with data for the specific index
            updated_widget = self.item_provider(index, widget)
            if updated_widget is not widget:
                # If a new widget was returned, replace the old one
                widget.deleteLater()
                widget = updated_widget
                widget.setParent(self.content)
                widget.setGeometry(x, y, self.item_width, self.item_height)
            
            # Show the widget
            widget.show()
            self.visible_widgets[index] = widget
            
    def eventFilter(self, obj, event):
        """Event filter for handling resize events.
        
        Args:
            obj: Object that triggered the event
            event: Event object
            
        Returns:
            bool: True if event was handled, False otherwise
        """
        if obj is self.viewport() and event.type() == QEvent.Type.Resize:
            # Calculate items per row based on the new width
            viewport_width = self.viewport().width()
            available_width = viewport_width - 2 * self.margin
            items_per_row = max(1, available_width // (self.item_width + self.h_spacing))
            
            # Update the items per row if changed
            if items_per_row != self.items_per_row:
                self.set_items_per_row(items_per_row)
            
            # Update the visible range
            self.update_visible_range()
            
        return super().eventFilter(obj, event)
    
    def scrollToIndex(self, index):
        """Scroll to make a specific index visible.
        
        Args:
            index (int): Index to scroll to
        """
        if index < 0 or index >= self.total_items:
            return
            
        # Calculate the position of the item
        row = index // self.items_per_row
        y = row * (self.item_height + self.v_spacing)
        
        # Scroll to the position
        self.verticalScrollBar().setValue(y)
