from aiohttp import web
import socketio #prevent repl from autoinstalling another package
import time
import pickle
import atexit
import gnupg #prevent repl from autoinstalling another package
from vincenty import vincenty
import requests
import math
import asyncio
import os

# DB Format: [[time_stamp, alt, lat, long, num_people, fovradius], ...]
if "database" in os.listdir():
    with open("database", "rb") as f:
        db = pickle.load(f)
else:
    db = []

print("Input API Key:")
api_key = input()
io = socketio.AsyncServer()
app = web.Application()
io.attach(app)
gpg = gnupg.GPG()
with open("pubkey", "r") as f:
    mlserverkey = gpg.import_keys(f.read())
authed_sids = []
drone_data = {} # sid : [slat, slong, salt, stime, high_altitude_mode]

root_html = """<html>
<body>
<center>
<h1 style="color:green;font-family:'Courier New'">COVIDMAPS BACKEND: ONLINE</h1>
</center>
</body>
</html>"""

def save_db(db):
    print()
    print("Saving Database..")
    with open("database", "wb") as f:
        pickle.dump(db, f)

atexit.register(save_db, db)

window = 3600 # one hour

# calculate the radius of the fov on the ground assuming the drone is roughly 40m up
fovradtan = math.tan(math.degrees(41))
fade_duration = window#seconds

def get_fov_radius(alt):
    return max(alt*fovradtan, 20)#meters

def weight(grouping, data):
    if data[4] > grouping[4] and abs(time.time()-data[0])<120:
        grouping[3] = data[0]
        grouping[4] = data[4]
        return grouping[4]
    else:
        return grouping[5]*max((grouping[3]+window-time.time())/window, 0)

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
                if vincenty((grouping[0], grouping[1]), (datapoint[0], datapoint[1]))*1000 < max(datapoint[5], grouping[5]):
                    grouping[0] = grouping[0]*0.9+datapoint[2]*0.1
                    grouping[1] = grouping[1]*0.9+datapoint[3]*0.1
                    grouping[2] = weight(grouping, datapoint)
                    grouping[5] = max(grouping[5], datapoint[5])
                    grouped = True
                    break

            if not grouped:
                hdata.append([datapoint[2], datapoint[3], datapoint[4]*max((datapoint[0]+window-time.time())/window, 0), datapoint[0], datapoint[4], datapoint[5]])

    return [[x[0], x[1], x[2]] for x in hdata] # [[lat, long, weight, lastupdatetime, refweight, fovradius], ...]

async def index(request):
    return web.Response(text=root_html, content_type='text/html')

def get_elevation(lat, long):
    r = []
    ctr = 0
    while (len(r) == 0 and ctr < 10):
        r = requests.get("https://maps.googleapis.com/maps/api/elevation/json?locations="+str(lat)+','+str(long)+"&key="+api_key).json()["results"]
        ctr += 1
    if (ctr == 10):
        print("Fatal Error: Could Not Determine Elevation")
        return 20
    return r[0]['elevation']

@io.event
async def disconnect(sid):
    if sid in authed_sids:
        authed_sids.remove(sid)
        if sid in drone_data.keys():
            del drone_data[sid]

@io.on("authenticate")
async def auth(sid, data):
    signature = gpg.verify(data)
    if signature:
        if abs(int(signature.timestamp)-time.time()) < 10:
            authed_sids.append(sid)
            await io.emit("authenticate_status", "Authentication Successful.", room=sid)
        else:
            await io.emit("authenticate_status", "Authentication Timeout.", room=sid)
    else:
        await io.emit("authenticate_status", "Authentication Unsuccessful.", room=sid)

@io.on("takeoff")
async def takeoff(sid, data):
    if sid in authed_sids:
        elev = get_elevation(data[0], data[1])
        drone_data[sid] = data+[elev, time.time(), False]
        await io.emit("takeoff_status", "Launch Data Received.", room=sid)
    else:
        await io.emit("takeoff_status", "Error: Not Authenticated.", room=sid)

@io.on("echo")
async def echo(sid, data):
    await io.emit("echo", data, room=sid)

@io.on("logdata")
async def log_data(sid, data):
    if sid in authed_sids:
        if sid in drone_data.keys():
            data[0] += drone_data[sid][2]-get_elevation(data[1], data[2])
            if data[0] > 70:
                if not drone_data[sid][4]:
                    await io.emit("takeoff_status", "Status: Entering High-Altitude Reposition Mode...", room=sid)
                    drone_data[sid][4] = True
            else:
                if drone_data[sid][4]:
                    await io.emit("takeoff_status", "Status: Exiting High-Altitude Reposition Mode...", room=sid)
                    drone_data[sid][4] = False
                db.append([time.time()]+data+[get_fov_radius(data[0])])
        else:
            await io.emit("takeoff_status", "Error: Received Log Data Without Takeoff Data.", room=sid)

@io.on("heatmap")
async def hmap(sid):
    await io.emit("heatmap_update", hmapalgo(), room=sid)
    
async def refresh_data():
    while True:
        await asyncio.sleep(10)
        await io.emit("heatmap_update", hmapalgo())

asyncio.ensure_future(refresh_data())
app.router.add_get('/', index)
web.run_app(app)
save_db(db)
