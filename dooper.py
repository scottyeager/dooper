"""
A library for interfacing with SooperLooper.
"""

import liblo

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

class Looper:
    """
    Handles I/O with SooperLooper via OSC. Organizes loops.

    See documentation here: http://essej.net/sooperlooper/doc_osc.html

     /ping s:return_url s:return_path

     If engine is there, it will respond with to the given URL and PATH
      with an OSC message with arguments:
         s:hosturl  s:version  i:loopcount

     """

    def __init__(self, port=9950, sl_port=9951, verbose=False):
        self.port = port
        self.sl_port = sl_port
        self.verbose = verbose

        self.server = liblo.Server(port) #Define liblo server for replies

        self.server.add_method('/sl/ping', None, self.ping_responder)
        self.server.add_method('/sl/loop', None, self.loop_responder)

        self.init_loops()

    def __repr__(self):
        return 'Looper(port={}, sl_port={}, verbose={})'.format(self.port, self.sl_port, self.verbose)

    def init_loops(self):
        self.loop_count = 0
        self.loops = []
        if self.ping() and self.loop_count:
            for i in range(self.loop_count):
                self.loops.append(Loop(self, i))
                self.loops[i].get('state')
                self.receive()
        else:
            print("Couldn't initialize loops. Either ping to SooperLooper failed, or loop count is zero.")

    def send_osc(self, path, *args):
        if self.verbose:
            print('Sending OSC message: {} {}'.format(path, args))
        liblo.send(self.sl_port, liblo.Message(path, *args))

    def ping_responder(self, path, args):
        self.loop_count = args[2]
        if self.verbose:
            print('Received OSC message: {} {}'.format(path, args))

    def loop_responder(self, path, args):
        """ Listens for replies from SL about loops (probably set all loop replies to come to one path, like '/sl/loop'), then update loop object accordingly."""

        loop = self.loops[args[0]]
        control, value = args[1:]

        if control == 'state':
            loop.state = state_codes[value]

        else:
            pass

        if self.verbose:
            print('Received OSC message: {} {}'.format(path, args))

    def send(self, path1, path2, *args):
        message = '/sl/' + str(path1)
        if path2:
            message += '/' + str(path2)
        self.send_osc(message, *args)

    def receive(self, timeout=1):
        #Timeout of 0 is too small to reliably receive replies, and there's no way to recover from blocking in the main thread, at least in this case
        return self.server.recv(timeout)

    def register_updates(self):
        # Int is update interval, currently ignored and set to 100ms
        # We have to auto update to get state info but it only sends with change
        # Don't forget to receive messages
        for n in len(self.loops):
            self.send_osc('/sl/' + str(loop.number) + '/register_auto_update', 'state', 100, l.server.url, '/sl/loop')

    def ping(self, timeout=1):
        self.send_osc('/ping', self.server.url, '/sl/ping')
        return self.receive(timeout)


class Loop:
    def __init__(self, looper, number, state='Off'):
        self.looper = looper
        self.number = number
        self.state = state

    def __repr__(self):
        return 'Loop(looper={}, number={}, state={})'.format(
                self.looper.sl_port, self.number, self.state)

    def __str__(self):
        return 'Loop({}, {})'.format(self.number, self.state)

    def set(self, control, value):
        self.looper.send('set', control, value)

    def get(self, control):
        self.send('get', control, self.looper.server.url, '/sl/loop')

    def send(self, action, *args):
        self.looper.send(self.number, action, *args)

    def hit(self, command):
        self.send('hit', command)

    def record(self):
        self.hit('record')

    def overdub(self):
        self.hit('overdub')

    def mute(self):
        self.hit('mute')
