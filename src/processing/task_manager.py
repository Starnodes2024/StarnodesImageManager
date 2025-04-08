#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Task manager for StarImageBrowse
Provides high-level utilities for managing parallel processing tasks.
"""

import os
import time
import uuid
import logging
from typing import Dict, List, Tuple, Optional, Union, Any, Callable
from PyQt6.QtCore import QObject, pyqtSignal, QTimer

from src.processing.parallel_pipeline import get_pipeline, ParallelPipeline
from src.memory.memory_utils import get_image_processor, is_memory_pool_enabled
from src.memory.image_processor_integration import process_image_for_ai, batch_process_images_for_ai

logger = logging.getLogger("StarImageBrowse.processing.task_manager")

class TaskProgress(QObject):
    """Signal emitter for task progress updates."""
    
    # Signals
    task_started = pyqtSignal(str, str)  # task_id, task_type
    task_progress = pyqtSignal(str, int, int, str)  # task_id, current, total, message
    task_completed = pyqtSignal(str, object)  # task_id, result
    task_failed = pyqtSignal(str, str)  # task_id, error
    all_tasks_completed = pyqtSignal()
    

class TaskManager(QObject):
    """Manages and monitors parallel processing tasks."""
    
    def __init__(self, config_manager=None):
        """Initialize the task manager.
        
        Args:
            config_manager: Configuration manager instance
        """
        super().__init__()
        
        self.config_manager = config_manager
        self.pipeline = get_pipeline("main", config_manager)
        self.task_groups = {}  # Map of group_id -> list of task_ids
        self.progress_signals = TaskProgress()
        
        # Start progress monitoring timer
        self.monitor_timer = QTimer(self)
        self.monitor_timer.timeout.connect(self._monitor_progress)
        self.monitor_timer.start(500)  # Check progress every 500ms
        
        # Initialize pipeline
        self._init_pipeline()
        
        logger.info("Task manager initialized")
    
    def _init_pipeline(self):
        """Initialize the processing pipeline."""
        # Create stages
        self.pipeline.add_stage("preprocessing", use_processes=False)
        self.pipeline.add_stage("main_processing", use_processes=True)
        self.pipeline.add_stage("postprocessing", use_processes=False)
        
        # Start pipeline
        self.pipeline.start()
    
    def _monitor_progress(self):
        """Monitor task progress."""
        # Check group completion
        empty_groups = []
        
        for group_id, task_ids in self.task_groups.items():
            all_completed = True
            for task_id in task_ids:
                # Check if task is still in progress
                result, error = self.pipeline.get_task_result("main_processing", task_id, timeout=0)
                if result is None and error is None:
                    all_completed = False
                    break
            
            if all_completed:
                # Emit group completion signal
                self.progress_signals.all_tasks_completed.emit()
                empty_groups.append(group_id)
        
        # Remove completed groups
        for group_id in empty_groups:
            self.task_groups.pop(group_id, None)
    
    def process_image_batch(self, images: List[Dict], operation: str, 
                           custom_processor: Optional[Callable] = None) -> str:
        """Process a batch of images.
        
        Args:
            images (list): List of image dictionaries (must have 'path' key)
            operation (str): Operation type (e.g., 'ai_description', 'thumbnail', 'resize')
            custom_processor (callable): Optional custom processing function
            
        Returns:
            str: Group ID for tracking the batch
        """
        group_id = str(uuid.uuid4())
        self.task_groups[group_id] = []
        
        # Generate task processor based on operation
        if operation == "ai_description" and not custom_processor:
            from src.ai.ai_image_processor import AIImageProcessor
            
            # Create AIImageProcessor
            ai_processor = AIImageProcessor(self.config_manager)
            
            def process_image(image_data):
                # Process image for AI
                image_path = image_data['path']
                
                # Use optimized image processing if available
                if is_memory_pool_enabled():
                    # Get pre-processed image
                    processed_path = process_image_for_ai(image_path)
                    if processed_path:
                        image_path = processed_path
                
                # Generate description
                description = ai_processor.generate_description(image_path)
                
                # Return result
                return {
                    'image_id': image_data.get('id'),
                    'path': image_data['path'],
                    'description': description
                }
            
            processor_fn = process_image
        
        elif operation == "thumbnail" and not custom_processor:
            def process_thumbnail(image_data):
                # Get image processor
                image_processor = get_image_processor()
                
                # Create thumbnail
                thumbnail = image_processor.create_thumbnail(image_data['path'])
                
                # Return result
                return {
                    'image_id': image_data.get('id'),
                    'path': image_data['path'],
                    'thumbnail': thumbnail
                }
            
            processor_fn = process_thumbnail
        
        elif custom_processor:
            processor_fn = custom_processor
        
        else:
            logger.error(f"Unsupported operation: {operation}")
            return group_id
        
        # Add tasks to pipeline
        for i, image_data in enumerate(images):
            # Create task ID
            task_id = f"{group_id}_{i}"
            
            # Add task to pipeline
            self.pipeline.add_task(
                "main_processing",
                task_id,
                image_data,
                processor_fn,
                priority=0,
                on_complete=self._on_task_complete
            )
            
            # Add to group
            self.task_groups[group_id].append(task_id)
            
            # Emit started signal
            self.progress_signals.task_started.emit(task_id, operation)
            
            # Emit initial progress
            self.progress_signals.task_progress.emit(
                task_id,
                0,
                100,
                f"Starting {operation} for {os.path.basename(image_data['path'])}"
            )
        
        return group_id
    
    def process_batch_ai_descriptions(self, images: List[Dict]) -> str:
        """Process AI descriptions for a batch of images.
        
        Args:
            images (list): List of image dictionaries (must have 'path' key)
            
        Returns:
            str: Group ID for tracking the batch
        """
        return self.process_image_batch(images, "ai_description")
    
    def process_batch_thumbnails(self, images: List[Dict]) -> str:
        """Process thumbnails for a batch of images.
        
        Args:
            images (list): List of image dictionaries (must have 'path' key)
            
        Returns:
            str: Group ID for tracking the batch
        """
        return self.process_image_batch(images, "thumbnail")
    
    def _on_task_complete(self, task_id: str, result: Any, error: Optional[str]):
        """Handle task completion."""
        if error:
            # Emit failure signal
            self.progress_signals.task_failed.emit(task_id, error)
            logger.error(f"Task {task_id} failed: {error}")
        else:
            # Emit completion signal
            self.progress_signals.task_completed.emit(task_id, result)
            logger.debug(f"Task {task_id} completed")
    
    def cancel_group(self, group_id: str):
        """Cancel all tasks in a group.
        
        Args:
            group_id (str): Group ID
        """
        if group_id in self.task_groups:
            # Remove from tracking
            self.task_groups.pop(group_id, None)
            logger.info(f"Cancelled task group {group_id}")
    
    def cancel_all_tasks(self):
        """Cancel all tasks."""
        # Clear tracking
        self.task_groups.clear()
        
        # Stop and restart pipeline
        self.pipeline.stop()
        self.pipeline.start()
        
        logger.info("Cancelled all tasks")
    
    def get_task_group_progress(self, group_id: str) -> Dict[str, Any]:
        """Get progress information for a task group.
        
        Args:
            group_id (str): Group ID
            
        Returns:
            dict: Progress information
        """
        if group_id not in self.task_groups:
            return {"error": f"Group {group_id} not found"}
        
        # Get task IDs for this group
        task_ids = self.task_groups[group_id]
        
        # Check task completion
        completed = 0
        failed = 0
        results = []
        errors = []
        
        for task_id in task_ids:
            result, error = self.pipeline.get_task_result("main_processing", task_id, timeout=0)
            if result is not None:
                completed += 1
                results.append(result)
            elif error is not None:
                failed += 1
                errors.append(error)
        
        # Calculate progress
        total = len(task_ids)
        progress_percent = (completed + failed) / total * 100 if total > 0 else 0
        
        return {
            "group_id": group_id,
            "total_tasks": total,
            "completed_tasks": completed,
            "failed_tasks": failed,
            "progress_percent": progress_percent,
            "results": results,
            "errors": errors
        }
    
    def get_all_progress(self) -> Dict[str, Any]:
        """Get progress information for all tasks.
        
        Returns:
            dict: Progress information
        """
        # Get pipeline stats
        pipeline_stats = self.pipeline.get_pipeline_stats()
        
        # Get progress for all groups
        group_progress = {}
        for group_id in self.task_groups:
            group_progress[group_id] = self.get_task_group_progress(group_id)
        
        return {
            "pipeline_stats": pipeline_stats,
            "group_progress": group_progress
        }
    
    def shutdown(self):
        """Shutdown the task manager."""
        # Stop timer
        self.monitor_timer.stop()
        
        # Stop pipeline
        self.pipeline.stop()
        
        logger.info("Task manager shut down")


# Global instance
_task_manager = None

def get_task_manager(config_manager=None) -> TaskManager:
    """Get the global task manager instance.
    
    Args:
        config_manager: Configuration manager instance
        
    Returns:
        TaskManager: Task manager instance
    """
    global _task_manager
    
    if _task_manager is None:
        _task_manager = TaskManager(config_manager)
    
    return _task_manager
