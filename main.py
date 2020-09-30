from functools import partial
import signal

from pywayland import lib
from pywayland.server import Display

from wlroots.backend import Backend
from wlroots.renderer import Renderer

from compositor import Compositor

def signalInt(display, signalNumber, frame):
    print("SIGINT Received")
    display.terminate()

def main():
    with Display() as display:
        signal.signal(signal.SIGINT, partial(signalInt, display))
        with Backend(display) as backend:
            renderer = Renderer(backend, display)
            compositor = Compositor(display, backend, renderer)
            backend.start()
            display.run()
            display.destroy()

main()
