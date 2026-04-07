import multiprocessing
import threading
import time
import requests
import csv
import random
import os
from flask import Flask, request, jsonify, render_template

SERVERS = {
    "S1": {"port": 5001, "type": "query"},
    "S2": {"port": 5002, "type": "upload"},
    "S3": {"port": 5003, "type": "background"}
}

# ==========================================
# 1. MONITORING AGGREGATOR (Port 5000)
# ==========================================
def run_monitoring():
    app = Flask("Aggregator")
    latency_matrix = [] 

    @app.route('/report', methods=['POST'])
    def receive_report():
        data = request.get_json()
        data['timestamp'] = time.time()
        latency_matrix.append(data)
        
        # Keep sliding 30-second window
        current_time = time.time()
        latency_matrix[:] = [entry for entry in latency_matrix if current_time - entry['timestamp'] <= 30]
        return jsonify({"status": "recorded"}), 200

    @app.route('/matrix', methods=['GET'])
    def get_matrix():
        return jsonify({"data": latency_matrix}), 200

    def run_agent():
        while True:
            for target_name, info in SERVERS.items():
                start_time = time.time()
                rtt_ms, failure, active_load = -1, 1, 0
                try:
                    resp = requests.get(f"http://127.0.0.1:{info['port']}/health", timeout=2)
                    if resp.status_code == 200:
                        rtt_ms = round((time.time() - start_time) * 1000, 2)
                        failure = 0
                        active_load = resp.json().get("active_requests", 0)
                except: pass
                
                try: requests.post("http://127.0.0.1:5000/report", json={"target": target_name, "rtt_ms": rtt_ms, "failure_count": failure, "load": active_load})
                except: pass
            time.sleep(5)

    threading.Thread(target=run_agent, daemon=True).start()
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)

# ==========================================
# 2. GATEWAY & SELECTOR (Port 8000)
# ==========================================
def run_gateway():
    app = Flask("Gateway")
    CSV_FILE = "routing_logs.csv"

    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, mode='w', newline='') as f:
            csv.writer(f).writerow(["timestamp", "request_type", "routed_to", "rtt_ms", "target_load", "response_ms", "routing_reason"])

    def select_best_server(req_type):
        try: matrix = requests.get("http://127.0.0.1:5000/matrix", timeout=1).json().get("data", [])
        except: matrix = []

        # Aggregate data
        stats = {s: {"failures": 0, "rtt": 0, "load": 0} for s in SERVERS}
        for entry in matrix:
            target = entry['target']
            if target in stats:
                stats[target]["failures"] += entry.get('failure_count', 0)
                if entry.get('rtt_ms') != -1:
                    stats[target]["rtt"] = entry['rtt_ms']
                    stats[target]["load"] = entry.get('load', 0)

        # Filter blacklisted
        healthy = {s: v for s, v in stats.items() if v["failures"] < 3}
        if not healthy: return random.choice(list(SERVERS.keys())), 0, 0, "Emergency: All servers blacklisted"

        best_server, reason = None, ""
        LOAD_THRESHOLD = 3 

        # Selection Algorithm
        for s_name, s_info in SERVERS.items():
            if s_info["type"] == req_type and s_name in healthy:
                if healthy[s_name]["load"] < LOAD_THRESHOLD:
                    best_server = s_name
                    reason = f"Specialized match ({req_type}) under load threshold"
                else:
                    reason = f"Specialized server overloaded. "
                break
        
        # Fallback to least loaded server
        if not best_server:
            best_server = min(healthy, key=lambda k: healthy[k]["load"])
            reason += f"Fallback: Selected lowest active load ({healthy[best_server]['load']} reqs)"

        return best_server, healthy[best_server]["rtt"], healthy[best_server]["load"], reason

    @app.route('/send', methods=['POST'])
    def proxy_request():
        data = request.get_json()
        req_type = data.get("type", "query")
        
        # Determine Routing
        target_name, rtt, load, reason = select_best_server(req_type)
        
        start_time = time.time()
        try:
            resp = requests.post(f"http://127.0.0.1:{SERVERS[target_name]['port']}/process", json=data, timeout=5)
            response_data = resp.json()
        except: response_data = {"error": "Server failed"}
        
        response_ms = round((time.time() - start_time) * 1000, 2)
        
        # Log to CSV
        with open(CSV_FILE, mode='a', newline='') as f:
            csv.writer(f).writerow([time.strftime("%H:%M:%S"), req_type, target_name, rtt, load, response_ms, reason])

        return jsonify({"routed_to": target_name, "reason": reason, "rtt": rtt, "load": load, "response": response_data}), 200

    def simulate_client():
        time.sleep(2) 
        while True:
            try: requests.post("http://127.0.0.1:8000/send", json={"type": random.choice(["query", "upload", "background"])})
            except: pass
            time.sleep(1)

    threading.Thread(target=simulate_client, daemon=True).start()
    app.run(host='0.0.0.0', port=8000, debug=False, use_reloader=False)

# ==========================================
# 3. DASHBOARD (Port 5005)
# ==========================================
def run_dashboard():
    app = Flask("Dashboard")
    @app.route('/')
    def admin_home(): return render_template('index.html')
    @app.route('/api/live-data')
    def get_live_data():
        try: return jsonify(requests.get("http://127.0.0.1:5000/matrix", timeout=2).json()), 200
        except: return jsonify({"error": "Offline"}), 500
    app.run(host='0.0.0.0', port=5005, debug=False, use_reloader=False)

if __name__ == '__main__':
    print("\n🚀 STARTING CENTRAL CONTROL SYSTEM (Aggregator, Gateway, UI)\n")
    procs = [multiprocessing.Process(target=run_monitoring), multiprocessing.Process(target=run_gateway), multiprocessing.Process(target=run_dashboard)]
    for p in procs: p.start()
    try:
        for p in procs: p.join()
    except KeyboardInterrupt:
        for p in procs: p.terminate()