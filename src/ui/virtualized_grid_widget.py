#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Virtualized grid widget for StarImageBrowse
Efficiently displays thumbnails by only rendering the visible ones
"""

import logging
import math
from PyQt6.QtWidgets import (
    QAbstractScrollArea, QWidget, QVBoxLayout, QScrollBar, QApplication
)
from PyQt6.QtCore import Qt, QRect, QTimer, pyqtSignal, QSize

logger = logging.getLogger("StarImageBrowse.ui.virtualized_grid_widget")

class VirtualizedGridWidget(QAbstractScrollArea):
    """
    A grid widget that only renders visible items.
    This significantly improves performance for large datasets.
    """
    
    # Signal emitted when visible range changes
    visibleRangeChanged = pyqtSignal(int, int)  # start_index, end_index
    
    # Signal emitted when scrolling starts or stops
    scrollStateChanged = pyqtSignal(bool)  # is_scrolling
    
    def __init__(self, parent=None):
        """Initialize the virtualized grid widget.
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        
        # Widget size parameters
        self.item_width = 220
        self.item_height = 300
        self.spacing = 10
        self.margin = 20
        
        # Grid layout properties
        self.columns = 4  # Default, will be recalculated on resize
        self.total_items = 0
        self.visible_items = {}  # Dictionary of visible widgets by index
        self.item_widgets = {}  # Cache of created widget instances
        self.item_positions = {}  # Cache of item positions (grid x, y)
        
        # Item creation
        self.item_creator = None  # Function to create a new item
        
        # Scroll properties
        self.is_scrolling = False
        self.scroll_timer = QTimer(self)
        self.scroll_timer.setSingleShot(True)
        self.scroll_timer.timeout.connect(self._on_scroll_stopped)
        
        # Selection
        self.selected_indices = set()
        self.selection_anchor = None
        
        # Configure scrollbars
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.verticalScrollBar().valueChanged.connect(self._on_scroll_changed)
        
        # Configure viewport
        self.viewport().setMouseTracking(True)
        
        # Initial update
        self._update_visible_items()
    
    def set_item_creator(self, creator_func):
        """Set the function to create item widgets.
        
        Args:
            creator_func: Function that creates a new item widget.
                          Should accept (index, parent) as parameters.
        """
        self.item_creator = creator_func
    
    def set_item_size(self, width, height, spacing=10):
        """Set the size of items in the grid.
        
        Args:
            width: Width of each item
            height: Height of each item
            spacing: Spacing between items
        """
        if width == self.item_width and height == self.item_height and spacing == self.spacing:
            return
            
        self.item_width = width
        self.item_height = height
        self.spacing = spacing
        
        # Update layout
        self._recalculate_layout()
        self._update_scrollbar_range()
        self._update_visible_items()
        self.viewport().update()
    
    def set_total_items(self, count):
        """Set the total number of items in the grid.
        
        Args:
            count: Total number of items
        """
        if count == self.total_items:
            return
            
        # Clear selection when the dataset changes
        self.selected_indices.clear()
        self.selection_anchor = None
        
        # Store old count for partial refreshes
        old_count = self.total_items
        self.total_items = count
        
        # Update item positions cache
        self._recalculate_item_positions()
        
        # Update scrollbar
        self._update_scrollbar_range()
        
        # Remove items that are no longer needed
        indices_to_remove = [idx for idx in self.item_widgets.keys() if idx >= count]
        for idx in indices_to_remove:
            if idx in self.item_widgets:
                self.item_widgets[idx].deleteLater()
                del self.item_widgets[idx]
                
        # Update visible items
        self._update_visible_items()
        self.viewport().update()
    
    def clear(self):
        """Clear all items from the grid."""
        # Remove all widgets
        for widget in self.item_widgets.values():
            widget.deleteLater()
            
        self.item_widgets.clear()
        self.visible_items.clear()
        self.item_positions.clear()
        self.selected_indices.clear()
        self.selection_anchor = None
        self.total_items = 0
        
        # Update scrollbar
        self._update_scrollbar_range()
        self.viewport().update()
    
    def ensure_visible(self, index):
        """Ensure the item at the given index is visible.
        
        Args:
            index: Index of the item to make visible
        """
        if index < 0 or index >= self.total_items:
            return
            
        # Calculate item position
        row, col = self._index_to_position(index)
        
        # Calculate position in viewport
        y = row * (self.item_height + self.spacing) + self.margin
        
        # Get viewport dimensions
        viewport_height = self.viewport().height()
        
        # Current scroll position
        scroll_pos = self.verticalScrollBar().value()
        
        # Check if the item is already visible
        item_top = y
        item_bottom = y + self.item_height
        
        view_top = scroll_pos
        view_bottom = scroll_pos + viewport_height
        
        # If item is above the viewport, scroll up to it
        if item_top < view_top:
            self.verticalScrollBar().setValue(item_top)
        
        # If item is below the viewport, scroll down to make it visible
        elif item_bottom > view_bottom:
            # Scroll so that the bottom of the item is at the bottom of the viewport
            self.verticalScrollBar().setValue(item_bottom - viewport_height)
    
    def select_item(self, index, extend_selection=False, range_selection=False):
        """Select the item at the given index.
        
        Args:
            index: Index of the item to select
            extend_selection: Whether to extend the current selection
            range_selection: Whether to select a range from the anchor to this item
        """
        if index < 0 or index >= self.total_items:
            return
            
        # Determine selection behavior
        if not extend_selection and not range_selection:
            # Single selection - clear previous selection
            self.selected_indices.clear()
            self.selected_indices.add(index)
            self.selection_anchor = index
            
        elif extend_selection:
            # Extend selection - toggle select/deselect
            if index in self.selected_indices:
                self.selected_indices.remove(index)
            else:
                self.selected_indices.add(index)
                self.selection_anchor = index
                
        elif range_selection and self.selection_anchor is not None:
            # Range selection from anchor to current index
            start = min(self.selection_anchor, index)
            end = max(self.selection_anchor, index)
            
            # Add range to selection
            for i in range(start, end + 1):
                self.selected_indices.add(i)
        
        # Update the visible items
        self._update_selection_state()
        self.viewport().update()
    
    def is_selected(self, index):
        """Check if the item at the given index is selected.
        
        Args:
            index: Index to check
            
        Returns:
            bool: True if the item is selected, False otherwise
        """
        return index in self.selected_indices
    
    def get_selected_indices(self):
        """Get the indices of all selected items.
        
        Returns:
            list: List of selected indices
        """
        return sorted(list(self.selected_indices))
    
    def select_all(self):
        """Select all items."""
        self.selected_indices = set(range(self.total_items))
        self._update_selection_state()
        self.viewport().update()
    
    def clear_selection(self):
        """Clear all selections."""
        self.selected_indices.clear()
        self.selection_anchor = None
        self._update_selection_state()
        self.viewport().update()
    
    def resizeEvent(self, event):
        """Handle resize events.
        
        Args:
            event: Resize event
        """
        super().resizeEvent(event)
        
        # Recalculate layout
        self._recalculate_layout()
        
        # Update scrollbar
        self._update_scrollbar_range()
        
        # Update visible items
        self._update_visible_items()
    
    def paintEvent(self, event):
        """Handle paint events.
        
        Args:
            event: Paint event
        """
        # Nothing to paint in the base widget, all items are child widgets
        pass
    
    def _recalculate_layout(self):
        """Recalculate grid layout based on current viewport size."""
        # Calculate number of columns
        viewport_width = self.viewport().width()
        available_width = viewport_width - 2 * self.margin
        
        # Calculate how many columns can fit
        item_space = self.item_width + self.spacing
        self.columns = max(1, int((available_width + self.spacing) / item_space))
        
        # Recalculate item positions
        self._recalculate_item_positions()
    
    def _recalculate_item_positions(self):
        """Update the cache of item positions."""
        # Clear cached positions
        self.item_positions.clear()
        
        # Calculate each item's position
        for idx in range(self.total_items):
            self.item_positions[idx] = self._index_to_position(idx)
    
    def _index_to_position(self, index):
        """Convert an item index to grid position (row, column).
        
        Args:
            index: Item index
            
        Returns:
            tuple: (row, column)
        """
        if index in self.item_positions:
            return self.item_positions[index]
            
        # Calculate row and column
        row = index // self.columns
        col = index % self.columns
        
        return (row, col)
    
    def _update_scrollbar_range(self):
        """Update the scrollbar range based on total items."""
        if self.total_items == 0:
            self.verticalScrollBar().setRange(0, 0)
            return
            
        # Calculate total rows
        rows = math.ceil(self.total_items / self.columns)
        
        # Calculate total height
        total_height = rows * (self.item_height + self.spacing) + self.margin * 2 - self.spacing
        
        # Viewport height
        viewport_height = self.viewport().height()
        
        # Set scrollbar range
        max_scroll = max(0, total_height - viewport_height)
        self.verticalScrollBar().setRange(0, max_scroll)
        self.verticalScrollBar().setPageStep(viewport_height)
    
    def _update_visible_items(self):
        """Update which items are visible in the viewport."""
        if not self.item_creator or self.total_items == 0:
            return
            
        # Get current scroll position and viewport size
        scroll_pos = self.verticalScrollBar().value()
        viewport_height = self.viewport().height()
        viewport_width = self.viewport().width()
        
        # Calculate the visible range of rows
        first_visible_row = max(0, scroll_pos - self.margin) // (self.item_height + self.spacing)
        last_visible_row = (scroll_pos + viewport_height + self.margin) // (self.item_height + self.spacing)
        
        # Calculate the range of indices
        first_visible_index = first_visible_row * self.columns
        last_visible_index = min(self.total_items - 1, (last_visible_row + 1) * self.columns - 1)
        
        # Keep track of which items we've updated
        updated_indices = set()
        
        # Update or create visible items
        for idx in range(first_visible_index, last_visible_index + 1):
            # Skip if index is out of range
            if idx >= self.total_items:
                continue
                
            # Create or get the widget
            if idx not in self.item_widgets:
                widget = self.item_creator(idx, self.viewport())
                if widget:
                    self.item_widgets[idx] = widget
                else:
                    # Skip if widget creation failed
                    continue
            
            widget = self.item_widgets[idx]
            updated_indices.add(idx)
            
            # Calculate position
            row, col = self._index_to_position(idx)
            x = col * (self.item_width + self.spacing) + self.margin
            y = row * (self.item_height + self.spacing) + self.margin - scroll_pos
            
            # Position the widget
            widget.setGeometry(x, y, self.item_width, self.item_height)
            
            # Show the widget if it fits in the viewport
            if (y + self.item_height > 0 and 
                y < viewport_height and 
                x + self.item_width > 0 and 
                x < viewport_width):
                widget.show()
                self.visible_items[idx] = widget
            else:
                widget.hide()
                if idx in self.visible_items:
                    del self.visible_items[idx]
        
        # Hide items that are no longer visible
        for idx in list(self.visible_items.keys()):
            if idx not in updated_indices:
                self.visible_items[idx].hide()
                del self.visible_items[idx]
        
        # Emit signal with visible range
        self.visibleRangeChanged.emit(first_visible_index, last_visible_index)
    
    def _on_scroll_changed(self, value):
        """Handle scrollbar value changes.
        
        Args:
            value: New scrollbar value
        """
        # Update visible items
        self._update_visible_items()
        
        # Track scrolling state
        if not self.is_scrolling:
            self.is_scrolling = True
            self.scrollStateChanged.emit(True)
            
        # Reset timer to detect when scrolling stops
        self.scroll_timer.start(300)
    
    def _on_scroll_stopped(self):
        """Handle scroll stop event."""
        self.is_scrolling = False
        self.scrollStateChanged.emit(False)
    
    def _update_selection_state(self):
        """Update the selection state of visible items."""
        for idx, widget in self.visible_items.items():
            if hasattr(widget, 'set_selected'):
                widget.set_selected(idx in self.selected_indices)
    
    def mousePressEvent(self, event):
        """Handle mouse press events.
        
        Args:
            event: Mouse event
        """
        if event.button() == Qt.MouseButton.LeftButton:
            # Find the clicked item
            pos = event.position()
            x, y = pos.x(), pos.y()
            
            # Add scroll offset to y
            y += self.verticalScrollBar().value()
            
            # Convert to grid position
            col = max(0, int((x - self.margin) / (self.item_width + self.spacing)))
            row = max(0, int((y - self.margin) / (self.item_height + self.spacing)))
            
            # Convert to index
            index = row * self.columns + col
            
            # Ignore if out of range
            if index >= self.total_items:
                if not event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier):
                    self.clear_selection()
                return
            
            # Select the item
            extend_selection = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
            range_selection = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
            self.select_item(index, extend_selection, range_selection)
        
        super().mousePressEvent(event)
    
    def keyPressEvent(self, event):
        """Handle key press events.
        
        Args:
            event: Key event
        """
        # Get the current selection
        selected = self.get_selected_indices()
        if not selected:
            # If nothing is selected, select the first item
            if event.key() in (Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Up, Qt.Key.Key_Down, Qt.Key.Key_Home, Qt.Key.Key_End):
                if self.total_items > 0:
                    self.select_item(0)
                    self.ensure_visible(0)
            return
        
        # Current index is the last selected item
        current = selected[-1]
        
        # Calculate new index based on key
        new_index = current
        
        if event.key() == Qt.Key.Key_Left:
            new_index = max(0, current - 1)
        elif event.key() == Qt.Key.Key_Right:
            new_index = min(self.total_items - 1, current + 1)
        elif event.key() == Qt.Key.Key_Up:
            new_index = max(0, current - self.columns)
        elif event.key() == Qt.Key.Key_Down:
            new_index = min(self.total_items - 1, current + self.columns)
        elif event.key() == Qt.Key.Key_Home:
            new_index = 0
        elif event.key() == Qt.Key.Key_End:
            new_index = self.total_items - 1
        elif event.key() == Qt.Key.Key_A and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            # Ctrl+A: Select all
            self.select_all()
            return
        elif event.key() == Qt.Key.Key_Escape:
            # Escape: Clear selection
            self.clear_selection()
            return
        
        # Select the new item with appropriate modifiers
        if new_index != current:
            extend_selection = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
            range_selection = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
            self.select_item(new_index, extend_selection, range_selection)
            self.ensure_visible(new_index)
        
        super().keyPressEvent(event)
