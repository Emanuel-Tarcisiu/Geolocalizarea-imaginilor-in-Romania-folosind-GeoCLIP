import requests
import os
import math
import json
from time import sleep


def _img_direction(img_data):
    if 'computed_compass_angle' in img_data:
        return img_data['computed_compass_angle']
    return None


def _score_img(img_data, lm_lat: float, lm_lon: float) -> float:
        scor: float = 100

        if 'geometry' in img_data and 'coordinates' in img_data['geometry']:
            img_lon, img_lat = img_data['geometry']['coordinates']
            distanta = _haversine_dist(lm_lon, lm_lat, img_lon, img_lat)

            if distanta < 10:
                scor -= 30
            elif distanta < 50:
                scor += 20
            else:
                scor -= distanta * 0.1

        # directie = _img_direction(img_data=img_data)
        # if directie is not None:
        #     # TODO implementeaza
        #     pass

        # if 'captured_at' in img_data:
        #     an = int(img_data['captured_at'][:4])

        #     if an >= 2018:
        #         scor += 15
        #     elif an >= 2016:
        #         scor += 10
        #     elif an >= 2014:
        #         scor += 5

        return scor


def _read_json(json_file_path: str) -> list:
    with open(json_file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        all_place_definitions = data.get('placedefinitions', [])
    return all_place_definitions


def _load_json(json_file_path: str) -> list[dict]:
    places_def = _read_json(json_file_path=json_file_path)
    if len(places_def) == 0 : raise Exception(f"NU s-au citit bine locatiile din json: {json_file_path}")

    all_coords: list[dict] = []
    for place in places_def:
        place_name = place.get('name', 'unknown')

        center_coord = place.get('google_center')
        google_coords = place.get('google_coords', [])

        if center_coord:
            all_coords.append({
                'lat': center_coord['lat'],
                'lon': center_coord['long'],
                'name': f"{place_name}_{0}"
            })

        for id, coord in enumerate(google_coords, start=1):
            all_coords.append({
                'lat': coord['lat'],
                'lon': coord['long'],
                'name': f"{place_name}_{id}"
            })

    return all_coords


def _haversine_dist(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    lon1, lat1, lon2, lat2 = map(math.radians, [lon1, lat1, lon2, lat2])

    dlon = lon2 - lon1
    dlat = lat2 - lat1

    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    r = 6371000

    return c * r


def _calc_bbox(lat: float, lon: float, raza: int=100) -> tuple:
        lat_offset = raza / 111000
        lon_offset = raza / (111000 * abs(lat * 3.14159 / 180))

        min_lat = lat - lat_offset
        max_lat = lat + lat_offset

        min_lon = lon - lon_offset
        max_lon = lon + lon_offset

        return min_lon, min_lat, max_lon, max_lat

class Mapillary_Interface:

    def __init__(self, access_token: str, json_file: str = None) -> None:
        self._access_token = access_token
        self._base_url = 'https://graph.mapillary.com'
        self._json_loc = _load_json(json_file) if json_file is not None else []     

    
    def get_json_imgs(self, output_dir: str, num_img: int = 3) -> list[dict] | None:
        if len(self._json_loc) == 0: raise Exception("Lista cu locatii este goala!")
        csv_entries: list[dict] = []

        for landmark in self._json_loc:
            entry = self.get_place_imgs(
                landmark=landmark,
                output_dir=output_dir,
                num_img=num_img,
                raza=150
            )
            if entry is not None: csv_entries.extend(entry)

        return csv_entries
        

    def get_place_imgs(self, landmark: dict[str, str | float], output_dir: str, num_img: int = 3, raza: int = 100) -> list[dict] | None:
        csv_entries: list[dict] = []

        try:
            min_lon, min_lat, max_lon, max_lat = _calc_bbox(landmark['lat'], landmark['lon'], raza)

            bbox = f"{min_lon},{min_lat},{max_lon},{max_lat}"

            params = {
                'fields': 'id,thumb_2048_url,computed_compass_angle,captured_at,geometry',
                'bbox': bbox,
                'limit': 100
            }
            headers = {"Authorization": f"OAuth {self._access_token}"}

            response = requests.get(
                f"{self._base_url}/images",
                params=params,
                headers=headers
            )

            if response.status_code != 200:
                print(f"Eroare API Mapillary {response.status_code}: {response.text}")
                return None
            
            data = response.json()

            if 'data' not in data or len(data['data']) == 0:
                print(f"NU au fost gasite imagini pentru {landmark['name']}")
                return None
            
            img_evaluate: list = []

            for img in data['data']:
                scor = _score_img(img, landmark['lat'], landmark['lon'])
                img_evaluate.append((img, scor))

            img_evaluate.sort(key=lambda x: x[1], reverse=True)

            top_img = img_evaluate[:num_img]

            for i, (img, scor) in enumerate(top_img):
                try:
                    if 'thumb_2048_url' in img:
                        img_url = img['thumb_2048_url']

                        retries = 3

                        while retries:
                            img_response = requests.get(img_url)

                            if img_response.status_code != 200:
                                retries -= 1
                                sleep(0.5)
                                continue

                            denumire = landmark['name'].replace('"', '').replace('/', '_').replace('\\', '_')

                            filename = f'{denumire}_mapillary_{i}.jpg'
                            filepath = os.path.join(output_dir, filename)

                            with open(filepath, 'wb') as f:
                                f.write(img_response.content)

                            csv_entries.append({
                                'IMG_FILE': filename,
                                'LAT': img['geometry']['coordinates'][1] if 'geometry' in img and 'coordinates' in img['geometry'] else landmark['lat'],
                                'LON': img['geometry']['coordinates'][0] if 'geometry' in img and 'coordinates' in img['geometry'] else landmark['lon']
                            })

                            break

                except Exception as e:
                    print(f"Eroare la descaracrea unei imagini pentru: {landmark['name']}")
                    continue
                                
        except Exception as e:
            print(f"Eroare la cautarea unei imaginilor pentru landmark: {landmark['name']} folosing mapillary api\nEroarea: {e}")
            return csv_entries

        return csv_entries
