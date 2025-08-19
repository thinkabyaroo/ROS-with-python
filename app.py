from flask import Flask, render_template, request
import os
import pandas as pd
import subprocess
import tempfile
import socket

app = Flask(__name__)

# Temporary folder for uploaded files
UPLOAD_FOLDER = tempfile.gettempdir()
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        if 'file' not in request.files:
            return "No file uploaded", 400

        file = request.files['file']
        if file.filename == "":
            return "No file selected", 400

        action = request.form.get("action")  # "check" or "execute"

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
        for _, row in df.iterrows():
            description = str(row["Description"])
            command = str(row["Command"])
            output, error = "", ""

            if action == "check":
                cmd_name = command.split(" ")[0]
                result = subprocess.run(["which", cmd_name], capture_output=True, text=True)
                if result.returncode != 0:
                    error = f"✗ Command not found: {cmd_name}"
                else:
                    test_result = subprocess.run(command, shell=True, capture_output=True, text=True)
                    if test_result.returncode == 0:
                        output = "✓ Command exists"
                    else:
                        error = test_result.stderr.strip() or test_result.stdout.strip()
            elif action == "execute":
                try:
                    result = subprocess.run(command, shell=True, capture_output=True, text=True)
                    if result.returncode == 0:
                        output = result.stdout.strip()
                    else:
                        error = result.stderr.strip() or result.stdout.strip()
                except Exception as e:
                    error = str(e)

            results.append({
                "description": description,
                "command": command,
                "output": output,
                "error": error
            })

        return render_template("results.html", results=results)

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

    print(f"Running Flask app on http://<your-ip>:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)