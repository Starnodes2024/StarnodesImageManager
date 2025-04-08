#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Advanced optimization dialog for StarImageBrowse
Provides a UI for configuring and activating Phase 4 scaling solutions.
"""

import os
import logging
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QTextEdit, QMessageBox, QDialogButtonBox,
    QGroupBox, QCheckBox, QComboBox, QSpinBox, QFormLayout,
    QTabWidget
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize

from src.database.db_sharding import ShardManager, FolderBasedSharding, DateBasedSharding
from src.image_processing.format_optimizer import FormatOptimizer
from src.memory.resource_manager import ResourceManager
from src.optimize_phase4 import Phase4Optimizer

logger = logging.getLogger("StarImageBrowse.ui.advanced_optimization_dialog")

class ShardingMigrationThread(QThread):
    """Thread for migrating the database to a sharded structure."""
    
    progress_signal = pyqtSignal(int, int, str)  # current, total, message
    finished_signal = pyqtSignal(bool, dict)  # success, stats
    
    def __init__(self, db_manager, shard_manager):
        """Initialize the migration thread.
        
        Args:
            db_manager: Database manager instance
            shard_manager: Shard manager instance
        """
        super().__init__()
        self.db_manager = db_manager
        self.shard_manager = shard_manager
        
    def run(self):
        """Run the migration process."""
        try:
            # Report progress
            self.progress_signal.emit(0, 3, "Starting database sharding migration...")
            
            # Create a backup before migration
            self.progress_signal.emit(1, 3, "Creating database backup...")
            
            # Migrate to sharded structure
            self.progress_signal.emit(2, 3, "Migrating to sharded database structure...")
            success = self.shard_manager.migrate_to_sharding()
            
            if not success:
                self.finished_signal.emit(False, {"error": "Failed to migrate to sharded database structure"})
                return
            
            # Report success
            self.progress_signal.emit(3, 3, "Migration completed successfully")
            self.finished_signal.emit(True, {})
            
        except Exception as e:
            logger.error(f"Error during sharding migration: {e}")
            self.finished_signal.emit(False, {"error": str(e)})


class AdvancedOptimizationDialog(QDialog):
    """Dialog for configuring and activating Phase 4 scaling solutions."""
    
    def __init__(self, app_instance, db_manager, config_manager, parent=None):
        """Initialize the advanced optimization dialog.
        
        Args:
            app_instance: Main application instance
            db_manager: Database manager instance
            config_manager: Configuration manager instance
            parent (QWidget, optional): Parent widget
        """
        super().__init__(parent)
        
        self.app_instance = app_instance
        self.db_manager = db_manager
        self.config_manager = config_manager
        self.migration_thread = None
        
        # Create a Phase4Optimizer instance
        self.phase4_optimizer = None
        
        self.setWindowTitle("Advanced Optimization - Phase 4 Scaling Solutions")
        self.setMinimumSize(600, 500)
        
        self.setup_ui()
        self.load_config_values()
    
    def setup_ui(self):
        """Set up the dialog UI."""
        # Main layout
        main_layout = QVBoxLayout(self)
        
        # Info label
        info_label = QLabel(
            "This tool configures advanced scaling solutions for handling very large image collections. "
            "These features are designed for collections with 100,000+ images or special requirements."
        )
        info_label.setWordWrap(True)
        main_layout.addWidget(info_label)
        
        # Tab widget
        tab_widget = QTabWidget()
        main_layout.addWidget(tab_widget)
        
        # === Database Sharding Tab ===
        db_tab = QWidget()
        db_layout = QVBoxLayout(db_tab)
        
        # Sharding group
        sharding_group = QGroupBox("Database Sharding")
        sharding_layout = QVBoxLayout(sharding_group)
        
        # Enable sharding checkbox
        self.enable_sharding_checkbox = QCheckBox("Enable Database Sharding")
        self.enable_sharding_checkbox.setToolTip(
            "Split the database into multiple smaller databases for better performance with very large collections."
        )
        sharding_layout.addWidget(self.enable_sharding_checkbox)
        
        # Sharding strategy
        sharding_form = QFormLayout()
        self.sharding_strategy_combo = QComboBox()
        self.sharding_strategy_combo.addItem("Folder-based Sharding", "folder")
        self.sharding_strategy_combo.addItem("Date-based Sharding", "date")
        self.sharding_strategy_combo.setToolTip(
            "Folder-based: Split database by folders. Date-based: Split database by image date ranges."
        )
        sharding_form.addRow("Sharding Strategy:", self.sharding_strategy_combo)
        
        # Folder-based settings
        self.folders_per_shard_spin = QSpinBox()
        self.folders_per_shard_spin.setRange(1, 100)
        self.folders_per_shard_spin.setValue(10)
        self.folders_per_shard_spin.setToolTip(
            "Maximum number of folders to store in each shard database."
        )
        sharding_form.addRow("Max Folders per Shard:", self.folders_per_shard_spin)
        
        # Date-based settings
        self.months_per_shard_spin = QSpinBox()
        self.months_per_shard_spin.setRange(1, 24)
        self.months_per_shard_spin.setValue(6)
        self.months_per_shard_spin.setToolTip(
            "Number of months to include in each shard database."
        )
        sharding_form.addRow("Months per Shard:", self.months_per_shard_spin)
        
        sharding_layout.addLayout(sharding_form)
        
        # Migration button
        self.migrate_button = QPushButton("Migrate to Sharded Database")
        self.migrate_button.setToolTip(
            "Migrate your current database to a sharded structure. This process may take a long time for large collections."
        )
        sharding_layout.addWidget(self.migrate_button)
        
        db_layout.addWidget(sharding_group)
        
        # Migration progress
        migration_group = QGroupBox("Migration Progress")
        migration_layout = QVBoxLayout(migration_group)
        
        self.migration_progress = QProgressBar()
        self.migration_progress.setRange(0, 100)
        self.migration_progress.setValue(0)
        migration_layout.addWidget(self.migration_progress)
        
        self.migration_status = QLabel("Ready to migrate")
        migration_layout.addWidget(self.migration_status)
        
        self.migration_log = QTextEdit()
        self.migration_log.setReadOnly(True)
        self.migration_log.setMaximumHeight(100)
        migration_layout.addWidget(self.migration_log)
        
        db_layout.addWidget(migration_group)
        
        # Add the tab
        tab_widget.addTab(db_tab, "Database Sharding")
        
        # === Image Format Optimization Tab ===
        img_tab = QWidget()
        img_layout = QVBoxLayout(img_tab)
        
        # Format optimization group
        format_group = QGroupBox("Image Format Optimization")
        format_layout = QVBoxLayout(format_group)
        
        # Enable format optimization
        self.enable_format_checkbox = QCheckBox("Enable Format Optimization")
        self.enable_format_checkbox.setToolTip(
            "Automatically select the best image format (WebP, PNG, JPEG) based on content type."
        )
        format_layout.addWidget(self.enable_format_checkbox)
        
        # Format settings
        format_form = QFormLayout()
        
        self.webp_quality_spin = QSpinBox()
        self.webp_quality_spin.setRange(1, 100)
        self.webp_quality_spin.setValue(80)
        self.webp_quality_spin.setToolTip(
            "Quality setting for WebP format (1-100). Higher values mean better quality but larger files."
        )
        format_form.addRow("WebP Quality:", self.webp_quality_spin)
        
        self.jpeg_quality_spin = QSpinBox()
        self.jpeg_quality_spin.setRange(1, 100)
        self.jpeg_quality_spin.setValue(85)
        self.jpeg_quality_spin.setToolTip(
            "Quality setting for JPEG format (1-100). Higher values mean better quality but larger files."
        )
        format_form.addRow("JPEG Quality:", self.jpeg_quality_spin)
        
        self.png_compression_spin = QSpinBox()
        self.png_compression_spin.setRange(0, 9)
        self.png_compression_spin.setValue(6)
        self.png_compression_spin.setToolTip(
            "Compression level for PNG format (0-9). Higher values mean better compression but slower saving."
        )
        format_form.addRow("PNG Compression:", self.png_compression_spin)
        
        format_layout.addLayout(format_form)
        
        # Explanation
        format_explanation = QLabel(
            "Format optimization intelligently selects the best format for each image:\n"
            "- WebP for photos (best compression)\n"
            "- PNG for text/diagrams/screenshots\n"
            "- JPEG as a fallback option"
        )
        format_explanation.setWordWrap(True)
        format_layout.addWidget(format_explanation)
        
        img_layout.addWidget(format_group)
        
        # Add the tab
        tab_widget.addTab(img_tab, "Image Format Optimization")
        
        # === Memory & Resource Tab ===
        mem_tab = QWidget()
        mem_layout = QVBoxLayout(mem_tab)
        
        # Resource management group
        resource_group = QGroupBox("Memory & Resource Management")
        resource_layout = QVBoxLayout(resource_group)
        
        # Enable resource management
        self.enable_resource_checkbox = QCheckBox("Enable Advanced Resource Management")
        self.enable_resource_checkbox.setToolTip(
            "Monitor memory usage and automatically clean up resources to prevent memory issues."
        )
        resource_layout.addWidget(self.enable_resource_checkbox)
        
        # Resource settings
        resource_form = QFormLayout()
        
        self.gc_threshold_spin = QSpinBox()
        self.gc_threshold_spin.setRange(50, 95)
        self.gc_threshold_spin.setValue(80)
        self.gc_threshold_spin.setToolTip(
            "Memory usage threshold (%) to trigger garbage collection."
        )
        resource_form.addRow("Memory Threshold (%):", self.gc_threshold_spin)
        
        self.monitor_interval_spin = QSpinBox()
        self.monitor_interval_spin.setRange(1, 60)
        self.monitor_interval_spin.setValue(10)
        self.monitor_interval_spin.setToolTip(
            "Interval (seconds) between memory usage checks."
        )
        resource_form.addRow("Monitor Interval (s):", self.monitor_interval_spin)
        
        self.aggressive_cleanup_checkbox = QCheckBox()
        self.aggressive_cleanup_checkbox.setToolTip(
            "Enable more aggressive cleanup when memory usage is high."
        )
        resource_form.addRow("Aggressive Cleanup:", self.aggressive_cleanup_checkbox)
        
        resource_layout.addLayout(resource_form)
        
        # Explanation
        resource_explanation = QLabel(
            "Advanced resource management helps prevent out of memory errors and improves stability "
            "when working with very large collections. It monitors memory usage and automatically "
            "cleans up resources when needed."
        )
        resource_explanation.setWordWrap(True)
        resource_layout.addWidget(resource_explanation)
        
        mem_layout.addWidget(resource_group)
        
        # Add the tab
        tab_widget.addTab(mem_tab, "Memory & Resources")
        
        # === Button Box ===
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Apply | 
            QDialogButtonBox.StandardButton.Save | 
            QDialogButtonBox.StandardButton.Cancel
        )
        
        button_box.button(QDialogButtonBox.StandardButton.Apply).setText("Apply")
        button_box.button(QDialogButtonBox.StandardButton.Save).setText("Save")
        button_box.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancel")
        
        button_box.clicked.connect(self.handle_button_click)
        main_layout.addWidget(button_box)
        
        # Connect signals
        self.enable_sharding_checkbox.stateChanged.connect(self.update_sharding_ui)
        self.sharding_strategy_combo.currentIndexChanged.connect(self.update_sharding_ui)
        self.migrate_button.clicked.connect(self.start_migration)
    
    def load_config_values(self):
        """Load configuration values from config manager."""
        # Database sharding
        self.enable_sharding_checkbox.setChecked(
            self.config_manager.get("database", "enable_sharding", False)
        )
        
        sharding_type = self.config_manager.get("database", "sharding_type", "folder")
        index = self.sharding_strategy_combo.findData(sharding_type)
        if index >= 0:
            self.sharding_strategy_combo.setCurrentIndex(index)
        
        self.folders_per_shard_spin.setValue(
            self.config_manager.get("database", "max_folders_per_shard", 10)
        )
        
        self.months_per_shard_spin.setValue(
            self.config_manager.get("database", "shard_interval_months", 6)
        )
        
        # Image format optimization
        self.enable_format_checkbox.setChecked(
            self.config_manager.get("thumbnails", "format_optimization", True)
        )
        
        self.webp_quality_spin.setValue(
            self.config_manager.get("thumbnails", "webp_quality", 80)
        )
        
        self.jpeg_quality_spin.setValue(
            self.config_manager.get("thumbnails", "jpeg_quality", 85)
        )
        
        self.png_compression_spin.setValue(
            self.config_manager.get("thumbnails", "png_compression", 6)
        )
        
        # Resource management
        self.enable_resource_checkbox.setChecked(
            self.config_manager.get("memory", "enable_resource_management", True)
        )
        
        self.gc_threshold_spin.setValue(
            self.config_manager.get("memory", "gc_threshold", 80)
        )
        
        self.monitor_interval_spin.setValue(
            self.config_manager.get("memory", "monitor_interval", 10)
        )
        
        self.aggressive_cleanup_checkbox.setChecked(
            self.config_manager.get("memory", "aggressive_cleanup", False)
        )
        
        # Update UI state
        self.update_sharding_ui()
    
    def update_sharding_ui(self):
        """Update the sharding UI based on current settings."""
        is_enabled = self.enable_sharding_checkbox.isChecked()
        strategy = self.sharding_strategy_combo.currentData()
        
        # Enable/disable sharding controls
        self.sharding_strategy_combo.setEnabled(is_enabled)
        self.migrate_button.setEnabled(is_enabled)
        
        # Show/hide strategy-specific controls
        is_folder_based = strategy == "folder"
        self.folders_per_shard_spin.setVisible(is_folder_based)
        self.folders_per_shard_spin.setEnabled(is_enabled and is_folder_based)
        
        is_date_based = strategy == "date"
        self.months_per_shard_spin.setVisible(is_date_based)
        self.months_per_shard_spin.setEnabled(is_enabled and is_date_based)
    
    def start_migration(self):
        """Start the database sharding migration process."""
        # Confirm with user
        response = QMessageBox.warning(
            self,
            "Confirm Migration",
            "Migrating to a sharded database structure can take a long time for large collections. "
            "A backup will be created, but it's recommended to perform your own backup first.\n\n"
            "Do you want to continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if response != QMessageBox.StandardButton.Yes:
            return
        
        try:
            # Save current settings to config
            self.save_settings()
            
            # Create sharding strategy
            if self.sharding_strategy_combo.currentData() == "date":
                interval_months = self.months_per_shard_spin.value()
                strategy = DateBasedSharding(interval_months=interval_months)
            else:
                max_folders = self.folders_per_shard_spin.value()
                strategy = FolderBasedSharding(max_folders_per_shard=max_folders)
            
            # Create shard manager
            db_path = self.config_manager.get("database", "path", None)
            if not db_path:
                self.log_migration("Error: Database path not configured")
                return
            
            shard_manager = ShardManager(db_path, strategy, True)
            
            # Disable UI elements
            self.migrate_button.setEnabled(False)
            self.migration_progress.setValue(0)
            self.migration_status.setText("Starting migration...")
            self.migration_log.clear()
            
            # Create and start migration thread
            self.migration_thread = ShardingMigrationThread(self.db_manager, shard_manager)
            self.migration_thread.progress_signal.connect(self.update_migration_progress)
            self.migration_thread.finished_signal.connect(self.migration_finished)
            self.migration_thread.start()
            
        except Exception as e:
            logger.error(f"Error starting migration: {e}")
            self.log_migration(f"Error: {e}")
            self.migration_button.setEnabled(True)
    
    def update_migration_progress(self, current, total, message):
        """Update the migration progress display."""
        progress_percent = int((current / total) * 100)
        self.migration_progress.setValue(progress_percent)
        self.migration_status.setText(message)
        self.log_migration(message)
    
    def log_migration(self, message):
        """Add a message to the migration log."""
        self.migration_log.append(message)
    
    def migration_finished(self, success, stats):
        """Handle migration completion."""
        if success:
            self.migration_progress.setValue(100)
            self.migration_status.setText("Migration completed successfully")
            self.log_migration("Database migration completed successfully")
            
            QMessageBox.information(
                self,
                "Migration Complete",
                "Database has been successfully migrated to a sharded structure.",
                QMessageBox.StandardButton.Ok
            )
        else:
            self.migration_progress.setValue(0)
            self.migration_status.setText("Migration failed")
            
            error_msg = stats.get("error", "Unknown error")
            self.log_migration(f"Migration failed: {error_msg}")
            
            QMessageBox.critical(
                self,
                "Migration Failed",
                f"Failed to migrate database: {error_msg}",
                QMessageBox.StandardButton.Ok
            )
        
        # Re-enable buttons
        self.migrate_button.setEnabled(self.enable_sharding_checkbox.isChecked())
    
    def handle_button_click(self, button):
        """Handle button box clicks."""
        role = self.sender().buttonRole(button)
        
        if role == QDialogButtonBox.ButtonRole.ApplyRole:
            # Apply button - save settings and apply without closing
            self.save_settings()
            self.apply_settings()
        elif role == QDialogButtonBox.ButtonRole.AcceptRole:
            # Save button - save settings, apply, and close
            self.save_settings()
            self.apply_settings()
            self.accept()
        elif role == QDialogButtonBox.ButtonRole.RejectRole:
            # Cancel button - close without saving
            self.reject()
    
    def save_settings(self):
        """Save settings to configuration."""
        # Database sharding
        self.config_manager.set("database", "enable_sharding", 
                               self.enable_sharding_checkbox.isChecked())
        
        self.config_manager.set("database", "sharding_type", 
                               self.sharding_strategy_combo.currentData())
        
        self.config_manager.set("database", "max_folders_per_shard", 
                               self.folders_per_shard_spin.value())
        
        self.config_manager.set("database", "shard_interval_months", 
                               self.months_per_shard_spin.value())
        
        # Image format optimization
        self.config_manager.set("thumbnails", "format_optimization", 
                               self.enable_format_checkbox.isChecked())
        
        self.config_manager.set("thumbnails", "webp_quality", 
                               self.webp_quality_spin.value())
        
        self.config_manager.set("thumbnails", "jpeg_quality", 
                               self.jpeg_quality_spin.value())
        
        self.config_manager.set("thumbnails", "png_compression", 
                               self.png_compression_spin.value())
        
        # Resource management
        self.config_manager.set("memory", "enable_resource_management", 
                               self.enable_resource_checkbox.isChecked())
        
        self.config_manager.set("memory", "gc_threshold", 
                               self.gc_threshold_spin.value())
        
        self.config_manager.set("memory", "monitor_interval", 
                               self.monitor_interval_spin.value())
        
        self.config_manager.set("memory", "aggressive_cleanup", 
                               self.aggressive_cleanup_checkbox.isChecked())
        
        # Save to file
        self.config_manager.save_config()
        logger.info("Saved Phase 4 optimization settings to configuration")
    
    def apply_settings(self):
        """Apply the current settings."""
        try:
            # Create Phase4Optimizer with current settings
            self.phase4_optimizer = Phase4Optimizer(self.config_manager)
            
            # Integrate with application components
            if hasattr(self.app_instance, 'db_manager'):
                self.phase4_optimizer.integrate_with_database_manager(self.app_instance.db_manager)
            
            if hasattr(self.app_instance, 'thumbnail_generator'):
                self.phase4_optimizer.integrate_with_thumbnail_generator(self.app_instance.thumbnail_generator)
            
            if hasattr(self.app_instance, 'batch_operations'):
                self.phase4_optimizer.integrate_with_batch_operations(self.app_instance.batch_operations)
            
            logger.info("Applied Phase 4 optimization settings")
            QMessageBox.information(
                self,
                "Settings Applied",
                "Phase 4 optimization settings have been applied.",
                QMessageBox.StandardButton.Ok
            )
            
        except Exception as e:
            logger.error(f"Error applying settings: {e}")
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to apply settings: {e}",
                QMessageBox.StandardButton.Ok
            )
    
    def closeEvent(self, event):
        """Handle dialog close event."""
        # Check if migration is running
        if self.migration_thread and self.migration_thread.isRunning():
            # Ask for confirmation
            response = QMessageBox.question(
                self,
                "Migration in Progress",
                "Database migration is still in progress. Are you sure you want to cancel?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            
            if response == QMessageBox.StandardButton.Yes:
                # Terminate thread
                self.migration_thread.terminate()
                self.migration_thread.wait()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()
