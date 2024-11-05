"""
============================================================================
               GAPPS – GeoRiskA Airphoto Pre-Processing Suite
============================================================================
                     = SUB-WINDOW 1 — Canvas sizing =

Description: Secondary Graphical User Interface (GUI) to perform the canvas
             sizing, i.e., adding lines and columns of black pixels to get
             all the scanned images with the same width and height. This
             tool is optional if you are sure that all the scanned images
             have the same pixel dimensions.

GUI Author: Benoît SMETS   – Royal Museum for Central Africa
                             Vrije Universiteit Brussel
                             (Tervuren / Brussels, BELGIUM)

Last update: 2024-07-09
============================================================================
"""

from tkinter import *
from tkinter import filedialog
import os

def open_gui1():
  # make this GUI a function to be called in the main GUI.

  # SECTION 1 — secondary GUI functions
  # ====================================

  def browse_folder(folder_entry, folder_type):
    """
    Opens a file dialog and sets the selected path in the corresponding entry field.

    Args:
        folder_entry (Entry): The entry widget where the path will be stored.
        folder_type (str): "Input" or "Output" to display a specific message.
    """
    filename = os.path.dirname(os.path.abspath(__file__))  # Initial directory
    if folder_type == "Input":
      folder_path = filedialog.askdirectory(initialdir=filename, title="Select Input Folder")
    else:
      folder_path = filedialog.askdirectory(initialdir=filename, title="Select Output Folder")
    if folder_path:
      folder_entry.delete(0, END)
      folder_entry.insert(0, folder_path)

  def launch_script():
    """
    Validates folder paths and launches the external script.

    This function checks if both input and output folder paths are provided.
    If valid, it calls the external script (replace 'your_script.py' with the actual script name)
    passing the folder paths as arguments. You'll need to modify this part to fit your specific script.
    """
    input_folder = input_entry.get()
    output_folder = output_entry.get()
    if input_folder and output_folder:
      # Replace 'your_script.py' with the actual script name and argument passing logic
      os.system(f"python ../GAPPS_tools/GAPP_Script_01_AirPhoto_CanvasSizing.py {input_folder} {output_folder}")
    else:
      messagebox.showerror("Error", "Please specify both Input and Output folders.")

  # SECTION 2 — Graphical User Interface (GUI)
  # ===========================================

  # Create the main window
  gui1 = Tk()
  gui1.title("GAPPS — Canvas Sizing")
  gui1.geometry("600x420")  # Set window size (width x height)

  # Subtitle
  subtitle = Label(gui1, text="Canvas Sizing Tool", font=("Arial", 24, "bold"), fg="black")
  subtitle.pack(pady=10)

  # Description Text
  description_text = Label(gui1, text="This script checks if all images have the same width and height. If not, it will add pixel columns and/or lines to standardize the size.", wraplength=300, font=("Arial", 14, "italic"), pady=15, fg="black")
  description_text.pack()

  # Input Folder Entry
  input_label = Label(gui1, text="Input Folder:", fg="black", pady=5)
  input_label.pack()
  input_entry = Entry(gui1)
  input_entry.pack()
  input_button = Button(gui1, text="Browse", command=lambda: browse_folder(input_entry, "Input"))
  input_button.pack()

  # Output Folder Entry
  output_label = Label(gui1, text="Output Folder:", fg="black", pady=5)
  output_label.pack()
  output_entry = Entry(gui1)
  output_entry.pack()
  output_button = Button(gui1, text="Browse", command=lambda: browse_folder(output_entry, "Output"))
  output_button.pack()

  # OK Button
  ok_button = Button(gui1, text="OK", command=launch_script, font=("Arial", 20))
  ok_button.pack(pady=30)

  # Add copyright label at the bottom using grid with sticky option
  copyright_label = Label(gui1, text="© Royal Museum for Central Africa / Vrije Universiteit Brussel, 2020-2024. This software is released under the MIT license.",
                           font=("Arial", 9, "italic"), fg="gray")
  copyright_label.pack(side="bottom")

  # Run the main loop
  gui1.mainloop()

### END OF SCRIPT ###