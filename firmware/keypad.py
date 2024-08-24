import gpio_config
from gpio_config import BIT, read_gpio_pins, write_gpio_pins, dont_write_gpio_pins
from machine import Pin
import array

rl_dir = Pin(gpio_config.PIN_RL_DIR, Pin.OUT)
rl_oe_n = Pin(gpio_config.PIN_RL_OE_n, Pin.OUT)
last_gpios = array.array("L", [0, 0, 0])
forced_gpios = array.array("L", [0, 0, 0])
pressed_keys = set()
forced_keys = set()


# import all the PIN_RLx and PIN_Gx constants from gpio_config.py into this module's namespace
# as bit masks, translating gpio_config.PIN_XXX to XXX=BIT(XXX)
for name in dir(gpio_config):
    if name.startswith("PIN_RL") or name.startswith("PIN_G"):
        globals()[name[4:]] = BIT(getattr(gpio_config, name))

# RL_DIR high A->B (read from meter)
# RL_OE_n low to enable 74LVC8T245 outputs
# RL0-RL6 returns from keypad (active low)
# G0-G2 strobes to keypad (active high)

RL_MASK = RL0 | RL1 | RL2 | RL3 | RL4 | RL5 | RL6
G_MASK = G0 | G1 | G2

# The 8840A and 8842A multimeters have different keypad layouts.

KEY_DECODE_8840A = {
    (0, 1): "SRQ",  # S0/RL0
    (0, 2): "LOC",
    (0, 3): "RATE",
    (0, 4): "OFFSET",
    (0, 5): "AUTO",
    (0, 6): "TRIG",
    (0, 7): "EXT TRIG",  # S0/RL6
    (1, 1): "200m",  # S1/RL0
    (1, 2): "2",
    (1, 3): "20",
    (1, 4): "200",
    (1, 5): "2000",
    (1, 6): "20M",  # S1/RL5
    # no key at (1, 7)
    (2, 1): "VDC",  # S2/RL0
    (2, 2): "VAC",
    (2, 3): "kΩ 2W",
    (2, 4): "kΩ 4W",
    (2, 5): "mA DC",
    (2, 6): "mA AC",  # S2/RL5
    # no key at (2, 7)
}

KEY_DECODE_8842A = {
    (0, 1): "SRQ",  # S0/RL0
    (0, 2): "LOC",
    (0, 3): "RATE",
    (0, 4): "OFFSET",
    (0, 5): "20M",
    (0, 6): "TRIG",
    (0, 7): "EXT TRIG",  # S0/RL6
    (1, 1): "20m",  # S1/RL0
    (1, 2): "200m",
    (1, 3): "2",
    (1, 4): "20",
    (1, 5): "200",
    (1, 6): "2000",  # S1/RL5
    # no key at (1, 7)
    (2, 1): "VDC",  # S2/RL0
    (2, 2): "VAC",
    (2, 3): "kΩ 2W",
    (2, 4): "kΩ 4W",
    (2, 5): "mA DC",
    (2, 6): "mA AC",
    (2, 7): "AUTO",  # S2/RL6
}


# Lookup table to map the masked 32-bit GPIO port reading to a 7-bit number.
def rl_decode(value: int) -> int:
    value = ~value  # invert the bits because the keypad is active low
    value &= RL_MASK
    retval = 0
    if value & RL0:
        retval |= 0x01
    if value & RL1:
        retval |= 0x02
    if value & RL2:
        retval |= 0x04
    if value & RL3:
        retval |= 0x08
    if value & RL4:
        retval |= 0x10
    if value & RL5:
        retval |= 0x20
    if value & RL6:
        retval |= 0x40
    return retval


# translate the 7-bit number to a masked 32-bit GPIO port reading
def rl_encode(value: int) -> int:
    retval = 0
    if value & 0x01:
        retval |= RL0
    if value & 0x02:
        retval |= RL1
    if value & 0x04:
        retval |= RL2
    if value & 0x08:
        retval |= RL3
    if value & 0x10:
        retval |= RL4
    if value & 0x20:
        retval |= RL5
    if value & 0x40:
        retval |= RL6
    return ~retval  # invert the bits because the keypad is active low


# Translate the G0-G2 masked 32-bit value to a number
# in the range 1-3, or 0 if no strobe is active.
def g_decode(value):
    retval = 0
    value &= G_MASK  # Only look at the G0-G2 bits
    if value == G0:
        retval = 0x01
    elif value == G1:
        retval = 0x02
    elif value == G2:
        retval = 0x03
    else:
        return 0
    return retval


# Read the keypad value from the GPIO value
# Return a strobe number and the decode return value
# or (0,0) if no strobe is active
def read():
    pin_value = read_gpio_pins()
    strobe_number = g_decode(pin_value)
    if strobe_number == 0:
        return
    return strobe_number, rl_decode(pin_value)


# strobe number is 1-3
# value is 0-127 bitmask of columns
def drive(strobe_number, value):
    pin_value = read_gpio_pins()
    strobe_value = g_decode(pin_value)
    if strobe_value != strobe_number:
        return
    rl_value = rl_encode(value)
    new_pin_value = (pin_value & ~RL_MASK) | rl_value
    # Set the direction to B=>A (force keypad signals)
    rl_dir.value(0)
    write_gpio_pins(RL_MASK, new_pin_value)


def release():
    # Set the direction to A=>B (read from meter)
    rl_dir.value(1)
    dont_write_gpio_pins(RL_MASK)


def initialize_io():
    # Set the direction to A=>B (read from meter)
    rl_dir.value(1)
    # Enable the 74LVC8T245 outputs so we can read the keyboard matrix.
    rl_oe_n.value(0)


# Generator that yields (group, bit_number) tuples for each bit that is set in value.
def tuples(group, value):
    mask = 1
    for bit_number in range(7):
        if value & mask:
            yield group, bit_number
        mask <<= 1


# updates pressed_keys and last_gpios
# returns True if any keys have changed state
# and pressed_keys has been updated
def interpret(gpio_values: array.array):
    changed = False
    for group in range(3):
        decoded = rl_decode(gpio_values[group])
        prior = last_gpios[group]
        if decoded != prior:
            changed = True
            pressed = decoded & ~prior
            released = prior & ~decoded
            for tup in tuples(group, pressed):
                pressed_keys.add(tup)
            for tup in tuples(group, released):
                pressed_keys.discard(tup)
            last_gpios[group] = decoded
    return changed
