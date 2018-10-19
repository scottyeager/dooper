import time
from multiprocessing import Process, Queue
from queue import Empty

class Button:
    def __init__(self, hold_time=0, double_time=0):
        self.hold_time = hold_time
        self.double_time = double_time
        self.pressed = False
        self.double_pressed = False
        self.holder = Process()
        self.doubler = Process()
        self.hold_queue = Queue()
        self.double_queue = Queue()

    def press(self):
        if self.pressed: #Some devices send 'down' continuously while pressed
            return

        if self.doubler.is_alive():
            self.double_queue.put(True)
            self.double_pressed = True
        elif self.double_time:
            self.doubler = Process(target=self.wait_double)
            self.doubler.start()

        if self.hold_time:
            self.holder = Process(target=self.wait_hold)
            self.holder.start()

        if not self.hold_time and not self.double_time:
            self.press_action()

        self.pressed = True

    def release(self):
        if self.hold_time and self.holder.is_alive():
            self.hold_queue.put(False)

            doubling = self.double_time and self.doubler.is_alive()
            if not doubling and not self.double_pressed:
                self.press_action()

        self.pressed = False
        self.double_pressed = False

    def wait_hold(self):
        try:
            self.hold_queue.get(timeout=self.hold_time)
        except Empty:
            self.hold_action()

    def wait_double(self):
        try:
            self.double_queue.get(timeout=self.double_time)
            self.double_action()
        except Empty:
            self.press_action()

    def press_action(self):
        print('press')

    def hold_action(self):
        print('hold')

    def double_action(self):
        print('double')


b = Button(2,2)

b.press()
b.release()
b.press()
b.release()
