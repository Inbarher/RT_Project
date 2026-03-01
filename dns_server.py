import socket

IP_ADDRESS = '0.0.0.0'
DNS_PORT = 9999        # Our local port
GOOGLE_DNS = '8.8.8.8' # Google's public DNS server
GOOGLE_PORT = 53       # Standard DNS port
BUFFER_SIZE = 1024

dns_table={"my_app.com":"192.168.1.100"}
def start_dns_server():
    s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((IP_ADDRESS,DNS_PORT))
    print("DNS Server Started")
    while True:
        data, client_address = s.recvfrom(BUFFER_SIZE)
        domain = data.decode()
        print(f" Client {client_address} is looking for: {domain}")
        if domain.strip() in dns_table:
            ip=dns_table[domain.strip()]
            print(f"Found in table: {ip}")
            s.sendto(ip.encode(), client_address)
        else:
            print(f"Domain {domain} not found in table,asking GOOGLE_DNS")
            try:
                temp_sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
                temp_sock.settimeout(2.0)  # Wait up to 2 seconds for Google
                temp_sock.sendto(domain.encode(), (GOOGLE_DNS, GOOGLE_PORT))
                # Placeholder for the external result (to be fully binary in Version 2)
                external_response = f"EXTERNAL_IP_FOR_{domain}"
                # Send the "external" result back to our original client
                s.sendto(external_response.encode(), client_address)
                print(f"[RECURSIVE] Forwarded result back to client.")
                temp_sock.close()
            except Exception as e:
                # Handle connection errors or timeouts
                print(f"[ERROR] Failed to reach external DNS: {e}")

if __name__ == "__main__":
    start_dns_server()