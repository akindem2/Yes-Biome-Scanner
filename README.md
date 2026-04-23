# Yes Biome Scanner

A comprehensive, multi-account automation and monitoring tool for Roblox, specifically optimized for games like **Sol's RNG**. This program allows you to run multiple Roblox instances, monitor them for rare biomes and merchants, and ensure they stay connected 24/7.

## Key Features

### ◈ Biome & Merchant Detection
- **Log-Based Scanning**: Monitors Roblox log files in real-time to detect biome changes (e.g., Snowy, Rainy, Corruption, Glitched, etc.).
- **Merchant Alerts**: Automatically detects when rare merchants like **Mari**, **Jester**, or **Rin** appear in your server.
- **Multi-Account Support**: Track dozens of accounts simultaneously with a centralized overview panel.

### ◈ Robust Automation
- **Auto-Launcher**: Automatically restarts Roblox instances if they crash or disconnect. It uses your Roblox cookies to join private servers directly.
- **Anti-AFK**: Periodically sends inputs to Roblox windows to prevent the "20-minute idle" disconnect.
- **Auto-Item Manager**: Automates in-game item usage and management (e.g., using Luck Potions or Speed Potions).

### ◈ Performance & Maintenance
- **RAM & CPU Limiting**: Built-in tools to manage system resources, allowing you to run more instances on the same hardware.
- **Log Trimmer & Cleanup**: Automatically deletes old Roblox logs to save disk space and trims active logs to keep the scanner fast.
- **Background Execution (BES)**: Optimizes background instances to further reduce CPU usage.

### ◈ Notifications & UI
- **Discord Webhooks**: Get instant mobile notifications when a rare biome is found or a merchant spawns.
- **Modern Interface**: A sleek PyQt6 UI with multiple customizable themes (Galaxy, Cherry, Mocha, Mint, etc.).
- **Live Status Grid**: See profile pictures, active status, and current biomes for all your accounts at a glance.

---

## Getting Started

### Prerequisites
- Windows OS
- Python 3.10+ (if running from source)
- Roblox accounts and Private Server links

### Installation
1. Clone the repository or download the latest release.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the application:
   ```bash
   python main.py
   ```

### Setup Instructions
1. **General Settings**: Set your Roblox log path (usually `%localappdata%\Roblox\logs`).
2. **Add Accounts**:
   - Go to the **Players** tab.
   - Use the **Cookie Login** button to securely extract your `.ROBLOSECURITY` cookie.
   - Enter your **Private Server (PS) Link**.
3. **Configure Webhooks**: Paste your Discord Webhook URL in the **Webhooks** tab to receive alerts.
4. **Start Scanning**: Click the **Start All** buttons for the Scanner, Auto-Launcher, and Anti-AFK as needed.

---

## Technical Details

- **Language**: Python 3
- **GUI Framework**: PyQt6
- **Interaction**: `pydirectinput`, `pywin32`
- **Detection Method**: Tail-reading Roblox log files (FLogs) for specific string patterns and animation IDs.

## Disclaimer
This tool is for educational purposes. Use of automation tools may violate the Roblox Terms of Service. Use at your own risk.
