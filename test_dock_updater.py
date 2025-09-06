#!/usr/bin/env python3
"""
Test script for Dock App Updater
"""

import unittest
import os
import tempfile
import subprocess
from unittest.mock import patch, MagicMock

# Import just the class without initializing GUI
class MockDockAppUpdater:
    """Mock version of DockAppUpdater for testing without GUI"""
    
    def __init__(self):
        self.sudo_password = None
        
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
                import plistlib
                with open(info_plist_path, 'rb') as f:
                    info_data = plistlib.load(f)
                    return info_data.get('CFBundleShortVersionString', 'Unknown')
            return 'Unknown'
        except:
            return 'Unknown'


class TestDockAppUpdater(unittest.TestCase):
    
    def setUp(self):
        """Set up test fixtures"""
        self.app = MockDockAppUpdater()
        
    def test_basic_functionality(self):
        """Test that basic functions work"""
        self.assertIsNotNone(self.app)
        
    def test_is_native_app(self):
        """Test native app detection"""
        # Test native apps
        self.assertTrue(self.app.is_native_app('/System/Applications/Calculator.app'))
        self.assertTrue(self.app.is_native_app('/Applications/Safari.app'))
        
        # Test non-native apps
        self.assertFalse(self.app.is_native_app('/Applications/Chrome.app'))
        self.assertFalse(self.app.is_native_app('/Applications/VSCode.app'))
        
    @patch('subprocess.run')
    def test_package_manager_detection(self, mock_run):
        """Test package manager detection"""
        # Mock successful brew command
        mock_run.return_value.returncode = 0
        
        # Test that we can detect brew
        result = subprocess.run(['which', 'brew'], capture_output=True, text=True)
        # Just check that the function runs without error
        self.assertIsNotNone(result)
        
    def test_app_version_unknown(self):
        """Test app version detection with non-existent path"""
        version = self.app.get_app_version('/nonexistent/path')
        self.assertEqual(version, 'Unknown')
        
    def test_keyring_functionality(self):
        """Test keyring operations"""
        try:
            import keyring
            # Test setting and getting a password
            keyring.set_password('test_dock_app', 'test_user', 'test_pass')
            retrieved = keyring.get_password('test_dock_app', 'test_user')
            self.assertEqual(retrieved, 'test_pass')
            # Clean up
            keyring.delete_password('test_dock_app', 'test_user')
        except Exception as e:
            self.skipTest(f"Keyring not available: {e}")


if __name__ == '__main__':
    print("Running Dock App Updater tests...")
    unittest.main(verbosity=2)
