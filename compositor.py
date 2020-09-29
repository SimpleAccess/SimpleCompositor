from pywayland.server import (Display, EventLoop, Listener)
from wlroots.backend import Backend
from wlroots.util.clock import Timespec

import random
class Compositor:
    def __init__(self, display, backend, renderer):
        self.display = display
        self.eventLoop = display.get_event_loop()
        self.backend = backend
        self.renderer = renderer
        self.outputs = []
        self.counter = 20
        self.color = [0.0,0.0,0.0,0.0]

        backend.new_output_event.add(Listener(self.serverNewOutput))

    def serverNewOutput(self, listener, output):
        if output.modes != []:
            mode = output.preferred_mode()
            if mode is None:
                print("Didn't Get Any Output Modes")
                return
            output.set_mode(mode)
            output.enable()
            if not output.commit():
                print("Failed to Commit Output")
                return

        self.outputs.append(output)
        output.destroy_event.add(Listener(self.serverDestroyOutput))
        output.frame_event.add(Listener(self.serverDrawFrame))

    def serverDestroyOutput(self, listener, output):
        for index in range(len(self.outputs)):
            if self.outputs[index] == output:
                self.outputs.remove(index)
                return
    
    def serverDrawFrame(self, listerer, data):
        now = Timespec.get_monotonic_time()
        output = self.outputs[0]
        if not output.attach_render():
            print("could not attach renderer")
            return
        width, height = output.effective_resolution()

        self.renderer.begin(width, height)

        if self.counter >= 20:
            self.color = [random.random(),random.random(),random.random(),1.0]
            self.counter = 0
        else:
            self.counter += 1

        self.renderer.clear(self.color)

        self.renderer.end()
        output.commit()