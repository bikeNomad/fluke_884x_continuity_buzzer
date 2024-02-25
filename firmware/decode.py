# Main module for the Fluke 8840A/8842A multimeter continuity tester.
# Digit lines G0-G7 are active-high, with a period of 4.6ms
# Segment lines Px are active-high.
# Switch return lines Sx are active-low and are synced to G0-G3.
from time import sleep_ms, sleep_us
import gpio_config
from gpio_config import read_gpio_pins, BIT
from micropython import const
import array
import pwm

# Delay in microseconds to wait after a digit line goes high before reading the GPIO pin states.
# Digit lines are high for 600us, then low for 4ms.
_EDGE_DELAY_US = const(200)
# Special segments that indicate that continuity is not present on the Fluke 8840A/8842A multimeter.
_NO_CONTINUITY = set(("OVER", "ERROR", "CAL", "mA", "mV", "DC", "AC", "M", "k"))
# Maximum resistance value that indicates continuity
_CONTINUITY_THRESHOLD = 10.0


# import all the PIN_ constants from gpio_config.py into this module's namespace
# as bit masks, translating gpio_config.PIN_XXX to XXX=BIT(XXX)
for name in dir(gpio_config):
    if name.startswith("PIN_"):
        globals()[name[4:]] = BIT(getattr(gpio_config, name))


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
# Digits 2-6 are normal 7-segment digits.
SEGMENT_LOOKUP = {
    (PA | PB | PC | PD | PE | PF): 0,
    (PB | PC): 1,
    (PA | PB | PD | PE | PG): 2,
    (PA | PB | PC | PD | PG): 3,
    (PB | PC | PF | PG): 4,
    (PA | PC | PD | PF | PG): 5,
    (PA | PC | PD | PE | PF | PG): 6,
    (PA | PB | PC): 7,
    (PA | PB | PC | PD | PE | PF | PG): 8,
    (PA | PB | PC | PF | PG): 9,
}

# Digit 1 is the +1 or -1 digit.
SEGMENT_LOOKUP_DIGIT_1 = {
    (PA | PB | PC): 1,  # positive 1
    (PA | PC): 1,  # negative 1
    (PB | PC): 0, # positive 0
    (PC): 0, # negative 0
}

SIGN_LOOKUP_DIGIT_1 = {
    (PB | PC): 1,  # positive
    (PC): -1,  # negative
}

# Lookup table by digit number and GPIO pin number to map the masked 32-bit GPIO port reading
# to the special segments on the 7-segment display.
# Keys are digit numbers.
# Values are tuples of (mask, (pin value(s), segment name) [, ...])
SPECIAL_LOOKUP = {
    0: (
        (PA | PB | PC | PD | PS1 | PS2 | PS3),  # mask
        (PA, "EX"),
        (PB, "TRIG"),
        (PC, "TEST"),
        (PD, "REMOTE"),
        (PS1, "TALK"),
        (PS2, "LISTEN"),
        (PS3, "SRQ"),
    ),
    1: (
        (PS1 | PS2 | PS3),  # mask
        (PS1, "S"),  # slow
        (PS2, "M"),  # medium
        (PS3, "F"),  # fast
    ),
    2: (PS1, (PS1, "OVER")),
    3: (PS1, (PS1, "ERROR")),
    4: (PS1, (PS1, "CAL")),
    5: (PS1, (PS1, "AUTO")),
    6: (
        (PS1 | PS2 | PS3),  # mask
        (PS1, "OFFSET"),
        (PS2, "m"),
        (PS3, "V"),
    ),
    7: (
        (PA | PB | PC | PS1 | PS2 | PS3 | PDP),  # mask
        (PA, "mA"),
        (PB, "DC"),
        (PC, "AC"),
        (PS1, "M"),
        (PS2, "k"),
        (PS3, "Ω"),
        (PDP, "4 WIRE"),
    ),
}

FORMAT_LOOKUP = [
    [('m', 'V', 'DC'), 'mV DC'],
    [('m', 'V', 'AC'), 'mV AC'],
    [('V', 'DC'), 'V DC'],
    [('V', 'AC'), 'V AC'],
    [('k', 'Ω'), 'kΩ'],
    [('M', 'Ω'), 'MΩ'],
    [('Ω'), 'Ω'],
    [('mA', 'DC'), 'mA DC'],
    [('mA', 'AC'), 'mA AC'],
]


