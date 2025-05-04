#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Error handling and user feedback utilities for StarImageBrowse
"""

import logging
import traceback
from enum import Enum
from PyQt6.QtWidgets import QMessageBox, QStatusBar
from PyQt6.QtCore import QTimer, Qt

logger = logging.getLogger("StarImageBrowse.ui.error_handler")

class MessageType(Enum):
    """Types of messages for user feedback."""
    INFO = 1
    SUCCESS = 2
    WARNING = 3
    ERROR = 4

class ErrorHandler:
    """Centralized error handling and user feedback utility."""
    
    @staticmethod
    def get_translation(language_manager, key, default=None):
        """Get a translation for a key.
        
        Args:
            language_manager: Language manager instance
            key (str): Key in the error_handler section
            default (str, optional): Default value if translation not found
            
        Returns:
            str: Translated string or default value
        """
        if language_manager:
            return language_manager.translate('error_handler', key, default)
        return default
    
    @staticmethod
    def show_message_box(parent, title, message, message_type=MessageType.INFO, details=None, language_manager=None):
        """Show a message box to the user.
        
        Args:
            parent: Parent widget for the message box
            title (str): Title of the message box
            message (str): Message to display
            message_type (MessageType): Type of message
            details (str, optional): Detailed information to show
            
        Returns:
            QMessageBox.StandardButton: Button clicked by the user
        """
        # Log the message
        if message_type == MessageType.ERROR:
            logger.error(f"{title}: {message}")
            if details:
                logger.error(f"Details: {details}")
        elif message_type == MessageType.WARNING:
            logger.warning(f"{title}: {message}")
        else:
            logger.info(f"{title}: {message}")
        
        # Create message box
        msg_box = QMessageBox(parent)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        
        # Set icon based on message type
        if message_type == MessageType.ERROR:
            msg_box.setIcon(QMessageBox.Icon.Critical)
        elif message_type == MessageType.WARNING:
            msg_box.setIcon(QMessageBox.Icon.Warning)
        elif message_type == MessageType.SUCCESS:
            msg_box.setIcon(QMessageBox.Icon.Information)
        else:
            msg_box.setIcon(QMessageBox.Icon.Information)
        
        # Add details if provided
        if details:
            msg_box.setDetailedText(details)
        
        # Translate buttons if language manager is available
        if language_manager:
            ok_button = msg_box.button(QMessageBox.StandardButton.Ok)
            if ok_button:
                ok_button.setText(ErrorHandler.get_translation(language_manager, 'ok_button', 'OK'))
        
        # Show message box and return result
        return msg_box.exec()
    
    @staticmethod
    def show_status_message(status_bar, message, message_type=MessageType.INFO, timeout=5000, language_manager=None):
        """Show a message in the status bar with optional styling.
        
        Args:
            status_bar (QStatusBar): Status bar widget
            message (str): Message to display
            message_type (MessageType): Type of message
            timeout (int): Time in milliseconds before message is cleared
        """
        if not status_bar:
            logger.warning(f"Status bar not provided, cannot show message: {message}")
            return
        
        # Log the message
        if message_type == MessageType.ERROR:
            logger.error(message)
        elif message_type == MessageType.WARNING:
            logger.warning(message)
        else:
            logger.info(message)
        
        # Set message style based on type
        if message_type == MessageType.ERROR:
            status_bar.setStyleSheet("background-color: #ffdddd; color: #990000;")
        elif message_type == MessageType.WARNING:
            status_bar.setStyleSheet("background-color: #ffffdd; color: #999900;")
        elif message_type == MessageType.SUCCESS:
            status_bar.setStyleSheet("background-color: #ddffdd; color: #009900;")
        else:
            status_bar.setStyleSheet("")
        
        # Show message
        status_bar.showMessage(message)
        
        # Set timeout if specified
        if timeout > 0:
            QTimer.singleShot(timeout, lambda: ErrorHandler.clear_status(status_bar))
    
    @staticmethod
    def clear_status(status_bar):
        """Clear the status bar message and reset styling.
        
        Args:
            status_bar (QStatusBar): Status bar widget
        """
        if status_bar:
            status_bar.setStyleSheet("")
            status_bar.clearMessage()
    
    @staticmethod
    def handle_exception(parent, exception, operation_name, status_bar=None, show_message_box=True, language_manager=None):
        """Handle an exception and provide appropriate feedback.
        
        Args:
            parent: Parent widget for message boxes
            exception (Exception): The exception to handle
            operation_name (str): Name of the operation that failed
            status_bar (QStatusBar, optional): Status bar for displaying messages
            show_message_box (bool): Whether to show a message box
            
        Returns:
            str: Error message generated for the exception
        """
        # Get exception details
        if language_manager:
            error_message = ErrorHandler.get_translation(
                language_manager,
                'error_during_operation',
                f"Error during {operation_name}: {str(exception)}"
            ).format(operation=operation_name, error=str(exception))
        else:
            error_message = f"Error during {operation_name}: {str(exception)}"
        error_details = traceback.format_exc()
        
        # Log the error
        logger.error(error_message)
        logger.error(f"Exception details: {error_details}")
        
        # Show status message if status bar provided
        if status_bar:
            ErrorHandler.show_status_message(status_bar, error_message, MessageType.ERROR, 5000, language_manager)
        
        # Show message box if requested
        if show_message_box and parent:
            # Get translated title
            if language_manager:
                title = ErrorHandler.get_translation(
                    language_manager,
                    'operation_failed',
                    f"{operation_name} Failed"
                ).format(operation=operation_name)
            else:
                title = f"{operation_name} Failed"
                
            ErrorHandler.show_message_box(
                parent,
                title,
                error_message,
                MessageType.ERROR,
                error_details,
                language_manager
            )
        
        return error_message
    
    @staticmethod
    def confirm_action(parent, title, message, details=None, language_manager=None):
        """Ask the user to confirm an action.
        
        Args:
            parent: Parent widget for the confirmation dialog
            title (str): Title of the confirmation dialog
            message (str): Message to display
            details (str, optional): Detailed information
            
        Returns:
            bool: True if the user confirmed, False otherwise
        """
        # Create confirmation dialog
        msg_box = QMessageBox(parent)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.setIcon(QMessageBox.Icon.Question)
        msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg_box.setDefaultButton(QMessageBox.StandardButton.No)
        
        # Translate buttons if language manager is available
        if language_manager:
            yes_button = msg_box.button(QMessageBox.StandardButton.Yes)
            no_button = msg_box.button(QMessageBox.StandardButton.No)
            if yes_button:
                yes_button.setText(ErrorHandler.get_translation(language_manager, 'yes_button', 'Yes'))
            if no_button:
                no_button.setText(ErrorHandler.get_translation(language_manager, 'no_button', 'No'))
        
        # Add details if provided
        if details:
            msg_box.setDetailedText(details)
        
        # Show dialog and return result
        return msg_box.exec() == QMessageBox.StandardButton.Yes
