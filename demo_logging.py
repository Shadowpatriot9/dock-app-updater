#!/usr/bin/env python3
"""
Demo script to showcase the logging functionality of Dock App Updater
"""

import os
import time
from dock_updater import DockAppUpdater

def demo_logging():
    """Demo the logging functionality without GUI"""
    print("🚀 Dock App Updater - Logging Demo")
    print("=" * 50)
    
    # Create app instance
    app = DockAppUpdater()
    
    # Demo various log messages
    app.log_message("Starting logging demo", "INFO")
    app.log_message("This is an informational message", "INFO")
    app.log_message("This is a warning message", "WARNING")  
    app.log_message("This is an error message", "ERROR")
    app.log_message("This is a debug message", "DEBUG")
    
    # Check if log file exists
    log_file = app.log_file_path
    if os.path.exists(log_file):
        print(f"✅ Log file created at: {log_file}")
        
        # Show last few lines of log
        with open(log_file, 'r') as f:
            lines = f.readlines()
            print(f"\n📝 Last {min(10, len(lines))} log entries:")
            print("-" * 40)
            for line in lines[-10:]:
                print(line.strip())
    else:
        print("❌ No log file found")
    
    # Demonstrate log file size
    if os.path.exists(log_file):
        size = os.path.getsize(log_file)
        print(f"\n📊 Log file size: {size} bytes")
    
    # Close the app
    app.root.quit()
    app.log_message("Logging demo completed", "INFO")
    
    print("\n✨ Demo completed! Check your log file for detailed entries.")
    print(f"Log location: {log_file}")

if __name__ == "__main__":
    demo_logging()
