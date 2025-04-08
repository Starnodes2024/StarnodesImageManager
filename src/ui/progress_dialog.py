#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Progress dialog for StarImageBrowse
Displays progress for long-running operations.
"""

import logging
import time
from datetime import timedelta
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QProgressBar, QPushButton, QTextEdit
)
from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot, QMetaObject, Q_ARG, Qt, QTimer

logger = logging.getLogger("StarImageBrowse.ui.progress_dialog")

class ProgressDialog(QDialog):
    """Dialog for displaying progress of long-running operations."""
    
    cancelled = pyqtSignal()  # Signal emitted when the operation is cancelled
    
    def __init__(self, title, description, parent=None, cancellable=True):
        """Initialize the progress dialog.
        
        Args:
            title (str): Dialog title
            description (str): Description of the operation
            parent (QWidget, optional): Parent widget
            cancellable (bool): Whether the operation can be cancelled
        """
        super().__init__(parent)
        
        self.setWindowTitle(title)
        self.description = description
        self.cancellable = cancellable
        self.is_complete = False
        self.user_cancelled = False  # Track whether user has explicitly requested cancellation
        
        # Time tracking for estimating remaining time
        self.start_time = None
        self.processed_items = 0
        self.last_current = 0
        
        self.setup_ui()
        
        logger.debug(f"Progress dialog created: {title}")
    
    def setup_ui(self):
        """Set up the progress dialog UI."""
        try:
            # Make dialog non-resizable
            self.setFixedSize(500, 300)
            
            # Remove close button if not cancellable
            if not self.cancellable:
                self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowCloseButtonHint)
            
            # Main layout
            layout = QVBoxLayout(self)
            
            # Description label
            self.description_label = QLabel(self.description)
            layout.addWidget(self.description_label)
            
            # Progress bar
            self.progress_bar = QProgressBar()
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(0)
            layout.addWidget(self.progress_bar)
            
            # Current operation label
            self.operation_label = QLabel("Initializing...")
            layout.addWidget(self.operation_label)
            
            # Time remaining label
            self.time_label = QLabel("Estimating time remaining...")
            self.time_label.setVisible(False)  # Hide initially until we have an estimate
            layout.addWidget(self.time_label)
            
            # Log text box
            self.log_text = QTextEdit()
            self.log_text.setReadOnly(True)
            self.log_text.setFixedHeight(150)
            layout.addWidget(self.log_text)
            
            # Button layout
            button_layout = QHBoxLayout()
            button_layout.addStretch(1)
            
            # Close button (initially hidden)
            self.close_button = QPushButton("Close")
            self.close_button.clicked.connect(self.accept)
            self.close_button.setVisible(False)
            button_layout.addWidget(self.close_button)
            
            # Cancel button
            if self.cancellable:
                self.cancel_button = QPushButton("Cancel")
                self.cancel_button.clicked.connect(self.on_cancel)
                button_layout.addWidget(self.cancel_button)
            
            layout.addLayout(button_layout)
            
            logger.debug("Progress dialog UI setup complete")
            
        except Exception as e:
            logger.error(f"Error setting up progress dialog UI: {str(e)}")
    
    def on_cancel(self):
        """Handle cancel button click."""
        try:
            # Only proceed if this was triggered by an actual user action on the cancel button
            # This prevents false cancellation messages
            if not hasattr(self, 'cancel_button') or not self.cancel_button.isVisible():
                logger.debug("Ignoring automatic cancel signal - not from user action")
                return
                
            logger.debug("Cancel button explicitly clicked by user")
            self.user_cancelled = True  # Mark as explicitly cancelled by user
            
            # Emit the cancelled signal to the worker
            self.cancelled.emit()
            
            # Disable the cancel button
            if hasattr(self, 'cancel_button'):
                self.cancel_button.setEnabled(False)
                
            # Update the UI
            self.update_operation("Cancelling operation...")
            self.log_message("Cancellation requested by user. Waiting for operations to complete...")
            
            # Automatically close after a reasonable timeout (5 seconds)
            QTimer.singleShot(5000, self.accept)
            
        except Exception as e:
            logger.error(f"Error in cancel handler: {str(e)}")
    
    def closeEvent(self, event):
        """Override closeEvent to handle dialog closing."""
        try:
            # If operation is complete, allow closing
            if self.is_complete:
                event.accept()
                logger.debug("Progress dialog closed")
            # Otherwise, treat as cancel if cancellable
            elif self.cancellable:
                self.on_cancel()
                event.ignore()
                logger.debug("Progress dialog close attempted - treated as cancel")
            # If not cancellable, don't allow closing
            else:
                event.ignore()
                logger.debug("Progress dialog close prevented - operation not cancellable")
        except Exception as e:
            logger.error(f"Error in closeEvent: {str(e)}")
            event.accept()  # Allow closing on error
    
    @pyqtSlot(int, int, str)
    def update_progress(self, current, total, message=None):
        """Update the progress bar.
        
        Args:
            current (int): Current progress value
            total (int): Total progress value
            message (str, optional): Operation message to display
        """
        try:
            # Start timing when we get the first progress update
            if self.start_time is None and current > 0:
                self.start_time = time.time()
            
            # Update processed items count for time estimation
            if current > self.last_current:
                items_processed_now = current - self.last_current
                self.processed_items += items_processed_now
                self.last_current = current
                
            # Use invokeMethod to ensure UI update happens on the main thread
            QMetaObject.invokeMethod(self, "_update_progress_ui",
                                    Qt.ConnectionType.QueuedConnection,
                                    Q_ARG(int, current),
                                    Q_ARG(int, total))
            
            # Update operation message if provided
            if message:
                self.update_operation(message)
        except Exception as e:
            logger.error(f"Error updating progress: {str(e)}")
    
    @pyqtSlot(int, int)
    def _update_progress_ui(self, current, total):
        """Internal method that actually updates the UI on the main thread.
        
        Args:
            current (int): Current progress value
            total (int): Total progress value
        """
        try:
            if not self.isVisible():
                return
                
            if total <= 0:
                self.progress_bar.setRange(0, 0)  # Show busy indicator
                self.time_label.setVisible(False)
            else:
                self.progress_bar.setRange(0, total)
                self.progress_bar.setValue(current)
                
                # Calculate and display time remaining
                if self.start_time is not None and current > 0:
                    elapsed_time = time.time() - self.start_time
                    
                    # Only show time estimate after processing a few items for better accuracy
                    if self.processed_items >= 3:
                        # Calculate time per item and estimate remaining time
                        items_remaining = total - current
                        if items_remaining > 0 and elapsed_time > 0:
                            avg_time_per_item = elapsed_time / self.processed_items
                            estimated_time_remaining = items_remaining * avg_time_per_item
                            
                            # Format time as HH:MM:SS
                            time_str = str(timedelta(seconds=int(estimated_time_remaining)))
                            
                            # Remove days from timedelta if present
                            if 'day' in time_str:
                                days, time_part = time_str.split(',')
                                day_count = int(days.split()[0])
                                hours, minutes, seconds = map(int, time_part.strip().split(':'))
                                total_hours = day_count * 24 + hours
                                time_str = f"{total_hours:02d}:{minutes:02d}:{seconds:02d}"
                            
                            # Update time label
                            percent_complete = (current / total) * 100
                            self.time_label.setText(f"Processing: {current} of {total} ({percent_complete:.1f}%) - Time remaining: {time_str}")
                            self.time_label.setVisible(True)
                    else:
                        self.time_label.setText("Calculating time remaining...")
                        self.time_label.setVisible(True)
                
            # Update the display
            self.repaint()
        except Exception as e:
            logger.error(f"Error in internal update progress UI: {str(e)}")
    
    def update_operation(self, message):
        """Update the current operation message.
        
        Args:
            message (str): Operation message
        """
        try:
            # Use invokeMethod to ensure UI update happens on the main thread
            QMetaObject.invokeMethod(self, "_update_operation_ui",
                                   Qt.ConnectionType.QueuedConnection,
                                   Q_ARG(str, message))
        except Exception as e:
            logger.error(f"Error updating operation: {str(e)}")
    
    @pyqtSlot(str)
    def _update_operation_ui(self, message):
        """Internal method that actually updates the operation label on the main thread.
        
        Args:
            message (str): Operation message
        """
        try:
            if not self.isVisible():
                return
                
            self.operation_label.setText(message)
            
            # Update the display
            self.repaint()
        except Exception as e:
            logger.error(f"Error in internal update operation UI: {str(e)}")
    
    def log_message(self, message):
        """Add a message to the log.
        
        Args:
            message (str): Message to log
        """
        try:
            # Use invokeMethod to ensure UI update happens on the main thread
            QMetaObject.invokeMethod(self, "_log_message_ui",
                                   Qt.ConnectionType.QueuedConnection,
                                   Q_ARG(str, message))
        except Exception as e:
            logger.error(f"Error logging message: {str(e)}")
    
    @pyqtSlot(str)
    def _log_message_ui(self, message):
        """Internal method that actually adds the message to the log on the main thread.
        
        Args:
            message (str): Message to log
        """
        try:
            if not self.isVisible():
                return
                
            self.log_text.append(message)
            
            # Scroll to bottom
            self.log_text.verticalScrollBar().setValue(
                self.log_text.verticalScrollBar().maximum()
            )
            
            # Update the display
            self.repaint()
        except Exception as e:
            logger.error(f"Error in internal log message UI: {str(e)}")
    
    def close_when_finished(self):
        """Enable the close button and mark the operation as complete."""
        try:
            # Mark dialog as complete to prevent further updates
            self.is_complete = True
            
            # Calculate and log total processing time
            if self.start_time is not None:
                total_time = time.time() - self.start_time
                time_str = str(timedelta(seconds=int(total_time)))
                self.log_message(f"Total processing time: {time_str}")
            
            # Use invokeMethod to ensure UI update happens on the main thread
            QMetaObject.invokeMethod(self, "_close_when_finished_ui",
                                   Qt.ConnectionType.QueuedConnection)
            
            # Log that we're finishing the dialog
            logger.debug(f"Progress dialog marked as complete: {self.windowTitle()}")
        except Exception as e:
            logger.error(f"Error in close_when_finished: {str(e)}")
    
    @pyqtSlot()
    def _close_when_finished_ui(self):
        """Internal method that actually updates the UI for completion on the main thread."""
        try:
            logger.debug("Operation marked as complete")
            self.is_complete = True
            
            # Update time label to show completion
            if hasattr(self, 'time_label'):
                self.time_label.setText("Processing complete")
            
            # Hide cancel button if present
            if self.cancellable and hasattr(self, 'cancel_button'):
                self.cancel_button.setVisible(False)
                self.cancel_button.setEnabled(False)
            
            # Show and enable close button
            if hasattr(self, 'close_button'):
                self.close_button.setVisible(True)
                self.close_button.setEnabled(True)
                # Focus the close button so Enter key works
                self.close_button.setFocus()
                
            # Update the display
            self.repaint()
            
            # If the user had already requested cancellation, close automatically
            if self.user_cancelled:
                logger.debug("Dialog was in cancellation state - closing automatically")
                # Use a short delay to ensure UI updates first
                QTimer.singleShot(500, self.accept)
        except Exception as e:
            logger.error(f"Error in internal close when finished UI: {str(e)}")
