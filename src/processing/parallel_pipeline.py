#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Parallel processing pipeline for StarImageBrowse
Enables efficient distribution of processing tasks across multiple CPU cores.
"""

import os
import time
import queue
import logging
import threading
import multiprocessing
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from typing import Dict, List, Tuple, Optional, Union, Any, Callable, TypeVar, Generic

# For type hints
T = TypeVar('T')
U = TypeVar('U')

logger = logging.getLogger("StarImageBrowse.processing.parallel_pipeline")

class TaskItem(Generic[T, U]):
    """Represents a task to be processed in the pipeline."""
    
    def __init__(self, task_id: str, input_data: T, processor_fn: Callable[[T], U], priority: int = 0):
        """Initialize a task item.
        
        Args:
            task_id (str): Unique identifier for the task
            input_data (T): Input data for the task
            processor_fn (callable): Function to process the input data
            priority (int): Task priority (higher values = higher priority)
        """
        self.task_id = task_id
        self.input_data = input_data
        self.processor_fn = processor_fn
        self.priority = priority
        self.creation_time = time.time()
        self.start_time = None
        self.end_time = None
        self.result = None
        self.error = None
        self.status = "pending"  # pending, running, completed, failed
    
    def __lt__(self, other):
        """Compare tasks for priority queue ordering.
        
        Higher priority tasks come first, then older tasks.
        """
        if self.priority != other.priority:
            return self.priority > other.priority
        return self.creation_time < other.creation_time
    
    def execute(self) -> U:
        """Execute the task processor function.
        
        Returns:
            The result of processing
        """
        try:
            self.start_time = time.time()
            self.status = "running"
            self.result = self.processor_fn(self.input_data)
            self.status = "completed"
            return self.result
        except Exception as e:
            self.status = "failed"
            self.error = str(e)
            logger.error(f"Task {self.task_id} failed: {e}")
            raise
        finally:
            self.end_time = time.time()
    
    def get_execution_time(self) -> float:
        """Get the task execution time in seconds.
        
        Returns:
            float: Execution time or -1 if not completed
        """
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return -1
    
    def get_wait_time(self) -> float:
        """Get the task wait time in seconds.
        
        Returns:
            float: Wait time or -1 if not started
        """
        if self.start_time:
            return self.start_time - self.creation_time
        return time.time() - self.creation_time


class PipelineStage:
    """Represents a stage in the processing pipeline."""
    
    def __init__(self, name: str, max_workers: int = None, use_processes: bool = False):
        """Initialize a pipeline stage.
        
        Args:
            name (str): Stage name
            max_workers (int): Maximum number of worker threads/processes
            use_processes (bool): Whether to use processes instead of threads
        """
        self.name = name
        self.max_workers = max_workers
        self.use_processes = use_processes
        self.input_queue = queue.PriorityQueue()
        self.output_queue = queue.Queue()
        self.executor = None
        self.futures = {}
        self.running = False
        self.worker_thread = None
        self.task_count = 0
        self.completed_count = 0
        self.failed_count = 0
        
        # Optional callbacks
        self.on_task_completed = None
        self.on_task_failed = None
        self.on_stage_completed = None
    
    def start(self):
        """Start the pipeline stage."""
        if self.running:
            return
        
        self.running = True
        
        # Create executor based on configuration
        if self.use_processes:
            # ProcessPoolExecutor for CPU-bound tasks
            self.executor = ProcessPoolExecutor(max_workers=self.max_workers)
        else:
            # ThreadPoolExecutor for I/O-bound tasks
            self.executor = ThreadPoolExecutor(max_workers=self.max_workers)
        
        # Start worker thread
        self.worker_thread = threading.Thread(
            target=self._worker_loop,
            name=f"PipelineStage-{self.name}"
        )
        self.worker_thread.daemon = True
        self.worker_thread.start()
        
        logger.info(f"Started pipeline stage: {self.name}, workers: {self.max_workers}, "
                   f"mode: {'processes' if self.use_processes else 'threads'}")
    
    def stop(self):
        """Stop the pipeline stage."""
        if not self.running:
            return
        
        self.running = False
        
        # Close executor
        if self.executor:
            self.executor.shutdown(wait=False)
            self.executor = None
        
        # Clear queues
        while not self.input_queue.empty():
            try:
                self.input_queue.get_nowait()
                self.input_queue.task_done()
            except queue.Empty:
                break
        
        # Wait for worker thread to finish
        if self.worker_thread and self.worker_thread.is_alive():
            self.worker_thread.join(timeout=1.0)
        
        logger.info(f"Stopped pipeline stage: {self.name}")
    
    def add_task(self, task: TaskItem):
        """Add a task to the pipeline stage.
        
        Args:
            task (TaskItem): Task to add
        """
        self.input_queue.put(task)
        self.task_count += 1
        logger.debug(f"Added task {task.task_id} to stage {self.name}")
    
    def _worker_loop(self):
        """Worker thread that submits tasks to the executor."""
        while self.running:
            try:
                # Get next task from input queue
                try:
                    task = self.input_queue.get(timeout=0.5)
                except queue.Empty:
                    continue
                
                # Skip task if shutting down
                if not self.running:
                    self.input_queue.task_done()
                    continue
                
                # Submit task to executor
                future = self.executor.submit(task.execute)
                self.futures[future] = task
                
                # Add callback to handle task completion
                future.add_done_callback(self._task_completed)
                
                # Mark task as processed in input queue
                self.input_queue.task_done()
                
            except Exception as e:
                logger.error(f"Error in pipeline stage {self.name}: {e}")
    
    def _task_completed(self, future):
        """Handle completed task."""
        task = self.futures.pop(future, None)
        if not task:
            return
        
        try:
            # Get result or exception
            result = future.result()
            
            # Update task
            task.result = result
            task.status = "completed"
            self.completed_count += 1
            
            # Add to output queue
            self.output_queue.put(task)
            
            # Call completion callback if present
            if self.on_task_completed:
                try:
                    self.on_task_completed(task)
                except Exception as e:
                    logger.error(f"Error in task completion callback: {e}")
            
            logger.debug(f"Task {task.task_id} completed in {task.get_execution_time():.2f}s")
            
        except Exception as e:
            # Update task
            task.error = str(e)
            task.status = "failed"
            self.failed_count += 1
            
            # Add to output queue
            self.output_queue.put(task)
            
            # Call failure callback if present
            if self.on_task_failed:
                try:
                    self.on_task_failed(task)
                except Exception as e:
                    logger.error(f"Error in task failure callback: {e}")
            
            logger.error(f"Task {task.task_id} failed: {e}")
        
        # Check if all tasks are completed
        if (self.completed_count + self.failed_count) == self.task_count and self.on_stage_completed:
            try:
                self.on_stage_completed()
            except Exception as e:
                logger.error(f"Error in stage completion callback: {e}")
    
    def is_idle(self) -> bool:
        """Check if the pipeline stage is idle.
        
        Returns:
            bool: True if idle (no pending or running tasks)
        """
        return self.input_queue.empty() and len(self.futures) == 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics for the pipeline stage.
        
        Returns:
            dict: Statistics dictionary
        """
        return {
            "name": self.name,
            "total_tasks": self.task_count,
            "completed_tasks": self.completed_count,
            "failed_tasks": self.failed_count,
            "pending_tasks": self.input_queue.qsize(),
            "running_tasks": len(self.futures),
            "use_processes": self.use_processes,
            "max_workers": self.max_workers
        }


