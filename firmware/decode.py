from machine import Pin, PWM
from micropython import const
from time import sleep_ms
import gpio_config


def BIT(n):
    return 1 << n


# import all the PIN_ constants from gpio_config.py into this module's namespace
# as bit masks, translating PIN_XXX to BIT(XXX)
for name in dir(gpio_config):
    if name.startswith("PIN_"):
        globals()[name.removeprefix("PIN_")] = BIT(getattr(gpio_config, name))


SEGMENT_MASK = PA | PB | PC | PD | PE | PF | PG
DIGIT_MASK = G0 | G1 | G2 | G3 | G4 | G5 | G6 | G7

# Keys: bit mask of the GPIO port reading for a digit
# values: digit number
DIGIT_LOOKUP = {
    G0: 0,
    G1: 1,
    G2: 2,
    G3: 3,
    G4: 4,
    G5: 5,
    G6: 6,
    G7: 7,
}

# Lookup table to map the masked 32-bit GPIO port reading to a digit on the 7-segment display.
SEGMENT_LOOKUP = {
    PA | PB | PC | PD | PE | PF: 0,
    PB | PC: 1,
    PA | PB | PD | PE | PG: 2,
    PA | PB | PC | PD | PG: 3,
    PB | PC | PF | PG: 4,
    PA | PC | PD | PF | PG: 5,
    PA | PC | PD | PE | PF | PG: 6,
    PA | PB | PC: 7,
    PA | PB | PC | PD | PE | PF | PG: 8,
    PA | PB | PC | PF | PG: 9,
}

SEGMENT_LOOKUP_DIGIT_1 = {
    PA | PB | PC | PD: 1,  # positive 1
    PA | PC | PD: -1,  # negative 1
}

# Lookup table by digit number and GPIO pin number to map the masked 32-bit GPIO port reading
# to the special segments on the 7-segment display.
# Keys are digit numbers.
# Values are tuples of (mask, tuple(pin values, segment names))
SPECIAL_LOOKUP = {
    0: (
        PA | PB | PC | PD | PS1 | S2 | PS3,
        (PA, "EX"),
        (PB, "TRIG"),
        (PC, "TEST"),
        (PD, "REMOTE"),
        (PS1, "TALK"),
        (PS2, "LISTEN"),
        (PS3, "SRQ"),
    ),
    1: (
        S1 | S2 | S3,
        (S1, "S"),  # slow
        (S2, "M"),  # medium
        (S3, "F"),  # fast
    ),
    2: (S1, (S1, "OVER")),
    3: (S1, (S1, "ERROR")),
    4: (S1, (S1, "CAL")),
    5: (S1, (S1, "AUTO")),
    6: (
        S1 | S2 | S3,
        (S1, "OFFSET"),
        (S2, "mV"),
        (S3, "V"),
    ),
    7: (
        PA | PB | PC | S1 | S2 | S3 | PDP,
        (PA, "mA"),
        (PB, "DC"),
        (PC, "AC"),
        (S1, "M"),
        (S2, "k"),
        (S3, "Ω"),
        (PDP, "4WIRE"),
    ),
}


# Given a 32-bit GPIO port reading, return the currently-active digit on the 7-segment display.
# Assumes that the GPIO port reading is valid and that only one digit is active at a time.
# Assumes that segment lines are active-low and digit lines are active-high.
def read_digit(digit_number, value):
    segment_lines = value & SEGMENT_MASK
    # invert value because segment lines are active-low
    segment_lines = ~segment_lines
    # look up the digit in the table
    if digit_number == 1:
        return SEGMENT_LOOKUP_DIGIT_1[segment_lines]
    else:
        return SEGMENT_LOOKUP[segment_lines]


# Return True if the decimal point is active for the given digit number and GPIO port reading.
def read_dp(digit_number, value):
    if 1 <= digit_number <= 6:
        return (value & PDP) == 0
    return False


# Return a list of strings representing the special segments that are active for the given digit number and GPIO port reading.
def read_specials(digit_number, value):
    mask, patterns = SPECIAL_LOOKUP.get(digit_number, (0,))
    retval = []
    if mask == 0:
        return retval
    segment_lines = ~(value & SEGMENT_MASK)
    for mask, value in patterns:
        if segment_lines & mask == mask:
            retval.append(value)
    return retval


# Given a 32-bit GPIO port reading, return the currently-active digit number (G0-G7) on the 7-segment display.
# Assumes that the GPIO port reading is valid and that only one digit is active at a time.
# Assumes that digit lines are active-high.
def read_digit_number(value):
    return DIGIT_LOOKUP[value & DIGIT_MASK]
