import socket
import os
import time

# הגדרות שרת - יושב על פורט 8080 (סטנדרט HTTP)
SERVER_IP = '0.0.0.0'
PORT = 8080
BUFFER_SIZE = 4096


def receive_from_buffer(s, buffer):
    try:
        data, addr = s.recvfrom(1024)
        if not data: return [], buffer
        chunk = data.decode('utf-8', errors='ignore')
        buffer += chunk
        messages = []
        while "#" in buffer:
            line, buffer = buffer.split("#", 1)
            messages.append(line.strip())
        return messages, buffer
    except (socket.timeout, ConnectionResetError):
        return ["TIMEOUT"], buffer
    except Exception:
        return [], buffer


def start_video_server_udp():
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_sock.bind((SERVER_IP, PORT))
    print(f"Server is listening on port {PORT} (UDP Reliable)...")

    while True:
        try:
            server_sock.settimeout(None)
            request_data, client_address = server_sock.recvfrom(BUFFER_SIZE)
            server_sock.settimeout(2.0)

            request = request_data.decode()
            if request:
                movie, quality = request.split("|")
                print(f"Request: {movie}/{quality} from {client_address}")

                folder_path = f"Movies/{movie}/{quality}"
                if os.path.exists(folder_path):
                    frames = sorted([f for f in os.listdir(folder_path) if f.endswith('.png')])
                    seq_num = 0
                    ack_buffer = ""

                    for frame_name in frames:
                        with open(os.path.join(folder_path, frame_name), "rb") as f:
                            image = f.read()

                        chunks = [image[i:i + 512] for i in range(0, len(image), 512)]
                        for chunk in chunks:
                            packet = f"{seq_num}|".encode() + chunk + b"#"
                            while True:
                                server_sock.sendto(packet, client_address)
                                messages, ack_buffer = receive_from_buffer(server_sock, ack_buffer)
                                if any(msg == f"ACK|{seq_num}" for msg in messages):
                                    seq_num += 1
                                    break

                        # סיגנל סיום פריים
                        end_packet = f"END|{seq_num}#".encode()
                        while True:
                            server_sock.sendto(end_packet, client_address)
                            messages, ack_buffer = receive_from_buffer(server_sock, ack_buffer)
                            if any(msg == f"ACK|END|{seq_num}" for msg in messages):
                                print(f"Sent: {frame_name}")
                                break
                else:
                    server_sock.sendto(b"0#", client_address)
        except Exception as e:
            print(f"Server Error: {e}")


if __name__ == "__main__":
    start_video_server_udp()

def start_video_server_tcp():
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)# Create an IPv4-based socket and TCP protocol for reliable data transfer
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)# Allows port reuse immediately after closing the server (prevents Address already in use errors)
    server_sock.bind((SERVER_IP, PORT))
    server_sock.listen(5)# Switch to listening mode and set up a waiting queue for up to 5 clients at the same time

    print(f"The video server is ready and listening on port -{PORT}")

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
                client_sock.sendall((str(len(frames)) + "#").encode())# Send the number of frames and then a clear separator

                for frame_name in frames:
                    file_path = os.path.join(folder_path, frame_name)
                    with open(file_path, "rb") as f:
                        image= f.read()
                        client_sock.sendall((str(len(image)) + "#").encode()) #Sending the size with a separator at the end
                        client_sock.sendall(image)#Sending the image
                        print(f"Sent successfully: {frame_name}")
                        time.sleep(0.5)
            else:
                client_sock.sendall("0#".encode())
        except Exception as e:
            print(f"Network error: {e}")
        finally:
            client_sock.close()


if __name__ == "__main__":
    start_video_server_udp()
    #start_video_server_tcp()