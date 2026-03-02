import socket
import os
import time
import threading


# Basic network settings

SERVER_IP = '0.0.0.0' # Listening on all available network cards
TCP_PORT = 8080 # Server port
UDP_PORT = 8081 # Server port
BUFFER_SIZE = 4096 # Buffer size for receiving requests

def receive_from_buffer(s):
    try:
        data, addr = s.recvfrom(1024)
        if not data: return []
        content = data.decode('utf-8', errors='ignore')# Decode the bytes into text while ignoring invalid characters (like parts of an image)
        messages = [m for m in content.split("#") if m.strip()]
        return messages
    except socket.timeout:
        return ["TIMEOUT"]


def start_video_server_udp():
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_sock.bind((SERVER_IP, UDP_PORT))
    print(f"Server is listening on port {UDP_PORT} (UDP Reliable)...")
    while True:
        try:

            server_sock.settimeout(None) #An endless wait until the first customer arrives.
            request_data, client_address = server_sock.recvfrom(BUFFER_SIZE)
            server_sock.settimeout(2.0)
            try:
                request = request_data.decode()
                movie, quality = request.split("|")
            except ValueError:
                continue

            if request:
                seq_num = 0  # Initialize the counter - will not reset until the end of the movie
                movie, quality = request.split("|")# Breaking down the request into the movie name and requested quality
                print(f"Request: {movie}/{quality} from {client_address}")
                server_sock.settimeout(0.1)
                while True:
                    try:
                        server_sock.recvfrom(BUFFER_SIZE)
                    except socket.timeout:
                        break
                server_sock.settimeout(2.0)
                folder_path = f"Movies/{movie}/{quality}"

                if os.path.exists(folder_path):
                    frames = sorted([f for f in os.listdir(folder_path) if f.endswith('.png')])# Get a list of all frames (images) sorted by name


                    window_size = 1.0 # Control Window (Starts at Slow Start)
                    ssthresh = 16.0# Threshold
                    dup_ack_count = 0# Duplicate Acknowledgement Counter for Fast Recovery

                    for frame_name in frames:
                        with open(os.path.join(folder_path, frame_name), "rb") as f:
                            image = f.read()
                        chunks = [image[i:i + 512] for i in range(0, len(image), 512)]# Split each image into small chunks (512 bytes)

                        not_ack_oldest = 0  # Index of the first chunk in the frame that has not yet been acknowledged
                        next_send_num = 0 # Index of the next chunk to be sent in the current frame

                        # The frame sending loop
                        while not_ack_oldest<len(chunks):
                            # Sending packages as long as there is free space in the window
                            while next_send_num < not_ack_oldest + window_size and next_send_num < len(chunks):
                                curr_seq=seq_num+next_send_num # Calculate the global serial number
                                packet = f"{curr_seq}|".encode() + chunks[next_send_num] + b"#"
                                server_sock.sendto(packet, client_address)
                                print(f"[WINDOW] Sent Packet {curr_seq} (Inside Window)")
                                next_send_num += 1
                            server_sock.settimeout(0.5)# Setting a short wait time for receiving ACKs from the client

                            try:
                                messages= receive_from_buffer(server_sock)
                                for msg in messages:
                                    if "ACK" in msg and "END" not in msg:
                                        parts = msg.split("|")# Extract the number from the ACK (e.g. ACK|95|WIN=8)
                                        ack_seq = int(parts[1])
                                        frame_ack = ack_seq - seq_num# Calculate the relative position within the current frame
                                        if frame_ack == not_ack_oldest - 1:# Packet loss
                                            dup_ack_count += 1
                                            if dup_ack_count == 3:# Spot packet loss detection using 3 duplicate certificates
                                                print(f"!!! 3 Duplicate ACKs for {ack_seq}. Fast Retransmit!")
                                                ssthresh = max(window_size / 2.0, 2.0)  # Cutting in half
                                                window_size = ssthresh + 3
                                                next_send_num = not_ack_oldest# resending of the missing package
                                        elif frame_ack >= not_ack_oldest:# new ACK has arrived that advances the window
                                            not_ack_oldest = frame_ack + 1
                                            dup_ack_count=0
                                            print(f" >>> [ACK RECEIVED] Client got up to {ack_seq}")
                                            if window_size < ssthresh:
                                                window_size += 1.0  # Slow Start
                                            else:
                                                window_size += 1.0 / int(window_size)  # Additive Increase
                                        if "WIN=" in msg:
                                            client_win = int(msg.split("WIN=")[1])
                                            window_size = min(window_size, client_win)# The allowed window is the minimum

                            except socket.timeout:# If there was a timeout, we will retransmit the unacknowledged packet.
                                print(f"!!! [TIMEOUT] Congestion Inferred. Resetting Window to 1.")
                                ssthresh = max(window_size / 2.0, 2.0)
                                window_size = 1.0
                                dup_ack_count = 0
                                next_send_num = not_ack_oldest# Re-send all packets that were not acknowledged from the beginning
                        end_num=seq_num+len(chunks)
                        end_packet = f"END|{end_num}#".encode()
                        while True:
                            #After all the chunks have been sent, the server sends a special message that the frame has ended.
                            server_sock.sendto(end_packet, client_address)
                            server_sock.settimeout(0.5)
                            try:
                                messages= receive_from_buffer(server_sock)
                                found_end_ack = False
                                for msg in messages:
                                    if msg == f"ACK|END|{end_num}":
                                        found_end_ack = True
                                        break
                                if found_end_ack:
                                    print(f"Frame {frame_name} confirmed by client.")
                                    break
                            except socket.timeout:
                                print(f"Retrying END for {frame_name}...")
                                continue
                        seq_num += len(chunks)
                else:
                    server_sock.sendto("0#".encode(), client_address)
        except Exception as e:
            print(f"Server Error: {e}")

