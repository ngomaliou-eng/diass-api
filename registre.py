from pymodbus.client import ModbusTcpClient
import struct

def decode_le(reg1, reg2):
    raw = struct.pack('>HH', reg2, reg1)
    return struct.unpack('>f', raw)[0]

client = ModbusTcpClient("192.168.123.111", port=502)
client.connect()

# Scanner de 300 à 5000
all_regs = {}
for debut in range(300, 5000, 125):
    r = client.read_holding_registers(address=debut, count=125, device_id=1)
    if not r.isError():
        for i, val in enumerate(r.registers):
            all_regs[debut + i] = val

print("=== Tous les totaux onduleurs (3000W - 15000W) ===")
count = 0
for reg in sorted(all_regs.keys()):
    if reg + 1 not in all_regs: continue
    total = decode_le(all_regs[reg], all_regs[reg+1])
    if not (3000 < total < 15000): continue
    if all(r in all_regs for r in [reg-6,reg-5,reg-4,reg-3,reg-2,reg-1]):
        p1 = decode_le(all_regs[reg-6], all_regs[reg-5])
        p2 = decode_le(all_regs[reg-4], all_regs[reg-3])
        p3 = decode_le(all_regs[reg-2], all_regs[reg-1])
        somme = p1 + p2 + p3
        if abs(total - somme) / total < 0.15:
            count += 1
            print(f"INV-{count:02d} | Reg {reg:5d} | {total:8.2f} W")

print(f"\nTotal : {count} onduleurs trouvés")
client.close()