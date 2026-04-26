from pymodbus.client import ModbusTcpClient
import time

IP_RTAC = "192.168.123.xx"  # IP à confirmer
NB_ONDULEURS = 32

client = ModbusTcpClient(IP_RTAC, port=502)
client.connect()

donnees_onduleurs = []

for numero in range(1, NB_ONDULEURS + 1):
    try:
        result = client.read_holding_registers(
            address=0,
            count=5,
            slave=numero
        )
        
        if not result.isError():
            donnees_onduleurs.append({
                "id": f"INV-{numero:02d}",
                "puissance_kw": result.registers[0] * 0.1,
                "tension_v": result.registers[1] * 0.1,
                "temperature_c": result.registers[3] * 0.1,
                "statut": "ok" if result.registers[4] == 1 else "erreur"
            })
            print(f"INV-{numero:02d} → {result.registers[0] * 0.1} kW")
        else:
            print(f"INV-{numero:02d} → Erreur de lecture")
            
    except Exception as e:
        print(f"INV-{numero:02d} → Exception : {e}")
    
    time.sleep(0.1)  # petite pause entre chaque lecture

client.close()
print(f"\n{len(donnees_onduleurs)} onduleurs lus avec succès")