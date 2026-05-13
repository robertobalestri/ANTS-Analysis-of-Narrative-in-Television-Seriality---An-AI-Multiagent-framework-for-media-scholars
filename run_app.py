import os
import sys
import subprocess
import webbrowser
import time

def setup_python_env(backend_dir):
    venv_dir = os.path.join(backend_dir, ".venv")
    requirements_file = os.path.join(backend_dir, "requirements.txt")
    
    # Check if .venv exists
    if not os.path.exists(venv_dir):
        print(f"\n[!] Python virtual environment not found at: {venv_dir}")
        choice = input("Would you like to create a virtual environment and install requirements? (y/n): ")
        if choice.lower() == 'y':
            print("Creating virtual environment...")
            subprocess.run([sys.executable, "-m", "venv", venv_dir], check=True)
            print("[+] Virtual environment created.")
        else:
            return sys.executable

    # Determine the venv python executable
    if sys.platform == "win32":
        venv_python = os.path.join(venv_dir, "Scripts", "python.exe")
    else:
        venv_python = os.path.join(venv_dir, "bin", "python")

    # Offer to install requirements if they haven't been installed (or just do it)
    if os.path.exists(requirements_file):
        print("Checking/Installing Python requirements...")
        try:
            subprocess.run([venv_python, "-m", "pip", "install", "-r", requirements_file], check=True)
            print("[+] Requirements installed.")
        except Exception as e:
            print(f"[-] Failed to install requirements: {e}")
    
    return venv_python

def run():
    # Detect the directory of this script
    base_dir = os.path.dirname(os.path.abspath(__file__))
    backend_dir = os.path.join(base_dir, "backend")
    frontend_dir = os.path.join(base_dir, "frontend")
    frontend_dist = os.path.join(frontend_dir, "dist")

    print("=== ANTS: Analysis of Narrative in Television Seriality ===")
    
    # 1. Setup Python Environment
    python_exe = setup_python_env(backend_dir)
    
    # 2. Check for frontend build
    if not os.path.exists(frontend_dist):
        print(f"\n[!] Frontend build not found at: {frontend_dist}")
        choice = input("Would you like to build the frontend now? (Requires Node.js/npm) (y/n): ")
        if choice.lower() == 'y':
            print("Building frontend (this may take a minute)...")
            try:
                subprocess.run("npm install", cwd=frontend_dir, shell=True, check=True)
                subprocess.run("npm run build", cwd=frontend_dir, shell=True, check=True)
                print("[+] Frontend built successfully.")
            except Exception as e:
                print(f"[-] Failed to build frontend: {e}")
                print("[!] Please ensure Node.js is installed and run 'npm run build' manually.")
                return
        else:
            print("[!] Proceeding in API-only mode.")

    # 3. Start the backend server
    print("\nStarting backend server...")
    
    # Command to run uvicorn
    cmd = [
        python_exe, "-m", "uvicorn", 
        "app.api.main:app", 
        "--host", "127.0.0.1", 
        "--port", "8000"
    ]
    
    print(f"Running: {' '.join(cmd)}")
    print("\n[+] Server is starting at http://127.0.0.1:8000")
    print("[+] Press Ctrl+C to stop the server.")
    
    # Open browser automatically after a short delay
    if os.path.exists(frontend_dist):
        def open_browser():
            time.sleep(2)
            webbrowser.open("http://127.0.0.1:8000")
        
        import threading
        threading.Thread(target=open_browser, daemon=True).start()

    try:
        # Run uvicorn in the backend directory
        subprocess.run(cmd, cwd=backend_dir)
    except KeyboardInterrupt:
        print("\nShutting down server...")

if __name__ == "__main__":
    run()
