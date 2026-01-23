import time
import serial
from PIL import Image
import re
import math

abs_x_pos = 0
abs_y_pos = 0


daisywheel_charmap = {
  ".": 0x00,
  ",": 0x01,
  "-": 0x02,
  "v": 0x03,
  "l": 0x04,
  "m": 0x05,
  "j": 0x06,
  "w": 0x07,
  "²": 0x08,
  "µ": 0x09,
  "f": 0x0A,
  "^": 0X0B,
  ">": 0x0C,
  "´": 0x0D,
  "+": 0x0E,
  "1": 0x0F,
  "2": 0x10,
  "3": 0x11,
  "4": 0x12,
  "5": 0x13,
  "6": 0x14,
  "7": 0x15,
  "8": 0x16,
  "9": 0x17,
  "0": 0x18,
  "E": 0x19,
  "pound": 0x1a,
  "B": 0x1b,
  "F": 0x1c,
  "P": 0x1d,
  "S": 0x1e,
  "Z": 0x1f,
  "V": 0x20,
  "&": 0x21,
  "Y": 0x22,
  "A": 0x23,
  "T": 0x24,
  "L": 0x25,
  "$": 0x26,
  "R": 0x27,
  "*": 0x28,
  "C": 0x29,
  "\"": 0x2A,
  "D": 0x2B,
  "?": 0x2C,
  "N": 0x2D,
  "I": 0x2E,
  "U": 0x2F,
  ")": 0x30,
  "W": 0x31,
  "_": 0x32,
  "=": 0x33,
  ";": 0x34,
  ":": 0x35,
  "M": 0x36,
  "'": 0x37,
  "H": 0x38,
  "(": 0x39,
  "K": 0x3A,
  "/": 0x3B,
  "O": 0x3C,
  "!": 0x3D,
  "X": 0x3E,
  "paragraph": 0x3F,
  "Q": 0x40,
  "J": 0x41,
  "%": 0x42,
  "hoch 3": 0x43,
  "G": 0x44,
  "grad": 0x45,
  "UE": 0x46,
  "`": 0x47,
  "OE": 0x48,
  "<": 0x49,
  "AE": 0x4A,
  "#": 0x4B,
  "t": 0x4C,
  "x": 0x4D,
  "q": 0x4E,
  "ß": 0x4F,
  "ue": 0x50,
  "oe": 0x51,
  "ae": 0x52,
  "y": 0x53,
  "k": 0x54,
  "p": 0x55,
  "h": 0x56,
  "c": 0x57,
  "g": 0x58,
  "n": 0x59,
  "r": 0x5A,
  "s": 0x5B,
  "e": 0x5C,
  "a": 0x5D,
  "i": 0x5E,
  "d": 0x5F,
  "u": 0x60,
  "b": 0x61,
  "o": 0x62,
  "z": 0x63,
}


def wait_cts(ser):
    for i in range(5):
        while not ser.cts:
            time.sleep(0.01)

def serial_slow_write(ser, data):
    #print(data)
    for x in data:
        wait_cts(ser)
        ser.write(bytearray([x]))
        ser.flush()
        wait_cts(ser)

def serial_sync(ser):
    sync = False
    tries = 0
    while not sync:
        ser.reset_input_buffer()
        serial_slow_write(ser, bytearray([0xA4, 0x00]))
        ser.timeout = 0.2
        buf = ser.read(10)
        if len(buf) >= 10:
            sync = True
        else:
            # we might be desynchronised
            print("desync :(")
            serial_slow_write(ser, bytearray([0x00]))
            tries += 1
            if tries > 5:
                raise Exception("Failed to send ENQ command 5 times :(") 

def bring_online(ser):
    serial_slow_write(ser, bytearray([0xA0, 0x00])) # CLEAR-Kommando -> die Schreibmaschine geht in den OFFLINE-Zustand und wird wieder “Schreibmaschine”.
    serial_slow_write(ser, bytearray([0xA1, 0x00])) # START-Kommando —> Übergang zu ONLINE wird vorbereitet
    serial_slow_write(ser, bytearray([0xA4, 0x00])) # ENQ-Kommando —> Schreibmaschine soll Zustand melden
    serial_slow_write(ser, bytearray([0xA2, 0x00])) # STX-Kommando —> Schreibmaschine wird “Drucker”, Zustand “ONLINE”, Übertragung von Druckbefehlen kann beginnen

def home_carriage(ser):
    serial_slow_write(ser, bytearray([0x82, 0x0F]))
    time.sleep(3)

def carriage_return(ser):
    serial_slow_write(ser, bytearray([0x82, 0x0F]))
    time.sleep(1)

def print_wheel(ser, wheelpos, strength, advance_carriage = True):
    if wheelpos > 0x7F:
        raise Exception("invalid wheelpos, greater than 0x7F")
    if strength > 0x3F:
        raise Exception("invalid strength, greater than 0x1F")

    buf = 0x00
    advance_left = False

    if advance_carriage:
        buf = buf | (1 << 7)

    if advance_left:
        buf = buf | (1 << 6)

    buf = buf | (strength & 0x3F)

    #print(bytearray([wheelpos, buf]))
    serial_slow_write(ser, bytearray([wheelpos, buf]))
    #time.sleep(0.1)

