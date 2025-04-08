#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Batch operations for StarImageBrowse
Provides high-level utilities for performing batch operations on images.
"""

import os
import time
import logging
from typing import Dict, List, Tuple, Optional, Union, Any, Callable
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QMessageBox

from src.processing.task_manager import get_task_manager, TaskProgress
from src.ui.progress_dialog import ProgressDialog

logger = logging.getLogger("StarImageBrowse.processing.batch_operations")

class BatchOperationSignals(QObject):
    """Signals for batch operations."""
    
    # Signals
    operation_started = pyqtSignal(str)  # operation_id
    operation_progress = pyqtSignal(str, int, int, str)  # operation_id, current, total, message
    operation_completed = pyqtSignal(str, dict)  # operation_id, results
    operation_failed = pyqtSignal(str, str)  # operation_id, error
    operation_cancelled = pyqtSignal(str)  # operation_id


class BatchOperations:
    """
    Batch operations manager for StarImageBrowse.
    Performs operations on multiple images using the parallel processing pipeline.
    """
    
    def __init__(self, config_manager=None, db_manager=None):
        """Initialize the batch operations manager.
        
        Args:
            config_manager: Configuration manager instance
            db_manager: Database manager instance
        """
        self.config_manager = config_manager
        self.db_manager = db_manager
        self.signals = BatchOperationSignals()
        
        # Get task manager
        self.task_manager = get_task_manager(config_manager)
        
        # Connect task manager signals
        self._connect_signals()
        
        # Operation tracking
        self.active_operations = {}  # operation_id -> {progress_dialog, group_id, etc.}
        
        logger.info("Batch operations manager initialized")
    
    def _connect_signals(self):
        """Connect task manager signals."""
        # Get progress signals
        progress_signals = self.task_manager.progress_signals
        
        # Connect signals
        progress_signals.task_progress.connect(self._on_task_progress)
        progress_signals.task_completed.connect(self._on_task_completed)
        progress_signals.task_failed.connect(self._on_task_failed)
        progress_signals.all_tasks_completed.connect(self._on_all_tasks_completed)
    
    def _on_task_progress(self, task_id, current, total, message):
        """Handle task progress updates."""
        # Find the operation for this task
        for operation_id, operation in self.active_operations.items():
            if operation.get('group_id') and task_id.startswith(operation['group_id']):
                # Update operation progress
                progress = operation.get('progress', {})
                progress[task_id] = (current, total, message)
                operation['progress'] = progress
                
                # Calculate overall progress
                self._update_operation_progress(operation_id)
                break
    
    def _on_task_completed(self, task_id, result):
        """Handle task completion."""
        # Find the operation for this task
        for operation_id, operation in self.active_operations.items():
            if operation.get('group_id') and task_id.startswith(operation['group_id']):
                # Update operation results
                results = operation.get('results', {})
                results[task_id] = result
                operation['results'] = results
                
                # Update operation progress
                self._update_operation_progress(operation_id)
                break
    
    def _on_task_failed(self, task_id, error):
        """Handle task failure."""
        # Find the operation for this task
        for operation_id, operation in self.active_operations.items():
            if operation.get('group_id') and task_id.startswith(operation['group_id']):
                # Update operation errors
                errors = operation.get('errors', {})
                errors[task_id] = error
                operation['errors'] = errors
                
                # Update operation progress
                self._update_operation_progress(operation_id)
                break
    
    def _on_all_tasks_completed(self):
        """Handle completion of all tasks in a group."""
        # Check which operations are complete
        completed_operations = []
        
        for operation_id, operation in self.active_operations.items():
            # Get progress from task manager
            group_id = operation.get('group_id')
            if group_id:
                progress = self.task_manager.get_task_group_progress(group_id)
                
                # Check if all tasks are complete
                total = progress.get('total_tasks', 0)
                completed = progress.get('completed_tasks', 0)
                failed = progress.get('failed_tasks', 0)
                
                if total > 0 and (completed + failed) == total:
                    # Operation is complete
                    self._complete_operation(operation_id, progress)
                    completed_operations.append(operation_id)
        
        # Remove completed operations
        for operation_id in completed_operations:
            self.active_operations.pop(operation_id, None)
    
    def _update_operation_progress(self, operation_id):
        """Update operation progress and UI."""
        operation = self.active_operations.get(operation_id)
        if not operation:
            return
        
        # Get progress dialog
        progress_dialog = operation.get('progress_dialog')
        if not progress_dialog:
            return
        
        # Get task group progress
        group_id = operation.get('group_id')
        if not group_id:
            return
        
        progress = self.task_manager.get_task_group_progress(group_id)
        
        # Update progress dialog
        total = progress.get('total_tasks', 0)
        completed = progress.get('completed_tasks', 0) + progress.get('failed_tasks', 0)
        percent = progress.get('progress_percent', 0)
        
        # Calculate message
        if progress.get('failed_tasks', 0) > 0:
            message = f"Processing {completed} of {total} images ({progress.get('failed_tasks', 0)} failed)"
        else:
            message = f"Processing {completed} of {total} images"
        
        # Update progress dialog
        progress_dialog.update_progress(completed, total)
        progress_dialog.update_operation(message)
        
        # Emit progress signal
        self.signals.operation_progress.emit(operation_id, completed, total, message)
    
    def _complete_operation(self, operation_id, progress):
        """Complete an operation and clean up."""
        operation = self.active_operations.get(operation_id)
        if not operation:
            return
        
        # Get progress dialog
        progress_dialog = operation.get('progress_dialog')
        
        # Get operation results
        results = operation.get('results', {})
        errors = operation.get('errors', {})
        
        # Create results object
        operation_results = {
            'operation_id': operation_id,
            'operation_type': operation.get('operation_type', ''),
            'total_tasks': progress.get('total_tasks', 0),
            'completed_tasks': progress.get('completed_tasks', 0),
            'failed_tasks': progress.get('failed_tasks', 0),
            'results': results,
            'errors': errors
        }
        
        # Call completion callback if provided
        callback = operation.get('on_complete')
        if callback:
            try:
                callback(operation_results)
            except Exception as e:
                logger.error(f"Error in operation completion callback: {e}")
        
        # Update database if needed
        if self.db_manager and operation.get('update_db', False):
            self._update_database(operation_results)
        
        # Close progress dialog if provided
        if progress_dialog:
            progress_dialog.close()
        
        # Emit completion signal
        if progress.get('failed_tasks', 0) > 0:
            # Some tasks failed
            error_msg = f"{progress.get('failed_tasks', 0)} of {progress.get('total_tasks', 0)} tasks failed"
            self.signals.operation_failed.emit(operation_id, error_msg)
        else:
            # All tasks completed successfully
            self.signals.operation_completed.emit(operation_id, operation_results)
    
    def _update_database(self, operation_results):
        """Update database with operation results."""
        operation_type = operation_results.get('operation_type', '')
        
        if operation_type == 'ai_description':
            # Update AI descriptions in database
            for task_id, result in operation_results.get('results', {}).items():
                if not result:
                    continue
                
                image_id = result.get('image_id')
                description = result.get('description')
                
                if image_id and description:
                    try:
                        # Update description in database
                        self.db_manager.update_image_description(image_id, description)
                        logger.debug(f"Updated description for image {image_id}")
                    except Exception as e:
                        logger.error(f"Error updating description for image {image_id}: {e}")
    
    def generate_descriptions(self, images: List[Dict], parent=None, show_progress=True,
                             on_complete=None) -> str:
        """Generate AI descriptions for a batch of images.
        
        Args:
            images (list): List of image dictionaries with 'id', 'path' keys
            parent: Parent widget for progress dialog
            show_progress (bool): Whether to show a progress dialog
            on_complete (callable): Function to call when operation completes
            
        Returns:
            str: Operation ID
        """
        # Create unique operation ID
        import uuid
        operation_id = f"desc_{str(uuid.uuid4())}"
        
        # Validate images
        if not images:
            logger.warning("No images provided for batch description generation")
            if on_complete:
                on_complete({
                    'operation_id': operation_id,
                    'operation_type': 'ai_description',
                    'total_tasks': 0,
                    'completed_tasks': 0,
                    'failed_tasks': 0,
                    'results': {},
                    'errors': {}
                })
            return operation_id
        
        # Create progress dialog if requested
        progress_dialog = None
        if show_progress and parent:
            progress_dialog = ProgressDialog(
                "Generating AI Descriptions",
                f"Processing {len(images)} images...",
                parent,
                cancellable=True
            )
            
            # Connect cancel button
            progress_dialog.cancelled.connect(lambda: self.cancel_operation(operation_id))
            
            # Show dialog
            progress_dialog.show()
        
        # Process batch
        group_id = self.task_manager.process_batch_ai_descriptions(images)
        
        # Store operation info
        self.active_operations[operation_id] = {
            'operation_type': 'ai_description',
            'group_id': group_id,
            'progress_dialog': progress_dialog,
            'start_time': time.time(),
            'images': images,
            'on_complete': on_complete,
            'update_db': True  # Update database with results
        }
        
        # Emit started signal
        self.signals.operation_started.emit(operation_id)
        
        # Initial progress update
        self.signals.operation_progress.emit(
            operation_id,
            0,
            len(images),
            f"Starting AI description generation for {len(images)} images"
        )
        
        return operation_id
    
    def process_thumbnails(self, images: List[Dict], parent=None, show_progress=True,
                          on_complete=None) -> str:
        """Process thumbnails for a batch of images.
        
        Args:
            images (list): List of image dictionaries with 'id', 'path' keys
            parent: Parent widget for progress dialog
            show_progress (bool): Whether to show a progress dialog
            on_complete (callable): Function to call when operation completes
            
        Returns:
            str: Operation ID
        """
        # Create unique operation ID
        import uuid
        operation_id = f"thumb_{str(uuid.uuid4())}"
        
        # Validate images
        if not images:
            logger.warning("No images provided for batch thumbnail processing")
            if on_complete:
                on_complete({
                    'operation_id': operation_id,
                    'operation_type': 'thumbnail',
                    'total_tasks': 0,
                    'completed_tasks': 0,
                    'failed_tasks': 0,
                    'results': {},
                    'errors': {}
                })
            return operation_id
        
        # Create progress dialog if requested
        progress_dialog = None
        if show_progress and parent:
            progress_dialog = ProgressDialog(
                "Processing Thumbnails",
                f"Processing {len(images)} images...",
                parent,
                cancellable=True
            )
            
            # Connect cancel button
            progress_dialog.cancelled.connect(lambda: self.cancel_operation(operation_id))
            
            # Show dialog
            progress_dialog.show()
        
        # Process batch
        group_id = self.task_manager.process_batch_thumbnails(images)
        
        # Store operation info
        self.active_operations[operation_id] = {
            'operation_type': 'thumbnail',
            'group_id': group_id,
            'progress_dialog': progress_dialog,
            'start_time': time.time(),
            'images': images,
            'on_complete': on_complete,
            'update_db': False  # No need to update database
        }
        
        # Emit started signal
        self.signals.operation_started.emit(operation_id)
        
        # Initial progress update
        self.signals.operation_progress.emit(
            operation_id,
            0,
            len(images),
            f"Starting thumbnail processing for {len(images)} images"
        )
        
        return operation_id
    
    def custom_batch_operation(self, images: List[Dict], operation_type: str, processor_fn: Callable,
                             parent=None, show_progress=True, on_complete=None,
                             update_db=False, title=None, message=None) -> str:
        """Run a custom batch operation on images.
        
        Args:
            images (list): List of image dictionaries
            operation_type (str): Type of operation
            processor_fn (callable): Function to process each image
            parent: Parent widget for progress dialog
            show_progress (bool): Whether to show a progress dialog
            on_complete (callable): Function to call when operation completes
            update_db (bool): Whether to update the database with results
            title (str): Progress dialog title
            message (str): Progress dialog message
            
        Returns:
            str: Operation ID
        """
        # Create unique operation ID
        import uuid
        operation_id = f"{operation_type}_{str(uuid.uuid4())}"
        
        # Validate images
        if not images:
            logger.warning(f"No images provided for batch {operation_type}")
            if on_complete:
                on_complete({
                    'operation_id': operation_id,
                    'operation_type': operation_type,
                    'total_tasks': 0,
                    'completed_tasks': 0,
                    'failed_tasks': 0,
                    'results': {},
                    'errors': {}
                })
            return operation_id
        
        # Create progress dialog if requested
        progress_dialog = None
        if show_progress and parent:
            progress_dialog = ProgressDialog(
                title or f"Batch {operation_type.capitalize()}",
                message or f"Processing {len(images)} images...",
                parent,
                cancellable=True
            )
            
            # Connect cancel button
            progress_dialog.cancelled.connect(lambda: self.cancel_operation(operation_id))
            
            # Show dialog
            progress_dialog.show()
        
        # Process batch
        group_id = self.task_manager.process_image_batch(images, operation_type, processor_fn)
        
        # Store operation info
        self.active_operations[operation_id] = {
            'operation_type': operation_type,
            'group_id': group_id,
            'progress_dialog': progress_dialog,
            'start_time': time.time(),
            'images': images,
            'on_complete': on_complete,
            'update_db': update_db
        }
        
        # Emit started signal
        self.signals.operation_started.emit(operation_id)
        
        # Initial progress update
        self.signals.operation_progress.emit(
            operation_id,
            0,
            len(images),
            f"Starting {operation_type} for {len(images)} images"
        )
        
        return operation_id
    
    def cancel_operation(self, operation_id: str):
        """Cancel a batch operation.
        
        Args:
            operation_id (str): Operation ID
        """
        operation = self.active_operations.get(operation_id)
        if not operation:
            logger.warning(f"Cannot cancel operation {operation_id}: not found")
            return
        
        # Cancel tasks
        group_id = operation.get('group_id')
        if group_id:
            self.task_manager.cancel_group(group_id)
        
        # Close progress dialog
        progress_dialog = operation.get('progress_dialog')
        if progress_dialog:
            progress_dialog.close()
        
        # Remove from active operations
        self.active_operations.pop(operation_id, None)
        
        # Emit cancelled signal
        self.signals.operation_cancelled.emit(operation_id)
        
        logger.info(f"Cancelled operation {operation_id}")
    
    def get_operation_progress(self, operation_id: str) -> Dict[str, Any]:
        """Get progress information for a batch operation.
        
        Args:
            operation_id (str): Operation ID
            
        Returns:
            dict: Progress information
        """
        operation = self.active_operations.get(operation_id)
        if not operation:
            return {"error": f"Operation {operation_id} not found"}
        
        # Get progress from task manager
        group_id = operation.get('group_id')
        if not group_id:
            return {"error": f"No group ID for operation {operation_id}"}
        
        # Get task group progress
        progress = self.task_manager.get_task_group_progress(group_id)
        
        # Add operation info
        progress['operation_id'] = operation_id
        progress['operation_type'] = operation.get('operation_type', '')
        progress['start_time'] = operation.get('start_time', 0)
        progress['elapsed_time'] = time.time() - operation.get('start_time', time.time())
        
        return progress
    
    def get_all_progress(self) -> Dict[str, Any]:
        """Get progress information for all batch operations.
        
        Returns:
            dict: Progress information for all operations
        """
        result = {}
        
        for operation_id in self.active_operations:
            result[operation_id] = self.get_operation_progress(operation_id)
        
        return result
    
    def shutdown(self):
        """Shutdown the batch operations manager."""
        # Cancel all active operations
        for operation_id in list(self.active_operations.keys()):
            self.cancel_operation(operation_id)
        
        logger.info("Batch operations manager shut down")


# Global instance
_batch_operations = None

def get_batch_operations(config_manager=None, db_manager=None) -> BatchOperations:
    """Get the global batch operations instance.
    
    Args:
        config_manager: Configuration manager instance
        db_manager: Database manager instance
        
    Returns:
        BatchOperations: Batch operations instance
    """
    global _batch_operations
    
    if _batch_operations is None:
        _batch_operations = BatchOperations(config_manager, db_manager)
    
    return _batch_operations
