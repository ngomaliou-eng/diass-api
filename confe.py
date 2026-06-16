from pymodbus.client import ModbusTcpClient
import struct

def decode_le(reg1, reg2):
    raw = struct.pack('>HH', reg2, reg1)
    return struct.unpack('>f', raw)[0]

client = ModbusTcpClient("192.168.123.111", port=502)
client.connect()

# Lire de 300 à 1500 pour tout couvrir
lectures = []
for debut in range(300, 1500, 125):
    r = client.read_holding_registers(address=debut, count=125, device_id=1)
    if not r.isError():
        lectures.extend(r.registers)

print("=== Toutes puissances cohérentes (500W - 15000W) ===")
for i in range(0, len(lectures)-1, 2):
    val = decode_le(lectures[i], lectures[i+1])
    reg = 300 + i
    if 500 < val < 15000:
        print(f"Reg {reg:5d} | {val:10.2f} W")

client.close()