# -*- coding: utf-8 -*-

#### https://stackoverflow.com/questions/41656176/tkinter-canvas-zoom-move-pan

# Advanced zoom example. Like in Google Maps.
# It zooms only a tile, but not the whole image. So the zoomed tile occupies
# constant memory and not crams it with a huge resized image for the large zooms.
from GAPPS_tools.GAPPS_Tool_02d_fid_marks_correction import Main_correction_fid_marks
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import os
import sys
import pandas as pd


absFilePath = os.path.abspath(__file__)
filepath, filename = os.path.split(absFilePath)

sys.path.insert(0, '{}/scriptsAndInterfaces'.format(filepath))


class AutoScrollbar(ttk.Scrollbar):
    ''' A scrollbar that hides itself if it's not needed.
        Works only if you use the grid geometry manager '''

    def set(self, lo, hi):
        if float(lo) <= 0.0 and float(hi) >= 1.0:
            self.grid_remove()
        else:
            self.grid()
            ttk.Scrollbar.set(self, lo, hi)

    def pack(self, **kw):
        raise tk.TclError('Cannot use pack with this widget')

    def place(self, **kw):
        raise tk.TclError('Cannot use place with this widget')


class Zoom_Advanced(ttk.Frame):
    ''' Advanced zoom of the image '''

    def __init__(self, mainframe, dataset, path,p,black_stripe_location):
        ''' Initialize the main Frame '''
        
        print('=============================================================================')
        print('=                             zoom and move                                 =')
        print('= https://stackoverflow.com/questions/41656176/tkinter-canvas-zoom-move-pan =')
        print('=                          A. Maginot (ENSG 2022)                           =')
        print('=============================================================================')
        
        ttk.Frame.__init__(self, master=mainframe)
        self.path = path  # folder path
        self.dataset = dataset
        self.p = p
        self.black_stripe_location = black_stripe_location
        
        self.i = 0
        self.check = pd.read_csv(self.path+'/'+[file for file in os.listdir(self.path) if 'TobeChecked' in file][0])

        print('init\n',self.check)
        #define canvas size
        self.CS = 800
        
        #initialize coordinate default
        self.x = 0
        self.y = 0
        
        # Vertical and horizontal scrollbars for canvas
        vbar = AutoScrollbar(self.master, orient='vertical')
        hbar = AutoScrollbar(self.master, orient='horizontal')
        vbar.grid(row=1, column=1, sticky='ns')
        hbar.grid(row=2, column=0, sticky='we')

        # Create canvas and put image on it
        self.canvas = tk.Canvas(self.master, highlightthickness=0,
                                xscrollcommand=hbar.set, yscrollcommand=vbar.set)
        self.canvas.config(width=self.CS, height=self.CS)
        self.canvas.grid(row=1, column=0, sticky='nswe')
        self.canvas.update()  # wait till canvas is created

        vbar.configure(command=self.scroll_y)  # bind scrollbars to the canvas
        hbar.configure(command=self.scroll_x)


        # get the first image to check
        self.img = os.listdir(self.path+'\cornerToCheck')[0]  # image name
 
        # Header
        self. L = ttk.Label(self.master, text='[1 out of {}] Correcting {} fiducial marks coordinate'.format(len(os.listdir(self.path+'\cornerToCheck')), self.img))
        self.L.grid(row=0)

        # #label for the waiting in the end
        # self.endlabel =ttk.Label(self.master,text="")
        # self.endlabel.grid(sticky='nsew')
        
        # Give a minimum size to the canvas
        self.master.grid_columnconfigure(0, minsize=self.CS)
        self.master.grid_rowconfigure(1, minsize=self.CS)

        # Bind events to the Canvas
        self.canvas.bind('<Configure>', self.show_image)  # canvas is resized
        self.canvas.bind('<ButtonPress-1>', self.move_from)
        self.canvas.bind('<B1-Motion>',     self.move_to)
        
        # with Windows and MacOS, but not Linux
        self.canvas.bind('<MouseWheel>', self.wheel)
        
        # only with Linux, wheel scroll down
        self.canvas.bind('<Button-5>',   self.wheel)
        
        # only with Linux, wheel scroll up
        self.canvas.bind('<Button-4>',   self.wheel)
        self.canvas.bind('<Double-Button-1>', self.clic_pixel)

        self.image = Image.open(r'{}\cornerToCheck\{}'.format(
            self.path, self.img))  # open image
        self.width, self.height = self.image.size

        self.imscale = 1.0  # scale for the canvas image
        self.delta = 1.3  # zoom magnitude

        # Put image into container rectangle and use it to set proper coordinates to the image
        self.container = self.canvas.create_rectangle(
            0, 0, self.width, self.height, width=0)  # ,fill='red')

        # Create cross
        P1 = self.canvas.canvasx(0),  self.canvas.canvasy(
            0)  # get visible area of the canvas
        P2 = self.canvas.canvasx(self.canvas.winfo_width(
        )), self.canvas.canvasy(self.canvas.winfo_height())

        self.circle = self.canvas.create_oval(P1, P2, outline=''),
        self.line1 = self.canvas.create_line(P1, P2, fill=''),
        self.line2 = self.canvas.create_line(
            P1[0], P2[1], P2[0], P1[1], fill='')

        # create right frame
        self.frame = tk.Frame(self.master)
        self.frame.grid(row=1, column=2)

        self.label = ttk.Label(self.frame)
        self.label.grid(row=0)

        self.buttonOk = ttk.Button(
            self.frame, text="ok", command=self.button_ok)
        self.buttonOk.grid(row=1)

        
        self.get_first_img()
        self.show_image()
        
        self.finish()
        

        
    def scroll_y(self, *args, **kwargs):
        ''' Scroll canvas vertically and redraw the image '''
        self.canvas.yview(*args, **kwargs)  # scroll vertically
        self.show_image()  # redraw the image

    def scroll_x(self, *args, **kwargs):
        ''' Scroll canvas horizontally and redraw the image '''
        self.canvas.xview(*args, **kwargs)  # scroll horizontally
        self.show_image()  # redraw the image

    def move_from(self, event):
        ''' Remember previous coordinates for scrolling with the mouse '''
        self.canvas.scan_mark(event.x, event.y)

    def move_to(self, event):
        ''' Drag (move) canvas to the new position '''
        self.canvas.scan_dragto(event.x, event.y, gain=1)
        self.show_image()  # redraw the image

    def wheel(self, event):
        ''' Zoom with mouse wheel '''
        # print("\nzoom +/-")

        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        bbox = self.canvas.bbox(self.container)  # get image area

        if bbox[0] < x < bbox[2] and bbox[1] < y < bbox[3]:
            pass  # Ok! Inside the image
        else:
            return  # zoom only inside image area
        scale = 1.0

        # Respond to Linux (event.num) or Windows (event.delta) wheel event
        if event.num == 5 or event.delta == -120:  # scroll down
            i = min(self.width, self.height)
            if int(i * self.imscale) < 30:
                return  # image is less than 30 pixels
            self.imscale /= self.delta
            scale /= self.delta

        if event.num == 4 or event.delta == 120:  # scroll up
            i = min(self.canvas.winfo_width(), self.canvas.winfo_height())
            if i < self.imscale:
                return  # 1 pixel is bigger than the visible area
            self.imscale *= self.delta
            scale *= self.delta
        # rescale all canvas objects
        self.canvas.scale('all', x, y, scale, scale)
        # print(self.imscale)

        self.show_image()

    def show_image(self, event=None):
        ''' Show image on the Canvas '''
        self.delete_cross()

        bbox1 = self.canvas.bbox(self.container)  # get image area
        # Remove 1 pixel shift at the sides of the bbox1
        bbox1 = (bbox1[0] + 1, bbox1[1] + 1, bbox1[2] - 1, bbox1[3] - 1)
        bbox2 = (self.canvas.canvasx(0),  # get visible area of the canvas
                 self.canvas.canvasy(0),
                 self.canvas.canvasx(self.canvas.winfo_width()),
                 self.canvas.canvasy(self.canvas.winfo_height()))
        bbox = [min(bbox1[0], bbox2[0]), min(bbox1[1], bbox2[1]),  # get scroll region box
                max(bbox1[2], bbox2[2]), max(bbox1[3], bbox2[3])]
        if bbox[0] == bbox2[0] and bbox[2] == bbox2[2]:  # whole image in the visible area
            bbox[0] = bbox1[0]
            bbox[2] = bbox1[2]
        if bbox[1] == bbox2[1] and bbox[3] == bbox2[3]:  # whole image in the visible area
            bbox[1] = bbox1[1]
            bbox[3] = bbox1[3]
        self.canvas.configure(scrollregion=bbox)  # set scroll region
        # get coordinates (x1,y1,x2,y2) of the image tile
        x1 = max(bbox2[0] - bbox1[0], 0)
        y1 = max(bbox2[1] - bbox1[1], 0)
        x2 = min(bbox2[2], bbox1[2]) - bbox1[0]
        y2 = min(bbox2[3], bbox1[3]) - bbox1[1]

        # print('x2 - x1 = ',int(x2 - x1))
        # print('y2 - y1 = ',int(y2 - y1))
        # print(self.canvas.winfo_width(),self.canvas.winfo_height())

        if int(x2 - x1) > 0 and int(y2 - y1) > 0:  # show image if it in the visible area
            # sometimes it is larger on 1 pixel...
            x = min(int(x2 / self.imscale), self.width)
            # ...and sometimes not
            y = min(int(y2 / self.imscale), self.height)
            image = self.image.crop(
                (int(x1 / self.imscale), int(y1 / self.imscale), x, y))
            imagetk = ImageTk.PhotoImage(
                image.resize((int(x2 - x1), int(y2 - y1))))
            imageid = self.canvas.create_image(max(bbox2[0], bbox1[0]),
                                               max(bbox2[1], bbox1[1]),
                                               anchor='nw',
                                               image=imagetk)
            self.canvas.lower(imageid)  # set image into background
            # keep an extra reference to prevent garbage-collection
            self.canvas.imagetk = imagetk

        self.draw_cross()

    def clic_pixel(self, e):
        ''' left clic on image'''
        # coords of image in canvas
        bbox1 = self.canvas.bbox(self.container)  # get image area
        P1x, P1y = bbox1[0], bbox1[1]

        # coords of visible area origine
        P3x, P3y = self.canvas.canvasx(0), self.canvas.canvasy(0)

        # coords of clic in canvas
        Cx = P3x + e.x
        Cy = P3y + e.y

        # coords of clic in image
        x, y = int((Cx-P1x)/self.imscale), int((Cy-P1y)/self.imscale)
        self.x = x
        self.y = y

        #display x and y
        self.label.configure(text='x ={}, y = {}'.format(self.x, self.y))
        print(self.img)


