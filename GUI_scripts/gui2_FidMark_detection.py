"""
============================================================================
               GAPPS – GeoRiskA Airphoto Pre-Processing Suite
============================================================================
                   = SUB-WINDOW 2 — FidMark Detection =

Description: Graphical User Interface (GUI) to perform the fiducial mark
             (FM) detection automatically, using template matching, and
             manually for the FM that were not detected properly.

GUI Authors: Benoît SMETS   – Royal Museum for Central Africa
                              Vrije Universiteit Brussel
                              (Tervuren / Brussels, BELGIUM)
             Antoine DILLE  – Royal Museum for Central Africa
                              (Tervuren, BELGIUM)
             Amélie MAGINOT – Ecole Nationale des Sciences Géographiques
                              (Marne la Vallée, FRANCE)

Last update: 2024-07-09
============================================================================
"""
from tkinter import *
from tkinter import Tk, Label, Button
from tkinter import filedialog
import os

# import GAPPS tools
from ..GAPPS_tools.GAPPS_Tool_02a_Add_Camera import add_camera
from ..GAPPS_tools.GAPPS_Tool_02b_Tool_FiducialTemplateCreator import fiducialTemplateCreator
from ..GAPPS_tools.GAPPS_Tool_02c_AutomaticFiducialDetection import main_script_02


