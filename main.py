import machine
import time
import _thread
from ir_rx.nec import NEC_8  # NEC remote, 8 bit addresses

STATUS_REG = 0x11
STATUS_IN1_BIT = (1 << 0)
STATUS_IN2_BIT = (1 << 1)
STATUS_IN3_BIT = (1 << 2)
STATUS_OUT_BIT = (1 << 4)

EN_IN1_BIT = (1 << 7)
EN_IN2_BIT = (1 << 6)
EN_IN3_BIT = (1 << 5)

led1 = machine.Pin(4, mode=machine.Pin.OUT)
led2 = machine.Pin(5, mode=machine.Pin.OUT)
led3 = machine.Pin(6, mode=machine.Pin.OUT)
led4 = machine.Pin(2, mode=machine.Pin.OUT)
led5 = machine.Pin(3, mode=machine.Pin.OUT)

ir = machine.Pin(7)
btn = machine.Pin(1)

sda = machine.Pin(8) # Phy pin 11
scl = machine.Pin(9) # Phy pin 12
i2c = machine.I2C(0, sda=sda, scl=scl, freq=100000)

switch1 = 0x5A
switch2 = 0x4A

switch_input_to = 0
switch_input = False

connection_status = [False, False, False, False, False, False]

btn_last = time.ticks_ms()

def ir_handler(data, addr, ctrl):
    global switch_input_to, switch_input
    if data < 0:  # NEC protocol sends repeat codes.
        pass #print('Repeat code.')
    else:
        if addr == 0x0080:
            if data == 0x02:
                switch_input_to = 1
                switch_input = True
            elif data == 0x04:
                switch_input_to = 2
                switch_input = True
            elif data == 0x05:
                switch_input_to = 3
                switch_input = True
            elif data == 0x06:
                switch_input_to = 4
                switch_input = True
            elif data == 0x08:
                switch_input_to = 5
                switch_input = True

def button_handler(pin):
    global btn_last, switch_input, switch_input_to

    if time.ticks_diff(time.ticks_ms(), btn_last) > 100: # debounce
        btn_last = time.ticks_ms()
        switch_input_to = 0
        switch_input = True


def write(buf, addr1, addr2=None):
    i2c.writeto(addr1, buf)
    if addr2 is not None:
        i2c.writeto(addr2, buf)


def read_switch_status(switch_addr):
    try:
        #i2c.writeto(switch_addr, bytearray([STATUS_REG]))
        #ret, = i2c.readfrom(switch_addr, 1)
        ret, = i2c.readfrom_mem(switch_addr, STATUS_REG, 1)
    except OSError as e:
        print("Read status", hex(switch_addr), "comm error:", e)
        return None, None, None, None
    
    if ret == 0x10:
        print("Read status", hex(switch_addr), "unknown return code: 0x10")
        return None, None, None, None

    in1_conn = bool(ret & STATUS_IN1_BIT)
    in2_conn = bool(ret & STATUS_IN2_BIT)
    in3_conn = bool(ret & STATUS_IN3_BIT)
    out_conn = bool(ret & STATUS_OUT_BIT)

    return out_conn, in1_conn, in2_conn, in3_conn

def read_connection_status():
    _, in3_conn, in4_conn, in5_conn = read_switch_status(switch2)
    out_conn, in1_conn, in2_conn, _ = read_switch_status(switch1)
    return out_conn, in1_conn, in2_conn, in3_conn, in4_conn, in5_conn

def write_conf():
    write(b'\x02\xFC', switch1, switch2)
    write(b'\x03\x71', switch1, switch2)
    write(b'\x04\x5D', switch1, switch2)
    write(b'\x09\x42', switch1, switch2)

    write(b'\x0A\x0E', switch1)
    write(b'\x0A\x09', switch2)

    write(b'\x0B\x0A', switch1)
    write(b'\x0B\x09', switch2)

    write(b'\x0C\xC5', switch1)
    write(b'\x0C\xC0', switch2)

    write(b'\x0D\x01', switch1, switch2)

def switch_to_input(input_nr):
    assert 1 <= input_nr <= 5

    led1.low()
    led2.low()
    led3.low()
    led4.low()
    led5.low()

    sw1 = 0x18
    sw2 = 0x18
    
    if input_nr == 1:
        sw1 |= EN_IN1_BIT
        sw2 |= 0
        led1.high()
    elif input_nr == 2:
        sw1 |= EN_IN2_BIT
        sw2 |= 0
        led2.high()
    elif input_nr == 3:
        sw1 |= EN_IN3_BIT
        sw2 |= EN_IN1_BIT
        led3.high()
    elif input_nr == 4:
        sw1 |= EN_IN3_BIT
        sw2 |= EN_IN2_BIT
        led4.high()
    elif input_nr == 5:
        sw1 |= EN_IN3_BIT
        sw2 |= EN_IN3_BIT
        led5.high()
    
    write(bytearray([0x10, sw1]), switch1)
    write(bytearray([0x10, sw2]), switch2)

    write_conf()



def main():
    global connection_status, switch_input

    ir_nec = NEC_8(ir, ir_handler)

    btn.irq(button_handler, machine.Pin.IRQ_FALLING)

    try:
        write_conf()
    except OSError as e:
        print("Could not write conf, status:", e)

    try:
        switch_to_input(1)
    except OSError as e:
        print("Could not switch to screen, status:", e)

    cur_input = 0
    new_input = 1

    while True:

        if switch_input:
            switch_input = False
            
            if switch_input_to:
                new_input = switch_input_to
            else:
                for _ in range(6): # Loops around and if no connected input is found will just switch to next input
                    new_input = new_input % 5 + 1
                    if connection_status[new_input]:
                        break

        if cur_input != new_input:
            try:
                switch_to_input(new_input)
                cur_input = new_input
            except OSError as e:
                print("Could not switch to screen, status:", e)

        conn = read_connection_status()
        
        for i in range(len(conn)):
            if conn[i] is not None:
                connection_status[i] = conn[i]

        time.sleep(0.2)
 

if __name__ == "__main__":
    main()