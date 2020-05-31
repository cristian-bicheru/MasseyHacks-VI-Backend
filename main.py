from aiohttp import web
import aiohttp_cors
import socketio # repl.it autoinstalls wrong package; run os.system("pip3 install -r requirements.txt") instead
import time
import pickle
import atexit
import gnupg # repl.it autoinstalls wrong package; run os.system("pip3 install -r requirements.txt") instead
from vincenty import vincenty
import requests
import math
import asyncio
import os
import polyline
import math

# DB Format: [[time_stamp, alt, lat, long, num_people, fovradius], ...]
if "database" in os.listdir():
    with open("database", "rb") as f:
        db = pickle.load(f)
else:
    db = []

print("Input Google+Here API Key:")
api_key, api_key_here = input().split('|')
io = socketio.AsyncServer(cors_allowed_origins='*')
app = web.Application()
io.attach(app)
gpg = gnupg.GPG()
with open("pubkey", "r") as f:
    mlserverkey = gpg.import_keys(f.read())
authed_sids = []
drone_data = {} # sid : [slat, slong, salt, stime, high_altitude_mode]
with open("index.html", "r") as f:
    root_html = f.read()
##root_html = """<html>
##<body>
##<center>
##<h1 style="color:green;font-family:'Courier New'">COVIDMAPS BACKEND: ONLINE</h1>
##</center>
##</body>
##</html>"""

def save_db(db):
    print()
    print("Saving Database..")
    with open("database", "wb") as f:
        pickle.dump(db, f)

atexit.register(save_db, db)

window = 3600 # one hour

fovradtan = math.tan(math.degrees(41)) # FOV ~ 82 deg
fade_duration = window#seconds

def get_fov_radius(alt):
    return max(alt*fovradtan, 12)#meters, cutoff if fov is under 12m radius

def weight(grouping, data):
    if data[4] > grouping[4] and abs(time.time()-data[0])<120:
        grouping[3] = data[0]
        grouping[4] = data[4]
        return grouping[4]
    else:
        return grouping[5]*max((grouping[3]+window-time.time())/window, 0)

def hmapalgo(full=False):
    hdata = []
    # remove old data
    cutoff = time.time()-window
    for datapoint in db:
        if cutoff > datapoint[0]:
            db.remove(datapoint)
        else:
            grouped = False
            for grouping in hdata:
                if vincenty((grouping[0], grouping[1]), (datapoint[2], datapoint[3]))*1000 < max(datapoint[5], grouping[5]):
                    grouping[0] = grouping[0]*0.9+datapoint[2]*0.1
                    grouping[1] = grouping[1]*0.9+datapoint[3]*0.1
                    grouping[2] = weight(grouping, datapoint)
                    grouping[5] = max(grouping[5], datapoint[5])
                    grouped = True
                    break

            if not grouped:
                hdata.append([datapoint[2], datapoint[3], datapoint[4]*max((datapoint[0]+window-time.time())/window, 0), datapoint[0], datapoint[4], datapoint[5]])
    if full:
        return hdata
    return [[x[0], x[1], x[2]] for x in hdata] # [[lat, long, weight, lastupdatetime, refweight, fovradius], ...]

def format_coord(lat, long):
    return str(lat)+','+str(long)

k = 180/(math.pi*6371000)
piby180 = math.pi/180
# (approximation which works for small dx,dy)
def add_m_to_coords(lat, long, dx, dy):
    return (lat+dy*k, long+dx*k/math.cos(lat*piby180))

root2 = math.sqrt(2)
# convert zones to format required by the here api
def format_exclusion_zones(exclusion_zones):
    outstr = ""
    for zone in exclusion_zones:
        delta = zone[5]/root2*5
        outstr += format_coord(*add_m_to_coords(zone[0], zone[1], delta, delta))+';'
        outstr += format_coord(*add_m_to_coords(zone[0], zone[1], -delta, -delta))+'!'

    return outstr[:-1] # remove last exclamation mark
    

def here_get_path(lat1, long1, lat2, long2, exclusion_zones):
    here_json = requests.get("https://route.ls.hereapi.com/routing/7.2/calculateroute.json?apiKey="+api_key_here+"&waypoint0=geo!"+str(lat1)+','+str(long1)+
                             "&waypoint1=geo!"+str(lat2)+','+str(long2)+"&mode=fastest;pedestrian&generalizationTolerances=0.00001,0.00001&routeAttributes=shape&avoidareas="+format_exclusion_zones(exclusion_zones)).json()
    return [list(map(float, x.split(','))) for x in here_json["response"]["route"][0]["shape"]]

def google_maps_get_path(lat1, long1, lat2, long2):
    google_json = requests.get("https://maps.googleapis.com/maps/api/directions/json?origin="+format_coord(lat1, long1)+"&destination="+format_coord(lat2, long2)+"&key="+api_key).json()
    return polyline.decode(google_json["routes"][0]["overview_polyline"]["points"])

k2 = 111133.34
# technically also an approximation but it should always work
def get_intersections(path, hdata):
    hdatastack = hdata.copy()
    ret = []
    for i in range(len(path)-1):
        a = path[i+1][1]-path[i][1]
        b = path[i+1][0]-path[i][0]
        for datap in hdatastack:
            if abs(a*datap[0]+b*datap[1]-path[i][0]*a-path[i][1]*b)/math.sqrt(a**2 + b**2)*k2 <= datap[5]:
                ret.append(datap)
                hdatastack.remove(datap)
    return ret


def pathfind(lat1, long1, lat2, long2):
    # HERE api limits number of exclusion zones to 20, therefore we have to take extra steps to figure out which
    # zones we are to give to the api. If more than 20 exclusion zones are in the database, this is done by first
    # getting the naive path from the Google Maps API, adding only the zones which intersect with the path, and
    # then getting a path which avoides these zones. This does not guarentee that the path will be free of exclusion
    # zones, but its the best we can do with these APIs.
    
    hdata = hmapalgo(full=True)
    if len(db) < 20:
        return polyline.encode(here_get_path(lat1, long1, lat2, long2, hdata))
    else:
        naive_path = google_maps_get_path(lat1, long1, lat2, long2)
        intersections = get_intersections(naive_path, hdata)
        return polyline.encode(here_get_path(lat1, long1, lat2, long2, intersections))

async def path_find_api(request):
    data = await request.post()
    return web.json_response({'path':pathfind(data["latitude1"], data["longitude1"], data["latitude2"], data["longitude2"])})

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

async def get_heatmap_data(request):
    return web.json_response({'data':hmapalgo()})

async def refresh_data():
    while True:
        await asyncio.sleep(60)
        await io.emit("heatmap_update", hmapalgo())

asyncio.ensure_future(refresh_data())
routes = [
    app.router.add_static('/assets', 'assets'),
    app.router.add_static('/images', 'images'),
    app.router.add_get('/', index),
    app.router.add_get('/heatmap', get_heatmap_data),
    app.router.add_post('/pathfind', path_find_api)]
cors = aiohttp_cors.setup(app, defaults={
    "*": aiohttp_cors.ResourceOptions(
            allow_credentials=True,
            expose_headers="*",
            allow_headers="*",
        )
})

for route in list(routes):
    cors.add(route)

web.run_app(app)
save_db(db)
