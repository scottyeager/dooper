import time, hid
from multiprocessing import Process, Queue, Event
from threading import Thread, Timer
from queue import Empty
from evdev import InputDevice, categorize, ecodes as e

# class Flag:
#     def __init__(self, state=False):
#         self.event = Event
#         self.set(state)
#
#     def get(self):
#         return self.event.is_set()
#
#     def set(self, state):
#         if state:
#             self.event.set()
#         else:
#             self.event.clear()
#
#     def wait(self, timeout):
#         self.event.wait(timeout)

class Button:
    def __init__(self, hold_time=0, double_time=0, simultaneous=False,
                 name=None):
        self.hold_time = hold_time
        self.double_time = double_time
        self.simultaneous = simultaneous
        self.name = name

        self.pressed = False
        self.held = False
        self.pressed_double = False
        self.pressed_simultaneous = False

        if self.hold_time:
            self.hold_timer = Thread()

        if self.double_time:
            self.double_timer = Thread()

        # self.pressed = Flag()
        # self.cancel_hold = Flag()
        # self.held = Flag()
        # self.pressed_double = Flag()
        # self.pressed_simultaneous = Flag()

        # self.hold = Process()
        # self.double = Process()
        # self.simultaneous = Process()
        #
        # self.hold_queue = Queue()
        # self.double_queue = Queue()
        # self.simultaneous_queue = Queue()

    def __repr__(self):
        return 'Button({}, {}, {}, {})'.format(self.hold_time, self.double_time, self.simultaneous, self.name)

    # def press(self):
    #     if self.pressed: #Some devices send 'down' continually while pressed
    #         return
    #
    #     if self.double.is_alive():
    #         self.double_queue.put(True)
    #         self.pressed_double = True
    #     elif self.hold_time:
    #         self.hold = Process(target=self.wait_hold)
    #         self.hold.start()
    #
    #     if self.simultaneous_time:
    #         self.simultaneous = Process(target=self.wait_simultaneous)
    #         self.simultaneous.start()
    #
    #     if not (self.hold_time or self.double_time or self.simultaneous_time):
    #         self.press_action()
    #
    #     self.pressed = True

    def press(self):
        if self.pressed: #Some devices send 'down' continually while pressed
            return

        if not (self.hold_time or self.double_time or self.simultaneous):
            self.press_action()

        elif self.double_time and self.double_timer.is_alive():
            self.double_timer.cancel()
            self.pressed_double = True
            self.double_action()

        elif self.hold_time and not self.pressed_double:
            print('starting hold timer')
            self.hold_timer = Timer(self.hold_time, self.hold)
            self.hold_timer.start()

        self.pressed = True

    def release(self):
        if not self.pressed:
            return

        if not (self.hold_time or self.double_time):
            self.press_action
            self.pressed = False
            self.pressed_simultaneous = False
            return

        starting_double = self.double_time and not self.pressed_double

        if self.hold_time and not self.held:
            print('canceling hold timer')
            self.hold_timer.cancel()

            if not (starting_double or self.pressed_double):
                self.press_action()

        if self.double_time and not (self.held or self.pressed_double or self.pressed_simultaneous):
            print('starting double timer')
            self.double_timer = Timer(self.double_time, self.press_action)
            self.double_timer.start()

        self.held = False
        self.pressed = False
        self.pressed_double = False
        self.pressed_simultaneous = False

    # def release(self):
    #     hold = self.hold_time and self.hold.is_alive()
    #     start_double = self.double_time and not self.double.is_alive()
    #     simultaneous = self.simultaneous_time and self.simultaneous.is_alive()
    #
    #     if hold:
    #         self.hold_queue.put(False)
    #
    #         if not start_double:
    #             self.press_action()
    #
    #     if simultaneous:
    #         self.simultaneous_queue.put(False)
    #
    #         if not (hold or start_double):
    #             self.press_action()
    #
    #     #if not (hold or self.held or double or self.pressed_double or
    #     #        simultaneous or self.pressed_simultaneous):
    #         #self.press_action()
    #
    #     if start_double:
    #         # Much simpler to trigger this on release, rather than press
    #         self.double = Process(target=self.wait_double)
    #         self.double.start()
    #
    #     self.pressed = False
    #     self.pressed_double = False
    #     self.pressed_simultaneous = False

    def hold(self):
        self.held = True
        self.hold_action()

    def press_simultaneous(self, button):
        if self.hold_timer.is_alive():
            self.hold_timer.cancel()
            self.simultaneous_action(button)
            self.pressed_simultaneous = True

    # def wait_hold(self):
    #     if not self.cancel_hold.wait(self.hold_time):
    #         self.hold_action()
    #     # try:
    #     #     self.hold_queue.get(timeout=self.hold_time)
    #     # except Empty:
    #     #     self.held = True
    #     #     self.hold_action()

    # def wait_double(self):
    #     try:
    #         event = self.double_queue.get(timeout=self.double_time)
    #         if event:
    #             self.double_action()
    #     except Empty:
    #         self.press_action()
    #
    # def wait_simultaneous(self):
    #     try:
    #         button = self.simultaneous_queue.get(timeout=self.double_time)
    #         if button:
    #             self.simultaneous_action(button)
    #     except Empty:
    #         self.press_action()

    def press_action(self):
        print('press')

    def hold_action(self):
        print('hold')

    def double_action(self):
        print('double')

    def simultaneous_action(self, button):
        print('simultaneous with: ' + str(button))

    # @property
    # def pressed(self):
    #     return self._pressed.get()
    #
    # @pressed.setter
    # def pressed(self, state):
    #     self._pressed.set(state)
    #
    # @property
    # def cancel_hold(self):
    #     return self._cancel_hold.get()
    #
    # @cancel_hold.setter
    # def cancel_hold(self, state):
    #     self._cancel_hold.set(state)

class Qwerty:
    """
    See here for code to make lights blink: https://stackoverflow.com/questions/854393/change-keyboard-locks-in-python/858992#858992
    """
    def __init__(self, path, key_map, grab=True):
        self.dev = InputDevice(path)
        self.key_map = key_map
        self.buttons = {key: Button(name=key) for key in key_map}

        if self.grab:
            dev.grab() #This requires user in input group or run as root

    def loop(self):
        for event in self.dev.read_loop():
            if event.type == e.EV_KEY:
                event = categorize(event)
                if debug:
                    print(event)

                try:
                    mapped = list(self.key_map[event.keycode])

                    if event.keystate == 1: # Key down event
                        self.buttons[event.keycode].press()

                    elif event.keystate == 0: # Key up event, not key specific
                        for b in self.buttons:
                            if b.pressed:
                                b.release()
                    if debug:
                        print(mapped)
                except:
                    pass

# Foot controller keyboard
#dev = InputDevice('/dev/input/by-id/usb-05a4_USB_Compliant_Keyboard-event-kbd')

# Desk keyboard
#dev = InputDevice('/dev/input/by-path/pci-0000:00:14.0-usb-0:1.1:1.0-event-kbd')

# Laptop keyboard
path = '/dev/input/by-path/platform-i8042-serio-0-event-kbd'

# Any ol' event
#dev = InputDevice('/dev/input/event0')

#dev.grab() # Capture input, so we're not typing

# Infinity Transcription Footpedal
try:
    infinity = hid.device()
    infinity.open(0x05f3, 0x00ff) # VendorId/ProductId
except OSError:
    print("Couldn't open Infinity")

b = Button(2,2)

b.press()
b.release()
b.press()
b.release()
