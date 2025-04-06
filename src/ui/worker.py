#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Worker thread implementation for StarImageBrowse
Handles background processing for long-running operations.
"""

import logging
import traceback
import sys
from PyQt6.QtCore import QObject, QRunnable, pyqtSignal, pyqtSlot

logger = logging.getLogger("StarImageBrowse.ui.worker")

class WorkerSignals(QObject):
    """Defines the signals available from a running worker thread."""
    started = pyqtSignal()
    finished = pyqtSignal()
    error = pyqtSignal(tuple)
    result = pyqtSignal(object)
    progress = pyqtSignal(int, int)  # Current, total


class Worker(QRunnable):
    """Worker thread for handling background tasks."""
    
    def __init__(self, fn, *args, **kwargs):
        """Initialize the worker thread.
        
        Args:
            fn (callable): The function to run on this worker thread
            *args: Arguments to pass to the function
            **kwargs: Keywords to pass to the function
        """
        super().__init__()
        
        # Store constructor arguments (re-used for processing)
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()
        
        # Add the signals to the kwargs if needed
        # Handle both 'progress_callback' and 'callback' parameter names for better compatibility
        if 'progress_callback' not in kwargs and 'callback' not in kwargs:
            self.kwargs['progress_callback'] = self.signals.progress
        elif 'callback' in kwargs and 'progress_callback' not in kwargs:
            # If only callback is provided, also add it as progress_callback for functions that expect that name
            self.kwargs['progress_callback'] = kwargs['callback']
    
    @pyqtSlot()
    def run(self):
        """Execute the function with the provided arguments."""
        # Emit started signal
        self.signals.started.emit()
        
        try:
            # Execute the function
            result = self.fn(*self.args, **self.kwargs)
        except Exception as e:
            # Emit error signal with detailed exception information
            exc_type, exc_value, exc_traceback = sys.exc_info()
            error_info = (
                str(e),
                traceback.format_exc()
            )
            self.signals.error.emit(error_info)
            logger.error(f"Error in worker thread: {error_info[1]}")
        else:
            # Emit result signal
            self.signals.result.emit(result)
        finally:
            # Emit finished signal
            self.signals.finished.emit()


class BackgroundTaskManager:
    """Manages background tasks using a thread pool."""
    
    def __init__(self, thread_pool):
        """Initialize the background task manager.
        
        Args:
            thread_pool (QThreadPool): Thread pool to use for tasks
        """
        self.thread_pool = thread_pool
        self.active_tasks = {}
        
    def start_task(self, task_id, fn, *args, **kwargs):
        """Start a new background task.
        
        Args:
            task_id (str): Unique identifier for the task
            fn (callable): The function to run as a task
            *args: Arguments to pass to the function
            **kwargs: Keywords to pass to the function
            
        Returns:
            bool: True if task was started, False if task_id already exists
        """
        if task_id in self.active_tasks:
            logger.warning(f"Task ID {task_id} is already active")
            return False
        
        # Extract callback handlers from kwargs to avoid passing them to the function
        signal_handlers = {}
        signal_keys = ['on_started', 'on_finished', 'on_error', 'on_result', 'on_progress']
        
        for key in signal_keys:
            if key in kwargs:
                signal_handlers[key] = kwargs.pop(key)
        
        # Standardize callback parameter naming
        # If 'callback' is provided, add it as progress_callback too (without removing the original)
        # This ensures both parameter names work without unexpected side effects
        if 'callback' in kwargs and 'progress_callback' not in kwargs:
            kwargs['progress_callback'] = kwargs['callback']
        
        # Create worker
        worker = Worker(fn, *args, **kwargs)
        
        # Connect signals if handlers are provided
        if 'on_started' in signal_handlers:
            worker.signals.started.connect(signal_handlers['on_started'])
        
        # Always connect finished signal to auto-cleanup
        def cleanup_task():
            self.remove_task(task_id)
            logger.debug(f"Auto-cleaned up task: {task_id}")
            
        # Connect user's finished handler if provided
        if 'on_finished' in signal_handlers:
            # Connect both the user's handler and our cleanup handler
            worker.signals.finished.connect(signal_handlers['on_finished'])
            worker.signals.finished.connect(cleanup_task)
        else:
            # Just connect our cleanup handler
            worker.signals.finished.connect(cleanup_task)
        
        if 'on_error' in signal_handlers:
            worker.signals.error.connect(signal_handlers['on_error'])
        
        if 'on_result' in signal_handlers:
            worker.signals.result.connect(signal_handlers['on_result'])
        
        if 'on_progress' in signal_handlers:
            worker.signals.progress.connect(signal_handlers['on_progress'])
        
        # Store worker reference
        self.active_tasks[task_id] = worker
        
        # Start worker
        self.thread_pool.start(worker)
        logger.debug(f"Started background task: {task_id}")
        
        return True
    
    def is_task_active(self, task_id):
        """Check if a task is active.
        
        Args:
            task_id (str): Unique identifier for the task
            
        Returns:
            bool: True if task is active, False otherwise
        """
        return task_id in self.active_tasks
    
    def remove_task(self, task_id):
        """Remove a completed task.
        
        Args:
            task_id (str): Unique identifier for the task
            
        Returns:
            bool: True if task was removed, False if task_id doesn't exist
        """
        if task_id in self.active_tasks:
            del self.active_tasks[task_id]
            logger.debug(f"Removed background task: {task_id}")
            return True
        return False
