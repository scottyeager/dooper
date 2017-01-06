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
