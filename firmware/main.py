import decode
import gpio_config
import pwm

gpio_config.initialize_pins()
pwm.initialize_pwm()

decode.main_loop()