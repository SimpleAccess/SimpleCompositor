from pywayland.server import Listener

class LayerView:
    def __init__(self, layerShell, server):
        self.layerShell = layerShell
        self.server = server
        self.mapped = False
        self.x = 0.0
        self.y = 0.0

        layerShell.map_event.add(Listener(self.layerShellMap))
        layerShell.unmap_event.add(Listener(self.layerShellUnmap))
        layerShell.destroy_event.add(Listener(self.layerShellDestroy))

    def layerShellMap(self, listener, data):
        self.mapped = True
        self.server.focusView(self)

    def layerShellUnmap(self, listener, data):
        self.mapped = False

    def layerShellDestroy(self, listener, data):
        self.server.views.remove(self)
        
    def layerViewAt(self, layoutX, layoutY):
        layerX = layoutX - self.x
        layerY = layoutY - self.y
        return self.layerShell.surface_at(layerX, layerY)