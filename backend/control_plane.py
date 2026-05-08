from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import time
import csv
import os

app = Flask(__name__)
CORS(app) # Unlocks the API for the separate frontend

# --- CONFIGURE WORKER NODES ---
SERVERS = {
    "S1": "http://3.91.134.233:5050",
    "S2": "http://54.167.251.217:5051"
}

LOG_FILE = "routing_logs.csv"
if not os.path.exists(LOG_FILE):
    with open(LOG_FILE, mode='w', newline='') as f:
        csv.writer(f).writerow(["Time", "Device_IP", "Type", "Chosen_Server", "RTT_ms", "CPU"])

def get_latency_matrix():
    """Aggregator Service: Pings worker nodes for health and latency."""
    matrix = {}
    for name, url in SERVERS.items():
        start = time.time()
        try:
            res = requests.get(f"{url}/status", timeout=2).json()
            rtt = (time.time() - start) * 1000 
            matrix[name] = {"rtt": rtt, "cpu": res["cpu"], "url": url, "alive": True}
        except:
            matrix[name] = {"rtt": 9999, "cpu": 100, "url": url, "alive": False}
    return matrix

def select_best_server(matrix, req_type):
    """Selector Service: Routes based on matrix data and workload type."""
    alive_servers = {k: v for k, v in matrix.items() if v["alive"]}
    if not alive_servers: return None, None
    
    if req_type == "query":
        best = min(alive_servers.keys(), key=lambda k: alive_servers[k]["rtt"])
    elif req_type == "upload":
        best = min(alive_servers.keys(), key=lambda k: alive_servers[k]["cpu"])
    else:
        best = list(alive_servers.keys())[0] 
        return best, alive_servers[best]

@app.route("/request")
def route_request():
    faculty_ip = request.remote_addr 
    req_type = request.args.get('type', 'query')
    
    print(f"\n[*] INCOMING TRAFFIC DETECTED")
    print(f"    -> Source IP: {faculty_ip} | Type: {req_type}")
    
    matrix = get_latency_matrix()
    best_name, best_data = select_best_server(matrix, req_type)
    
    if not best_name:
        return jsonify({"error": "All backend servers offline"}), 500
        
    try:
        forward_url = f"{best_data['url']}/process?type={req_type}&client_ip={faculty_ip}"
        resp = requests.get(forward_url, timeout=5).json()
    except Exception as e:
        resp = {"error": str(e)}

    # Save routing decisions to database
    with open(LOG_FILE, mode='a', newline='') as f:
        csv.writer(f).writerow([time.strftime("%H:%M:%S"), faculty_ip, req_type, best_name, round(best_data['rtt'], 2), best_data['cpu']])

    return jsonify({
        "1_device_ip_recorded": faculty_ip,
        "2_request_type": req_type,
        "3_routed_to_server": best_name,
        "4_latency_matrix_used": matrix,
        "5_server_response": resp
    })

if __name__ == "__main__":
    print("[*] API Gateway Active on Port 8000")
    app.run(host="0.0.0.0", port=8000)