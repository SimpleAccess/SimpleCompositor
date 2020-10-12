from pywayland.server import Listener

class View:
    def __init__(self, xdgSurface, server):
        self.xdgSurface = xdgSurface
        self.server = server
        self.mapped = False
        self.x = 0.0
        self.y = 0.0

        xdgSurface.map_event.add(Listener(self.xdgSurfaceMap))
        xdgSurface.unmap_event.add(Listener(self.xdgSurfaceUnmap))
        xdgSurface.destroy_event.add(Listener(self.xdgSurfaceDestroy))

    def xdgSurfaceMap(self, listener, data):
        self.mapped = True
        self.server.focusView(self)

    def xdgSurfaceUnmap(self, listener, data):
        self.mapped = False

    def xdgSurfaceDestroy(self, listener, data):
        self.server.views.remove(self)
    def viewAt(self, layoutX, layoutY):
        viewX = layoutX - self.x
        viewY = layoutY - self.y
        return self.xdgSurface.surface_at(viewX, viewY)

    