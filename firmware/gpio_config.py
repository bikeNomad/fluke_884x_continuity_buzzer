# Definitions of GPIO pin names and numbers
from micropython import const
from machine import Pin, mem32

# GPIO pin names for the RP2040 microcontroller pins connected to the Fluke multimeter signals.
# The pin numbers are the GPIO pin numbers on the RP2040.
# The pin names are the names used in the Fluke 8840A/8842A multimeter documentation.
# RL0-RL6 are the switch return lines for the matrix keyboard and are active-low signals.
# G0-G7 are the digit select lines for the 7-segment display and are active-high signals.
# PA-PG are the segment select lines for the 7-segment display and are active-high signals.
# PDP is the decimal point signal for the 7-segment display and is an active-high signal.
# PS1-PS3 are the segment select lines for the extra words on the display and are active-high signals.
PIN_RL3 = const(0)
PIN_RL5 = const(1)
PIN_RL2 = const(2)
PIN_RL4 = const(3)
PIN_RL6 = const(4)
PIN_G5 = const(5)
PIN_RL1 = const(6)
PIN_G7 = const(7)
PIN_RL0 = const(8)
PIN_G6 = const(9)
PIN_G2 = const(10)
PIN_PDP = const(11)
PIN_G3 = const(12)
PIN_PS1 = const(13)
PIN_G4 = const(14)
PIN_PD = const(15)
PIN_PC = const(16)
PIN_PG = const(17)
PIN_PA = const(18)
PIN_PS3 = const(19)
PIN_PB = const(20)
PIN_PS2 = const(21)
PIN_PF = const(22)
PIN_G0 = const(23)
PIN_G1 = const(24)
PIN_PE = const(25)

# Control of the 74LVC8T245 level shifter for the keyboard signals.
# High for A=>B (read from meter), Low for B=>A (force keypad signals)
PIN_RL_DIR = const(26)
PIN_RL_OE_n = const(27)  # Low to enable the 74LVC8T245 outputs.

# Two GPIO pins are used to drive the piezo buzzer.
PIN_BUZZER1 = const(28)
PIN_BUZZER2 = const(29)

INPUT_PIN_MASK = const(0x03FFFFFF)  # mask for the 26 GPIO pins used as inputs

# Address of the GPIO input register on the RP2040
GPIO_IN_ADDR = const(0xD0000004)
GPIO_OUT_ADDR = const(0xD0000010)
GPIO_OE_ADDR = const(0xD0000020)
GPIO_OE_SET_ADDR = const(0xD0000024)
GPIO_OE_CLEAR_ADDR = const(0xD0000028)


def initialize_pins():
    # Set all the GPIO pins to inputs with pull-up resistors.
    for pin in range(26):
        Pin(pin, Pin.IN, 0)

    # Set the RL_DIR and RL_OE_n pins to outputs.
    Pin(PIN_RL_DIR, Pin.OUT).value(1)  # Set the direction to A=>B (read from meter)
    # Enable the 74LVC8T245 outputs so we can read the keyboard matrix.
    Pin(PIN_RL_OE_n, Pin.OUT).value(0)

    # Set the piezo buzzer pins to outputs.
    Pin(PIN_BUZZER1, Pin.OUT).value(0)
    Pin(PIN_BUZZER2, Pin.OUT).value(0)


# Read all 30 of the GPIO pin states at once.
def read_gpio_pins() -> int:
    return mem32[GPIO_IN_ADDR]


# Write a selected subset of the GPIO pins.
# The mask selects which bits to write.
def write_gpio_pins(mask, value) -> None:
    # set the GPIO output direction to output
    mem32[GPIO_OE_SET_ADDR] = mask
    mem32[GPIO_OUT_ADDR] = value


# Stop writing the masked outputs.
def dont_write_gpio_pins(mask):
    mem32[GPIO_OE_CLEAR_ADDR] = mask


# Create a bit mask for a given bit number
def BIT(n):
    return 1 << n
