# dooper

A Python library for interfacing with SooperLooper. Requires pyliblo.

Tracks full state and provides interface to all loop commands. Almost a complete client, just missing changing loop count, saving sessions, and modifying midi bindings.

## Install

It's just a simple module, so place the folder somewhere in your Python path or copy/link `dooper.py` to your project folder.

## Examples

To connect to SooperLooper, query state and control loops:

```
from dooper import LooperThread

l = LooperThread()
l.start_server()

l.loops[0].state # Automatically converts the number SL uses to a string
l.loops[0].mute() # Hits mute for the first loop

l.selected_loop_num = 2
```



Here's how you might use dooper to add a feature to SooperLooper. Assuming here that we're working with an external sync source, this will stop recording four bars (in 4/4) after recording starts on a given loop. Some additional features to add would be catching the divide by zero error that occurs if there's no tempo set and canceling the timer if we cancel recording of the loop.

```
from threading import Timer
from dooper import LooperThread, state_codes

l = LooperThread()
l.start_server()

def auto_stop(args):
    if args[1] == 'state' and state_codes[args[2]] == 'Recording':
        bar_time = 1 / (l.tempo / 60) * 4
        wait1 = bar_time * 3.1
        Timer(wait1, l.loops[int(args[0])].record).start()

l.loop_callbacks.append(auto_stop)

while 1:
    time.sleep(1000)
```
