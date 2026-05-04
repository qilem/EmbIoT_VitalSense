import serial
import struct
import threading
import numpy as np

from pipeline import Pipeline

SAMPLE_PER_CHIRP = 128
CHIRP_PER_FRAME = 256
MAGIC = 0xFFDDFFDD

# Read data from serial port
class Processor:
    def __init__(self, result: dict, lock: threading.Lock, port_name: str):
        self._result = result
        self._lock = lock
        self._pipe = Pipeline(SAMPLE_PER_CHIRP, buffer_size=CHIRP_PER_FRAME * 32, window_size=CHIRP_PER_FRAME * 8, stride=64)
        self._port_name = port_name

    def worker(self):
        s = serial.Serial(self._port_name)
        self._sync_buffer(s)

        while True:
            nbytes = struct.unpack('<I', s.read(4))[0]
            data = s.read(nbytes) 

            data = [ d[0] for d in struct.iter_unpack('<H', data) ]
            # print(len(data), data[0], data[-1])
            self._pipe.enque(data)
            if self._pipe.data_ready():
                self._process()

            peek = s.read(4)
            if struct.unpack('<I', peek)[0] != MAGIC:
                self._sync_buffer(s)
                continue

    def _process(self):
        mag = np.abs(self._pipe.range_fft()).mean(axis=0)
        breath, heart = self._pipe.vitals()
        with self._lock:
            self._result["mag"] = mag
            self._result["breath"] = breath
            self._result["heart"] = heart


    def _sync_buffer(self, s: serial.Serial):
        buf = b""
        while True:
            buf = (buf + s.read(1))[-4:]
            if (len(buf) == 4) and struct.unpack('<I', buf)[0] == MAGIC:
                return
