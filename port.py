import socket

# Tableau d'adressage — Centrale PV Diass
equipements = {
    "192.168.123.100": "Switch IKS",
    "192.168.123.101": "Serveur TS",
    "192.168.123.102": "Serveur DDBB",
    "192.168.123.111": "UC8112-1 (datalogger principal)",
    "192.168.123.112": "UC8112-2 (datalogger redondant)",
    "192.168.123.113": "IOLOGIK1210-1",
    "192.168.123.114": "IOLOGIK1210-2",
    "192.168.123.115": "IOLOGIK1210-3",
    "192.168.123.116": "IOLOGIK1210-4",
    "192.168.123.117": "IOLOGIK1260-1",
    "192.168.123.118": "NPORT-1",
    "192.168.123.119": "NPORT-2",
    "192.168.123.120": "NPORT-3",
    "192.168.123.200": "RTAC SEL3530-4",
}

ports_a_tester = {
    502:   "Modbus TCP",
    80:    "HTTP",
    443:   "HTTPS",
    20000: "DNP3",
    4840:  "OPC-UA",
}

print("=" * 60)
print("Scan réseau — Centrale PV Diass")
print("=" * 60)

for ip, nom in equipements.items():
    print(f"\n {nom} ({ip})")
    for port, protocole in ports_a_tester.items():
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex((ip, port))
        sock.close()
        if result == 0:
            print(f"   ✓ Port {port} — {protocole} OUVERT")