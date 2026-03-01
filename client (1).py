import socket

DHCP_PORT = 6767
BUFFER_SIZE = 4096
DNS_SERVER_IP = '127.0.0.1'
DNS_PORT = 9999
VIDEO_SERVER_PORT = 8080
def start_dhcp_conn():
    client_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    client_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    print("client Sending DISCOVER to find our DHCP server...")
    client_sock.sendto("DISCOVER".encode(), ('<broadcast>', DHCP_PORT))# Send DISCOVER to the broadcast address on the specific port
    # Add this line to talk to the real home router (Port 67)
    client_sock.sendto("DISCOVER".encode(), ('<broadcast>', 67))
    client_sock.settimeout(3.0)
    try:
        while True:
            data, server_address = client_sock.recvfrom(BUFFER_SIZE)
            response = data.decode()
            if response.startswith("OFFER") and "MY_APP_SERVER" in response:
                parts = response.split("|")# Split the message
                offered_ip = parts[1]
                server_id = parts[2]

                request_msg = f"REQUEST|{offered_ip}|{server_id}"#Send REQUEST for the offered IP back to the server
                client_sock.sendto(request_msg.encode(), server_address)
                # Acknowledgment (ACK)
                ack_data, _ = client_sock.recvfrom(BUFFER_SIZE)
                ack_msg = ack_data.decode()
                if ack_msg.startswith("ACK"):
                    my_final_ip = ack_msg.split("|")
                    my_final_ip=my_final_ip[1]
                    print(" SUCCESS! My new IP is: ", my_final_ip)
                    return my_final_ip
            else:
                print("[CLIENT] Received offer from unknown server, ignoring...")

    except Exception as e:
        print(f"[CLIENT] DHCP Error: {e}")
        return None

def start_dns_conn(domain_name):
    print("DNS connection will be establish...")
    dns_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    dns_sock.settimeout(3.0)
    try:
        print(f"Client: Asking DNS Server ({DNS_SERVER_IP}) for: {domain_name}")
        dns_sock.sendto(domain_name.encode(), (DNS_SERVER_IP, DNS_PORT))
        data, _ = dns_sock.recvfrom(BUFFER_SIZE)
        resolved_ip = data.decode()

        print(f" SUCCESS! DNS resolved '{domain_name}' to: {resolved_ip}")
        return resolved_ip

    except socket.timeout:
        print("[CLIENT] DNS Error: No response from DNS server.")
        return None
    finally:
        dns_sock.close()


def get_size_data(sock):
    ans = ""
    while True:
        try:
            char_b = sock.recv(1)
            if not char_b:
                break
            char = char_b.decode()
            if char == "#":
                break
            ans += char
        except:
            break
    if ans.isdigit():
        return int(ans)
    return 0
def watch_video_tcp(server_ip, movie_selection):
    print(f"HTTP Streaming Connecting to {server_ip} ---")
    try:
        video_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        video_sock.connect((server_ip, VIDEO_SERVER_PORT))

        video_sock.sendall(movie_selection.encode())

        num_frames= get_size_data(video_sock)
        if num_frames == 0:
            print("Server: Movie or Quality not found.")
            return

        print(f"Stream: Server has {num_frames} frames for us. Starting download...")

        for i in range(num_frames):
            size= get_size_data(video_sock)
            img_data = b""
            while len(img_data) < size:
                packet = video_sock.recv(BUFFER_SIZE)
                if not packet:
                    break
                img_data += packet

            with open(f"received_frame_{i + 1}.png", "wb") as f:
                f.write(img_data)
            print(f" Playing: Frame {i + 1}/{num_frames} received.")

        print("\n--- Video playback finished successfully! ---")
    except Exception as e:
        print(f"Streaming Error: {e}")
    finally:
        video_sock.close()


def receive_from_buffer_binary(s, buffer):
    try:
        chunk, addr = s.recvfrom(BUFFER_SIZE)
        if not chunk: return [], buffer, None
        buffer += chunk
        messages = []
        while b"#" in buffer:
            line, buffer = buffer.split(b"#", 1)
            messages.append(line)
        return messages, buffer, addr
    except: return ["TIMEOUT"], buffer, None


def watch_video_udp(server_ip, movie_selection):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(2.0)
    sock.sendto(movie_selection.encode(), (server_ip, VIDEO_SERVER_PORT))
    img_data, buffer, expected_seq = b"", b"", 0

    print(f"Starting download for {movie_selection}...")

    while True:
        try:
            packets, buffer, addr = receive_from_buffer_binary(sock, buffer)
            if not addr: addr = (server_ip, VIDEO_SERVER_PORT)

            for packet in packets:
                if packet == "TIMEOUT": continue

                parts = packet.split(b"|", 1)
                if len(parts) < 2: continue

                try:
                    header = parts[0].decode('utf-8', errors='ignore')
                except:
                    continue

                if header == "END":
                    try:
                        seq = int(parts[1].decode('utf-8', errors='ignore'))
                        if img_data:
                            # שימוש ב-with מבטיח שהקובץ ייסגר מיד לאחר הכתיבה
                            file_name = f"received_frame_{seq}.png"
                            with open(file_name, "wb") as f:
                                f.write(img_data)
                                f.flush()  # מוודא שהנתונים נכתבו פיזית לדיסק
                            print(f"Saved and Closed: {file_name}")

                        sock.sendto(f"ACK|END|{seq}#".encode(), addr)
                        img_data = b""
                    except Exception as e:
                        print(f"Error saving frame: {e}")
                    continue

                try:
                    seq = int(header)
                    if seq == expected_seq:
                        img_data += parts[1]
                        sock.sendto(f"ACK|{seq}#".encode(), addr)
                        expected_seq += 1
                    elif seq < expected_seq:
                        sock.sendto(f"ACK|{seq}#".encode(), addr)
                except ValueError:
                    continue
        except Exception as e:
            print(f"Download sequence finished: {e}")
            break
    sock.close()



if __name__ == "__main__":
    my_ip = start_dhcp_conn()

    if my_ip:
        video_server_ip = start_dns_conn("my_app.com")
        if video_server_ip:
            print(f"\nReady to connect to the video server at {video_server_ip}!")
            way_of_conn=input("Which way would you like to connect to(TCP OR UDP)?\n")
            if way_of_conn == "TCP":
                watch_video_tcp("127.0.0.1", "Circle|High")
            elif way_of_conn == "UDP":
                watch_video_udp("127.0.0.1", "Triangle|High")
            else:
                print("[CLIENT] Invalid option. Exiting...")
