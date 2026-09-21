import subprocess
import sys
import time
import os

def main():
    print("=" * 70)
    print(" ⚡ HAVELOC PLACEMENT APPLICATION AGENT — PRODUCTION SYSTEM LAUNCHER")
    print("=" * 70)

    # 1. Seed database
    print("\n[1/3] Checking and seeding database with student facts and jobs...")
    seed_process = subprocess.run([sys.executable, "-m", "backend.seed_data"])
    if seed_process.returncode != 0:
        print("Database seed failed. Aborting.")
        return

    # 2. Start Backend API on port 8000
    print("\n[2/3] Starting Backend API & Dashboard on http://localhost:8000 ...")
    backend_proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
    )

    # 3. Start Mock Haveloc Portal on port 8080
    print("\n[3/3] Starting Mock Haveloc Portal on http://localhost:8080 ...")
    portal_proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "mock_portal.server:mock_portal", "--host", "0.0.0.0", "--port", "8080"]
    )

    time.sleep(2)
    print("\n" + "=" * 70)
    print(" ✓ SYSTEM READY & RUNNING:")
    print("   • Student Control Dashboard : http://localhost:8000/dashboard")
    print("   • Backend API Swagger Docs  : http://localhost:8000/docs")
    print("   • Mock Haveloc Portal       : http://localhost:8080/jobs")
    print("   • Browser Extension Dir     : " + os.path.abspath("extension"))
    print("=" * 70)
    print("Press Ctrl+C to stop all services.\n")

    try:
        backend_proc.wait()
        portal_proc.wait()
    except KeyboardInterrupt:
        print("\nStopping services...")
        backend_proc.terminate()
        portal_proc.terminate()
        print("All processes stopped safely.")

if __name__ == "__main__":
    main()
