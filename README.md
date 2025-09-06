# Dock App Updater

A macOS GUI utility to update non-OS native apps in your dock using various package managers.

## Features

- **GUI Interface**: Clean, intuitive interface built with tkinter
- **Secure Credential Storage**: Stores sudo credentials securely in macOS Keychain using keyring
- **Auto-Close Timer**: Automatically closes after updates unless you interact with the app (10-second timer)
- **Multiple Package Manager Support**:
  - Homebrew (brew)
  - MacPorts (port)
  - npm (Node.js packages)
  - pip awareness (Python packages)
- **App Detection**: Automatically detects non-native apps in your dock
- **Selective Updates**: Update individual apps or all at once

## Requirements

- macOS
- Python 3.6+
- pip3

## Installation

1. Clone this repository:
```bash
git clone <your-repo-url>
cd dock-app-updater
```

2. Install dependencies:
```bash
pip3 install -r requirements.txt
```

## Usage

1. Run the application:
```bash
python3 dock_updater.py
```

2. On first run, click "Set Credentials" to securely store your sudo password
3. Click "Refresh Apps" to scan your dock for non-native apps
4. Select specific apps or use "Update All" to update everything
5. The app will automatically close 10 seconds after updates complete unless you interact with it

## Package Manager Support

The app automatically detects and uses available package managers:

- **Homebrew**: Updates both formulas and casks
- **MacPorts**: Updates ports (requires sudo)
- **npm**: Updates global npm packages
- **pip**: Lists outdated packages (manual update recommended for safety)

## Security

- Sudo credentials are stored securely in macOS Keychain
- Passwords are never displayed in plain text
- Credentials are automatically loaded on app restart

## Auto-Close Feature

After completing updates, the app will:
- Display a 10-second countdown
- Close automatically if you don't interact with it
- Stay open if you click anywhere in the app during the countdown

## License

MIT License - see LICENSE file for details