def space(ser):
    serial_slow_write(ser, bytearray([0x83, 0x00]))
    time.sleep(0.05)

def line_feed(ser):
    serial_slow_write(ser, bytearray([0xD0, 0x0F]))
    time.sleep(1)

def move_carriage(ser, vertical, leftOrBackwards, distance):
    distance = abs(distance)
    if distance > 0xFFF:
        raise Exception("invalid distance, greater than 4095")

    first_buf = 0x00
    if vertical:
        first_buf = first_buf | (1 << 4)

    if leftOrBackwards:
        first_buf = first_buf | (1 << 5)

    first_buf = first_buf | (1 << 6)
    first_buf = first_buf | (1 << 7)

    first_buf = first_buf | ((distance >> 8) & 0x0F)
    second_buf = distance & 0xFF

    #print(bytearray([first_buf, second_buf]))
    serial_slow_write(ser, bytearray([first_buf, second_buf]))
    time.sleep(0.1)

    time.sleep(float(80.0 + 2.0 * distance) / 1000.0)

def move_absolute_x(ser, x):
    global abs_x_pos

    steps_to_move = x - abs_x_pos

    #print(f"move_absolute_x: x: {x}, abs_x_pos: {abs_x_pos}, steps: {steps_to_move}")
    if steps_to_move > 0:
        move_carriage(ser, False, False, steps_to_move)

    if steps_to_move < 0:
        move_carriage(ser, False, True, steps_to_move)

    abs_x_pos = x

def move_absolute_y(ser, y):
    global abs_y_pos

    steps_to_move = y - abs_y_pos

    #print(f"move_absolute_y: y: {y}, abs_y_pos: {abs_y_pos}, steps: {steps_to_move}")
    if steps_to_move > 0:
        move_carriage(ser, True, False, steps_to_move)

    if steps_to_move < 0:
        move_carriage(ser, True, True, steps_to_move)

    abs_y_pos = y

def print_char(ser, char, strength):
    if char in daisywheel_charmap:
        print_wheel(ser, daisywheel_charmap[char] + 1, strength)

    if ord(char) == 0x0A:
        # line feed
        carriage_return(ser)
        line_feed(ser)

    if ord(char) == 0x0D:
        # carriage return
        carriage_return(ser)

    if ord(char) == 0x20: # space
        space(ser)

def print_string(ser, stri, strength):
    for x in stri:
        print_char(ser, x, strength)

def print_image(ser, imagefile):
    steps_per_pixel = 2
    typewriter_x_pos = 0

    img = Image.open(imagefile)
    pix = img.load()
    for y in range(img.height):
        print (f"New Y: {y}")
        move_carriage(ser, False, True, typewriter_x_pos) # Carriage return
        typewriter_x_pos = 0
        move_carriage(ser, True, False, 2) # Advance one pixel vertically

        for x in range(img.width):

            color = pix[x,y]
            if color == 0:
                steps_to_move = (x * steps_per_pixel) - typewriter_x_pos
                move_carriage(ser, False, False, steps_to_move)
                typewriter_x_pos += steps_to_move
                print(f"Moving carriage right by {steps_to_move} steps")
                
                #print_wheel(ser, daisywheel_charmap["."], 0x15, False)


ser = serial.Serial(None, 4800, timeout=None, parity=serial.PARITY_NONE, rtscts=False)

ser.port = '/dev/serial/by-id/usb-Silicon_Labs_CP2104_USB_to_UART_Bridge_Controller_020YOCAE-if00-port0'
ser.rts = True
ser.open()

#time.sleep(1)
#bring_online(ser)

serial_sync(ser)
home_carriage(ser)
time.sleep(1)
serial_sync(ser)
serial_sync(ser)
#for x in range(125):
#   print_wheel(ser, x + 2, 0x1F)

#content = open('meow.txt', 'r').read()
#print_string(ser, content, 0x1F)

#move_carriage(ser, False, False, 681)


# latex Latex-Briefvorlage.tex && dvitype -dpi=1000 -magnification=1000 Latex-Briefvorlage.dvi
dvidata = open('dvidata.txt', 'r').read()

current_y_steps = 0
for line in dvidata.splitlines():
    # Y coords
    level_regex = r"level .*?,vv=([\-0-9]+)\)"
    matches = re.finditer(level_regex, line, re.MULTILINE)
    for matchNum, match in enumerate(matches, start=1):
        vv = match.group(1)

        y_steps = math.ceil(float(vv) / 1000.0 * 96.0)
        current_y_steps = y_steps

    setchar_regex = r"setchar([0-9]+) .*?, hh:=([\-0-9]+)"
    matches = re.finditer(setchar_regex, line, re.MULTILINE)
    for matchNum, match in enumerate(matches, start=1):
        character = str(chr(int(match.group(1))))
        hh = int(match.group(2))

        x_steps = math.ceil(float(hh) / 1000.0 * 120.0)

        move_absolute_y(ser, current_y_steps + 100)
        move_absolute_x(ser, x_steps + 100)

        #print(f"{character} @ X: {x_steps}, Y: {abs_y_pos}")

        if character in daisywheel_charmap:
            print_wheel(ser, daisywheel_charmap[character] + 1, 0x1F, False)

        time.sleep(0.1)

#print_image(ser, "awake.png")
#ser.flush()
#ser.close()