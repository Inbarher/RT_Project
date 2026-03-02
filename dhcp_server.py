import socket

IP_ADDRESS = '0.0.0.0'
PORT = 6767
BUFFER_SIZE = 1024
# Address database: 0 means free, 1 means taken (leased)
address_database= {
    "192.168.1.100": 0,
    "192.168.1.101": 0,
    "192.168.1.102": 0
}
def start_dhcp_server():
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)# Create a UDP socket
    server_sock.bind((IP_ADDRESS, PORT))# Link the socket to the specified IP and Port
    print("DHCP Server is listening on port ",PORT)
    while True:
        try:
            data, client_address = server_sock.recvfrom(BUFFER_SIZE)
            message = data.decode()# Convert binary data to a readable string
            if message=="DISCOVER":#DISCOVER message from client
                offered_ip=None
                for ip in address_database:# Iterate through the database to find the first available IP
                    if address_database[ip] == 0:
                        offered_ip = ip
                        break
                response=f"OFFER|{offered_ip}|MY_APP_SERVER"# Prepare the OFFER message
                server_sock.sendto(response.encode(), client_address)
                print(f"Sent OFFER for {offered_ip} to {client_address}")
            elif message.startswith("REQUEST"):# REQUEST message from client
                parts = message.split("|")# Split the message to extract requested IP and the Server ID
                requested_ip = parts[1]
                server_id = parts[2]
                if server_id=="MY_APP_SERVER":# Verify the request is for our specific server
                    address_database[requested_ip] = 1# Mark the IP as taken
                    response = f"ACK|{requested_ip}"#sending an Acknowledgment (ACK)
                    server_sock.sendto(response.encode(), client_address)

                    print(f"Sent ACK for {requested_ip}. IP is now LEASED.")
        except Exception as e:
                print(f"DHCP Error: {e}")
                continue

if _name_ == "_main_":
    start_dhcp_server()

