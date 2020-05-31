const server_url = "https://covmapsbackend--cristianbicheru.repl.co";
const socket = io(server_url);
var heatmap;
var map;
var path;
var coder;

function parseData(data) {
	var ret = [];
	for (pair of data) {
		ret.push({location: new google.maps.LatLng(pair[0], pair[1]), weight: pair[2]});
	}
	return ret;
}

socket.on("heatmap_update", function(data) {
    heatmap.set('data', parseData(data));
});

function initBackend() {
    var data;
    $.ajax({url:server_url+"/heatmap", type:"get", async: false, success:function(gdata) {
        data = gdata;
    }});
    map = new google.maps.Map(document.getElementById('map'), {
        center: new google.maps.LatLng(data.data[0][0], data.data[0][1]),
        zoom: 15,
        mapTypeId: 'satellite'
    });
    heatmap = new google.maps.visualization.HeatmapLayer({
        data: parseData(data.data),
        dissipating: false,
        radius: 0.001
    });
    heatmap.setMap(map);
    var input1 = document.getElementById('pac-input-origin');
    var input2 = document.getElementById('pac-input-dest');
    var searchBox1 = new google.maps.places.SearchBox(input1);
    var searchBox2 = new google.maps.places.SearchBox(input2);
    map.addListener('bounds_changed', function() {
        searchBox1.setBounds(map.getBounds());
        searchBox2.setBounds(map.getBounds());
    });

    coder = new google.maps.Geocoder();
    path = new google.maps.Polyline({
        geodesic: true,
        strokeColor: '#FF0000',
        strokeOpacity: 1.0,
        strokeWeight: 2});
    path.setMap(map);
}

function get_route() {
    var input1 = document.getElementById('pac-input-origin');
    var input2 = document.getElementById('pac-input-dest');
    var data1;
    var data2;
    coder.geocode({address:input1.value}, function(data) {
        var data1 = data[0]['access_points'][0]['location'];
        coder.geocode({address:input2.value}, function(data) {
            var data2 = data[0]['access_points'][0]['location'];
            $.post(server_url+"/pathfind", {"latitude1":data1["latitude"], "longitude1":data1["longitude"], "latitude2":data2["latitude"], "longitude2":data2["longitude"]}, function(data) {
                path.setMap(null);
                path = new google.maps.Polyline({
                    path: google.maps.geometry.encoding.decodePath(data['path']),
                    geodesic: true,
                    strokeColor: '#FF0000',
                    strokeOpacity: 1.0,
                    strokeWeight: 2});
                path.setMap(map);
            });
        });
    });
}