# Given a 32-bit GPIO port reading, return the currently-displayed digit on the 7-segment display.
# Assumes that the GPIO port reading is valid and that only one digit is active at a time.
# Assumes that segment lines are active-high.
# @param digit_number: int 0-7 corresponding to G0-G7 active
# @param value: int reading from GPIO port
def read_digit(digit_number, value) -> int:
    segment_lines = value & SEGMENT_MASK
    # look up the digit in the table
    return (
        SEGMENT_LOOKUP_DIGIT_1.get(segment_lines, 0)
        if digit_number == 1
        else SEGMENT_LOOKUP.get(segment_lines, 0)
    )


# Return True if the decimal point is active for the given digit number and GPIO port reading.
# The only valid digit numbers are 1-6.
def read_dp(digit_number, value) -> bool:
    if 1 <= digit_number <= 6:
        return (value & PDP) == PDP  # active-high
    return False


# Return a set of strings representing the special segments that are active for the given digit number and GPIO port reading.
def read_specials(digit_number: int, value) -> set:
    smask, *patterns = SPECIAL_LOOKUP.get(digit_number, (0,))
    retval = set()
    if smask == 0:
        return retval
    segment_lines = value & smask  # segment lines are active-high
    for mask, name in patterns:
        if segment_lines & mask == mask:
            retval.add(name)
    return retval


# Format the specials set as a string, giving the range and units.
# Outputs strings like:
# "V DC"
# "V AC"
# "Ω", "kΩ", "MΩ"
# "mA DC"
# "mA AC"
def format_specials(specials: set) -> str:
    for pattern, result in FORMAT_LOOKUP:
        if specials.issuperset(pattern):
            return result


# Given a 32-bit GPIO port reading, return the currently-active digit number (G0-G7) on the 7-segment display.
# Assumes that the GPIO port reading is valid and that only one digit is active at a time.
# Assumes that digit lines are active-high.
def read_digit_number(value):
    return DIGIT_LOOKUP[value & DIGIT_MASK]


# Read the states of the GPIO pins when each of the G0-G7 digit lines becomes active.
# Store the results in the given array.
# Assumes that digit lines are active-high.
def read_all_digit_gpios_into(arr: array.array):
    for digit_number, digit_mask in enumerate((G0, G1, G2, G3, G4, G5, G6, G7)):
        # wait until digit line goes high
        while read_gpio_pins() & digit_mask == 0:
            pass
        # wait a little bit for the signal to stabilize
        sleep_us(_EDGE_DELAY_US)
        # read the GPIO pin states
        arr[digit_number] = read_gpio_pins()


def make_float(digits, decimal_point_position, sign):
    # build a floating point number from the digits and decimal point position
    full_number = 0
    for digit_number in range(1, 7):
        full_number += abs(digits[digit_number])
        full_number *= 10
    # Now scale the number to the right place using decimal_point_position
    full_number /= 10 ** (7 - decimal_point_position)
    return full_number * sign


# Generator that reads the GPIO pin states when each of the G0-G7 digit lines becomes active,
# decodes the display, and yields the results.
def read_all_digit_gpios(gpio_values, digits, specials):
    while True:
        specials.clear()
        decimal_point_position = 0
        read_all_digit_gpios_into(gpio_values)
        for digit_number, value in enumerate(gpio_values):
            digit = read_digit(digit_number, value)
            digits[digit_number] = digit
            if read_dp(digit_number, value):
                decimal_point_position = digit_number
            sp = read_specials(digit_number, value)
            specials.update(sp)
            # print(f"{digit_number} {value:08x} {digit} {sp}")
        sign = SIGN_LOOKUP_DIGIT_1.get(gpio_values[1] & (PB | PC), 1)
        yield make_float(digits, decimal_point_position, sign), specials


# Return True if the given value is a valid continuity reading.
def has_continuity(value: float, specials: set):
    if not specials.isdisjoint(_NO_CONTINUITY):
        return False
    return value <= _CONTINUITY_THRESHOLD

def print_result(value, specials, cont):
    if 'OVER' in specials:
        print(f"OVER {format_specials(specials)}")
    elif 'ERROR' in specials:
        print(f"ERROR {value}")
    else:
        print(f"{value:5f} {format_specials(specials)}{' *' if cont else ''}")

def main_loop():
    gpio_values = array.array("L", [0, 0, 0, 0, 0, 0, 0, 0])
    digits = array.array(
        "b", [0, 0, 0, 0, 0, 0, 0, 0]
    )  # signed because of possible leading -1
    specials = set()
    for value, specials in read_all_digit_gpios(gpio_values, digits, specials):
        cont = has_continuity(value, specials)
        if cont:
            pwm.enable_pwm()  # buzzer ON
        else:
            pwm.disable_pwm()  # buzzer OFF

        print_result(value, specials, cont)