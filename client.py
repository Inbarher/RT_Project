import os
import socket
import numpy as np
import cv2
DHCP_PORT = 6767
BUFFER_SIZE = 4096
DNS_SERVER_IP = '127.0.0.1'
DNS_PORT = 9999
VIDEO_TCP_PORT = 8080
VIDEO_UDP_PORT = 8081
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
        video_sock.connect((server_ip, VIDEO_TCP_PORT))

        video_sock.sendall(movie_selection.encode())

        num_frames= get_size_data(video_sock)
        if num_frames == 0:
            print("Server: Movie or Quality not found.")
            return

        print(f"Stream: Server has {num_frames} frames for us. Starting download...")

        for i in range(num_frames):
            size = get_size_data(video_sock)
            print(f"[DEBUG] Expecting to receive {size} bytes for frame {i + 1}")
            img_data = b""
            while len(img_data) < size:
                remaining = size - len(img_data)
                packet = video_sock.recv(min(BUFFER_SIZE, remaining))
                if not packet:
                    break
                img_data += packet
            if not img_data or len(img_data) == 0:
                print(f"[ERROR] Frame {i + 1} is empty, skipping...")
                continue
            with open(f"received_frame_{i + 1}.png", "wb") as f:
                f.write(img_data)
            nparr = np.frombuffer(img_data, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if frame is not None:
                cv2.imshow("Video Player (TCP)", frame)
                if cv2.waitKey(2000) & 0xFF == ord('q'): break

        cv2.destroyAllWindows()

        print("\n--- Video playback finished successfully! ---")
    except Exception as e:
        print(f"Streaming Error: {e}")
    finally:
        video_sock.close()


def receive_from_buffer_binary(s):
    try:
        packet, addr = s.recvfrom(BUFFER_SIZE)
        if not packet:
            return [], b"", addr
        if packet.endswith(b"#"):
            clean_packet = packet[:-1]# Trimming only the last byte to leave the binary information clean
            return [clean_packet], b"", addr
        return [packet], b"", addr
    except socket.timeout:
        return ["TIMEOUT"], b"", None

def watch_video_udp(server_ip, movie_selection):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(2.0)
    sock.sendto(movie_selection.encode(), (server_ip, VIDEO_UDP_PORT))# Sending the movie request (movie name and quality)
    print(f"\n--- Starting Stream for {movie_selection} ---")

    img_data= b"" # Accumulates the current image parts
    buffer= b""# Temp buffer for cleaning up packages (according to the #)
    expected_seq = 0 # The next sequence number we expect to receive
    max_window=10# Maximum window size
    out_of_order_packets = {} # The window for out of order packets

    print(f"Starting download for {movie_selection}...")
    while True:
        try:
            packets, buffer, addr = receive_from_buffer_binary(sock)# Receiving packets from the buffer
            if not addr:
                addr = (server_ip, VIDEO_UDP_PORT)
            for packet in packets:
                if packet == "TIMEOUT":
                    #print("!!! Timeout: Waiting for packets...")
                    return
                parts = packet.split(b"|", 1)# Splitting the packet into Header (serial number/END) and information (Data)
                if len(parts) < 2:
                    print("DEBUG: Client received a bad packet (no '|')")
                    continue
                header = parts[0].decode('utf-8', errors='ignore')
                # Information package (serial number) arrived
                if header.isdigit():
                    seq_num= int(header)
                    print(f"DEBUG: Processing packet {seq_num} - Everything is OK!")
                    # The package arrived in exactly the right order
                    if seq_num==expected_seq: #The package arrived just in time.
                        img_data=img_data+parts[1]
                        expected_seq=expected_seq+1
                        # Clearing the window: Checking if the next packages are already waiting for us there
                        while expected_seq in out_of_order_packets:
                            print(f"[Buffer] Moving packet {expected_seq} from window to image")
                            img_data += out_of_order_packets.pop(expected_seq)
                            expected_seq=expected_seq+1
                        # Maybe we're done, an END package has arrived?
                        if "END" in out_of_order_packets:
                            if out_of_order_packets["END"] < expected_seq:
                                seq_end = out_of_order_packets.pop("END")
                                if img_data:
                                    with open(f"received_frame_{seq_end}.png", "wb") as f:
                                        f.write(img_data)
                                print(f"Saved Frame {seq_end} from Buffer")
                                sock.sendto(f"ACK|END|{seq_end}#".encode(), addr)
                                img_data = b"" # Reset to next frame data
                    elif seq_num > expected_seq:# Package arrived ahead of schedule - we will put it in the warehouse if there is space.
                        if len(out_of_order_packets) < max_window:# Keeping in the waiting room only if there is space (flow control)
                            out_of_order_packets[seq_num] = parts[1]
                            print(f"[Out-of-Order] Packet {seq_num} stored in warehouse")
                    free_win=max_window-len(out_of_order_packets)
                    # Sending an acknowledgement (ACK) to the server - updating what the last packet we received was and how much space is left in the window
                    sock.sendto(f"ACK|{expected_seq - 1}|WIN={free_win}#".encode(), addr)
                #frame END arrived
                elif header == "END":
                    try:
                        seq_end = int(parts[1].decode('utf-8', errors='ignore'))
                        if seq_end == expected_seq:# Do we already have all the parts for the frame?
                            if img_data:
                                file_name = f"received_frame_{seq_end}.png"
                                with open(file_name, "wb") as f:
                                    f.write(img_data)
                                    f.flush()
                                print(f"Saved and Closed: {file_name}")
                                nparr = np.frombuffer(img_data, np.uint8)
                                frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                                if frame is not None:
                                    cv2.imshow("Maayan Video Player (UDP)", frame)
                                    if cv2.waitKey(2000) & 0xFF == ord('q'): break
                            # Final confirmation to the server that the frame is complete
                            sock.sendto(f"ACK|END|{seq_end}#".encode(), addr)
                            print(f"[ACK-SENT] Confirmed frame {seq_end} to server")
                            img_data = b"" # Cleaning up for the next frame
                            out_of_order_packets = {}
                        else:
                            print(f"[Wait] END received for {seq_end}, but we are only at {expected_seq}")
                            out_of_order_packets["END"] = seq_end # The END came too soon - we'll keep it in the waiting room
                    except Exception as e:
                        print(f"Error saving frame: {e}")
                    continue
        except Exception as e:
            print(f"Download sequence finished: {e}")
            break
    sock.close()
def choose_movie_and_quality():
    movies_base_path = "Movies"
    if not os.path.exists(movies_base_path):# Does the source folder even exist in the file system? to prevent a crash
        print("[CLIENT] Error: Movies folder not found!")
        return None, None
    # Create a movie list: We go through all the files in the folder and filter only those that are folders
    movies = [d for d in os.listdir(movies_base_path) if os.path.isdir(os.path.join(movies_base_path, d))]
    if not movies:
        print("[CLIENT] No movies found in the folder.")
        return None, None
    print("\n--- Available Movies ---")
    for i in range(len(movies)):
        print(f"{i + 1}. {movies[i]}")
    #the user's choice
    movie_choice = int(input("\nChoose a movie number: ")) - 1
    selected_movie = movies[movie_choice]

    movie_path = os.path.join(movies_base_path, selected_movie)
    qualities = [d for d in os.listdir(movie_path) if os.path.isdir(os.path.join(movie_path, d))]

    print(f"\n--- Available Qualities for {selected_movie} ---")
    for i in range(len(qualities)):
        print(f"{i + 1}. {qualities[i]}")

    quality_choice = int(input("\nChoose quality number: ")) - 1
    selected_quality = qualities[quality_choice]

    return selected_movie, selected_quality
if _name_ == "_main_":
    my_ip = start_dhcp_conn()

    if my_ip:
        video_server_ip = start_dns_conn("my_app.com")
        if video_server_ip:
            print(f"\nReady to connect to the video server at {video_server_ip}!")
            while True:
                movie,quality=choose_movie_and_quality()
                if not movie or not quality:
                    break
                choice = f"{movie}|{quality}"
                way_of_conn=input("Which way would you like to connect to(TCP OR UDP) or EXIT to exit?\n")
                if way_of_conn == "EXIT":
                    print(f"[CLIENT] Exit!")
                    break
                if video_server_ip == my_ip:
                    print(f"[DEBUG] DNS resolved to my own IP. Connecting via Loopback...")
                    target = "127.0.0.1"
                else:
                    target = video_server_ip
                if way_of_conn == "TCP":
                    watch_video_tcp(target, choice)
                elif way_of_conn == "UDP":
                    watch_video_udp(target, choice)
                else:
                    print("[CLIENT] Invalid option. Exiting...")
                exit=input("Do you want to exit?(y/n): ")
                if exit.lower() == "y":
                    break