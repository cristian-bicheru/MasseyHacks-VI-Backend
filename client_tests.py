import socketio
import time
import os

io = socketio.Client()
io.connect("https://covmapsbackend--cristianbicheru.repl.co")
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
io.emit("heatmap")
print("Simulating Datalog...")
io.emit("logdata", [10, 43.4690083, -80.5771629, 5])
time.sleep(0.5)
io.emit("logdata", [80, 43.4690083, -80.5771629, 5])
time.sleep(0.5)
# Flying to SJAM... (+26m elevation)
io.emit("logdata", [50, 43.471011, -80.594829, 7])
print("Running in background..")
io.wait()
