# Creation of a user-friendly GAPPS Launcher for Linux (Ubuntu 22.04 LTS)

This guide explains how to create a user-friendly launcher for GAPPS on Linux (Ubuntu 22.04 LTS). The launcher will allow users to easily start the GAPPS application from a desktop launcher without needing to use the command line.

## Step 1: Create a Desktop Entry File

1.1. Open a text editor and create a new file named `GAPPS.desktop` in your Desktop folder. You can use any text editor, such as `gedit`, `nano`, or `vim`.

1.2. Copy the following lines into the `gapps.desktop` file, replacing `/absolute/path/to/GAPPS` with the actual path to your GAPPS installation directory:
```INI
[Desktop Entry]
Name=GAPPS
Comment=Launch GAPPS
Exec=/absolute/path/to/GAPPS/.venv/bin/python /absolute/path/to/GAPPS/run_gapps.py
Icon=/absolute/path/to/GAPPS/assets/GAPPS_icon.png
Terminal=true
Type=Application
Categories=Science;Heritage;Utility;
StartupNotify=true
```

1.3. Save the file and close the text editor.

## Step 2: Make the Desktop Entry Executable

Make GAPPS.desktop executable by running the following command in the terminal:
```bash
sudo chmod +x ~/Desktop/gapps.desktop
```

## Step 3: Allow Launching from the Desktop
Right-click on the `GAPPS.desktop` file on your desktop and select "Allow Launching" from the context menu. This will allow you to launch GAPPS by double-clicking the icon.
