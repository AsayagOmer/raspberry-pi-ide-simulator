class BaseComponent:
    def __init__(self, canvas, x, y):
        self.canvas = canvas
        self.app = canvas.winfo_toplevel()
        self.x, self.y = x, y
        self.rotation = 0 # 0, 90, 180, 270
        self.tag = f"comp_{id(self)}"
        self.items = []
        self.connected_to = None

    def draw(self): pass

    def get_ports(self):
        """Return a list of port definitions for this component.

        Each port is a dict with keys:
          name      – unique port identifier (e.g. "gpio_header")
          direction – "in" (accepts connections) or "out" (initiates connections)
          x, y      – current canvas position of the port
        Override in subclasses.
        """
        return []

    def snap_port_to(self, port_name, target_x, target_y):
        """Move the component so that *port_name* is at (target_x, target_y).

        Override in subclasses to implement port-specific snap behavior.
        """
        pass

    def redraw(self):
        for item in self.items:
            self.canvas.delete(item)
        self.items = []
        self.draw()

    def delete(self):
        for item in self.items:
            self.canvas.delete(item)
        if self in getattr(self.app, 'components', []):
            self.app.components.remove(self)
        if getattr(self.app, 'hovered_component', None) == self:
            self.app.hovered_component = None
        
    def rotate(self, event=None):
        self.rotation = (self.rotation + 90) % 360
        self.redraw()
        self.app.save_hardware_state()

    def setup_draggable(self, specific_tag=None):
        tag = specific_tag if specific_tag else self.tag
        self.canvas.tag_bind(tag, "<ButtonPress-1>", self.on_drag_start)
        self.canvas.tag_bind(tag, "<B1-Motion>", self.on_drag_motion)
        
        def on_drag_stop_wrapper(e):
            if hasattr(self, 'on_drag_stop'): self.on_drag_stop(e)
            self.app.save_hardware_state()
            
        self.canvas.tag_bind(tag, "<ButtonRelease-1>", on_drag_stop_wrapper)
        # Right click to rotate
        self.canvas.tag_bind(tag, "<Button-3>", self.rotate)
        def on_enter(e):
            self.canvas.config(cursor="fleur")
            self.app.hovered_component = self
        def on_leave(e):
            self.canvas.config(cursor="")
            if getattr(self.app, 'hovered_component', None) == self:
                self.app.hovered_component = None
        self.canvas.tag_bind(tag, "<Enter>", on_enter)
        self.canvas.tag_bind(tag, "<Leave>", on_leave)

    def _get_z(self):
        return getattr(self.app, 'zoom_factor', 1.0)

    def _rot_pt(self, rx, ry):
        if self.rotation == 90: return self.h - ry, rx
        elif self.rotation == 180: return self.w - rx, self.h - ry
        elif self.rotation == 270: return ry, self.w - rx
        return rx, ry

    def _scale_kwargs(self, kwargs, z):
        if 'width' in kwargs:
            kwargs['width'] = max(1, int(float(kwargs['width']) * z))
        if 'font' in kwargs:
            f = kwargs['font']
            new_size = max(1, int(f[1] * z))
            if len(f) == 3: kwargs['font'] = (f[0], new_size, f[2])
            else: kwargs['font'] = (f[0], new_size)
        if 'tags' not in kwargs: kwargs['tags'] = self.tag

    def _rect(self, rx, ry, rw, rh, **kwargs):
        if self.rotation == 90:
            x1, y1, w, h = self.h - ry - rh, rx, rh, rw
        elif self.rotation == 180:
            x1, y1, w, h = self.w - rx - rw, self.h - ry - rh, rw, rh
        elif self.rotation == 270:
            x1, y1, w, h = ry, self.w - rx - rw, rh, rw
        else:
            x1, y1, w, h = rx, ry, rw, rh
        
        z = self._get_z()
        x1, y1, w, h = x1*z, y1*z, w*z, h*z
        self._scale_kwargs(kwargs, z)
        item = self.canvas.create_rectangle(self.x+x1, self.y+y1, self.x+x1+w, self.y+y1+h, **kwargs)
        self.items.append(item)
        return item

    def _oval(self, rx, ry, rw, rh, **kwargs):
        if self.rotation == 90:
            x1, y1, w, h = self.h - ry - rh, rx, rh, rw
        elif self.rotation == 180:
            x1, y1, w, h = self.w - rx - rw, self.h - ry - rh, rw, rh
        elif self.rotation == 270:
            x1, y1, w, h = ry, self.w - rx - rw, rh, rw
        else:
            x1, y1, w, h = rx, ry, rw, rh
            
        z = self._get_z()
        x1, y1, w, h = x1*z, y1*z, w*z, h*z
        self._scale_kwargs(kwargs, z)
        item = self.canvas.create_oval(self.x+x1, self.y+y1, self.x+x1+w, self.y+y1+h, **kwargs)
        self.items.append(item)
        return item

    def _text(self, rx, ry, text, **kwargs):
        px, py = self._rot_pt(rx, ry)
        z = self._get_z()
        px, py = px*z, py*z
        
        angle = (kwargs.pop('angle', 0) + self.rotation) % 360
        self._scale_kwargs(kwargs, z)
        item = self.canvas.create_text(self.x+px, self.y+py, text=text, angle=angle, **kwargs)
        self.items.append(item)
        return item

    def _window(self, rx, ry, **kwargs):
        px, py = self._rot_pt(rx, ry)
        z = self._get_z()
        px, py = px*z, py*z
        self._scale_kwargs(kwargs, z)
        item = self.canvas.create_window(self.x+px, self.y+py, **kwargs)
        self.items.append(item)
        return item

    def on_drag_start(self, event):
        self.drag_x = event.x
        self.drag_y = event.y
        for item in self.items:
            self.canvas.tag_raise(item)

    def on_drag_motion(self, event):
        dx = event.x - self.drag_x
        dy = event.y - self.drag_y
        self.canvas.move(self.tag, dx, dy)
        self.drag_x = event.x
        self.drag_y = event.y
        self.x += dx
        self.y += dy

    def on_drag_stop(self, event):
        pass
