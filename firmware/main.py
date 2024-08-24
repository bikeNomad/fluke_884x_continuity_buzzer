import decode
import gpio_config
import pwm
import keypad

gpio_config.initialize_pins()
pwm.initialize_pwm()
keypad.initialize_io()

decode.main_loop()