#!/usr/bin/env python3
import socket
import threading
import time
import json

HOST = "0.0.0.0"
PORT = 5005

def handle_client(conn: socket.socket, addr):
    print(f"[+] Connection from {addr}")
    try:
        buf = b""
        while True:
            data = conn.recv(4096)
            if not data:
                break
            buf += data
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                line = line.decode("utf-8", errors="replace").strip()
                if not line:
                    continue
                # Expect: robot_id,timestamp,x,y
                parts = [p.strip() for p in line.split(",")]
                if len(parts) != 4:
                    print(f"[WARN] Bad line from {addr}: {line}")
                    continue
                robot_id, ts, x, y = parts
                print(f"{robot_id}  t={ts}  x={x}  y={y}")

                try:
                    with open("state.json", "w") as f:
                        json.dump({"id": robot_id, "t": ts, "x": float(x), "y": float(y)}, f)
                except Exception as e:
                    print(f"[!] Write error: {e}")
    except Exception as e:
        print(f"[!] Client error {addr}: {e}")
    finally:
        print(f"[-] Disconnected {addr}")
        try:
            conn.close()
        except Exception:
            pass

def main():
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((HOST, PORT))
    srv.listen(20)
    print(f"RTLS server listening on {HOST}:{PORT}")

    while True:
        conn, addr = srv.accept()
        t = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
        t.start()

if __name__ == "__main__":
    main()