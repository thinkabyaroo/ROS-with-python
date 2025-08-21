from flask import Flask, render_template, request, session
import os
import pandas as pd
import subprocess
import tempfile
import socket

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this'  # Required for sessions

# Temporary folder for uploaded files
UPLOAD_FOLDER = tempfile.gettempdir()
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        action = request.form.get("action")  # "check" or "execute"
        
        # Handle execute action from results page
        if action == "execute" and 'commands' in session:
            commands_data = session['commands']
            results = []
            
            for cmd_data in commands_data:
                description = cmd_data["description"]
                command = cmd_data["command"]
                
                try:
                    result = subprocess.run(command, shell=True, capture_output=True, text=True)
                    if result.returncode == 0:
                        output = result.stdout.strip()
                        error = ""
                    else:
                        error = result.stderr.strip() or result.stdout.strip()
                        output = ""
                except Exception as e:
                    error = str(e)
                    output = ""

                results.append({
                    "description": description,
                    "command": command,
                    "output": output,
                    "error": error
                })
            
            return render_template("results.html", results=results, 
                                   all_ok=False, only_cmd_not_found=False)
        
        # Handle file upload for check action
        if 'file' not in request.files:
            return "No file uploaded", 400

        file = request.files['file']
        if file.filename == "":
            return "No file selected", 400

        filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(filepath)

        # Read CSV or Excel
        ext = file.filename.split(".")[-1].lower()
        if ext == "csv":
            df = pd.read_csv(filepath)
        elif ext in ["xlsx", "xls"]:
            df = pd.read_excel(filepath)
        else:
            return "Unsupported file type", 400

        # Validate required columns
        if "Description" not in df.columns or "Command" not in df.columns:
            return "File must have 'Description' and 'Command' columns", 400

        results = []
        all_ok = True
        only_cmd_not_found = True
        commands_data = []  # Store for later execution

        for _, row in df.iterrows():
            description = str(row["Description"])
            command = str(row["Command"])
            output, error = "", ""
            
            # Store command data for later execution
            commands_data.append({
                "description": description,
                "command": command
            })

            if action == "check":
                cmd_name = command.split(" ")[0]
                result = subprocess.run(["which", cmd_name], capture_output=True, text=True)
                if result.returncode != 0:
                    error = f"Command not found"
                    all_ok = False
                else:
                    test_result = subprocess.run(command, shell=True, capture_output=True, text=True)
                    if test_result.returncode == 0:
                        output = f"Command exists"
                    else:
                        error = test_result.stderr.strip() or test_result.stdout.strip()
                        all_ok = False
                        only_cmd_not_found = False

            results.append({
                "description": description,
                "command": command,
                "output": output,
                "error": error
            })

        # Store commands in session for later execution
        session['commands'] = commands_data
        
        return render_template("results.html", results=results,
                               all_ok=all_ok, only_cmd_not_found=only_cmd_not_found)

    return render_template("index.html")


def find_free_port(start_port=5000, max_port=9000):
    """Find a free port on localhost starting from start_port."""
    for port in range(start_port, max_port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("0.0.0.0", port))
                return port
            except OSError:
                continue
    raise RuntimeError("No free ports available")


if __name__ == "__main__":
    import sys

    # Default port
    port = 5000

    # Parse command line for --port
    if len(sys.argv) > 1:
        for i, arg in enumerate(sys.argv):
            if arg.startswith("--port="):
                port = int(arg.split("=")[1])
            elif arg == "--port" and i + 1 < len(sys.argv):
                port = int(sys.argv[i + 1])

    # Check if port is free, if not pick a free one
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("0.0.0.0", port))
    except OSError:
        old_port = port
        port = find_free_port()
        print(f"Port {old_port} is in use. Using free port {port} instead.")

    app.run(host="0.0.0.0", port=port, debug=False)