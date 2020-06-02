const server_url = "https://covmapsbackend--cristianbicheru.repl.co";
const socket = io(server_url);
var heatmap;
var map;
var path;
var coder;
var searchBox1;
var last_payload;

function parseData(data) {
	var ret = [];
	for (pair of data) {
		ret.push({location: new google.maps.LatLng(pair[0], pair[1]), weight: pair[2]});
	}
	return ret;
}

function clearMap() {
    path.setMap(null);
    toggleClearButton();
    last_payload = null;
}

function toggleClearButton() {
    if (document.getElementById("clearbutton").style.display == "none") {
        document.getElementById("clearbutton").style.display = "";
    } else {
        document.getElementById("clearbutton").style.display = "none";
    }
}

socket.on("heatmap_update", function(data) {
    if (last_payload) {
        $.post(server_url+"/pathfind", last_payload, function(data) {
            path.setMap(null);
            path = new google.maps.Polyline({
                path: google.maps.geometry.encoding.decodePath(data['path']),
                geodesic: true,
                strokeColor: '#FF0000',
                strokeOpacity: 1.0,
                strokeWeight: 2});
            path.setMap(map);
        });
    }
    heatmap.setData(parseData(data));
});

function initBackend() {
    var data;
    $.ajax({url:server_url+"/heatmap", type:"get", async: false, success:function(gdata) {
        data = gdata;
    }});
    map = new google.maps.Map(document.getElementById('map'), {
        zoom: 15,
        mapTypeId: 'satellite'
    });
    if (data.data.length > 0) {
        map.set('center', new google.maps.LatLng(data.data[0][0], data.data[0][1]));
    }
    heatmap = new google.maps.visualization.HeatmapLayer({
        data: parseData(data.data),
        dissipating: false,
        radius: 0.001
    });
    heatmap.setMap(map);
    var input1 = document.getElementById('pac-input-origin');
    var input2 = document.getElementById('pac-input-dest');
    searchBox1 = new google.maps.places.SearchBox(input1);
    var searchBox2 = new google.maps.places.SearchBox(input2);

    map.addListener('bounds_changed', function() {
        searchBox1.setBounds(map.getBounds());
        searchBox2.setBounds(map.getBounds());
    });

    searchBox2.addListener('places_changed', function() {
        var bounds = new google.maps.LatLngBounds();
        var dplaces = searchBox2.getPlaces();
        if (dplaces.length == 0) {
            return;
        }
        var splaces = searchBox1.getPlaces();
        if (splaces.length == 0) {
            return;
        }
        splaces.forEach(function(splace) {
            if (!splace.geometry) {
                return;
            }
            dplaces.forEach(function(dplace) {
                if (!dplace.geometry) {
                    return;
                }
                last_payload = {"latitude1":splace.geometry.location.lat(), "longitude1":splace.geometry.location.lng(), "latitude2":dplace.geometry.location.lat(), "longitude2":dplace.geometry.location.lng()};
                $.post(server_url+"/pathfind", last_payload, function(data) {
                    path.setMap(null);
                    path = new google.maps.Polyline({
                        path: google.maps.geometry.encoding.decodePath(data['path']),
                        geodesic: true,
                        strokeColor: '#FF0000',
                        strokeOpacity: 1.0,
                        strokeWeight: 2});
                    path.setMap(map);
                    toggleClearButton();
                });
                if (splace.geometry.viewport) {
                    bounds.union(splace.geometry.viewport);
                } else {
                    bounds.extend(splace.geometry.location);
                }
                if (dplace.geometry.viewport) {
                    bounds.union(dplace.geometry.viewport);
                } else {
                    bounds.extend(dplace.geometry.location);
                }
            });
        });
        map.fitBounds(bounds);
    });

    coder = new google.maps.Geocoder();
    path = new google.maps.Polyline({
        geodesic: true,
        strokeColor: '#FF0000',
        strokeOpacity: 1.0,
        strokeWeight: 2});
    path.setMap(map);

    $('#pac-input-origin').keypress(function(e) {
        if (e.which == 13) {
            google.maps.event.trigger(searchBox2, 'places_changed');
            return;
        }
    });

    $('#pac-input-dest').keypress(function(e) {
        if (e.which == 13) {
            google.maps.event.trigger(searchBox2, 'places_changed');
            return;
        }
    });
}
