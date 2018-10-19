import time
from multiprocessing import Process, Queue
from queue import Empty

class Button:
    def __init__(self, hold_time=0, double_time=0):
        self.hold_time = hold_time
        self.double_time = double_time
        self.pressed = False
        self.holding = False
        self.doubling = False
        self.hold_queue = Queue()
        self.double_queue = Queue()

    def press(self):
        if self.pressed: #Some devices send 'down' continuously while pressed
            return
        if self.doubling:
            self.double_queue.put(True)
        elif self.double_time:
            self.doubler()

        if self.hold_time:
            self.holder()

        if not self.hold_time and not self.double_time:
            self.press_action()

        self.pressed = True

        # if self.doubling or self.holding:
        #     self.queue.put(True)
        # elif self.hold:
        #     self.held()
        # elif self.double:
        #     self.doubled()
        # else:
        #     self.press_action()

    def release(self):
        self.pressed = False
        if self.holding:
            self.hold_queue.put(False)

    def cancel(self):
        if self.holding:
            self.hold_queue.put(None)

        if self.doubling:
            self.double_queue.put(None)

    def stop_doubling(self):
        self.doubling = False
        self.press_action()

    def stop_holding(self):
        self.holding = False
        if not self.doubling:
            self.press_action()

    def holder(self):
        self.holding = True
        Process(target=self.waiter,
                args=(self.hold_time, self.hold_queue, False, self.stop_holding, self.hold_action)
                ).start()

    def doubler(self):
        self.doubling = True
        Process(target=self.waiter,
                args=(self.double_time, self.double_queue, True, self.double_action, self.stop_doubling)
                ).start()

    def waiter(self, wait, queue, event, action_if, action_else=None):
        later = time.time() + wait

        while 1:
            delta = later - time.time() #Compute remaining hold time
            try:
                event_in = queue.get(timeout=delta)
                if event_in == event:
                    action_if()
                    return
                elif event_in == None: #None means cancel
                    return
            except Empty:
                if action_else:
                    action_else()
                return

    def one_waiter(self):
        delta = 0
        while 1:
            try:
                event = self.queue.get(delta)
            except Empty:
                pass
            if event:
                if self.pressed:
                    break
                else:
                    self.pressed = True

                if not self.hold_time and not self.double_time:
                    self.press_action()
                elif self.hold_time:
                    self.holding = True
                    when_held = time.time() + self.hold_time
                elif self.double_time and not self.doubling:
                    self.doubling = True
                    when_doubled = time.time() + self.double_time
                elif self.doubling:
                    self.double_action()
                    self.doubling = False

    # Probably need to have separate functions called when button actions are engaged and then the callback. Need some logic to cancel certain functions when others are triggered; don't see way to build into waiter code

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
