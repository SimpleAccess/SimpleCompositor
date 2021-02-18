from pywayland.server import Listener
from wlroots import ffi, lib

class LayerView:
    def __init__(self, layerShell, server):
        self.layerShell = layerShell
        self.server = server
        self.mapped = False
        self.x = 0.0
        self.y = 0.0

        self.layerShell._ptr.output = server.outputs[0]._ptr
        lib.wlr_layer_surface_v1_configure(self.layerShell._ptr,self.layerShell._ptr.current.desired_width,self.layerShell._ptr.current.desired_height)
        layerShell.map_event.add(Listener(self.layerShellMap))
        layerShell.unmap_event.add(Listener(self.layerShellUnmap))
        layerShell.destroy_event.add(Listener(self.layerShellDestroy))

    def layerShellMap(self, listener, data):
        self.mapped = True
        self.server.focusLayerView(self)

    def layerShellUnmap(self, listener, data):
        self.mapped = False

    def layerShellDestroy(self, listener, data):
        self.server.layerViews.remove(self)
        
    def layerViewAt(self, layoutX, layoutY):
        layerX = layoutX - self.x
        layerY = layoutY - self.y
        return self.layerShell.surface_at(layerX, layerY)