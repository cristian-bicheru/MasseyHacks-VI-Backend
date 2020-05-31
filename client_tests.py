import socketio
import time
import os
import requests

server_url = "https://covmapsbackend--cristianbicheru.repl.co"
io = socketio.Client()
io.connect(server_url)
start = 1
heat_map = []

@io.on("echo")
def echo(msg):
    print("Latency:", str(int((time.perf_counter()-start)*1000))+"ms")
    print("Echoed:", msg)

@io.on("authenticate_status")
def status(msg):
    print(msg)

@io.on("takeoff_status")
def status(msg):
    print(msg)

@io.on("heatmap_update")
def update(data):
    global heat_map
    heat_map = data
    print("Data Updated:", data)

print("Pinging Server...")
start = time.perf_counter()
io.emit("echo", "test")

time.sleep(1)

print("Testing Authentication... NOTE: This requires the privkey file.")
import gnupg
# ON UNIX, THE GPGBINARY ARG SHOULD BE REMOVED. THIS WAS MY GPG INSTALL PATH ON WINDOWS 10
gpg = gnupg.GPG(gpgbinary="C:\\Program Files (x86)\\GnuPG\\bin\\gpg.exe", gnupghome=os.getcwd()+"\\gpg_scratch")
with open("privkey", "r") as f:
    gpg.import_keys(f.read())
io.emit("authenticate", str(gpg.sign("auth")))

time.sleep(1)

print("Simulating Takeoff Data...")
io.emit("takeoff", [43.4690083,-80.5771629])

time.sleep(1)

print("Syncing Heatmap...")
heat_map = requests.get(server_url+"/heatmap").json()["data"]
print("Synced Map:", heat_map)
print("Simulating Datalog...")
io.emit("logdata", [10, 43.4690083, -80.5771629, 5])
time.sleep(0.5)
io.emit("logdata", [80, 43.4690083, -80.5771629, 5])
time.sleep(0.5)
# Flying to SJAM... (+26m elevation)
io.emit("logdata", [50, 43.471011, -80.594829, 7])
time.sleep(0.5)
# Sighting on Road
io.emit("logdata", [50, 43.470441, -80.594310, 4])

time.sleep(1)
print("Simulating Pathfind...")
print("Path:", requests.post(server_url+"/pathfind", {"latitude1":43.472180, "longitude1":-80.585154, "latitude2":43.469424, "longitude2":-80.598612}).json()['path'])

print("Running in background..")
io.wait()
