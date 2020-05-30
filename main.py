from aiohttp import web
import socketio
import time
import pickle
import signal
import gnupg
from vincenty import vincenty
import requests
import math
import asyncio

# DB Format: [[time_stamp, alt, lat, long, num_people], ...]
with open("db.pkl", "rb") as f:
    db = pickle.load(f)

io = socketio.AsyncServer()
app = web.Application()
io.attach(app)
gpg = gnupg.GPG(gpgbinary="C:\\Program Files (x86)\\GnuPG\\bin\\gpg.exe")
with open("pubkey", "r") as f:
    mlserverkey = gpg.import_keys(f.read())
authed_sids = []
drone_data = {} # sid : [slat, slong, salt, stime]

root_html = """<html>
<body>
<h1>COVIDMAPS BACKEND</h1>
</body>
</html>"""

def save_db(*args):
    with open("db.pkl", "wb") as f:
        pickle.dump(db, f)

for sig in (signal.SIGTERM, signal.SIGBREAK, signal.SIGINT):
    signal.signal(sig, save_db)

window = 3600 # one hour

# calculate the radius of the fov on the ground assuming the drone is roughly 40m up
fovrad = 40*math.tan(math.degrees(41))#metes
grouping_radius = 0.05+fovrad/1000#meters
fade_duration = window#seconds

def weight(grouping, data):
    if data[4] > grouping[4] and abs(time.time()-data[0])<120:
        grouping[4] = data[0]
        grouping[5] = data[4]
        grouping[3] = grouping[5]
    else:
        grouping[3] = grouping[5]*max(grouping[4]+window-time.time(), 0)

def hmapalgo():
    hdata = []
    # remove old data
    cutoff = time.time()-window
    for datapoint in db:
        if cutoff > datapoint[0]:
            db.remove(datapoint)
        else:
            grouped = False
            for grouping in hdata:
                if vincenty((grouping[0], grouping[1]), (datapoint[0], datapoint[1])) < grouping_radius:
                    grouping[0] = grouping[0]*0.9+datapoint[0]*0.1
                    grouping[1] = grouping[1]*0.9+datapoint[1]*0.1
                    grouping[2] = weight(grouping, datapoint)
                    grouped = True
                    break

            if not grouped:
                hdata += [data[1], data[2], data[4], data[0], data[4]]

    return hdata # [[lat, long, weight, lastupdatetime, refweight], ...]

async def index(request):
    return web.Response(text=root_html, content_type='text/html')

@io.on("authenticate")
def auth(sid, data):
    if gpg.verify(data):
        if abs(int(data)-time.time()) < 10:
            authed_sids.append(sid)
        else:
            return False
    else:
        return False

@io.on("takeoff")
def takeoff(sid, data):
    if sid in authed_sids:
        query = 'https://api.open-elevation.com/api/v1/lookup?locations='+str(data[0])+','+str(data[1])
        r = requests.get(query).json()
        drone_data[sid] = data+[r['elevation'], time.time()]

@io.on("echo")
async def echo(sid, data):
    io.emit("echo", data, room=sid)

@io.on("logdata")
async def log_data(sid, data):
    if sid in authed_sids:
        data[0] += drone_data[sid]
        db.append([time.time()]+data)

@io.on("heatmap")
async def hmap(sid, data):
    io.emit("heatmap", hmapalgo(), room=sid)

async def update():
    await io.emit("heatmap_update", hmapalgo())

while True:
    asyncio.run(update())
    time.sleep(10)
    
