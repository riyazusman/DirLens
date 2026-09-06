# DirLens

A lightweight, high-performance disk space analyzer that generates clean, interactive HTML reports. Built entirely with standard Python libraries, DirLens is designed for speed, stability, and ease of use.

## Features

* **High Performance:** Utilizes `os.scandir` and memory-efficient heap queues for rapid scanning of massive directory structures.
* **Interactive HTML Report:** Automatically generates a minimalist, responsive web report featuring a collapsible folder tree.
* **Deep Insights:** Instantly identifies the Top 10 largest files, Top 10 largest folders (by exclusive size), and Top 10 file types.
* **UX Focused:** Includes click-to-copy buttons for all file and folder paths directly within the UI.
* **Robust Path Handling:** Automatically bypasses Windows 260-character path limits and cleanly formats UNC network paths.
* **Smart Elevation:** Features a graceful, built-in UAC elevation prompt on Windows to scan restricted system folders.
* **Zero Dependencies:** Requires no third-party packages to run the source code.

## Requirements

* Python 3.x

## Usage

You can run DirLens directly from the terminal. If no path is provided, the script will open an interactive prompt.

**Interactive Mode:**
```bash
python dirlens.py
```

**CLI Mode:**
```bash
python dirlens.py "C:\Your\Target\Directory"
```

Once the scan is complete, DirLens will automatically generate a timestamped HTML file (e.g., dirlens_report_20260906_143000.html) and open it in your default web browser.

## Building a Standalone Executable
If you want to run DirLens on machines without Python installed, you can easily package it into a standalone .exe using PyInstaller.

1. Install PyInstaller:
```bash
pip install pyinstaller
```

2. Build the executable:

```bash
pyinstaller --onefile --icon=dirlens.ico dirlens.py
```

The compiled executable will be located in the dist folder.

Latest compiled windows executable can be downloaded from Releases.

**Interactive Mode:**
```bash
dirlens.exe
```

**CLI Mode:**
```bash
dirlens.exe "C:\Your\Target\Directory"
```
