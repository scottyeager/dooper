#!/usr/bin/python

import time, inspect, liblo, hid, rtmidi
from operator import itemgetter
from multiprocessing import Process, Queue
from queue import Empty
from evdev import InputDevice, categorize, ecodes as e
from itertools import chain
from dooper import Looper
from pressed import Infinity

debug = False
#debug = True
hold_time = .35 #How long user has to press a button before it triggers hold actions

# looper = Looper()
# loops = len(looper.loops) #How many loops. Dies if this doesn't match SL's current state, should query instead
loops = 6


in_server = liblo.Server(9950) #Define liblo server for replies from sooperlooper
out_port = 9951 #Port that sl is listening on, for us to send messages to

osc_in_q = Queue()
in_server.add_method(None, None, lambda p, a: osc_in_q.put((p, a)))

def send_osc(*args):
    """Takes a loop, command, and argument (e.g. "up", "down", state) and sends appropriate osc message"""
    if debug:
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
           'KEY_KPASTERISK': [5, *top_row_actions]}

# -3 for selected loop, -1 for all loops
infinity_map = {(1, 0): [-3, 'undo', 'undo_all'],
                (2, 0): [-3, 'record', 'overdub'],
                (4, 0): [-3, 'mute', 'reverse']}

midi_map_inverse = dict(zip(range(0,8), chain(range(36,40), range(44,48))))
midi_map = dict(zip(chain(range(36,40), range(44,48)), range(0,8)))

midi_map_top_inverse = dict(zip(range(0,8), chain(range(40,44), range(48,52))))
midi_map_top = dict(zip(chain(range(40,44), range(48,52)), range(0,8)))

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
        try:
            reply = osc_in_q.get(timeout=.1)
            loop_states[i] = state_codes[int(reply[1][2])] #Get reply from looper, key into state codes
        except Empty:
            print("No reply from SooperLooper")
        except IndexError:
            print("Couldn't key into loop states reply:")
            print(reply)
        except KeyError as e:
            print(e)
    return loop_states

# Traceback (most recent call last):
#   File "./keystoslosc2.py", line 369, in <module>
#     update_loop_states()
#   File "./keystoslosc2.py", line 102, in update_loop_states
#     loop_states[i] = state_codes[int(reply[1][2])] #Get reply from looper, key into state codes
# KeyError: 15

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
def global_catcher(q):
    """Receives presses sends messages for global and selected commands"""
    while(1):
        event = q.get()
        loop = event[0]
        if event[1] == 'down':
            was_held = held(q)
        else:
            continue

        if not was_held:
            try:
                send_osc(loop, 'hit', event[2])
            except KeyError:
                pass
        else:
            try:
                send_osc(loop, 'hit', event[3])
            except KeyError:
                pass

        update_loop_states()

        # if event[2] == 'mute' or event[3] == 'mute':
        #     try:
        #         lit.remove(midi_map[loop])
        #     except ValueError:
        #         pass

taps = 0

def infinity_catcher(q):
    """Receive input from infinity foot controller and place commands into queue"""
    # Infinity Transcription Footpedal
    # try:
    #     infinity = hid.device()
    #     infinity.open(0x05f3, 0x00ff) # VendorId/ProductId
    # except OSError:
    #     print("Couldn't open Infinity")
    #     return

    infinity = Infinity()
    midiout_tap = rtmidi.MidiOut(name="tap")
    midiout_tap.open_virtual_port("tap")

    def record(button):
        send_osc(-3, 'hit', 'record')

    def overdub(button):
        send_osc(-3, 'hit', 'overdub')

    def undo(button):
        send_osc(-3, 'hit', 'undo')

    def undo_all(button):
        send_osc(-3, 'hit', 'undo_all')

    def tap_tempo(button):
        button.midiout_tap.send_message([0x90, 59, 127])
            #rtmidi.MidiMessage.noteOn(1, 59, 127))

        if button.taps == 3:
            button.midiout_tap.send_message([0x90, 56, 127])
                #rtmidi.MidiMessage.noteOn(1, 56, 127))

        button.taps += 1
        button.taps %= 4

    def play_pause(button):
        button.midiout_tap.send_message([0x90, 69, 127])
            #rtmidi.MidiMessage.noteOn(1, 69, 127))


    infinity.buttons['left'].press_action = undo
    infinity.buttons['left'].hold_action = undo_all

    infinity.buttons['center'].press_action = record
    infinity.buttons['center'].hold_action = overdub

    infinity.buttons['right'].midiout_tap = midiout_tap
    infinity.buttons['right'].taps = 0
    infinity.buttons['right'].press_action = tap_tempo
    infinity.buttons['right'].hold_action = play_pause

    while(1):
        press = infinity.dev.read(8)[0]

        if press == 0:
            for button in infinity.buttons.values():
                if button.pressed:
                    button.release()

        elif press in [1, 2, 4]:
            name = infinity.button_map[press]
            infinity.buttons[name].press()


    # Clear any messages waiting in queue
    while infinity.read(8,1):
        pass

    while(1):
        press = infinity.read(8)
        if debug:
            print(press)

        if press[0] != 0: # Key down event
            try:
                mapped = list(infinity_map[tuple(press)])
            except KeyError:
                continue
            mapped.insert(1, 'down')
            q.put(mapped)
        else:
            # Key up event, loop number not used here
            q.put([1, 'up'])
        if debug:
            print(mapped)

