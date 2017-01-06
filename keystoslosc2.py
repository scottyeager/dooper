#!/usr/bin/python

import time, inspect, liblo
from operator import itemgetter
from multiprocessing import Process, Queue
from queue import Empty
from evdev import InputDevice, categorize, ecodes as e

hold_time = .25 #How long user has to press a button before it triggers hold actions
loops = 6 #How many loops. 6 for now, but buttons are mapped for 9 or 10

dev = InputDevice('/dev/input/by-id/usb-05a4_USB_Compliant_Keyboard-event-kbd') #External keyboard
dev.grab() # Capture input, so we're not typing
#dev = InputDevice('/dev/input/by-path/platform-i8042-serio-0-event-kbd') #Laptop keyboard

in_server = liblo.Server(9950) #Define liblo server for replies from sooperlooper
out_port = 9951 #Port that sl is listening on, for us to send messages to

osc_in_q = Queue()
in_server.add_method(None, None, lambda p, a: osc_in_q.put((p, a)))

def send_osc(*args):
    """Takes a loop, command, and argument (e.g. "up", "down", state) and sends appropriate osc message"""
#    print('Sending OSC message: {}'.format(args))
    liblo.send(9951, liblo.Message("/sl/{}/{}".format(*args[:2]), *args[2:]))

# Map keyboard keys to loop numbers. Set commands for loop 0 ('master'), other loops have single button
key_map = {'KEY_LEFTMETA': (0, 'record'),
           'KEY_SPACE': (1,),
           'KEY_RIGHTALT': (2,),
           'KEY_RIGHTCTRL': (3,),
           'KEY_RIGHT': (4,),
           'KEY_KPENTER': (5,),

           'KEY_TAB': (0, 'mute'),
           'KEY_E': (6,),
           'KEY_U': (7,),
           'KEY_LEFTBRACE': (8,),
           'KEY_SYSRQ': (9,),
           'KEY_KP8': (10,)}

# Map sl's integer codes to loop states
state_codes = {-1: 'unknown',
               0: 'Off',
               1: 'WaitStart',
               2: 'Recording',
               3: 'WaitStop',
               4: 'Playing',
               5: 'Overdubbing',
               6: 'Multiplying',
               7: 'Inserting',
               8: 'Replacing',
               9: 'Delay',
               10: 'Muted',
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

def master_catcher(key_q):
    """Receives keypresses sends messages as needed--for master loop"""
    while(1):
        event = key_q.get()
        send_osc(*event)

def catcher(key_q):
    """Receives keypresses sends messages as needed"""
    while(1):
        event = key_q.get()
        loop = event[0]
        state = update_loop_states()[event[0]]
        if event[1] == 'down': # Key down event
            if loop_states[loop] == 'Recording':
                send_osc(loop, 'hit', 'record')

            else: #So, 'muted', or 'off'.
                pressed = time.time() #Record current time
                held = pressed + hold_time #Calculate when user will have held for designated hold time
                while 1:
                    delta = held - time.time() #Compute remaining hold time
                    if delta < 0: #This should probably not go negative, so just in case
                        delta = 0
                    try:
                        new_event = key_q.get(timeout=delta) #Wait to see if the user is holding
                        if new_event[1] == 'up': #Got the key up message, so user released
                            command = 'mute'
                            break
                    except: #We got no up message and queue raised empty error
                        command = 'record'
                        break

                send_osc(loop, 'hit', command) #Actually trigger osc, now that we know what to do

for i, q in enumerate(loop_queues):
    if i == 0:
        p = Process(target=master_catcher, args=(q,))
    else:
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
        except:
            pass

    #print(categorize(event).keycode, (categorize(event).keystate))
