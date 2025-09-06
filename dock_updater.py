#!/usr/bin/env python3
"""
Dock App Updater - A utility to update non-OS native apps in macOS dock
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import threading
import subprocess
import time
import os
import plistlib
import keyring
import psutil
from pathlib import Path


class DockAppUpdater:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Dock App Updater")
        self.root.geometry("600x400")
        
        # Auto-close timer variables
        self.auto_close_timer = None
        self.user_interacted = False
        self.close_after_update = False
        
        # Bind focus and click events to detect user interaction
        self.root.bind('<Button-1>', self.on_user_interaction)
        self.root.bind('<Key>', self.on_user_interaction)
        self.root.bind('<FocusIn>', self.on_user_interaction)
        
        self.setup_ui()
        self.load_sudo_credentials()
        
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
        
        # Treeview for apps
        self.app_tree = ttk.Treeview(list_frame, columns=("name", "version", "status"), show="headings")
        self.app_tree.heading("name", text="App Name")
        self.app_tree.heading("version", text="Version")
        self.app_tree.heading("status", text="Status")
        
        # Scrollbar for treeview
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.app_tree.yview)
        self.app_tree.configure(yscrollcommand=scrollbar.set)
        
        self.app_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=2, column=0, columnspan=2, pady=(0, 10))
        
        # Buttons
        self.refresh_btn = ttk.Button(button_frame, text="Refresh Apps", command=self.refresh_apps)
        self.refresh_btn.grid(row=0, column=0, padx=(0, 10))
        
        self.update_btn = ttk.Button(button_frame, text="Update Selected", command=self.update_selected_apps)
        self.update_btn.grid(row=0, column=1, padx=(0, 10))
        
        self.update_all_btn = ttk.Button(button_frame, text="Update All", command=self.update_all_apps)
        self.update_all_btn.grid(row=0, column=2, padx=(0, 10))
        
        self.creds_btn = ttk.Button(button_frame, text="Set Credentials", command=self.set_sudo_credentials)
        self.creds_btn.grid(row=0, column=3)
        
        # Progress bar
        self.progress = ttk.Progressbar(main_frame, mode='indeterminate')
        self.progress.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # Status label
        self.status_label = ttk.Label(main_frame, text="Ready")
        self.status_label.grid(row=4, column=0, columnspan=2)
        
        # Configure grid weights
        main_frame.rowconfigure(1, weight=1)
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
            else:
                self.status_label.config(text="No sudo credentials found. Click 'Set Credentials' to add them.")
        except Exception as e:
            self.sudo_password = None
            self.status_label.config(text="Error loading credentials")
            
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
                else:
                    messagebox.showerror("Error", "Invalid sudo password")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save credentials: {str(e)}")
                
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
        
        def refresh_thread():
            apps = self.get_dock_apps()
            self.root.after(0, lambda: self.update_app_list(apps))
            
        threading.Thread(target=refresh_thread, daemon=True).start()
        
    def update_app_list(self, apps):
        """Update the app list in the UI"""
        # Clear existing items
        for item in self.app_tree.get_children():
            self.app_tree.delete(item)
            
        # Add new items
        for app in apps:
            status = "Ready for update"
            self.app_tree.insert("", "end", values=(app['name'], app['version'], status))
            
        self.progress.stop()
        self.status_label.config(text=f"Found {len(apps)} non-native apps")
        
    def update_selected_apps(self):
        """Update selected apps"""
        selection = self.app_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select apps to update")
            return
            
        self.perform_updates([self.app_tree.item(item)['values'][0] for item in selection])
        
    def update_all_apps(self):
        """Update all apps"""
        app_names = [self.app_tree.item(item)['values'][0] for item in self.app_tree.get_children()]
        if not app_names:
            messagebox.showinfo("Info", "No apps to update")
            return
            
        self.perform_updates(app_names)
        
    def perform_updates(self, app_names):
        """Perform updates for specified apps"""
        if not self.sudo_password:
            messagebox.showerror("Error", "Please set sudo credentials first")
            return
            
        self.status_label.config(text="Updating apps...")
        self.progress.start()
        self.close_after_update = True
        
        def update_thread():
            try:
                updated_something = False
                
                # Check if Homebrew is available
                result = subprocess.run(['which', 'brew'], capture_output=True, text=True)
                if result.returncode == 0:
                    self.root.after(0, lambda: self.status_label.config(text="Updating Homebrew packages..."))
                    # First update Homebrew itself
                    subprocess.run(['brew', 'update'], check=True)
                    # Then upgrade packages
                    subprocess.run(['brew', 'upgrade'], check=True)
                    # Also check for casks
                    subprocess.run(['brew', 'upgrade', '--cask'], check=True)
                    updated_something = True
                    
                # Check if MacPorts is available
                result = subprocess.run(['which', 'port'], capture_output=True, text=True)
                if result.returncode == 0:
                    self.root.after(0, lambda: self.status_label.config(text="Updating MacPorts packages..."))
                    # Update MacPorts
                    subprocess.run(['sudo', '-S', 'port', 'selfupdate'], 
                                 input=f"{self.sudo_password}\n", text=True, check=True)
                    subprocess.run(['sudo', '-S', 'port', 'upgrade', 'outdated'], 
                                 input=f"{self.sudo_password}\n", text=True, check=True)
                    updated_something = True
                    
                # Check if pip is available for Python packages
                result = subprocess.run(['which', 'pip3'], capture_output=True, text=True)
                if result.returncode == 0:
                    self.root.after(0, lambda: self.status_label.config(text="Updating pip packages..."))
                    subprocess.run(['pip3', 'list', '--outdated', '--format=freeze'], check=True)
                    # Note: We don't auto-upgrade pip packages as it can break system
                    
                # Check if npm is available
                result = subprocess.run(['which', 'npm'], capture_output=True, text=True)
                if result.returncode == 0:
                    self.root.after(0, lambda: self.status_label.config(text="Updating npm packages..."))
                    subprocess.run(['npm', 'update', '-g'], check=True)
                    updated_something = True
                    
                if not updated_something:
                    self.root.after(0, lambda: self.update_failed("No supported package managers found"))
                else:
                    self.root.after(0, self.update_complete)
                
            except Exception as e:
                self.root.after(0, lambda: self.update_failed(str(e)))
                
        threading.Thread(target=update_thread, daemon=True).start()
        
    def update_complete(self):
        """Handle update completion"""
        self.progress.stop()
        self.status_label.config(text="Updates completed successfully!")
        self.refresh_apps()  # Refresh to show new versions
        self.start_auto_close_timer()
        
    def update_failed(self, error):
        """Handle update failure"""
        self.progress.stop()
        self.status_label.config(text="Update failed")
        self.close_after_update = False
        messagebox.showerror("Update Failed", f"Failed to update apps: {error}")
        
    def run(self):
        """Run the application"""
        self.refresh_apps()  # Initial app refresh
        self.root.mainloop()


if __name__ == "__main__":
    app = DockAppUpdater()
    app.run()
