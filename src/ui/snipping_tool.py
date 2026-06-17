import tkinter as tk
from tkinter import Canvas
import mss
from PIL import Image

class SnippingTool(tk.Toplevel):
    """
    A transparent overlay window that lets the user draw a rectangle to snip a region of the screen.
    """
    def __init__(self, master, on_snip_callback):
        super().__init__(master)
        self.on_snip_callback = on_snip_callback
        
        self.attributes("-fullscreen", True)
        self.attributes("-alpha", 0.3)
        self.config(bg="black")
        self.configure(cursor="crosshair")
        
        self.canvas = Canvas(self, cursor="crosshair", bg="black")
        self.canvas.pack(fill="both", expand=True)
        
        self.rect = None
        self.start_x = None
        self.start_y = None
        
        self.canvas.bind("<ButtonPress-1>", self.on_button_press)
        self.canvas.bind("<B1-Motion>", self.on_move_press)
        self.canvas.bind("<ButtonRelease-1>", self.on_button_release)
        
        # Press escape to cancel
        self.bind("<Escape>", lambda e: self.destroy())

    def on_button_press(self, event):
        self.start_x = event.x
        self.start_y = event.y
        self.rect = self.canvas.create_rectangle(self.start_x, self.start_y, 1, 1, outline='red', width=2, fill="white")

    def on_move_press(self, event):
        curX, curY = (event.x, event.y)
        self.canvas.coords(self.rect, self.start_x, self.start_y, curX, curY)

    def on_button_release(self, event):
        end_x, end_y = (event.x, event.y)
        
        # Calculate bounding box
        left = min(self.start_x, end_x)
        top = min(self.start_y, end_y)
        width = abs(self.start_x - end_x)
        height = abs(self.start_y - end_y)
        
        self.destroy()
        
        if width > 10 and height > 10:
            # Capture the screen region
            with mss.mss() as sct:
                monitor = {"top": top, "left": left, "width": width, "height": height}
                sct_img = sct.grab(monitor)
                img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
                self.on_snip_callback(img)
