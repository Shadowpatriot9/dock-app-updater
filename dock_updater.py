#!/usr/bin/env python3
"""
Dock App Updater - A utility to update non-OS native apps in macOS dock
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
import threading
import subprocess
import time
import os
import plistlib
import keyring
import psutil
from pathlib import Path
import logging
from datetime import datetime


class DockAppUpdater:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Dock App Updater")
        self.root.geometry("700x500")
        
        # Auto-close timer variables
        self.auto_close_timer = None
        self.user_interacted = False
        self.close_after_update = False
        
        # Logging variables
        self.enable_logging = tk.BooleanVar(value=True)
        self.log_file_path = os.path.expanduser("~/dock_updater.log")
        self.setup_logging()
        
        # Force-stop and timeout variables
        self.update_process = None
        self.update_thread = None
        self.force_stop_requested = False
        self.update_timeout = 300  # 5 minutes timeout for updates
        self.timeout_timer = None
        
        # Bind focus and click events to detect user interaction
        self.root.bind('<Button-1>', self.on_user_interaction)
        self.root.bind('<Key>', self.on_user_interaction)
        self.root.bind('<FocusIn>', self.on_user_interaction)
        
        self.setup_ui()
        self.load_sudo_credentials()
        
        # Log startup
        self.log_message("Dock App Updater started", "INFO")
        
    def setup_logging(self):
        """Setup logging configuration"""
        # Create logger
        self.logger = logging.getLogger('DockAppUpdater')
        self.logger.setLevel(logging.INFO)
        
        # Clear any existing handlers
        self.logger.handlers.clear()
        
        # Create file handler
        if self.enable_logging.get():
            file_handler = logging.FileHandler(self.log_file_path)
            file_handler.setLevel(logging.INFO)
            
            # Create formatter
            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            file_handler.setFormatter(formatter)
            
            # Add handler to logger
            self.logger.addHandler(file_handler)
            
    def log_message(self, message, level="INFO"):
        """Log a message both to file and GUI display"""
        if self.enable_logging.get():
            if level == "INFO":
                self.logger.info(message)
            elif level == "WARNING":
                self.logger.warning(message)
            elif level == "ERROR":
                self.logger.error(message)
            elif level == "DEBUG":
                self.logger.debug(message)
                
        # Also display in GUI log area if it exists
        if hasattr(self, 'log_display'):
            try:
                timestamp = datetime.now().strftime("%H:%M:%S")
                log_entry = f"[{timestamp}] {level}: {message}\n"
                self.log_display.insert(tk.END, log_entry)
                self.log_display.see(tk.END)  # Auto-scroll to bottom
            except tk.TclError:
                # GUI is being destroyed, skip GUI logging
                pass
            
    def toggle_logging(self):
        """Toggle logging on/off"""
        self.setup_logging()
        if self.enable_logging.get():
            self.log_message("Logging enabled", "INFO")
        else:
            self.log_message("Logging disabled", "WARNING")
            
    def choose_log_file(self):
        """Choose log file location"""
        filename = filedialog.asksaveasfilename(
            title="Choose log file location",
            defaultextension=".log",
            filetypes=[("Log files", "*.log"), ("Text files", "*.txt"), ("All files", "*.*")],
            initialfile="dock_updater.log"
        )
        
        if filename:
            self.log_file_path = filename
            self.setup_logging()  # Reinitialize with new path
            self.log_message(f"Log file path changed to: {filename}", "INFO")
            
    def view_log_file(self):
        """View the current log file in default text editor"""
        if os.path.exists(self.log_file_path):
            try:
                if os.name == 'posix':  # macOS/Linux
                    subprocess.run(['open', self.log_file_path])
                elif os.name == 'nt':  # Windows
                    subprocess.run(['notepad', self.log_file_path])
                self.log_message(f"Opened log file: {self.log_file_path}", "INFO")
            except Exception as e:
                messagebox.showerror("Error", f"Could not open log file: {str(e)}")
                self.log_message(f"Failed to open log file: {str(e)}", "ERROR")
        else:
            messagebox.showwarning("Warning", "Log file does not exist yet.")
            
    def clear_log(self):
        """Clear the log display and optionally the log file"""
        # Clear GUI display
        self.log_display.delete(1.0, tk.END)
        
        # Ask if user wants to clear the log file too
        if messagebox.askyesno("Clear Log File", "Do you also want to clear the log file on disk?"):
            try:
                with open(self.log_file_path, 'w') as f:
                    f.write('')
                self.log_message("Log file cleared", "INFO")
            except Exception as e:
                messagebox.showerror("Error", f"Could not clear log file: {str(e)}")
                self.log_message(f"Failed to clear log file: {str(e)}", "ERROR")
                
    def force_stop_update(self):
        """Force stop the current update process"""
        self.force_stop_requested = True
        self.log_message("Force stop requested by user", "WARNING")
        
        # Cancel timeout timer if active
        if self.timeout_timer:
            self.root.after_cancel(self.timeout_timer)
            self.timeout_timer = None
            
        # Terminate update process if running
        if self.update_process and self.update_process.poll() is None:
            try:
                self.update_process.terminate()
                self.log_message("Update process terminated", "INFO")
            except Exception as e:
                self.log_message(f"Failed to terminate process: {str(e)}", "ERROR")
                
        # Reset UI state
        self.progress.stop()
        self.status_label.config(text="Update stopped by user")
        self.stop_btn.config(state="disabled")
        self.update_all_btn.config(state="normal")
        self.update_btn.config(state="normal")
        self.refresh_btn.config(state="normal")
        self.close_after_update = False
        
    def start_update_timeout(self):
        """Start timeout timer for updates"""
        if self.timeout_timer:
            self.root.after_cancel(self.timeout_timer)
            
        self.timeout_timer = self.root.after(self.update_timeout * 1000, self.handle_update_timeout)
        self.log_message(f"Update timeout set for {self.update_timeout} seconds", "INFO")
        
    def handle_update_timeout(self):
        """Handle update timeout"""
        self.log_message("Update timeout reached, forcing stop", "ERROR")
        self.force_stop_update()
        messagebox.showwarning("Update Timeout", f"Update process timed out after {self.update_timeout} seconds and was stopped.")
        
    def on_treeview_click(self, event):
        """Handle treeview click to toggle app selection"""
        region = self.app_tree.identify("region", event.x, event.y)
        if region == "cell":
            item = self.app_tree.identify_row(event.y)
            column = self.app_tree.identify_column(event.x)
            
            # Only process clicks on the checkbox column
            if column == "#1" and item:  # #1 is the first column (selected)
                current_values = list(self.app_tree.item(item, "values"))
                if current_values:
                    # Toggle selection
                    current_values[0] = "☐" if current_values[0] == "☑" else "☑"
                    self.app_tree.item(item, values=current_values)
                    
                    app_name = current_values[1]
                    selected = current_values[0] == "☑"
                    self.log_message(f"App {app_name} {'selected' if selected else 'deselected'} for update", "INFO")
        
    def setup_ui(self):
        """Setup the main UI components"""
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Title
        title_label = ttk.Label(main_frame, text="Dock App Updater", font=("Arial", 16, "bold"))
        title_label.grid(row=0, column=0, columnspan=2, pady=(0, 20))
        
        # App list frame
        list_frame = ttk.LabelFrame(main_frame, text="Detected Apps", padding="5")
        list_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        
        # Treeview for apps with checkboxes
        self.app_tree = ttk.Treeview(list_frame, columns=("selected", "name", "version", "status"), show="headings")
        self.app_tree.heading("selected", text="✓")
        self.app_tree.heading("name", text="App Name")
        self.app_tree.heading("version", text="Version")
        self.app_tree.heading("status", text="Status")
        
        # Configure column widths
        self.app_tree.column("selected", width=40, minwidth=40, stretch=False)
        self.app_tree.column("name", width=200, minwidth=150)
        self.app_tree.column("version", width=100, minwidth=80)
        self.app_tree.column("status", width=150, minwidth=100)
        
        # Bind click event to toggle selection
        self.app_tree.bind('<Button-1>', self.on_treeview_click)
        
        # Scrollbar for treeview
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.app_tree.yview)
        self.app_tree.configure(yscrollcommand=scrollbar.set)
        
        self.app_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # Button frame - stacked vertically to avoid overlap
        button_frame = ttk.LabelFrame(main_frame, text="Actions", padding="10")
        button_frame.grid(row=2, column=0, columnspan=2, pady=(10, 5), sticky=(tk.W, tk.E))
        
        # Row 1: Main action buttons
        button_row1 = ttk.Frame(button_frame)
        button_row1.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 5))
        button_row1.columnconfigure((0, 1), weight=1)
        
        self.refresh_btn = ttk.Button(button_row1, text="🔄 Refresh Apps", command=self.refresh_apps)
        self.refresh_btn.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 5))
        
        self.update_all_btn = ttk.Button(button_row1, text="⚡ Update All Apps", command=self.update_all_apps, style="Accent.TButton")
        self.update_all_btn.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(5, 0))
        
        # Row 2: Secondary action buttons  
        button_row2 = ttk.Frame(button_frame)
        button_row2.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(5, 0))
        button_row2.columnconfigure((0, 1, 2), weight=1)
        
        self.update_btn = ttk.Button(button_row2, text="📝 Update Selected", command=self.update_selected_apps)
        self.update_btn.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 3))
        
        self.creds_btn = ttk.Button(button_row2, text="🔐 Set Credentials", command=self.set_sudo_credentials)
        self.creds_btn.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(3, 3))
        
        self.stop_btn = ttk.Button(button_row2, text="⏹️ Force Stop", command=self.force_stop_update, state="disabled")
        self.stop_btn.grid(row=0, column=2, sticky=(tk.W, tk.E), padx=(3, 0))
        
        button_frame.columnconfigure(0, weight=1)
        
        # Logging controls frame
        log_control_frame = ttk.LabelFrame(main_frame, text="Logging Controls", padding="5")
        log_control_frame.grid(row=3, column=0, columnspan=2, pady=(5, 5), sticky=(tk.W, tk.E))
        log_control_frame.columnconfigure((1, 2, 3), weight=1)
        
        # Logging checkbox
        self.log_checkbox = ttk.Checkbutton(log_control_frame, text="📋 Enable Logging", 
                                          variable=self.enable_logging, 
                                          command=self.toggle_logging)
        self.log_checkbox.grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        
        # Log file button
        self.log_file_btn = ttk.Button(log_control_frame, text="📂 Choose File", 
                                     command=self.choose_log_file)
        self.log_file_btn.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 3))
        
        # View log button
        self.view_log_btn = ttk.Button(log_control_frame, text="👁️ View Log", 
                                     command=self.view_log_file)
        self.view_log_btn.grid(row=0, column=2, sticky=(tk.W, tk.E), padx=(3, 3))
        
        # Clear log button
        self.clear_log_btn = ttk.Button(log_control_frame, text="🗑️ Clear Log", 
                                      command=self.clear_log)
        self.clear_log_btn.grid(row=0, column=3, sticky=(tk.W, tk.E), padx=(3, 0))
        
        # Log display frame
        log_frame = ttk.LabelFrame(main_frame, text="Activity Log", padding="5")
        log_frame.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(5, 10))
        
        # Log text area with scrollbar
        self.log_display = tk.Text(log_frame, height=8, wrap=tk.WORD)
        log_scrollbar = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_display.yview)
        self.log_display.configure(yscrollcommand=log_scrollbar.set)
        
        self.log_display.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        log_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        log_frame.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)
        
        # Progress bar
        self.progress = ttk.Progressbar(main_frame, mode='indeterminate')
        self.progress.grid(row=5, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # Status label
        self.status_label = ttk.Label(main_frame, text="Ready")
        self.status_label.grid(row=6, column=0, columnspan=2)
        
        # Configure grid weights
        main_frame.rowconfigure(1, weight=1)  # App list
        main_frame.rowconfigure(4, weight=1)  # Log display
        main_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)
        list_frame.columnconfigure(0, weight=1)
        
        self.root.rowconfigure(0, weight=1)
        self.root.columnconfigure(0, weight=1)
        
    def on_user_interaction(self, event=None):
        """Handle user interaction to prevent auto-close"""
        self.user_interacted = True
        if self.auto_close_timer:
            self.root.after_cancel(self.auto_close_timer)
            self.auto_close_timer = None
            
    def start_auto_close_timer(self):
        """Start 10-second auto-close timer"""
        if not self.close_after_update:
            return
            
        self.user_interacted = False
        self.auto_close_timer = self.root.after(10000, self.auto_close)
        self.status_label.config(text="Updates complete. App will close in 10 seconds unless you interact with it.")
        
    def auto_close(self):
        """Close the app if user hasn't interacted"""
        if not self.user_interacted:
            self.root.quit()
            
    def load_sudo_credentials(self):
        """Load sudo credentials from keychain"""
        try:
            password = keyring.get_password("dock_updater", "sudo_password")
            self.sudo_password = password
            if password:
                self.status_label.config(text="Sudo credentials loaded from keychain")
                self.log_message("Sudo credentials loaded from keychain", "INFO")
            else:
                self.status_label.config(text="No sudo credentials found. Click 'Set Credentials' to add them.")
                self.log_message("No sudo credentials found in keychain", "WARNING")
        except Exception as e:
            self.sudo_password = None
            self.status_label.config(text="Error loading credentials")
            self.log_message(f"Error loading credentials: {str(e)}", "ERROR")
            
    def set_sudo_credentials(self):
        """Set sudo credentials and store in keychain"""
        password = simpledialog.askstring("Sudo Password", "Enter your sudo password:", show='*')
        if password:
            try:
                # Test the password
                result = subprocess.run(['sudo', '-S', 'echo', 'test'], 
                                      input=f"{password}\n", 
                                      text=True, 
                                      capture_output=True, 
                                      timeout=10)
                
                if result.returncode == 0:
                    keyring.set_password("dock_updater", "sudo_password", password)
                    self.sudo_password = password
                    self.status_label.config(text="Sudo credentials saved successfully")
                    messagebox.showinfo("Success", "Sudo credentials saved to keychain")
                    self.log_message("Sudo credentials saved successfully to keychain", "INFO")
                else:
                    messagebox.showerror("Error", "Invalid sudo password")
                    self.log_message("Invalid sudo password provided", "ERROR")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save credentials: {str(e)}")
                self.log_message(f"Failed to save credentials: {str(e)}", "ERROR")
                
    def get_dock_apps(self):
        """Get list of apps from dock"""
        try:
            dock_plist_path = os.path.expanduser("~/Library/Preferences/com.apple.dock.plist")
            with open(dock_plist_path, 'rb') as f:
                dock_data = plistlib.load(f)
                
            apps = []
            for item in dock_data.get('persistent-apps', []):
                if 'tile-data' in item and 'file-label' in item['tile-data']:
                    app_name = item['tile-data']['file-label']
                    if 'file-data' in item['tile-data'] and '_CFURLString' in item['tile-data']['file-data']:
                        app_path = item['tile-data']['file-data']['_CFURLString'].replace('file://', '')
                        apps.append({
                            'name': app_name,
                            'path': app_path,
                            'version': self.get_app_version(app_path),
                            'is_native': self.is_native_app(app_path)
                        })
            
            # Filter out native macOS apps
            return [app for app in apps if not app['is_native']]
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to read dock apps: {str(e)}")
            return []
            
    def is_native_app(self, app_path):
        """Check if app is native macOS app (simplified check)"""
        native_paths = ['/System/', '/Applications/Utilities/', '/usr/']
        native_apps = ['Finder', 'Safari', 'Mail', 'Calendar', 'Contacts', 'Maps', 
                      'Photos', 'Messages', 'FaceTime', 'Music', 'TV', 'Podcasts',
                      'News', 'Stocks', 'Home', 'Shortcuts', 'System Preferences']
        
        app_name = os.path.basename(app_path).replace('.app', '')
        
        return (any(app_path.startswith(path) for path in native_paths) or 
                app_name in native_apps)
                
    def get_app_version(self, app_path):
        """Get app version from Info.plist"""
        try:
            info_plist_path = os.path.join(app_path, 'Contents', 'Info.plist')
            if os.path.exists(info_plist_path):
                with open(info_plist_path, 'rb') as f:
                    info_data = plistlib.load(f)
                    return info_data.get('CFBundleShortVersionString', 'Unknown')
            return 'Unknown'
        except:
            return 'Unknown'
            
    def refresh_apps(self):
        """Refresh the app list"""
        self.status_label.config(text="Refreshing app list...")
        self.progress.start()
        self.log_message("Starting app list refresh", "INFO")
        
        def refresh_thread():
            apps = self.get_dock_apps()
            self.root.after(0, lambda: self.update_app_list(apps))
            
        threading.Thread(target=refresh_thread, daemon=True).start()
        
    def update_app_list(self, apps):
        """Update the app list in the UI"""
        # Clear existing items
        for item in self.app_tree.get_children():
            self.app_tree.delete(item)
            
        # Add new items - all pre-selected by default
        for app in apps:
            status = "Ready for update"
            # Pre-select all apps with checked checkbox
            self.app_tree.insert("", "end", values=("☑", app['name'], app['version'], status))
            self.log_message(f"Found app: {app['name']} (v{app['version']}) - pre-selected for update", "DEBUG")
            
        self.progress.stop()
        selected_count = len(apps)  # All apps are pre-selected
        self.status_label.config(text=f"Found {len(apps)} non-native apps ({selected_count} selected for update)")
        self.log_message(f"App list refresh complete: {len(apps)} non-native apps found, all pre-selected", "INFO")
        
    def update_selected_apps(self):
        """Update selected apps (those with checked checkboxes)"""
        selected_apps = []
        
        # Get all checked apps
        for item in self.app_tree.get_children():
            values = self.app_tree.item(item, "values")
            if values and len(values) >= 2 and values[0] == "☑":  # Checked
                selected_apps.append(values[1])  # App name is in column 1
                
        if not selected_apps:
            messagebox.showwarning("Warning", "Please select apps to update by checking their checkboxes")
            return
            
        self.perform_updates(selected_apps)
        
    def update_all_apps(self):
        """Update all apps (automatically selects all)"""
        app_names = []
        
        # Get all apps and select them
        for item in self.app_tree.get_children():
            values = list(self.app_tree.item(item, "values"))
            if values and len(values) >= 2:
                app_names.append(values[1])  # App name is in column 1
                # Ensure app is selected
                values[0] = "☑"
                self.app_tree.item(item, values=values)
                
        if not app_names:
            messagebox.showinfo("Info", "No apps to update")
            return
            
        self.perform_updates(app_names)
        
    def perform_updates(self, app_names):
        """Perform updates for specified apps"""
        if not self.sudo_password:
            messagebox.showerror("Error", "Please set sudo credentials first")
            self.log_message("Update aborted: No sudo credentials available", "ERROR")
            return
            
        # Reset force stop flag
        self.force_stop_requested = False
        
        # Update UI state
        self.status_label.config(text="Updating apps...")
        self.progress.start()
        self.close_after_update = True
        
        # Disable buttons during update
        self.update_all_btn.config(state="disabled")
        self.update_btn.config(state="disabled")
        self.refresh_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        
        # Start timeout timer
        self.start_update_timeout()
        
        self.log_message(f"Starting update process for {len(app_names)} apps: {', '.join(app_names)}", "INFO")
        
        def update_thread():
            try:
                updated_something = False
                
                # Check if Homebrew is available
                result = subprocess.run(['which', 'brew'], capture_output=True, text=True)
                if result.returncode == 0:
                    self.root.after(0, lambda: self.status_label.config(text="Updating Homebrew packages..."))
                    self.root.after(0, lambda: self.log_message("Homebrew detected, starting Homebrew updates", "INFO"))
                    # First update Homebrew itself
                    subprocess.run(['brew', 'update'], check=True)
                    self.root.after(0, lambda: self.log_message("Homebrew updated successfully", "INFO"))
                    # Then upgrade packages
                    subprocess.run(['brew', 'upgrade'], check=True)
                    self.root.after(0, lambda: self.log_message("Homebrew packages upgraded", "INFO"))
                    # Also check for casks
                    subprocess.run(['brew', 'upgrade', '--cask'], check=True)
                    self.root.after(0, lambda: self.log_message("Homebrew casks upgraded", "INFO"))
                    updated_something = True
                    
                # Check if MacPorts is available
                result = subprocess.run(['which', 'port'], capture_output=True, text=True)
                if result.returncode == 0:
                    self.root.after(0, lambda: self.status_label.config(text="Updating MacPorts packages..."))
                    self.root.after(0, lambda: self.log_message("MacPorts detected, starting MacPorts updates", "INFO"))
                    # Update MacPorts
                    subprocess.run(['sudo', '-S', 'port', 'selfupdate'], 
                                 input=f"{self.sudo_password}\n", text=True, check=True)
                    self.root.after(0, lambda: self.log_message("MacPorts selfupdate completed", "INFO"))
                    subprocess.run(['sudo', '-S', 'port', 'upgrade', 'outdated'], 
                                 input=f"{self.sudo_password}\n", text=True, check=True)
                    self.root.after(0, lambda: self.log_message("MacPorts packages upgraded", "INFO"))
                    updated_something = True
                    
                # Check if pip is available for Python packages
                result = subprocess.run(['which', 'pip3'], capture_output=True, text=True)
                if result.returncode == 0:
                    self.root.after(0, lambda: self.status_label.config(text="Checking pip packages..."))
                    self.root.after(0, lambda: self.log_message("pip detected, checking for outdated packages", "INFO"))
                    subprocess.run(['pip3', 'list', '--outdated'], check=True)
                    self.root.after(0, lambda: self.log_message("pip outdated packages listed (manual update recommended)", "WARNING"))
                    # Note: We don't auto-upgrade pip packages as it can break system
                    
                # Check if npm is available
                result = subprocess.run(['which', 'npm'], capture_output=True, text=True)
                if result.returncode == 0:
                    self.root.after(0, lambda: self.status_label.config(text="Updating npm packages..."))
                    self.root.after(0, lambda: self.log_message("npm detected, starting global package updates", "INFO"))
                    subprocess.run(['npm', 'update', '-g'], check=True)
                    self.root.after(0, lambda: self.log_message("npm global packages updated", "INFO"))
                    updated_something = True
                    
                if not updated_something:
                    self.root.after(0, lambda: self.update_failed("No supported package managers found"))
                    self.root.after(0, lambda: self.log_message("No supported package managers found", "ERROR"))
                else:
                    self.root.after(0, self.update_complete)
                
            except Exception as e:
                error_msg = str(e)
                self.root.after(0, lambda: self.update_failed(error_msg))
                
        threading.Thread(target=update_thread, daemon=True).start()
        
    def update_complete(self):
        """Handle update completion"""
        # Cancel timeout timer
        if self.timeout_timer:
            self.root.after_cancel(self.timeout_timer)
            self.timeout_timer = None
            
        self.progress.stop()
        self.status_label.config(text="Updates completed successfully!")
        self.log_message("All updates completed successfully", "INFO")
        
        # Reset button states
        self.update_all_btn.config(state="normal")
        self.update_btn.config(state="normal")
        self.refresh_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        
        self.refresh_apps()  # Refresh to show new versions
        self.start_auto_close_timer()
        
    def update_failed(self, error):
        """Handle update failure"""
        # Cancel timeout timer
        if self.timeout_timer:
            self.root.after_cancel(self.timeout_timer)
            self.timeout_timer = None
            
        self.progress.stop()
        self.status_label.config(text="Update failed")
        self.close_after_update = False
        self.log_message(f"Update failed: {error}", "ERROR")
        
        # Reset button states
        self.update_all_btn.config(state="normal")
        self.update_btn.config(state="normal")
        self.refresh_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        
        messagebox.showerror("Update Failed", f"Failed to update apps: {error}")
        
    def run(self):
        """Run the application"""
        self.log_message("Application started, performing initial app refresh", "INFO")
        self.refresh_apps()  # Initial app refresh
        
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            self.log_message("Application interrupted by user", "INFO")
        finally:
            self.log_message("Application shutting down", "INFO")


if __name__ == "__main__":
    app = DockAppUpdater()
    app.run()
