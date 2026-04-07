import multiprocessing
import time
from flask import Flask, request, jsonify

def create_and_run_server(port, server_name, specialization):
    """Creates a Flask app and runs it. This runs in its own process."""
    app = Flask(server_name)

    # We use a dictionary to hold state so it can be modified by the inner route functions.
    # Each process gets its own independent copy of this state.
    state = {
        "is_crashed": False,
        "is_slow": False
    }
    @app.route('/', methods=['GET'])
    def home():
        return f"<h1>Welcome to {server_name}</h1><p>Specialization: {specialization}</p><p>Status: Running</p>"
    @app.route('/process', methods=['POST', 'GET'])
    def process_request():
        if state["is_crashed"]:
            return jsonify({"error": f"{server_name} is currently crashed!"}), 500

        if state["is_slow"]:
            time.sleep(3)

        request_type = "unknown"
        if request.is_json:
            data = request.get_json()
            request_type = data.get("type", "unknown")

        return jsonify({
            "message": "Request processed successfully.",
            "server": server_name,
            "specialization": specialization,
            "handled_type": request_type,
            "status": "success"
        }), 200

    @app.route('/simulate-crash', methods=['POST'])
    def simulate_crash():
        state["is_crashed"] = True
        return jsonify({"message": f"{server_name} state changed to: CRASHED"}), 200

    @app.route('/simulate-slow', methods=['POST'])
    def simulate_slow():
        state["is_slow"] = True
        return jsonify({"message": f"{server_name} state changed to: SLOW"}), 200

    @app.route('/recover', methods=['POST'])
    def recover():
        state["is_crashed"] = False
        state["is_slow"] = False
        return jsonify({"message": f"{server_name} state changed to: NORMAL (Recovered)"}), 200

    @app.route('/health', methods=['GET'])
    def health_check():
        if state["is_crashed"]:
            return jsonify({"status": "unhealthy", "server": server_name}), 500
        return jsonify({"status": "healthy", "server": server_name}), 200

    # Start the server
    print(f"[*] Starting {server_name} ({specialization}) on port {port}...")
    # debug=False is required when using multiprocessing
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False) 

if __name__ == '__main__':
    # Define your three application servers
    servers_config = [
        {"port": 5001, "name": "S1", "specialization": "Low Latency"},
        {"port": 5002, "name": "S2", "specialization": "High Throughput"},
        {"port": 5003, "name": "S3", "specialization": "General"}
    ]

    processes = []

    # Spawn a new process for each server
    for config in servers_config:
        p = multiprocessing.Process(
            target=create_and_run_server, 
            args=(config["port"], config["name"], config["specialization"])
        )
        p.start()
        processes.append(p)

    print("\n[+] All application servers are running. Press Ctrl+C to stop.\n")

    # Keep the main script alive and handle clean shutdown
    try:
        for p in processes:
            p.join()
    except KeyboardInterrupt:
        print("\n[-] Shutting down all servers...")
        for p in processes:
            p.terminate()
        print("Done.")