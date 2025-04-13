#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Catalog panel UI component for StarImageBrowse
Displays and manages catalogs for organizing images.
"""

import os
import logging
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTreeWidget,
    QTreeWidgetItem, QPushButton, QMenu, QMessageBox, QInputDialog
)
from PyQt6.QtGui import QIcon, QAction
from PyQt6.QtCore import Qt, pyqtSignal

logger = logging.getLogger("StarImageBrowse.ui.catalog_panel")

class CatalogPanel(QWidget):
    """Panel for displaying and managing image catalogs."""
    
    catalog_selected = pyqtSignal(int, str)  # Signal emitted when a catalog is selected (catalog_id, name)
    catalog_added = pyqtSignal(int, str)  # Signal emitted when a catalog is added (catalog_id, name)
    catalog_removed = pyqtSignal(int)  # Signal emitted when a catalog is removed (catalog_id)
    add_catalog_requested = pyqtSignal()  # Signal to request adding a new catalog
    
    def __init__(self, db_manager, parent=None):
        """Initialize the catalog panel.
        
        Args:
            db_manager: Database manager instance
            parent (QWidget, optional): Parent widget
        """
        super().__init__(parent)
        
        self.db_manager = db_manager
        
        self.setup_ui()
        self.refresh_catalogs()
    
    def setup_ui(self):
        """Set up the catalog panel UI."""
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Header
        header_layout = QHBoxLayout()
        header_label = QLabel("Catalogs")
        header_label.setStyleSheet("font-weight: bold;")
        header_layout.addWidget(header_label)
        
        # Add New Catalog button
        self.add_catalog_button = QPushButton("+")
        self.add_catalog_button.setToolTip("Add New Catalog")
        self.add_catalog_button.setFixedSize(30, 30)  # Increased size for better visibility
        self.add_catalog_button.setStyleSheet("""
            QPushButton {
                font-weight: bold;
                font-size: 16px;
                background-color: #494949;
                border-radius: 15px;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: #5a5a5a;
            }
        """)
        self.add_catalog_button.clicked.connect(self.on_add_catalog_clicked)
        header_layout.addWidget(self.add_catalog_button)
        
        layout.addLayout(header_layout)
        
        # Catalog tree
        self.catalog_tree = QTreeWidget()
        self.catalog_tree.setHeaderHidden(True)
        self.catalog_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.catalog_tree.itemClicked.connect(self.on_catalog_clicked)
        self.catalog_tree.customContextMenuRequested.connect(self.on_context_menu)
        layout.addWidget(self.catalog_tree)
    
    def on_add_catalog_clicked(self):
        """Handler for Add New Catalog button click."""
        # Show dialog to get catalog name
        name, ok = QInputDialog.getText(self, "Add New Catalog", "Catalog Name:")
        
        if ok and name:
            # Add the catalog to the database
            catalog_id = self.db_manager.create_catalog(name)
            
            if catalog_id:
                # Refresh the catalog list
                self.refresh_catalogs()
                
                # Emit signal that a catalog was added
                self.catalog_added.emit(catalog_id, name)
                
                # Select the new catalog
                self.select_catalog_by_id(catalog_id)
            else:
                QMessageBox.critical(
                    self, "Error", 
                    "Failed to create catalog.",
                    QMessageBox.StandardButton.Ok
                )
        
    def refresh_catalogs(self):
        """Refresh the catalog list from the database."""
        self.catalog_tree.clear()
        
        # Get all catalogs
        catalogs = self.db_manager.get_catalogs()
        
        # Add each catalog to the tree
        for catalog in catalogs:
            catalog_id = catalog["catalog_id"]
            
            # Get image count for this catalog
            image_count = self.db_manager.get_image_count_for_catalog(catalog_id)
            
            # Format the display text with image count
            display_text = f"{catalog['name']} ({image_count})"
            
            catalog_item = QTreeWidgetItem([display_text])
            catalog_item.setData(0, Qt.ItemDataRole.UserRole, catalog_id)
            catalog_item.setToolTip(0, f"{catalog['name']} - {image_count} images")
            self.catalog_tree.addTopLevelItem(catalog_item)
        
        # Automatically select the first catalog if available
        if self.catalog_tree.topLevelItemCount() > 0:
            self.catalog_tree.setCurrentItem(self.catalog_tree.topLevelItem(0))
    
    def on_catalog_clicked(self, item, column):
        """Handle catalog item click.
        
        Args:
            item: The clicked tree item
            column: The clicked column
        """
        catalog_id = item.data(0, Qt.ItemDataRole.UserRole)
        catalog_name = item.text(0)
        
        # Emit signal with catalog ID and name
        if catalog_id is not None:
            self.catalog_selected.emit(catalog_id, catalog_name)
    
    def on_context_menu(self, position):
        """Show context menu for catalog items.
        
        Args:
            position: Position where to show the menu
        """
        # Get the item at the clicked position
        item = self.catalog_tree.itemAt(position)
        
        if not item:
            return
        
        # Get catalog ID from item data
        catalog_id = item.data(0, Qt.ItemDataRole.UserRole)
        
        if catalog_id is None:
            return
        
        # Get catalog info from database
        catalog_info = self.db_manager.get_catalog_by_id(catalog_id)
        
        if not catalog_info:
            return
        
        catalog_name = catalog_info["name"]
        
        # Create context menu
        menu = QMenu()
        
        # Add actions
        rename_action = menu.addAction("Rename Catalog")
        
        menu.addSeparator()
        
        remove_action = menu.addAction("Remove Catalog")
        
        # Show menu and get selected action
        action = menu.exec(self.catalog_tree.mapToGlobal(position))
        
        # Handle selected action
        if action == rename_action:
            self.rename_catalog(catalog_id, catalog_name)
        elif action == remove_action:
            self.remove_catalog(catalog_id)
    
    def rename_catalog(self, catalog_id, current_name):
        """Rename a catalog.
        
        Args:
            catalog_id (int): ID of the catalog to rename
            current_name (str): Current name of the catalog
        """
        # Show dialog to get new catalog name
        new_name, ok = QInputDialog.getText(
            self, "Rename Catalog", 
            "New Catalog Name:", 
            text=current_name
        )
        
        if ok and new_name:
            # Update the catalog in the database
            # Since we don't have a direct rename method, we'll create a new one and delete the old one
            new_catalog_id = self.db_manager.create_catalog(new_name)
            
            if new_catalog_id:
                # Get all images from the old catalog
                images = self.db_manager.get_images_for_catalog(catalog_id)
                
                # Add all images to the new catalog
                for image in images:
                    self.db_manager.add_image_to_catalog(image["image_id"], new_catalog_id)
                
                # Delete the old catalog
                self.db_manager.delete_catalog(catalog_id)
                
                # Refresh the catalog list
                self.refresh_catalogs()
                
                # Select the new catalog
                self.select_catalog_by_id(new_catalog_id)
            else:
                QMessageBox.critical(
                    self, "Error", 
                    "Failed to rename catalog.",
                    QMessageBox.StandardButton.Ok
                )
    
    def remove_catalog(self, catalog_id):
        """Remove a catalog.
        
        Args:
            catalog_id (int): ID of the catalog to remove
        """
        # Confirm removal
        confirm = QMessageBox.question(
            self, "Confirm Removal", 
            "Are you sure you want to remove this catalog? Images will not be deleted, but their association with this catalog will be removed.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if confirm != QMessageBox.StandardButton.Yes:
            return
        
        # Remove catalog from database
        success = self.db_manager.delete_catalog(catalog_id)
        
        if success:
            # Emit signal
            self.catalog_removed.emit(catalog_id)
            
            # Refresh display
            self.refresh_catalogs()
        else:
            QMessageBox.critical(
                self, "Error", 
                "Failed to remove catalog from database.",
                QMessageBox.StandardButton.Ok
            )
    
    def get_selected_catalog_id(self):
        """Get the ID of the currently selected catalog.
        
        Returns:
            int: ID of the selected catalog, or None if no catalog is selected
        """
        selected_items = self.catalog_tree.selectedItems()
        
        if not selected_items:
            return None
        
        # Get the first selected item
        item = selected_items[0]
        
        # Return the catalog ID stored in the item's user role data
        return item.data(0, Qt.ItemDataRole.UserRole)
    
    def get_selected_catalog_name(self):
        """Get the name of the currently selected catalog.
        
        Returns:
            str: Name of the selected catalog, or None if no catalog is selected
        """
        selected_items = self.catalog_tree.selectedItems()
        
        if not selected_items:
            return None
        
        # Get the first selected item
        item = selected_items[0]
        
        # Return the catalog name
        return item.text(0)
    
    def select_catalog_by_id(self, catalog_id):
        """Select a catalog by its ID.
        
        Args:
            catalog_id (int): ID of the catalog to select
        """
        # Find the catalog item with the matching ID
        for i in range(self.catalog_tree.topLevelItemCount()):
            item = self.catalog_tree.topLevelItem(i)
            if item.data(0, Qt.ItemDataRole.UserRole) == catalog_id:
                self.catalog_tree.setCurrentItem(item)
                self.on_catalog_clicked(item, 0)
                break
