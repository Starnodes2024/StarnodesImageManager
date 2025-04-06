#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Notification manager for StarImageBrowse
Provides centralized error handling and user feedback.
"""

import logging
import traceback
from enum import Enum
from PyQt6.QtWidgets import QMessageBox, QStatusBar
from PyQt6.QtCore import QTimer

logger = logging.getLogger("StarImageBrowse.ui.notification_manager")

class NotificationType(Enum):
    """Types of notifications."""
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"

class NotificationManager:
    """Manager for application notifications and error handling."""
    
    def __init__(self, status_bar=None, parent_widget=None):
        """Initialize the notification manager.
        
        Args:
            status_bar (QStatusBar, optional): Status bar for displaying messages
            parent_widget (QWidget, optional): Parent widget for message boxes
        """
        self.status_bar = status_bar
        self.parent_widget = parent_widget
        self.status_message_timer = QTimer()
        self.status_message_timer.setSingleShot(True)
        self.status_message_timer.timeout.connect(self.clear_status)
    
    def set_status_bar(self, status_bar):
        """Set the status bar for displaying messages.
        
        Args:
            status_bar (QStatusBar): Status bar widget
        """
        self.status_bar = status_bar
    
    def set_parent_widget(self, parent_widget):
        """Set the parent widget for message boxes.
        
        Args:
            parent_widget (QWidget): Parent widget
        """
        self.parent_widget = parent_widget
    
    def show_status_message(self, message, message_type=NotificationType.INFO, timeout=5000):
        """Show a message in the status bar.
        
        Args:
            message (str): Message to display
            message_type (NotificationType, optional): Type of message
            timeout (int, optional): Time in milliseconds before message is cleared (0 for no timeout)
        """
        if not self.status_bar:
            logger.warning(f"Status bar not set, cannot show message: {message}")
            return
        
        # Log the message
        if message_type == NotificationType.ERROR:
            logger.error(message)
        elif message_type == NotificationType.WARNING:
            logger.warning(message)
        else:
            logger.info(message)
        
        # Set message style based on type
        if message_type == NotificationType.ERROR:
            self.status_bar.setStyleSheet("background-color: #ffdddd; color: #990000;")
        elif message_type == NotificationType.WARNING:
            self.status_bar.setStyleSheet("background-color: #ffffdd; color: #999900;")
        elif message_type == NotificationType.SUCCESS:
            self.status_bar.setStyleSheet("background-color: #ddffdd; color: #009900;")
        else:
            self.status_bar.setStyleSheet("")
        
        # Show message
        self.status_bar.showMessage(message)
        
        # Set timeout if specified
        if timeout > 0:
            self.status_message_timer.start(timeout)
    
    def clear_status(self):
        """Clear the status bar message and reset styling."""
        if self.status_bar:
            self.status_bar.setStyleSheet("")
            self.status_bar.clearMessage()
    
    def show_message_box(self, title, message, message_type=NotificationType.INFO, details=None):
        """Show a message box to the user.
        
        Args:
            title (str): Title of the message box
            message (str): Message to display
            message_type (NotificationType, optional): Type of message
            details (str, optional): Detailed information to show in a collapsible section
        
        Returns:
            QMessageBox.StandardButton: Button clicked by the user
        """
        if not self.parent_widget:
            logger.warning(f"Parent widget not set, cannot show message box: {title} - {message}")
            return None
        
        # Log the message
        if message_type == NotificationType.ERROR:
            logger.error(f"{title}: {message}")
            if details:
                logger.error(f"Details: {details}")
        elif message_type == NotificationType.WARNING:
            logger.warning(f"{title}: {message}")
        else:
            logger.info(f"{title}: {message}")
        
        # Create message box
        msg_box = QMessageBox(self.parent_widget)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        
        # Set icon based on message type
        if message_type == NotificationType.ERROR:
            msg_box.setIcon(QMessageBox.Icon.Critical)
        elif message_type == NotificationType.WARNING:
            msg_box.setIcon(QMessageBox.Icon.Warning)
        elif message_type == NotificationType.SUCCESS:
            msg_box.setIcon(QMessageBox.Icon.Information)
        else:
            msg_box.setIcon(QMessageBox.Icon.Information)
        
        # Add details if provided
        if details:
            msg_box.setDetailedText(details)
        
        # Show message box and return result
        return msg_box.exec()
    
    def handle_exception(self, exception, operation_name, show_message_box=True):
        """Handle an exception and provide appropriate feedback.
        
        Args:
            exception (Exception): The exception to handle
            operation_name (str): Name of the operation that failed
            show_message_box (bool, optional): Whether to show a message box
        
        Returns:
            str: Error message generated for the exception
        """
        # Get exception details
        error_message = f"Error during {operation_name}: {str(exception)}"
        error_details = traceback.format_exc()
        
        # Log the error
        logger.error(error_message)
        logger.error(f"Exception details: {error_details}")
        
        # Show status message
        if self.status_bar:
            self.show_status_message(error_message, NotificationType.ERROR)
        
        # Show message box if requested
        if show_message_box and self.parent_widget:
            self.show_message_box(
                f"{operation_name} Failed",
                error_message,
                NotificationType.ERROR,
                error_details
            )
        
        return error_message
    
    def confirm_action(self, title, message, details=None):
        """Ask the user to confirm an action.
        
        Args:
            title (str): Title of the confirmation dialog
            message (str): Message to display
            details (str, optional): Detailed information
        
        Returns:
            bool: True if the user confirmed, False otherwise
        """
        if not self.parent_widget:
            logger.warning(f"Parent widget not set, cannot show confirmation dialog: {title} - {message}")
            return False
        
        # Create confirmation dialog
        msg_box = QMessageBox(self.parent_widget)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.setIcon(QMessageBox.Icon.Question)
        msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg_box.setDefaultButton(QMessageBox.StandardButton.No)
        
        # Add details if provided
        if details:
            msg_box.setDetailedText(details)
        
        # Show dialog and return result
        return msg_box.exec() == QMessageBox.StandardButton.Yes
    
    def show_success_message(self, title, message, show_message_box=False):
        """Show a success message to the user.
        
        Args:
            title (str): Title of the message
            message (str): Message to display
            show_message_box (bool, optional): Whether to show a message box in addition to status bar
        """
        # Show status message
        self.show_status_message(message, NotificationType.SUCCESS)
        
        # Show message box if requested
        if show_message_box and self.parent_widget:
            self.show_message_box(title, message, NotificationType.SUCCESS)
