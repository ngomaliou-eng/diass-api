import socket

IP_RTAC = "192.168.123.200"

ports = {
    80:    "HTTP — Interface web",
    443:   "HTTPS — Interface web sécurisée",
    502:   "Modbus TCP",
    20000: "DNP3",
    22:    "SSH",
    23:    "Telnet",
    8080:  "HTTP alternatif",
    4840:  "OPC-UA",
    102:   "IEC 61850",
}

print(f"Scan ports — RTAC {IP_RTAC}")
print("-" * 50)

ouverts = []
for port, description in ports.items():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(2)
    result = sock.connect_ex((IP_RTAC, port))
    sock.close()
    if result == 0:
        print(f"✓ Port {port:5d} — OUVERT — {description}")
        ouverts.append(port)
    else:
        print(f"✗ Port {port:5d} — fermé  — {description}")

print("-" * 50)
print(f"Ports ouverts : {ouverts}")