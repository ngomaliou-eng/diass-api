from pymodbus.client import ModbusTcpClient
import struct

def decode_le(reg1, reg2):
    raw = struct.pack('>HH', reg2, reg1)
    return struct.unpack('>f', raw)[0]

client = ModbusTcpClient("192.168.123.111", port=502)
client.connect()

# Scanner largement de 0 à 2000
for debut in [0, 100, 200, 300, 400, 500, 600, 700, 800, 900, 1000, 1100, 1200, 1500, 2000]:
    result = client.read_holding_registers(address=debut, count=50, device_id=1)
    if result.isError():
        continue
    regs = result.registers
    print(f"\n=== Adresse {debut} ===")
    for i in range(0, len(regs)-1, 2):
        val = decode_le(regs[i], regs[i+1])
        # Chercher :
        # Irradiance → entre 0 et 1200 W/m²
        # Puissance  → entre 0 et 23000 kW
        # Énergie    → entre 0 et 100000 MWh
        if 0 < val < 100000:
            print(f"  Reg {debut+i}-{debut+i+1} | {val:12.2f}")

client.close()