from pywayland.server import (Display, EventLoop, Listener)
from pywayland.protocol.wayland import WlSeat
from wlroots.backend import Backend
from wlroots.util.clock import Timespec
from wlroots import ffi, lib
from wlroots.wlr_types.xdg_shell import XdgSurface, XdgSurfaceRole
from wlroots.wlr_types.input_device import ButtonState, InputDeviceType



from wlroots.wlr_types.keyboard import KeyState, KeyboardModifier

from wlroots.wlr_types import (
    Box,
    Matrix,
    Output,
    Compositor,
    InputDevice,
    Keyboard
)


from xkbcommon import xkb

from keyboardHandler import KeyboardHandler
from layerView import LayerView
from view import View
from cursorMode import CursorMode

import os

def get_keysyms(xkb_state, keyCode):
    syms_out = ffi.new("const xkb_keysym_t **")
    nsyms = lib.xkb_state_key_get_syms(xkb_state, keyCode, syms_out)
    if nsyms > 0:
        assert syms_out[0] != ffi.NULL
        
    syms = [syms_out[0][i] for i in range(nsyms)]
    print(f"[IN] got {nsyms} syms: {syms}")
    return syms



import random
class SimpleAccessWM:
    def __init__(self, display, backend, renderer, xdgShell, outputLayout, cursor, xCursorManager, seat, layerShell):
        self.display = display
        self.socket = self.display.add_socket()
        print(f"[OUT] Compositor is running on wayland display {str(self.socket)}")
        os.environ['WAYLAND_DISPLAY'] = str(self.socket)
        self.display.init_shm()
        self.eventLoop = display.get_event_loop()
        self.backend = backend
        self.renderer = renderer
        self.xdgShell = xdgShell
        self.outputLayout = outputLayout
        self.cursor = cursor
        self.cursorManager = xCursorManager
        self.seat = seat
        self.cursor_mode = CursorMode.PASSTHROUGH
        self.grabbed_view = None
        self.grab_x = 0.0
        self.grab_y = 0.0
        self.grab_geobox = None
        self.layerShell = layerShell
        
        self.keyboards = []
        
        self.views = []
        self.layerViews = []
        self.outputs = []
        self.color = [0.75,0.75,0.75,1.0]

        xdgShell.new_surface_event.add(Listener(self.serverNewXdgSurface))

        layerShell.new_surface_event.add(Listener(self.serverNewLayerShell))

        backend.new_output_event.add(Listener(self.serverNewOutput))

        cursor.motion_event.add(Listener(self.serverCursorMotion))
        cursor.motion_absolute_event.add(Listener(self.serverCursorMotionAbsolute))
        cursor.button_event.add(Listener(self.serverCursorButton))
        cursor.axis_event.add(Listener(self.serverCursorAxis))
        cursor.frame_event.add(Listener(self.serverCursorFrame))

        seat.request_set_cursor_event.add(Listener(self.seatRequestCursor))
        seat.request_set_selection_event.add(Listener(self.seatRequestSetSelection))

        backend.new_input_event.add(Listener(self.serverNewInput))

    def viewAt(self, layoutX, layoutY):
        for layerView in self.layerViews[::-1]:
            surface, x, y = layerView.layerViewAt(layoutX, layoutY)
            if surface is not None:
                return layerView, surface, x, y
        for view in self.views[::-1]:
            surface, x, y = view.viewAt(layoutX, layoutY)
            if surface is not None:
                return view, surface, x, y
        return None, None, 0, 0

    def layerViewAt(self, layoutX, layoutY):
        for layerView in self.layerViews[::-1]:
            surface, x, y = layerView.layerViewAt(layoutX, layoutY)
            if surface is not None:
                return layerView, surface, x, y
        return None, None, 0, 0

    def serverNewXdgSurface(self, listener, xdgSurface):
        output = self.outputs[0]
        width, height = output.effective_resolution()
        print(f"[INFO] EFFECTIVE RESOLUTION:{width}x{height}")
        print("[XDG] new surface")
        if xdgSurface.role != XdgSurfaceRole.TOPLEVEL:
            print("[XDG] But not a top level surface")
            return
        x = ffi.getctype(xdgSurface.toplevel._ptr)
        print(x)
        view = View(xdgSurface, self)
        self.views.append(view)

    def serverNewLayerShell(self, listener, layerShell):
        print("[LAYER] new layer surface")
        layerView = LayerView(layerShell, self)
        self.layerViews.append(layerView)

    def serverNewOutput(self, listener, output):
        if output.modes != []:
            mode = output.preferred_mode()
            if mode is None:
                print("[OUT] Didn't Get Any Output Modes")
                return
            output.set_mode(mode)
            output.enable()
            if not output.commit():
                print("[OUT] Failed to Commit Output")
                return

        self.outputs.append(output)
        self.outputLayout.add_auto(output)
        output.destroy_event.add(Listener(self.serverDestroyOutput))
        output.frame_event.add(Listener(self.serverDrawFrame))
        output.create_global()

    def serverDestroyOutput(self, listener, output):
        for index in range(len(self.outputs)):
            if self.outputs[index] == output:
                self.outputs.remove(index)
                return
    
    def serverDrawFrame(self, listerer, data):
        now = Timespec.get_monotonic_time()
        output = self.outputs[0]
        if not output.attach_render():
            print("[COMP] could not attach renderer")
            return
        width, height = output.effective_resolution()

        self.renderer.begin(width, height)

        self.renderer.clear(self.color)
        
        for view in self.views:
            #print(f"******{view}")
            if not view.mapped:
                continue
            data = output,view, now
            view.xdgSurface.for_each_surface(self.renderSurface, data)
        
        for layerView in self.layerViews:
            if not layerView.mapped:
                continue
            date = output, layerView, now
            # lib.wlr_layer_surface_v1_for_each_surface(layerView.layerShell._ptr,self.renderSurface,data)
            layerView.layerShell.for_each_surface(self.renderSurface, data)

        output.render_software_cursors()
        self.renderer.end()
        output.commit()

    def renderSurface(self, surface, surfaceX, surfaceY, data):
        output, view, now = data

        texture = surface.get_texture()
        if texture is None:
            return
        
        outputX, outputY = self.outputLayout.output_coords(output)
        outputW, outputH = output.effective_resolution()
        box = Box(
            int((outputX+surfaceX+view.x) * output.scale),
            int((outputY+surfaceY+view.y) * output.scale),
            int(surface.current.width * output.scale),
            int(surface.current.height * output.scale)
        )
        transform = surface.current.transform
        inverse = Output.transform_invert(transform)
        matrix = Matrix.project_box(box, inverse, 0, output.transform_matrix)

        self.renderer.render_texture_with_matrix(texture, matrix, 1)
        surface.send_frame_done(now)
    
    def serverNewInput(self, listener, inputDevice):
        if inputDevice.device_type == InputDeviceType.POINTER:
            self.serverNewPointer(inputDevice)
        elif inputDevice.device_type == InputDeviceType.KEYBOARD:
            self.serverNewKeyboard(inputDevice)
        
        capabilities = WlSeat.capability.pointer
        if len(self.keyboards) > 0:
            capabilities |= WlSeat.capability.keyboard
        
        self.seat.set_capabilities(capabilities)
    
    def serverNewPointer(self, inputDevice):
        self.cursor.attach_input_device(inputDevice)

    def serverNewKeyboard(self, inputDevice):
        keeb = inputDevice.keyboard
        xkbContext = xkb.Context()
        keymap = xkbContext.keymap_new_from_names()

        keeb.set_keymap(keymap)
        keeb.set_repeat_info(25,600)

        keyboardHandler = KeyboardHandler(keeb, inputDevice, self)
        self.keyboards.append(keyboardHandler)

        self.seat.set_keyboard(inputDevice)
    
    def serverCursorMotion(self, listener, eventMotion):
        # print('MOV')
        self.cursor.move(eventMotion.device, eventMotion.delta_x, eventMotion.delta_y)
        self.processCursorMotion(eventMotion.time_msec)

    def serverCursorMotionAbsolute(self, listener, absEventMotion):
        # print('ABS')
        self.cursor.warp_absolute(absEventMotion.device, absEventMotion.x, absEventMotion.y)
        self.processCursorMotion(absEventMotion.time_msec)

    def serverCursorButton(self, listener, event):
        print(f"[IN] Got button click event {event.button_state}")
        self.seat.pointer_notify_button(event.time_msec, event.button, event.button_state)

        view, surface, _, _ = self.viewAt(self.cursor.x, self.cursor.y)
        if event.button_state == ButtonState.RELEASED:
            # exit interactive move/resize
            self.cursor_mode = CursorMode.PASSTHROUGH
        elif view is not None and lib.wlr_surface_is_xdg_surface(surface._ptr):
            self.focusView(view, surface)
        elif view is not None:
            self.focusLayerView(view, surface)
    def processCursorMotion(self, time):
        view, surface, sx, sy = self.viewAt(self.cursor.x, self.cursor.y)
        if view is None or surface is None:
            self.cursorManager.set_cursor_image("left_ptr", self.cursor)
            self.seat.pointer_clear_focus()
        else:
            focusChanged = self.seat.pointer_state.focused_surface != surface

            self.seat.pointer_notify_enter(surface, sx, sy)
            if not focusChanged:
                self.seat.pointer_notify_motion(time, sx, sy)

    def serverCursorAxis(self, listener, event):
        self.seat.pointer_notify_axis(event.time_msec, event.orientation, event.delta, event.delta_discrete, event.source)
    
    def serverCursorFrame(self, listener, data):
        self.seat.pointer_notify_frame()

    def seatRequestCursor(self, listener, event):
        self.cursor.set_surface(event.surface, event.hotspot)
    
    def seatRequestSetSelection(self, listener, event) -> None:
        print("[IN] request set selection")
        self.seat.set_selection(event._ptr.source, event.serial)
    
    def sendModifiers(self, modifiers, inputDevice):
        self.seat.set_keyboard(inputDevice)
        self.seat.keyboard_notify_modifiers(modifiers)
    
    def sendKey(self, keyEvent, inputDevice):
        keyboard = inputDevice.keyboard
        keyboardModifier = keyboard.modifier
        
        handled = False
        
        if (keyboardModifier == keyboardModifier.LOGO or keyboardModifier == keyboardModifier.CTRL) and keyEvent.state == KeyState.KEY_PRESSED:
            keyCode = keyEvent.keycode + 8
            keySyms = get_keysyms(keyboard._ptr.xkb_state, keyCode)
            for keySym in keySyms:
                if self.handleKeybinding(keySym):
                    handled = True
                    break
                
        if not handled:
            self.seat.set_keyboard(inputDevice)
            self.seat.keyboard_notify_key(keyEvent)
    
    def handleKeybinding(self, keySym):
        if keySym == xkb.keysym_from_name("Escape"):
            print('[IN] ctrl-esc received')
            self.display.terminate()
        elif keySym == xkb.keysym_from_name("F1"):
            print('[IN] ctrl-F1 received')
            if len(self.views) >= 2:
                *rest, new_view, prev_view = self.views
                self.focusView(new_view,None)
                self.views = [prev_view] + rest + [new_view]
        elif keySym == xkb.keysym_from_name("F2"):
            print('[IN] ctrl-F2 received')
            os.system('WAYLAND_DISPLAY=wayland-0 weston-terminal --font-size=36 &')
        elif keySym == xkb.keysym_from_name("F3"):
            print('[IN] ctrl-F3 received')
            os.system('WAYLAND_DISPLAY=wayland-0 nautilus &')
        elif keySym == xkb.keysym_from_name("F4"):
            print('[IN] ctrl-F4 received')
            os.system('~/Git/wlroots/build/examples/layer-shell -l background -w 1920 -h 1080')
            # os.system('WAYLAND_DISPLAY=wayland-0 vscodium &')
        else:
            print(f'[IN] ctrl-{xkb.keysym_get_name(keySym)} recieved')
            return False
        return True
    
    def focusView(self, view, surface=None):
        if surface is None:
            surface = view.xdgSurface.surface

        previousSurface = self.seat.keyboard_state.focused_surface
        if previousSurface == surface:
            return

        keyboard = self.seat.keyboard

        if previousSurface is not None and lib.wlr_surface_is_xdg_surface(previousSurface._ptr):
            previousXdgSurface = XdgSurface.from_surface(previousSurface)
            previousXdgSurface.set_activated(False)

        views = self.views[:]
        views.remove(view)
        views.append(view)
        self.views = views
        width, height = self.outputs[0].effective_resolution()
        view.xdgSurface.set_size(width, height)
        view.xdgSurface.set_activated(True)

        self.seat.keyboard_notify_enter(view.xdgSurface.surface,keyboard)

    def focusLayerView(self, layerView, surface=None):
        if surface is None:
            surface = layerView.layerShell.surface
        
        keyboard = self.seat.keyboard
        self.seat.keyboard_notify_enter(layerView.layerShell.surface,keyboard)

    def getPrimaryDisplayResolution(self):
        w, h = self.outputs[0].effective_resolution()
        return {'width':w, 'height': h}