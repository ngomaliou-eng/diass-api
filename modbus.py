from pymodbus.client.sync import ModbusTcpClient

def sint16(val):
    """Convertit uint16 brut en entier signé"""
    return val if val < 32768 else val - 65536

client = ModbusTcpClient("192.168.123.101", port=502, timeout=5)
client.connect()

for uid in range(1, 6):
    print(f"\n{'='*55}")
    print(f"  Onduleur UID {uid} — Conext Core XC")
    print(f"{'='*55}")

    # Bloc data log 0x4813 → 0x482C (adresses décimales)
    rr = client.read_holding_registers(0x4813, 26, unit=uid)
    if rr.isError():
        print("  Pas de réponse")
        continue

    r = rr.registers

    # Énergie totale (Uint32 sur 2 registres, ÷10)
    energy_kwh = ((r[0] << 16) | r[1]) / 10.0

    # Tensions AC (Sint16, ÷10)
    vab = sint16(r[2]) / 10.0
    vbc = sint16(r[3]) / 10.0
    vca = sint16(r[4]) / 10.0

    # Courants AC (Sint16, ÷10)
    ia = sint16(r[5]) / 10.0

    # Fréquence (Sint16, ÷10)
    freq = sint16(r[8]) / 10.0

    # Puissances (Sint16, kW / kVAr)
    p_active  = sint16(r[9])
    p_reactive = sint16(r[10])

    # Tensions DC (Sint16, ÷10)
    v_dc = sint16(r[11]) / 10.0
    v_pv = sint16(r[12]) / 10.0
    i_pv = sint16(r[13]) / 10.0
    p_pv = sint16(r[14])

    print(f"  Énergie totale  : {energy_kwh:.1f} kWh")
    print(f"  Tension AC Vab  : {vab:.1f} V")
    print(f"  Tension AC Vbc  : {vbc:.1f} V")
    print(f"  Tension AC Vca  : {vca:.1f} V")
    print(f"  Courant AC Ia   : {ia:.1f} A")
    print(f"  Fréquence       : {freq:.1f} Hz")
    print(f"  P active        : {p_active} kW")
    print(f"  P réactive      : {p_reactive} kVAr")
    print(f"  Tension DC bus  : {v_dc:.1f} V")
    print(f"  Tension PV      : {v_pv:.1f} V")
    print(f"  Courant PV      : {i_pv:.1f} A")
    print(f"  Puissance PV    : {p_pv} kW")

    # État opérationnel
    rr2 = client.read_holding_registers(0x1700, 1, unit=uid)
    if not rr2.isError():
        state = rr2.registers[0]
        states = {0x0000:"PV Offline", 0x0001:"PV Reconnecting",
                  0x0002:"PV Online ✓", 0x0100:"CP Offline",
                  0x0102:"CP Online ✓"}
        print(f"  État            : {states.get(state, f'Code 0x{state:04X}')}")

client.close()