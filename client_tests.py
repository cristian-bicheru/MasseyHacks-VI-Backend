import socketio
import time
import os
import requests
import random

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
    if len(heat_map) != len(data):
        print("Data Length Change:", data)
    heat_map = data

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
#io.emit("logdata", [10, 43.4690083, -80.5771629, 5])
time.sleep(0.5)
#io.emit("logdata", [80, 43.4690083, -80.5771629, 5])
time.sleep(0.5)
# Sighting on Road lo:43.467164, -80.597815 hi:43.474946, -80.597344
#io.emit("logdata", [50, 43.470441, -80.594310, 4])
#dp = [[50,43.472895, -80.588717, 4], [50, 43.472280, -80.591056, 4], [50,43.472132, -80.592976, 7], [50,43.470692, -80.596677, 9], [50,43.471573, -80.593546,9]]
#for p in dp:
    #time.sleep(1)
    #io.emit("logdata", p)
time.sleep(1)
while True:
    io.emit("logdata", [50, random.uniform(43.467164, 43.474946), random.uniform(-80.597815, -80.597344), 4])
    time.sleep(random.randint(1, 400))
print("Simulating Pathfind...")
print("Path:", requests.post(server_url+"/pathfind", {"latitude1":43.472180, "longitude1":-80.585154, "latitude2":43.469424, "longitude2":-80.598612}).json()['path'])

print("Running in background..")
io.wait()
