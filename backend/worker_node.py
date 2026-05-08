from flask import Flask, request, jsonify
import psutil
import time
import threading

app = Flask(__name__)

# --- SERVER CONFIGURATION ---
SERVER_NAME = "S1" # Change to S2 for second instance
PORT = 5050        # Change to 5051 for second instance
TARGET_LOAD = 40   # Simulated baseline load
# ----------------------------

def cpu_loader(target_percentage):
    """Generates a consistent background CPU load for testing."""
    sleep_time = (100 - target_percentage) / 1000.0
    work_time = target_percentage / 1000.0
    while True:
        start_time = time.time()
        while time.time() - start_time < work_time:
            _ = 12345 * 67890
        time.sleep(sleep_time)

@app.route("/process")
def process():
    client_ip = request.args.get('client_ip', request.remote_addr)
    req_type = request.args.get('type', 'unknown')
    
    print("\n" + "="*45)
    print(f"[+] NEW REQUEST ROUTED TO {SERVER_NAME}")
    print(f"    -> Device IP : {client_ip}")
    print(f"    -> Workload  : {req_type.upper()}")
    print("="*45)
    
    if req_type == "query":
        time.sleep(0.5)
    elif req_type == "upload":
        time.sleep(2.0)
    
    return jsonify({
        "server": SERVER_NAME,
        "status": "Task Completed Successfully",
        "processed_type": req_type,
        "device_ip_logged": client_ip
    })

@app.route("/status")
def status():
    return jsonify({"server": SERVER_NAME, "cpu": psutil.cpu_percent()})

if __name__ == "__main__":
    print(f"[*] Initializing Worker {SERVER_NAME} on port {PORT}...")
    threading.Thread(target=cpu_loader, args=(TARGET_LOAD,), daemon=True).start()
    app.run(host="0.0.0.0", port=PORT)