def start_video_server_tcp():
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)# Create an IPv4-based socket and TCP protocol for reliable data transfer
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)# Allows port reuse immediately after closing the server (prevents Address already in use errors)
    server_sock.bind((SERVER_IP, TCP_PORT))
    server_sock.listen(5)# Switch to listening mode and set up a waiting queue for up to 5 clients at the same time

    print(f"The video server is ready and listening on port -{TCP_PORT}")

    while True:
        client_sock, addr = server_sock.accept()#The server waits for clients, creates a socket for a new client
        try:
            request = client_sock.recv(BUFFER_SIZE).decode()
            if not request: continue
            parts = request.split("|")  # Split the message
            movie = parts[0]
            quality  = parts[1]
            print(f"Client request: {movie} in quality {quality} from address {addr}")

            folder_path = f"Movies/{movie}/{quality}"

            if os.path.exists(folder_path):# Check whether the folder with the requested movie and quality exists on the server
                frames = [f for f in os.listdir(folder_path) if f.endswith('.png')]# Scan the folder and create a list of all image files (frames) of type PNG only
                frames.sort()# Sorting file names to ensure frames are sent to the client in the correct order
                print(f"[SERVER DEBUG] I found these frames: {frames}")
                client_sock.sendall((str(len(frames)) + "#").encode())# Send the number of frames and then a clear separator

                for frame_name in frames:
                    file_path = os.path.join(folder_path, frame_name)
                    with open(file_path, "rb") as f:
                        image= f.read()
                        client_sock.sendall((str(len(image)) + "#").encode()) #Sending the size with a separator at the end
                        client_sock.sendall(image)#Sending the image
                        print(f"Sent successfully: {frame_name}")
                    time.sleep(0.2)
                try:
                    client_sock.shutdown(socket.SHUT_WR)  # מודיע ללקוח שסיימנו לשלוח
                    time.sleep(0.5)
                except:
                    pass
            else:
                client_sock.sendall("0#".encode())
        except Exception as e:
            print(f"Network error: {e}")
        finally:
            client_sock.close()



if _name_ == "_main_":
    # יצירת התהליכונים
    udp_thread = threading.Thread(target=start_video_server_udp, daemon=True)
    tcp_thread = threading.Thread(target=start_video_server_tcp, daemon=True)

    # הפעלת שניהם
    udp_thread.start()
    tcp_thread.start()

    print(f"--- Server Started ---")
    print(f"UDP Reliable listening on port: {UDP_PORT}")
    print(f"TCP Server listening on port: {TCP_PORT}")

    # לולאה ששומרת על ה-Main בחיים כדי שה-Threads לא ייסגרו
    while True:
        time.sleep(1)