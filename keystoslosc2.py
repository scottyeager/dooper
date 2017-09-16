#!/usr/bin/python

import time, inspect, liblo
from operator import itemgetter
from multiprocessing import Process, Queue
from queue import Empty
from evdev import InputDevice, categorize, ecodes as e

hold_time = .35 #How long user has to press a button before it triggers hold actions
loops = 6 #How many loops. 6 for now, but buttons are mapped for 9 or 10

# Foot controller keyboard
dev = InputDevice('/dev/input/by-id/usb-05a4_USB_Compliant_Keyboard-event-kbd')

# Desk keyboard
#dev = InputDevice('/dev/input/by-path/pci-0000:00:14.0-usb-0:1.1:1.0-event-kbd')

# Any ol' event
#dev = InputDevice('/dev/input/event0')

dev.grab() # Capture input, so we're not typing

in_server = liblo.Server(9950) #Define liblo server for replies from sooperlooper
out_port = 9951 #Port that sl is listening on, for us to send messages to

osc_in_q = Queue()
in_server.add_method(None, None, lambda p, a: osc_in_q.put((p, a)))

def send_osc(*args):
    """Takes a loop, command, and argument (e.g. "up", "down", state) and sends appropriate osc message"""
    print('Sending OSC message: {}'.format(args))
    liblo.send(9951, liblo.Message("/sl/{}/{}".format(*args[:2]), *args[2:]))

# Map keyboard keys to loop numbers and commands. Probably should specify here both the press and hold actions for each of recording, mute, and off states. Or maybe just need recording and mute/off like we do below. Change that code to just send the specified command.

# Map keys to actions: [LoopNumber, [off, recording, playing, mute], [off, recording, playing, mute]] | [None, press, hold]. For loop specific actions, first list entry is loop number. Next is a list of actions for pressed keys for loop states off, recording, and mute, respectively. Or give a single item list to send that action regardless of state. Then an option list of actions for held keys. For global actions, loop number is None, followed by press and hold actions.

#Well, hmmmm. Just how many states do we need to account for? Playing, at the least should be included. But how about overdub, etc.? Need a default to cover uncovered states? How about all the states, specified by name so we can key in using the current state as a string. And defaults, which are easy enough.

bottom_row_actions = [
{'Off': 'record', 'Recording': 'record', 'Playing': 'mute', 'Muted': 'mute', 'WaitStop': 'record'},
{'Off': 'record', 'Recording': 'mute', 'Playing': 'record', 'Muted': 'record', 'WaitStop': 'mute'}]
bottom_row_actions[0].setdefault(None)
bottom_row_actions[1].setdefault(None)

top_row_actions = ['overdub', 'undo']

key_map = {'KEY_LEFTMETA': [0, *bottom_row_actions],
           'KEY_SPACE': [1, *bottom_row_actions],
           'KEY_RIGHTALT': [2, *bottom_row_actions],
           'KEY_RIGHTCTRL': [3, *bottom_row_actions],
           'KEY_RIGHT': [4, *bottom_row_actions],
           'KEY_KPENTER': [5, *bottom_row_actions],

           'KEY_TAB': [0, *top_row_actions],
           'KEY_E': [1, *top_row_actions],
           'KEY_U': [2, *top_row_actions],
           'KEY_LEFTBRACE': [3, *top_row_actions],
           'KEY_SYSRQ': [4, *top_row_actions],
           'KEY_KP8': [5, *top_row_actions]}

# Map sl's integer codes to loop states
state_codes = {-1: 'unknown',
               0: 'Off',
               1: 'WaitStart', # Waiting to start recording
               2: 'Recording',
               3: 'WaitStop', # Waiting to stop recording
               4: 'Playing', # Or maybe waiting to mute
               5: 'Overdubbing',
               6: 'Multiplying',
               7: 'Inserting',
               8: 'Replacing',
               9: 'Delay',
               10: 'Muted', # Or maybe waiting to play
               11: 'Scratching',
               12: 'OneShot',
               13: 'Substitute',
               14: 'Paused',
               20: 'Off and muted'} #20 isn't documented...

loop_states = [None for i in range(loops)] #Keep track of loop states--we'll initialize them below
def update_loop_states():
    """
    Query and update loop states.
    Expected states for foot controller operation are 'Off', 'Muted', 'Recording', and 'Playing'
    Note: Hangs if sl doesn't have as many loops as we've specified. Query # of loops instead?
    """
    for i in range(len(loop_states)):
        send_osc(i, 'get', 'state', '127.0.0.1:9950', '/slreplies/')
        in_server.recv()
        reply = osc_in_q.get()
        loop_states[i] = state_codes[int(reply[1][2])] #Get reply from looper, key into state codes
    return loop_states

update_loop_states() #Do this once, because we don't know what the initial states are

loop_queues = [Queue() for i in range(loops)] #Individual queues for each loop's key presses

def held(key_q):
    pressed = time.time() #Record current time
    held = pressed + hold_time #Calculate when user will have held for designated hold time
    while 1:
        delta = held - time.time() #Compute remaining hold time
        if delta < 0: #This should probably not go negative, so just in case
            delta = 0
        try:
            new_event = key_q.get(timeout=delta) #Wait to see if the user is holding
            if new_event[1] == 'up': #Got the key up message, so user released
                return False
        except: #We got no up message and queue raised empty error
            return True

# No more "master loop", though we should be able to implement this under new framework, by giving an option to ignore held keys to eliminate latency waiting for key up event. Actually, since all commands are routed to loop queues, we'll need something like this for global commands, if we want to use them.
def master_catcher(key_q):
    """Receives keypresses sends messages as needed--for master loop"""
    while(1):
        event = key_q.get()
        print("master catcher time")
        send_osc(*event)

def catcher(key_q):
    """Receives keypresses sends messages as needed"""
    while(1):
        event = key_q.get()
        loop = event[0]
        state = update_loop_states()[event[0]] # No need to update all loops
        was_held = None

        if event[1] == 'down':
            was_held = held(key_q)
        else:
            continue

        if loop is None:
            pass # Placeholder for global commands
        else:
            if not was_held:
                try:
                    send_osc(loop, 'hit', event[2][state])
                except TypeError: # Mapping has only single action
                    send_osc(loop, 'hit', event[2])
                except KeyError:
                    pass
            else:
                try:
                    send_osc(loop, 'hit', event[3][state])
                except TypeError: # Mapping has only single action
                    send_osc(loop, 'hit', event[3])
                except KeyError:
                    pass

def statedump():
    while(1):
        print(update_loop_states())
        time.sleep(0.2)

#Process(target=statedump).start()

for i, q in enumerate(loop_queues):
    p = Process(target=catcher, args=(q,))
    p.start()

for event in dev.read_loop():
    if event.type == e.EV_KEY:
        event = categorize(event)
        try:
            mapped = list(key_map[event.keycode])

            if event.keystate == 1: # Key down event
                mapped.insert(1, 'down')
                loop_queues[mapped[0]].put(mapped)
            elif event.keystate == 0: # Key up event
                mapped.insert(1, 'up')
                loop_queues[mapped[0]].put(mapped)
            print(mapped)
        except:
            pass

    #print(categorize(event).keycode, (categorize(event).keystate))
