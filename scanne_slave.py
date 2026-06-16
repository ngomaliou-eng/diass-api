from pymodbus.client import ModbusTcpClient

# UC8112-1 — datalogger principal
client = ModbusTcpClient("192.168.123.111", port=502)

if client.connect():
    print("✓ Connexion UC8112-1 réussie !")
    
    # Essai avec différents slave IDs
    for slave_id in [1, 2, 3, 255]:
        try:
            result = client.read_holding_registers(
                address=0, 
                count=10, 
                device_id=slave_id  # paramètre correct pour pymodbus 3.x
            )
            if not result.isError():
                print(f"✓ Slave {slave_id} → registres : {result.registers}")
            else:
                print(f"✗ Slave {slave_id} → pas de réponse")
        except Exception as e:
            print(f"✗ Slave {slave_id} → erreur : {e}")
    
    client.close()
else:
    print("✗ Connexion échouée")