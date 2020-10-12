from pywayland.server import Listener

class KeyboardHandler:
    def __init__(self, keyboard, inputDevice, server):
        self.keyboard = keyboard
        self.inputDevice = inputDevice
        self.server = server

        keyboard.modifiers_event.add(Listener(self.keyboardHandleModifiers))
        keyboard.key_event.add(Listener(self.keyboardHandleKey))

    def keyboardHandleModifiers(self, listener, data):
        self.server.sendModifiers(self.keyboard.modifiers, self.inputDevice)

    def keyboardHandleKey(self, listener, keyEvent):
        self.server.sendKey(keyEvent, self.inputDevice)