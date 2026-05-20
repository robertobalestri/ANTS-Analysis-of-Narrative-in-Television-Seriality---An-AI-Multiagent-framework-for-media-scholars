import os
import sys
import subprocess
import webbrowser
import time
import urllib.request
import zipfile
import tarfile
import io
import platform
import stat
import shutil

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

def ensure_ffmpeg(backend_dir):
    bin_dir = os.path.join(backend_dir, "bin")
    if not os.path.exists(bin_dir):
        os.makedirs(bin_dir)

    ffmpeg_exe = os.path.join(bin_dir, "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg")
    ffprobe_exe = os.path.join(bin_dir, "ffprobe.exe" if sys.platform == "win32" else "ffprobe")

    if os.path.exists(ffmpeg_exe) and os.path.exists(ffprobe_exe):
        return bin_dir

    print("\n[!] FFmpeg/FFprobe binaries not found in backend/bin.")
    print("Downloading appropriate binaries for your OS...")

    # Define URLs based on platform (using BtbN/FFmpeg-Builds for Win/Linux)
    system = platform.system().lower()
    
    # BtbN URLs for Win/Linux, evermeet.cx for macOS
    urls = {
        "windows": "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip",
        "linux": "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linux64-gpl.tar.xz",
        "darwin": [
            "https://evermeet.cx/ffmpeg/getrelease/zip",
            "https://evermeet.cx/ffmpeg/getrelease/ffprobe/zip"
        ]
    }

    if system not in urls:
        print(f"[-] Unsupported system: {system}. Please install FFmpeg manually.")
        return None

    try:
        download_urls = urls[system] if isinstance(urls[system], list) else [urls[system]]
        
        # Temporary directory for extraction
        temp_extract = os.path.join(bin_dir, "temp_extract")
        if os.path.exists(temp_extract):
            shutil.rmtree(temp_extract)
        os.makedirs(temp_extract)

        for url in download_urls:
            print(f"  Downloading from {url}...")
            # Use a more descriptive User-Agent to avoid issues with some APIs
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as response:
                content = response.read()
                # Determine format from URL or Content-Type (default to zip)
                is_tar = url.endswith(".tar.xz") or "application/x-xz" in response.info().get_content_type()
                
                if is_tar:
                    with tarfile.open(fileobj=io.BytesIO(content), mode="r:xz") as t:
                        t.extractall(temp_extract)
                else:
                    with zipfile.ZipFile(io.BytesIO(content)) as z:
                        z.extractall(temp_extract)
        
        # Find ffmpeg and ffprobe in the extracted files
        found_tools = {}
        target_tools = ["ffmpeg", "ffprobe"]
        if sys.platform == "win32":
            target_tools = ["ffmpeg.exe", "ffprobe.exe"]

        for root, dirs, files in os.walk(temp_extract):
            for file in files:
                if file in target_tools:
                    found_tools[file] = os.path.join(root, file)

        # Move tools to bin_dir
        for tool, src_path in found_tools.items():
            dest_path = os.path.join(bin_dir, tool)
            if os.path.exists(dest_path):
                os.remove(dest_path)
            shutil.move(src_path, dest_path)
            
            # Set executable permissions on non-windows
            if sys.platform != "win32":
                st = os.stat(dest_path)
                os.chmod(dest_path, st.st_mode | stat.S_IEXEC)

        # Cleanup
        shutil.rmtree(temp_extract)
                
        print("[+] FFmpeg and FFprobe successfully installed in backend/bin.")
    except Exception as e:
        print(f"[-] Error downloading FFmpeg: {e}")
        return None

    return bin_dir

def run():
    # Detect the directory of this script
    base_dir = os.path.dirname(os.path.abspath(__file__))
    backend_dir = os.path.join(base_dir, "backend")
    frontend_dir = os.path.join(base_dir, "frontend")
    frontend_dist = os.path.join(frontend_dir, "dist")

    print("=== ANTS: Analysis of Narrative in Television Seriality ===")
    
    # 1. Setup Python Environment
    python_exe = setup_python_env(backend_dir)
    
    # 2. Setup FFmpeg
    bin_dir = ensure_ffmpeg(backend_dir)
    if bin_dir:
        # Add bin directory to PATH for the current process and its children
        os.environ["PATH"] = bin_dir + os.pathsep + os.environ.get("PATH", "")
    
    # 3. Check for frontend build
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