def open_gui2():
  # make this GUI a function to be called in the main GUI.

  # SECTION 1 — Add camera function
  # ================================

  def add_camera_interface():
    camgui = tk.Tk()

    camgui.title("Add camera model to GAPPS")

    # camera name
    tk.Label(camgui, text="   Camera name (without space):   ").grid(
      row=1, column=0)
    cam = tk.StringVar(camgui)
    camera = tk.Entry(camgui, textvariable=cam)
    camera.grid(row=1, column=1)

    # resolution
    tk.Label(camgui, text="    High resolution:").grid(row=3, column=0)
    resh = tk.IntVar(camgui, value=2000)
    resolution = tk.Entry(camgui, textvariable=resh)
    resolution.grid(row=3, column=1)

    tk.Label(camgui, text="    Low resolution:").grid(row=4, column=0)
    resl = tk.IntVar(camgui, value=600)
    resolution = tk.Entry(camgui, textvariable=resl)
    resolution.grid(row=4, column=1)

    # total length in x
    tk.Label(camgui, text="    Total length X:").grid(row=5, column=0)
    Lux = tk.DoubleVar(camgui)
    resolution = tk.Entry(camgui, textvariable=Lux)
    resolution.grid(row=5, column=1)

    # total length in y
    tk.Label(camgui, text="    Total length Y:").grid(row=6, column=0)
    Luy = tk.DoubleVar(camgui)
    resolution = tk.Entry(camgui, textvariable=Luy)
    resolution.grid(row=6, column=1)

    #  between fiducial marks in x
    tk.Label(camgui, text="    Lenth beetween fiducial marks X:").grid(row=7, column=0)
    FMux = tk.DoubleVar(camgui)
    resolution = tk.Entry(camgui, textvariable=FMux)
    resolution.grid(row=7, column=1)

    # length between fiducial marks in y
    tk.Label(camgui, text="    length beetween fiducial marks Y:").grid(row=8, column=0)
    FMuy = tk.DoubleVar(camgui)
    resolution = tk.Entry(camgui, textvariable=FMuy)
    resolution.grid(row=8, column=1)

    # unit
    u = tk.StringVar(camgui, "Unit")
    tk.OptionMenu(camgui, u, *["cm", "inche"]).grid(row=10, columnspan=2)

    # add camera button
    ttk.Button(camgui, text="Add camera", style='Accent.TButton',
               command=add_camera(camera, resh, resl, Lux, Luy, FMux, FMuy, u)).grid(row=12, columnspan=2)

    tk.Label(camgui, text=" ").grid(row=11, column=1)
    tk.Label(camgui, text=" ").grid(row=13, column=1)
    tk.Label(camgui, text=" ").grid(row=13, column=2)
    tk.Label(camgui, text="   ").grid(row=0, column=2)
    tk.Label(camgui, text=" ").grid(row=9, column=2)


    camera_file = open("../camera_models/camera_list.txt", "r")
    update_list = camera_file.readlines()[0].split(";")
    camera_file.close()

    return update_list

  camgui.mainloop()

  # SECTION 2 — Fiducial template creator function
  # ===============================================

  def interface_fiducial_template():
    templ_gui = tk.Tk()
    templ_gui.title("Fiducial Template creator")
    tk.Label(templ_gui, text=" ").grid(rowspan=15, column=0)
    tk.Label(templ_gui, text=" ").grid(rowspan=15, column=5)
    tk.Label(templ_gui, text=" ").grid(rowspan=15, column=7)

    # Upper (high - H) left corner
    tk.Label(templ_gui, text="Upper left corner coordinates").grid(row=1, column=0, columnspan=2)
    tk.Label(templ_gui, text="X =").grid(row=2, column=0)
    tk.Label(templ_gui, text="Y =").grid(row=3, column=0)
    X1 = tk.IntVar(templ_gui)
    Y1 = tk.IntVar(templ_gui)
    HLx = tk.Entry(templ_gui, textvariable=X1)
    HLy = tk.Entry(templ_gui, textvariable=Y1)
    HLx.grid(row=2, column=1)
    HLy.grid(row=3, column=1)

    # Upper (high - H) right corner
    tk.Label(templ_gui, text="Upper right corner coordinates").grid(row=1, column=3, columnspan=2)
    tk.Label(templ_gui, text="X =").grid(row=2, column=3)
    tk.Label(templ_gui, text="Y =").grid(row=3, column=3)
    X2 = tk.IntVar(templ_gui)
    Y2 = tk.IntVar(templ_gui)
    HRx = tk.Entry(templ_gui, textvariable=X2)
    HRy = tk.Entry(templ_gui, textvariable=Y2)
    HRx.grid(row=2, column=4)
    HRy.grid(row=3, column=4)

    # lower right corner
    tk.Label(templ_gui, text="Lower right corner coordinates").grid(row=9, column=3, columnspan=2)
    tk.Label(templ_gui, text="X =").grid(row=10, column=3)
    tk.Label(templ_gui, text="Y =").grid(row=11, column=3)
    X3 = tk.IntVar(templ_gui)
    Y3 = tk.IntVar(templ_gui)
    LRx = tk.Entry(templ_gui, textvariable=X3)
    LRy = tk.Entry(templ_gui, textvariable=Y3)
    LRx.grid(row=10, column=4)
    LRy.grid(row=11, column=4)

    # lower left corner
    tk.Label(templ_gui, text="Lower left corner coordinates").grid(row=9, column=0, columnspan=2)
    tk.Label(templ_gui, text="X =").grid(row=10, column=0)
    tk.Label(templ_gui, text="Y =").grid(row=11, column=0)
    X4 = tk.IntVar(templ_gui)
    Y4 = tk.IntVar(templ_gui)
    LLx = tk.Entry(templ_gui, textvariable=X4)
    LLy = tk.Entry(templ_gui, textvariable=Y4)
    LLx.grid(row=10, column=1)
    LLy.grid(row=11, column=1)

    # settings
    # half width
    tk.Label(templ_gui, text="half width (int)").grid(row=4, column=2)
    halfwidth = tk.IntVar(templ_gui)
    tk.Entry(templ_gui, textvariable=halfwidth).grid(row=5, column=2)

    # dataset
    tk.Label(templ_gui, text="dataset name (without space)").grid(row=6, column=2)
    dataset = tk.StringVar(templ_gui)
    tk.Entry(templ_gui, textvariable=dataset).grid(row=7, column=2)

    # image
    tk.Label(templ_gui, text="  Input image").grid(row=13, column=0)
    entry_input_images = tk.Entry(templ_gui, width=80)
    entry_input_images.grid(row=13, column=1, columnspan=4)

    tk.Button(templ_gui, text="Select image", command=lambda: find_input_image(
      entry_input_images, "Select image ")).grid(row=13, column=6)

    # folders
    tk.Label(templ_gui, text="  Output data folder").grid(row=14, column=0)
    entry_output_folder = tk.Entry(templ_gui, width=80)
    entry_output_folder.grid(row=14, column=1, columnspan=4)

    tk.Button(templ_gui, text="Select folder", command=lambda: find_output_folder(
      entry_output_folder, "Select output directory")).grid(row=14, column=6)

    global path
    path = "./"

    def find_input_image(e, text):
      global path
      templ_gui.filename = filedialog.askopenfilename(initialdir=path, title=text)
      path = templ_gui.filename
      e.insert(0, templ_gui.filename)
      input_image.append(path)

    def find_output_folder(e, text):
      global path
      templ_gui.filename = filedialog.askdirectory(initialdir=path, title=text)
      path = templ_gui.filename
      e.insert(0, templ_gui.filename)
      output_folder.append(path)

    input_image = []
    output_folder = []

    def CreateTemplate():
      fiducialCenters = {'top_left': [X1.get(), Y1.get()],
                         'top_right': [X2.get(), Y2.get()],
                         'bot_right': [X3.get(), Y3.get()],
                         'bot_left': [X4.get(), Y4.get()]}
      print("interface fidcenter: {}".format(X1.get()))
      w = halfwidth.get()
      d = dataset.get()

      fiducialTemplateCreator(input_image[0], output_folder[0], fiducialCenters, w, d)
      sleep(1)
      root.destroy()

    tk.Label(root, text=" ").grid(row=12)
    tk.Label(root, text=" ").grid(row=15)
    tk.Label(root, text=" ").grid(row=17)

    ttk.Button(root, text="Create fiducial template",
               command=CreateTemplate()).grid(row=16, column=2)

    root.mainloop()

  # SECTION 3 — Manual Fiducial Mark Detection function
  # ====================================================



  # SECTION 4 — FM Detection Graphical User Interface (GUI)
  # ===========================================

  # Create the main window
  gui2 = Tk()
  gui2.title("GAPPS — Fiducial Mark Detection tools")
  gui2.geometry("600x420")  # Set window size (width x height)

  # Subtitle
  subtitle = Label(gui2, text="Fiducial Mark Detection Tools", font=("Arial", 24, "bold"), fg="black")
  subtitle.pack(pady=10)

  # Camera model (pre-existing)
  camera_file = open("../camera_models/camera_list.txt", "r")
  camera_value_list = camera_file.readlines()[0].split(";")
  camera_file.close()
       # Clean camera model names (optional)
  camera_models = [model.strip() for model in camera_value_list]
       # Label camera model
  label_cam_model = Label(gui2, text="Camera model: ", font=("Arial", 16), fg="black")
  label_cam_model.pack(pady=5)
       # Define a variable to store the selected model
  selected_camera_model = tk.StringVar(gui2)
       # Create the option menu
  camMenu = OptionMenu(gui2, selected_camera_model, *camera_models)
  camMenu.pack(pady=5)

  # Add new camera model
  subsubtitle1 = Label(gui2, text="1. Add new camera model (optional)", font=("Arial", 20, "bold"), fg="black")
  subsubtitle1.config(justify='left')
  subsubtitle1.pack(pady=10)

  button1 = Button(gui2, text='Create new camera model', command=add_camera, font=("Arial", 16), pady=10)
  for text, script_name in button1:
    button = Button(gui2, text=text, command=lambda script=script_name: open_new_gui(script), font=("Arial", 16), pady=10)
    button.pack()



  # Add copyright label at the bottom using grid with sticky option
  copyright_label = Label(gui2, text="© Royal Museum for Central Africa / Vrije Universiteit Brussel, 2020-2024. This software is released under the MIT license.",
                           font=("Arial", 9, "italic"), fg="gray")
  copyright_label.pack(side="bottom")

  # Run the main loop
  gui2.mainloop()