def catcher(key_q):
    """Receives button presses and sends messages as needed"""
    while(1):
        event = key_q.get()
        loop = event[0]
        state = update_loop_states()[event[0]] # No need to update all loops
        was_held = None

        if event[1] == 'down':
            was_held = held(key_q)
        else:
            continue

        liblo.send(9951, "/set", "selected_loop_num", loop)
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

# TODO: Ok, so, we can't just block on the PC keyboard anymore, if we want the new transcription pedal to play along too. That means processes for each input device, as well as each loop, and probably one for the looper itself as well.

global_q = Queue()
p1 = Process(target=infinity_catcher, args=(global_q,))
p2 = Process(target=global_catcher, args=(global_q,))
p1.start()
p2.start()
#p.join()

#infinity_catcher(global_q, infinity)

midin = rtmidi.MidiIn(name="dooper")
midiout_lpd = rtmidi.MidiOut(name="dooper")
midin.open_virtual_port("dooper")
midiout_lpd.open_virtual_port("dooper")

toprow = list(chain(range(40, 44), range(48, 52), range(56, 58), range(62, 66)))
bottomrow = list(chain(range(36, 40), range(44, 48), range(52, 56), range(58, 62)))
lit = []

def light():
    for l in lit:
        midiout_lpd.send_message([0xb0, l, 127])
                #rtmidi.MidiMessage.controllerEvent(1, l, 127))

    for i, state in enumerate(loop_states):
        if state in ("Muted", "Off and muted"):
            midiout_lpd.send_message([0xb0, midi_map_inverse[i], 127])
                    #rtmidi.MidiMessage.controllerEvent(1, midi_map_inverse[i], 127))

        else:
            midiout_lpd.send_message([0xb0, midi_map_inverse[i], 0])
                    #rtmidi.MidiMessage.controllerEvent(1, midi_map_inverse[i], 0))

def cb(msg, etc):
    if debug:
        print(msg)

    if msg[0][0] >> 4 == 0b1011:
    #msg.isController():
        #number = msg.getControllerNumber()
        #value = msg.getControllerValue()
        number = msg[0][1]
        value = msg[0][2]

        if number in toprow:
            for i in toprow:
                midiout_lpd.send_message([0xb0, i, 0])
                        #rtmidi.MidiMessage.controllerEvent(1, i, 0))
                try:
                    lit.remove(i)
                except ValueError:
                    pass

            lit.append(number)
            if debug:
                print(lit)

            liblo.send(9951, liblo.Message("/set", "selected_loop_num", midi_map_top[number]))

            time.sleep(.01)

            update_loop_states()
            light()

        elif number in bottomrow and value:
            send_osc(midi_map[number], 'hit', 'mute')

            time.sleep(.01)

            update_loop_states()
            light()

        # elif number in bottomrow and value:
        #     try:
        #         lit.remove(number)
        #     except ValueError:
        #         lit.append(number)
        #
        #     light()

midin.set_callback(cb)

# Update to reflect changes made in other front ends.
# This breaks on SL reboot and hangs a thread
# Should register for updates from SL instead
try:
    while 1:
        if time.time() % .5 < .5:
            update_loop_states()
        light()
        time.sleep(.05)

except KeyboardInterrupt:
    # Need to kill catcher processes so we can exit cleanly
    # If these were threads, we could set them as daemons for same effect
    p1.terminate()
    p2.terminate()

except Exception as e:
    print(e)

finally:
    # Need to kill catcher processes so we can exit cleanly
    # If these were threads, we could set them as daemons for same effect
    p1.terminate()
    p2.terminate()
