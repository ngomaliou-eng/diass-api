from pymodbus.client import ModbusTcpClient
import struct
from datetime import datetime
import time

def decode_le(reg1, reg2):
    raw = struct.pack('>HH', reg2, reg1)
    return struct.unpack('>f', raw)[0]

def lire(client, adresse):
    r = client.read_holding_registers(address=adresse, count=2, device_id=1)
    return round(decode_le(r.registers[0], r.registers[1]), 3)

client = ModbusTcpClient("192.168.123.111", port=502)
client.connect()

print("Comparez avec GPM Plus en temps réel !")
print(f"{'Heure':<12} {'Reg52':>12} {'Reg306':>12} {'Reg86':>12}")
print("-" * 50)

for _ in range(10):
    print(f"{datetime.now().strftime('%H:%M:%S'):<12} "
          f"{lire(client, 52):>12.3f} "
          f"{lire(client, 306):>12.3f} "
          f"{lire(client, 86):>12.3f}")
    time.sleep(3)

client.close()