class ParallelPipeline:
    """Processing pipeline that executes tasks in parallel."""
    
    def __init__(self, name: str, config_manager=None):
        """Initialize the parallel pipeline.
        
        Args:
            name (str): Pipeline name
            config_manager: Configuration manager instance
        """
        self.name = name
        self.config_manager = config_manager
        self.stages = {}
        self.running = False
        self.lock = threading.RLock()
        self.completion_callbacks = {}
        
        # Configure default num_workers based on system
        self.num_workers = min(os.cpu_count() or 4, 8)
        
        # Load configuration if available
        if config_manager:
            self.num_workers = config_manager.get(
                "processing", "num_workers", self.num_workers
            )
    
    def add_stage(self, name: str, max_workers: Optional[int] = None, use_processes: bool = False) -> PipelineStage:
        """Add a processing stage to the pipeline.
        
        Args:
            name (str): Stage name
            max_workers (int): Maximum number of worker threads/processes
            use_processes (bool): Whether to use processes instead of threads
            
        Returns:
            PipelineStage: The created stage
        """
        with self.lock:
            if name in self.stages:
                logger.warning(f"Pipeline stage {name} already exists")
                return self.stages[name]
            
            # Use default num_workers if not specified
            if max_workers is None:
                max_workers = self.num_workers
            
            # Create stage
            stage = PipelineStage(name, max_workers, use_processes)
            self.stages[name] = stage
            
            # Start stage if pipeline is running
            if self.running:
                stage.start()
            
            logger.info(f"Added pipeline stage: {name}")
            return stage
    
    def start(self):
        """Start the pipeline."""
        with self.lock:
            if self.running:
                return
            
            self.running = True
            
            # Start all stages
            for stage in self.stages.values():
                stage.start()
            
            logger.info(f"Started pipeline: {self.name}")
    
    def stop(self):
        """Stop the pipeline."""
        with self.lock:
            if not self.running:
                return
            
            self.running = False
            
            # Stop all stages
            for stage in self.stages.values():
                stage.stop()
            
            logger.info(f"Stopped pipeline: {self.name}")
    
    def add_task(self, stage_name: str, task_id: str, input_data: Any, processor_fn: Callable, 
                priority: int = 0, on_complete: Optional[Callable] = None) -> str:
        """Add a task to a pipeline stage.
        
        Args:
            stage_name (str): Name of the pipeline stage
            task_id (str): Unique identifier for the task
            input_data: Input data for the task
            processor_fn (callable): Function to process the input data
            priority (int): Task priority (higher values = higher priority)
            on_complete (callable): Callback for task completion
            
        Returns:
            str: Task ID
        """
        with self.lock:
            # Ensure pipeline is running
            if not self.running:
                self.start()
            
            # Get or create stage
            stage = self.stages.get(stage_name)
            if not stage:
                logger.warning(f"Pipeline stage {stage_name} not found, creating it")
                stage = self.add_stage(stage_name)
            
            # Create task
            task = TaskItem(task_id, input_data, processor_fn, priority)
            
            # Store completion callback
            if on_complete:
                self.completion_callbacks[task_id] = on_complete
                
                # Set task completion callback for stage if not already set
                if not stage.on_task_completed:
                    stage.on_task_completed = self._handle_task_completed
            
            # Add task to stage
            stage.add_task(task)
            
            return task_id
    
    def _handle_task_completed(self, task: TaskItem):
        """Handle task completion."""
        # Call task-specific completion callback
        callback = self.completion_callbacks.pop(task.task_id, None)
        if callback:
            try:
                callback(task.task_id, task.result, task.error)
            except Exception as e:
                logger.error(f"Error in task completion callback: {e}")
    
    def get_task_result(self, stage_name: str, task_id: str, timeout: Optional[float] = None) -> Tuple[Any, str]:
        """Get the result of a task.
        
        Args:
            stage_name (str): Name of the pipeline stage
            task_id (str): Task ID
            timeout (float): Maximum time to wait
            
        Returns:
            tuple: (result, error) - error is None if successful
        """
        stage = self.stages.get(stage_name)
        if not stage:
            return None, f"Stage {stage_name} not found"
        
        # Search output queue
        start_time = time.time()
        while timeout is None or (time.time() - start_time) < timeout:
            # Check all completed tasks
            try:
                # Get all tasks from output queue
                all_tasks = []
                while not stage.output_queue.empty():
                    task = stage.output_queue.get_nowait()
                    if task.task_id == task_id:
                        # Return task result
                        return task.result, task.error
                    all_tasks.append(task)
                
                # Put tasks back into queue
                for task in all_tasks:
                    stage.output_queue.put(task)
                
                # Wait a bit before trying again
                time.sleep(0.1)
                
            except queue.Empty:
                time.sleep(0.1)
                continue
        
        return None, "Timeout waiting for task result"
    
    def get_stage_stats(self, stage_name: str) -> Dict[str, Any]:
        """Get statistics for a pipeline stage.
        
        Args:
            stage_name (str): Name of the pipeline stage
            
        Returns:
            dict: Statistics dictionary
        """
        stage = self.stages.get(stage_name)
        if not stage:
            return {"error": f"Stage {stage_name} not found"}
        
        return stage.get_stats()
    
    def get_pipeline_stats(self) -> Dict[str, Any]:
        """Get statistics for the entire pipeline.
        
        Returns:
            dict: Statistics dictionary
        """
        stats = {
            "name": self.name,
            "running": self.running,
            "num_stages": len(self.stages),
            "stages": {}
        }
        
        # Get stats for each stage
        for name, stage in self.stages.items():
            stats["stages"][name] = stage.get_stats()
        
        # Calculate totals
        total_tasks = 0
        completed_tasks = 0
        failed_tasks = 0
        pending_tasks = 0
        running_tasks = 0
        
        for stage_stats in stats["stages"].values():
            total_tasks += stage_stats["total_tasks"]
            completed_tasks += stage_stats["completed_tasks"]
            failed_tasks += stage_stats["failed_tasks"]
            pending_tasks += stage_stats["pending_tasks"]
            running_tasks += stage_stats["running_tasks"]
        
        stats["total_tasks"] = total_tasks
        stats["completed_tasks"] = completed_tasks
        stats["failed_tasks"] = failed_tasks
        stats["pending_tasks"] = pending_tasks
        stats["running_tasks"] = running_tasks
        stats["progress_percent"] = (
            (completed_tasks + failed_tasks) / total_tasks * 100 
            if total_tasks > 0 else 0
        )
        
        return stats
    
    def wait_for_stage_completion(self, stage_name: str, timeout: Optional[float] = None) -> bool:
        """Wait for all tasks in a stage to complete.
        
        Args:
            stage_name (str): Name of the pipeline stage
            timeout (float): Maximum time to wait
            
        Returns:
            bool: True if all tasks completed
        """
        stage = self.stages.get(stage_name)
        if not stage:
            logger.error(f"Stage {stage_name} not found")
            return False
        
        # Wait for stage to become idle
        start_time = time.time()
        while timeout is None or (time.time() - start_time) < timeout:
            if stage.is_idle():
                return True
            time.sleep(0.1)
        
        return False
    
    def wait_for_pipeline_completion(self, timeout: Optional[float] = None) -> bool:
        """Wait for all tasks in the pipeline to complete.
        
        Args:
            timeout (float): Maximum time to wait
            
        Returns:
            bool: True if all tasks completed
        """
        # Wait for all stages to become idle
        start_time = time.time()
        while timeout is None or (time.time() - start_time) < timeout:
            all_idle = True
            for stage in self.stages.values():
                if not stage.is_idle():
                    all_idle = False
                    break
            
            if all_idle:
                return True
            
            time.sleep(0.1)
        
        return False
    
    def __del__(self):
        """Clean up resources."""
        self.stop()


# Global instance of the parallel pipeline
_pipeline_instances = {}

def get_pipeline(name: str = "default", config_manager=None) -> ParallelPipeline:
    """Get or create a parallel pipeline.
    
    Args:
        name (str): Pipeline name
        config_manager: Configuration manager instance
        
    Returns:
        ParallelPipeline: Pipeline instance
    """
    if name not in _pipeline_instances:
        _pipeline_instances[name] = ParallelPipeline(name, config_manager)
    
    return _pipeline_instances[name]

def cleanup_pipelines():
    """Stop and clean up all pipeline instances."""
    for pipeline in _pipeline_instances.values():
        pipeline.stop()
    
    _pipeline_instances.clear()
