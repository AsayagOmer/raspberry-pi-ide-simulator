class BaseComponent:
    def __init__(self, canvas, x, y):
        self.canvas = canvas
        self.x, self.y = x, y
        self.tag = f"comp_{id(self)}"
        self.items = []
        self.connected_to = None

    def draw(self): pass

    def setup_draggable(self, specific_tag=None):
        tag = specific_tag if specific_tag else self.tag
        self.canvas.tag_bind(tag, "<ButtonPress-1>", self.on_drag_start)
        self.canvas.tag_bind(tag, "<B1-Motion>", self.on_drag_motion)
        self.canvas.tag_bind(tag, "<ButtonRelease-1>", self.on_drag_stop)
        self.canvas.tag_bind(tag, "<Enter>", lambda e: self.canvas.config(cursor="fleur"))
        self.canvas.tag_bind(tag, "<Leave>", lambda e: self.canvas.config(cursor=""))

    def on_drag_start(self, event):
        self.drag_x = event.x
        self.drag_y = event.y
        # BUG FIX: By raising each individual item in the order they were appended to self.items,
        # we preserve their relative z-index (e.g. screen text stays on top of the screen rectangle).
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
