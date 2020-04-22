# Machine is a MicroPython library.
from machine import Pin, UART, I2C
import time

serial = UART(4, 115200)
serial.init(115200, bits=8, parity=None, stop=1)

i2c2 = I2C(scl=Pin('PB10'), sda=Pin('PB11'), freq=100000)


# Get PB14 and treat it as a GPIO Output pin
led_1 = Pin('PB14', Pin.OUT)
led_2 = Pin('PA5', Pin.OUT)
value1 = 1
value2 = 0

# Toggle the pin every one second
while 1:
    led_1.value(value1)
    led_2.value(value2)
    if value1 == 1:
        value1 = 0
        value2 = 1
    else:
        value1 = 1
        value2 = 0

    buff = bytearray(100)
    var = serial.readinto(buff)
    if (var != None):
        print("Preamble: " + str(hex(buff[0])))
        print("Type: " + str((buff[1] >> 4)))
        print("Length: " + str(buff[1] & 0x0F))
        print("SID: " + str(buff[2]))
        print("I2CAddr: " + str(hex(buff[3])))
        print("Regaddr: " + str(hex(buff[4])))
        print("Regval: " + str(buff[5]))
        print("\n\n")
        
    serial.write("Tx String\n")

    # Somewhat similar to HAL_Delay()
    time.sleep(1)