#%%%  (re)draw and delete cross

    def draw_cross(self, event=None):

        P1 = self.canvas.canvasx(0), self.canvas.canvasy(0)  # get visible area of the canvas
        P2 = self.canvas.canvasx(self.canvas.winfo_width(
        )), self.canvas.canvasy(self.canvas.winfo_height())

        self.circle = self.canvas.create_oval(P1, P2, outline='red'),
        self.line1 = self.canvas.create_line(P1, P2, fill='red'),
        self.line2 = self.canvas.create_line(P1[0], P2[1], P2[0], P1[1],
                                             fill='red')

    def delete_cross(self, event=None):
        self.canvas.delete(self.circle)
        self.canvas.delete(self.line1)
        self.canvas.delete(self.line2)


#%%% 

    def finish(self):
        # Check if there are photo to check
        f=0
        for c in self.check:
            if c :
                f+=1
        if f== len(os.listdir(self.path+'\cornerToCheck')):
            self.close()
            

    def get_first_img(self):
        # find the first image to check if the check process has been interupt
        if False in self.check['is Check'].values:
            i=1
            img = self.img.split('.')[0]+'.tif'
            c = self.img.split('.')[1][4:]
            check = self.check.loc[self.check['image'] == img ]
            index = check.loc[self.check['corner'] == c].index[0]
            
            # print(check.loc[self.check['corner'] == c])
            
            while check.loc[index]['is Check']:           
                # print(img, c, index)
                self.next_img()
                self.img = os.listdir(self.path+'/cornerTocheck')[i]
                img = self.img.split('.')[0]+'.tif'
                c = self.img.split('.')[1][4:]
                check = self.check.loc[self.check['image'] == img ]
                index = check.loc[self.check['corner'] == c].index[0]
                i+=1
            
            
            
    def next_img(self):
        
        listdir = os.listdir(self.path+'\cornerToCheck')
        j = listdir.index(self.img)
        j+=1
        if j < len(listdir):
            self.img = listdir[j]
            self.i = self.i+1        
            
            self.image = Image.open(r'{}\cornerToCheck\{}'.format(
                self.path, self.img))  # open image
            self.width, self.height = self.image.size
            
            
            #labels
            self.L.configure(text='[{} out of {}] Correcting {} fiducial marks coordinate'.format(
                        self.i+1, len(os.listdir(self.path+'\cornerToCheck')), self.img))
            
            self.show_image()
        else:
            self.close()
        
        
    def close(self):
        self.canvas.destroy()
        Main_correction_fid_marks(self.dataset, self.path,self.p,self.black_stripe_location)
        self.master.destroy()
        
        print('==========================================')
        print('=           Process Completed            =')
        print('==========================================')


    def button_ok(self):
        
        img = self.img.split('.')[0]+'.tif'
        c = self.img.split('.')[1][4:]
        check = self.check.loc[self.check['image'] == img ]
        index = check.loc[self.check['corner'] == c].index[0]
        
        if False not in list(self.check['is Check']):
            self.close()
        
        if self.x == 0 and self.y == 0  :
            self.label.configure(text='double clic to choose pixel')
            
        elif self.x!=0 and self.y!=0 and not check.loc[index]['is Check']:
            
            #label
            self.label.configure(text='x ={}, y = {}'.format(self.x, self.y))
            
            check.update(pd.Series([True], name='is Check', index=[index]))
            
            self.check.update(check)
            
            # ceate and add line to checked corner file for the current image
            line = pd.DataFrame({
                'image': self.img.split('.')[0],
                'corner': self.img.split('.')[1][4:],
                'corner width': [self.width],
                'corner height': [self.height],
                'x': [self.x],
                'y': [self.y]
            })
            
            self.x =0
            self.y= 0
            
            P = self.path + '/_fiducial_marks_coordinates_'+self.dataset+'_Checked.csv'
            if not os.path.isfile(P):
                line.to_csv(P, mode='w', header=['image', 'corner', 'corner width',
                                                  'corner height', 'x', 'y'], sep=",", index=False)  # append to file

            else:  # else it exists so append without writing the header
                line.to_csv(P, mode='a', header=False,
                            index=False)  # append to file
            
            self.check.to_csv(self.path+'/'+[file for file in os.listdir(self.path) if 'TobeChecked' in file][0])
            
            if False not in list(self.check['is Check']):
                self.close()
            else:
                
                #label
                self.label.configure(text='x ={}, y = {}'.format(self.x, self.y))
                self.next_img()
                
        else:
            self.next_img()
        
        if False not in list(self.check['is Check']):
            self.close()
            
            # print(line)
            

#%%% Main

def check_corners(dataset, path):
    win = tk.Toplevel()
    Zoom_Advanced(win, dataset, path,0.04,'right')
    win.mainloop()


if __name__ == '__main__':

    Path = r'C:\Users\AmelieMaginot\Documents\ING_2\StageMRAC\bot_left_issue\testusumbura\01_CanvasSized'
    dataset = 'Usumbura_1957-58-59'
    Path = r'E:\PROCESSING\SCANS\Dossier_Mohamed\_PROCESSING\A_CanvasSized_Cropped'

    check_corners(dataset, Path)
