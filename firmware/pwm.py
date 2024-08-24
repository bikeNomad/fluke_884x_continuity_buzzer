import machine
from micropython import const
from gpio_config import PIN_BUZZER1, PIN_BUZZER2

PWM_FREQUENCY = const(1000)  # 1 kHz
PWM_DUTY_CYCLE = const(32768)  # 50%

# Global register EN has an alias of the CSR_EN flag for each slice.
PWM_EN = const(0x400500A0)  # bits 0-7 are the enable bits for each PWM slice

pwm1 = None
pwm2 = None

# Configure PWM on GPIO pins 28 and 29
# Both of these pins are connected to the piezo buzzer.
# They are also controlled by PWM slice #6, so we can use them to generate complementary PWM signals.


def initialize_pwm():
    global pwm1, pwm2
    if pwm1 is None:
        pwm1 = machine.PWM(machine.Pin(PIN_BUZZER1), freq=PWM_FREQUENCY, invert=False)
        pwm1.duty_u16(PWM_DUTY_CYCLE)
    if pwm2 is None:
        pwm2 = machine.PWM(machine.Pin(PIN_BUZZER2), freq=PWM_FREQUENCY, invert=True)
        pwm2.duty_u16(PWM_DUTY_CYCLE)

    enable_pwm(False)


def enable_pwm(enable=True):
    if enable:
        machine.mem32[PWM_EN] |= 0x40  # enable slice 6
    else:
        machine.mem32[PWM_EN] &= ~0x40  # disable slice 6
