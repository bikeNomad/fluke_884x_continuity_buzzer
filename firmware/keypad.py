import gpio_config
from gpio_config import BIT, read_gpio_pins, write_gpio_pins, dont_write_gpio_pins
from machine import Pin


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


# Lookup table to map the masked 32-bit GPIO port reading to a 7-bit number.
def rl_decode(value):
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
def rl_encode(value):
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


rl_dir = Pin(gpio_config.PIN_RL_DIR, Pin.OUT)
rl_oe_n = Pin(gpio_config.PIN_RL_OE_n, Pin.OUT)


def initialize_keypad():
    # Set the direction to A=>B (read from meter)
    rl_dir.value(1)
    # Enable the 74LVC8T245 outputs so we can read the keyboard matrix.
    rl_oe_n.value(0)


# Read the keypad value from the GPIO value
# Return a strobe number and the decode return value
# or (0,0) if no strobe is active
def read_keypad(value):
    strobe_number = g_decode(value)
    if strobe_number == 0:
        return strobe_number, 0
    decoded = rl_decode(value)
    return strobe_number, decoded


# strobe number is 1-3
def drive_keypad(strobe_number, value):
    pin_value = read_gpio_pins()
    strobe_value = g_decode(pin_value)
    if strobe_value != strobe_number:
        return
    rl_value = rl_encode(value)
    new_pin_value = (pin_value & ~RL_MASK) | rl_value
    # Disable the 74LVC8T245 outputs so we can drive the keyboard matrix.
    rl_oe_n.value(1)
    # Set the direction to B=>A (force keypad signals)
    rl_dir.value(0)
    write_gpio_pins(new_pin_value, RL_MASK)