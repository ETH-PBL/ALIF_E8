import os
import sys
import time
import serial
from xmodem import XMODEM

port = sys.argv[1]
path = sys.argv[2]
ser = serial.Serial(port, 115200, timeout=2)
time.sleep(0.3)
ser.reset_input_buffer()


def getc(size, timeout=2):
    return ser.read(size) or None


def putc(data, timeout=2):
    return ser.write(data)


def cb(total_packets, success, error):
    if total_packets % 200 == 0:
        print(f"  packets {total_packets} ok {success} err {error}", flush=True)


sz = os.path.getsize(path)
print(f"XMODEM send {path} ({sz} bytes, ~{sz//128} packets) -> {port}")
modem = XMODEM(getc, putc)
ok = modem.send(open(path, "rb"), retry=16, callback=cb)
print("RESULT:", "OK" if ok else "FAILED")
ser.close()
