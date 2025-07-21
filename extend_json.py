import requests, json
from geopy.distance import geodesic
from math import atan2, degrees, radians, sin, cos
from mapillary_class import _read_json


OVERPASS_QUERY = """
[out:json][timeout:60];
(
  way
    {query_params}
    (around:{radius_meters},{center_latitude},{center_longitude});
);
out geom;
"""
_OVERPASS_URL = "https://overpass-api.de/api/interpreter"

def calc_dist(pct_start: tuple, pct_sfarsit: tuple) -> float:
    lat1, lon1 = radians(pct_start[0]), radians(pct_start[1])
    lat2, lon2 = radians(pct_sfarsit[0]), radians(pct_sfarsit[1])

    delta_lon = lon2 - lon1

    y = sin(delta_lon) * cos(lat2)
    x = cos(lat1) * sin(lat2) - sin(lat1) * cos(lat2) * cos(delta_lon)

    dir_init_rad = atan2(y, x)
    dir_init_deg = degrees(dir_init_rad)

    return (dir_init_deg + 360) % 360

def get_overpass_data(query: str):
    try:
        resp = requests.get(_OVERPASS_URL, params={'data': query}, timeout=60)
        resp.raise_for_status()
        return resp.json()
    
    except requests.exceptions.Timeout:
        print('Eroare la request: Timeout')
        return None
    
    except requests.exceptions.RequestException as e:
        print(f'Eroare la request: {e}')
        return None
    
    except json.JSONDecodeError:
        print(f'Eroare la request: Decodare json-ului, {resp.text[:500]}')
        return None
    
def interpol_polyline(noduri: list[dict], interval: float=10.0):
    if not noduri or len(noduri) < 2:
        return None
    
    pcte_path = [(nod['lat'], nod['lon']) for nod in noduri]
    if not pcte_path:
        return None

    coords = []
    coords.append(pcte_path[0])
    dist_urm_interval_pct = interval

    for i in range(len(pcte_path) - 1):
        nod_start_segm = pcte_path[i]
        nod_sfarsit_segm = pcte_path[i + 1]

        lung_segm = geodesic(nod_start_segm, nod_sfarsit_segm).meters

        if lung_segm < 1e-3: continue

        dist_segment_curent = calc_dist(nod_start_segm, nod_sfarsit_segm)
        dist_segment_parcursa = 0.0

        while dist_segment_parcursa + dist_urm_interval_pct <= lung_segm:
            dist_segment_parcursa += dist_urm_interval_pct

            geopoint = geodesic(meters=dist_segment_parcursa).destination(
                point=nod_start_segm,
                bearing=dist_segment_curent
            )
            coords.append((geopoint.latitude, geopoint.longitude))
            dist_urm_interval_pct = interval
        
        dist_urm_interval_pct -= (lung_segm - dist_segment_parcursa)

    coord_unice = []
    coord_vazute = set()
    for coord in coords:
        coord_rotunjite = (round(coord[0], 15), round(coord[1], 15))
        if coord_rotunjite not in coord_vazute:
            coord_unice.append(coord)
            coord_vazute.add(coord_rotunjite)

    coord_finale = [{'lat': coord[0], 'long': coord[1]}  for coord in coord_unice]

    return coord_finale

def _get_centers(places_def: list) -> list[dict]:
    all_coords: list[dict] = []

    for place in places_def:
        place_name = place.get('name', 'unknown')

        center_coord = place.get('google_center')
        if center_coord:
            all_coords.append({
                'lat': center_coord['lat'],
                'lon': center_coord['long'],
                'name': f"{place_name.replace(' ', '_')}"
            })
    
    return all_coords

def get_place_coords(center: list[dict], query_params: tuple) -> dict[str|list] | None:
    center_name = center['name']
    center_lat = center['lat']
    center_lon = center['lon']

    query = OVERPASS_QUERY.format(
        radius_meters=query_params[0],
        center_latitude=center_lat,
        center_longitude=center_lon,
        query_params=query_params[2]
    )
    overpass_data = get_overpass_data(query)
    if not overpass_data: return None

    all_extracted_points = []
    id_count = 0

    if overpass_data and 'elements' in overpass_data:
        ways_with_geometry = [
            elem for elem in overpass_data['elements'] 
            if elem.get('type') == 'way' and 'geometry' in elem and elem['geometry']
        ]

        for i, way_element in enumerate(ways_with_geometry):
            geometry_nodes = way_element.get('geometry')
            
            if len(geometry_nodes) >= 2:
                interpolated_points = interpol_polyline(geometry_nodes)
                
                if interpolated_points:
                    all_extracted_points.extend(interpolated_points)

    final_unique_points_overall = []
    seen_overall_coords_set = set()
    if all_extracted_points:
        for p_coord_overall in all_extracted_points:
            coord_tuple_overall_rounded = (round(p_coord_overall['long'], 7), round(p_coord_overall['lat'], 7))
            if coord_tuple_overall_rounded not in seen_overall_coords_set:
                final_unique_points_overall.append(p_coord_overall)
                seen_overall_coords_set.add(coord_tuple_overall_rounded)

    for coord in final_unique_points_overall:
        coord['id_coord'] = id_count
        id_count += 1

    center_final = {
        'name': center_name,
        'google_center': {
            'lat': center_lat,
            'long': center_lon,
        },
        'google_coords': final_unique_points_overall
    }

    return center_final

def _read_params(params_file: str) -> list[tuple]:
    with open(params_file) as f:
        lines = f.readlines()

    params_list = []

    for line in lines:
        line = line.split(' ')
        params_list.append((float(line[0]), float(line[1]), line[2]))

    return params_list

if __name__ == "__main__":
    places_def = _read_json('dataset_request_directview.json')
    params = _read_params('json_distances.txt')
    centers = _get_centers(places_def)

    entries = []
    
    for i in range(len(centers)):
        entry = get_place_coords(
            center=centers[i],
            query_params=params[i]
        )
        if entry: entries.append(entry)

    json_final = {
        'placedefinitions': entries
    }

    with open('dataset_coords_meu_mare.json', 'w') as f:
        json.dump(json_final, f, indent=4, ensure_ascii=False)
    