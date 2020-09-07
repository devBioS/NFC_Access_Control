"""
Keypad module/class for MicroPython, using a timer callback (interrupt)
=======================================================================

Notes
-----

    * Timer callbacks do not allow any memory to be allocated on the heap.
        - `for x in [list]` loop can NOT be used as an iterator object is allocated.
           NOTE: may not be true for newer versions of MicroPython !!
        - `for x in range(y)` is ok.

    * To run type:
        >>> import keypad_timer
        >>> keypad_timer.run()

Testing
-------

    * Tested on an Olimex E407 board (STM32F407 micro-controller)
    https://www.olimex.com/Products/ARM/ST/STM32-E407

    * with 16-key (4x4 matrix) membrane keypad, similar to this (bought on eBay).
    https://www.youtube.com/watch?v=wRse5uqvPZs

To Do
-----

    * Pass the key and pin info to the class via function parameters.
    * Support long key press events.
    * Refactor into a common base class.
    * Unit tests :-/
    * Video the keypad working :)
    * Fix bugs :)

"""

#!============================================================================

import micropython

#try:
from machine import Pin
#except ImportError :
#    from pyb import Pin

#try:
from machine import Timer
#except ImportError :
#    from pyb import Timer

#!============================================================================

class Keypad_Timer () :
    """
    Class to scan a Keypad matrix (e.g. 16-keys as 4x4 matrix) and report
    last key press.
    """

    #! Key states
    KEY_UP      = const( 0 )
    KEY_DOWN    = const( 1 )

    #-------------------------------------------------------------------------

    def __init__ ( self,pins_row,pins_col ) :
        self.init(pins_row=pins_row,pins_col=pins_col)

    #-------------------------------------------------------------------------

    def init ( self,pins_row,pins_col ) :
        """Initialise/Reinitialise the instance."""

        keys = [
                '1', '2', '3', 'A',
                '4', '5', '6', 'B',
                '7', '8', '9', 'C',
                '*', '0', '#', 'D',
               ]

        #! Initialise all keys to the UP state.
        self.keys = [ { 'char' : key, 'state' : self.KEY_UP } for key in keys ]

        #! Pin names for rows and columns.
        self.rows = pins_row # [ 'PD1', 'PD3', 'PD5', 'PD7' ]
        self.cols = pins_col # [ 'PD9', 'PD11', 'PD13', 'PD15' ]

        #! Initialise row pins as outputs.
        self.row_pins = [ Pin(pin_name, mode=Pin.OUT) for pin_name in self.rows ]

        #! Initialise column pins as inputs.
        self.col_pins = [ Pin(pin_name, mode=Pin.IN, pull=Pin.PULL_DOWN) for pin_name in self.cols ]

        self.timer = Timer(5)
        
        
        #self.timer.callback( None )

        self.scan_row = 0
        self.key_code = None
        self.key_char = ""

    #-------------------------------------------------------------------------

    def get_key ( self ) :
        """Get last key pressed."""

        key_char = self.key_char

        self.key_code = None    #! consume last key pressed
        self.key_char = ""    #! consume last key pressed

        return key_char

    #-------------------------------------------------------------------------

    def key_process ( self, key_code, col_pin ) :
        """Process a key press or release."""

        key_event = None

        if col_pin.value() :
            if self.keys[ key_code ][ 'state' ] == self.KEY_UP :
                key_event = self.KEY_DOWN
                self.keys[ key_code ][ 'state' ] = key_event
        else:
            if self.keys[ key_code ][ 'state' ] == self.KEY_DOWN :
                key_event = self.KEY_UP
                self.keys[ key_code ][ 'state' ] = key_event

        return key_event

    #-------------------------------------------------------------------------

    def scan_row_update(self):
        """
        Timer interrupt callback to scan next keypad row/column.
        NOTE: This is a true interrupt and no memory can be allocated !!
        """

        #! Deassert row.
        self.row_pins[ self.scan_row ].value( 0 )

        #! Next scan row.
        self.scan_row = ( self.scan_row + 1 ) % len( self.row_pins )

        #! Assert next row.
        self.row_pins[ self.scan_row ].value( 1 )

    #-------------------------------------------------------------------------

    def timer_callback ( self, timer ) :
        """
        Timer interrupt callback to scan next keypad row/column.
        NOTE: This is a true interrupt and no memory can be allocated !!
        """

        #print("DEBUG: Keypad.timer_callback()")

        #! Can't use `for x in [list]` loop in micropython time callback as memory is allocated
        #! => exception in timer interrupt !!

        #! key code/index for first column of current row
        key_code = self.scan_row * len( self.cols )

        for col in range( len( self.cols ) ) :
            #! Process pin state.
            key_event = self.key_process( key_code, self.col_pins[ col ] )
            
            #! Process key event.
            if key_event == self.KEY_DOWN:
                self.key_code = key_code
                self.key_char += self.keys[ key_code ][ 'char' ]

            #! Next key code (i.e. for next column)
            key_code += 1

        self.scan_row_update()

    #-------------------------------------------------------------------------

    def start ( self ) :
        """Start the timer."""

        self.timer.init(mode=Timer.PERIODIC, period=10, callback=self.timer_callback)
        #self.timer.callback( self.timer_callback )

    #-------------------------------------------------------------------------

    def stop ( self ) :
        """Stop the timer."""
        self.timer.deinit()
        #self.timer.callback( None )



