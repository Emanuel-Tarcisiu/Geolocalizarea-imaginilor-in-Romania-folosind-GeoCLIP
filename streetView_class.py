import os, math, requests, time


def _clean_name(name: str) -> str:
    name = name.replace('"', '').replace('/', '_').replace('\\', '_').replace(' ', '_')
    return "".join(c for c in name if c.isalnum() or c in ('_', '-')).strip()


def _calc_heading(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)

    delta_lon = lon2_rad - lon1_rad

    y = math.sin(delta_lon) * math.cos(lat2_rad)
    x = math.cos(lat1_rad) * math.sin(lat2_rad) - math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(delta_lon)

    initial_bearing = math.atan2(y, x)
    initial_bearing_deg = math.degrees(initial_bearing)
    
    return (initial_bearing_deg + 360) % 360


def _calc_offset_coord(lat: float, lon: float, distance_m: float, bearing_deg: float) -> tuple[float, float]:
    R_earth_m = 6378137.0

    lat_rad = math.radians(lat)
    lon_rad = math.radians(lon)
    bearing_rad = math.radians(bearing_deg)

    angular_distance = distance_m / R_earth_m

    new_lat_rad = math.asin(math.sin(lat_rad) * math.cos(angular_distance) + math.cos(lat_rad) * math.sin(angular_distance) * math.cos(bearing_rad))
    new_lon_rad = lon_rad + math.atan2(math.sin(bearing_rad) * math.sin(angular_distance) * math.cos(lat_rad), math.cos(angular_distance) - math.sin(lat_rad) * math.sin(new_lat_rad))

    return math.degrees(new_lat_rad), math.degrees(new_lon_rad)


class StreetView:

    def __init__(self, api_key: str, fov: int = 90, pitch: int = 0, req_delay: int =1, img_size: str = '640x480', output_dir: str = 'imagini', imgs_per_heading: int = 4, num_offset_loc: int = 4, offset_dist: float = 15.0) -> None:
        self._api_key = api_key
        self._fov = fov
        self._pitch = pitch
        self._request_delay_sec = req_delay
        self._img_size = img_size
        self._output_dir = output_dir
        self._base_url = 'https://maps.googleapis.com/maps/api/streetview'
        self._num_headings_at_location = imgs_per_heading
        self._num_offset_locations = num_offset_loc
        self._offset_distance_m = offset_dist
        os.makedirs(self._output_dir, exist_ok=True)


    def _make_img_path(self, lm_name: str, img_id: str) -> str:
        filename = f"{lm_name}_{img_id}.jpg"
        return os.path.join(self._output_dir, filename)


    def _download_single_image(self, landmark_name_original: str, landmark_clean_name: str, photo_location_lat: float, photo_location_lon: float, image_identifier: str, heading: float | None = None, target_lat: float | None = None, target_lon: float | None = None) -> dict | None:
        params = {
            'size': self._img_size,
            'location': f"{photo_location_lat},{photo_location_lon}",
            'fov': self._fov,
            'pitch': self._pitch,
            'key': self._api_key,
            'source': 'outdoor',
            'return_error_code': 'true'
        }

        if heading is not None:
            params['heading'] = round(heading, 2)

        filepath = self._make_img_path(landmark_clean_name, image_identifier)

        try:
            response = requests.get(self._base_url, params=params, stream=True)
            time.sleep(self._request_delay_sec)

            if response.status_code == 200:
                content_type = response.headers.get('Content-Type', '')
                if 'image/jpeg' in content_type:
                    with open(filepath, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            f.write(chunk)
                    return {
                                'IMG_FILE': filepath,
                                'LAT': photo_location_lat if photo_location_lat else target_lat,
                                'LON': photo_location_lon if photo_location_lon else target_lon
                            }
                else:
                    resp_cont_sample = response.content[:500].decode('utf-8', errors='ignore')
                    if "ZERO_RESULTS" in resp_cont_sample or "Sorry, we have no imagery here" in resp_cont_sample or "No Street View imagery found" in resp_cont_sample:
                        print(f"INFO: Nicio imagine Street View la {photo_location_lat},{photo_location_lon} pentru '{landmark_name_original}'. Raspuns: {resp_cont_sample}")
                        return None
                    else:
                        print(f"EROARE: Status 200 pentru '{landmark_name_original}', dar continutul nu este imagine JPEG. Raspuns: {resp_cont_sample}")
                        return None

            elif response.status_code == 403:
                error_details = response.text
                print(f"EROARE 403 (Forbidden) pentru '{landmark_name_original}'. Verificati API key/billing. Detalii: {error_details}")
                return None
            elif response.status_code == 400 and "ZERO_RESULTS" in response.text:
                print(f"INFO: Nicio imagine (ZERO_RESULTS) la {photo_location_lat},{photo_location_lon} pentru '{landmark_name_original}'.")
                return None
            else:
                error_details = response.text
                print(f"EROARE API ({response.status_code}) pentru '{landmark_name_original}'. Detalii: {error_details}")
                return None

        except requests.exceptions.RequestException as e:
            print(f"EROARE DE RETEA la descarcarea pentru '{landmark_name_original}': {e}")
            return None
        except Exception as e:
            print(f"EROARE NEASTEPTATA la descarcarea pentru '{landmark_name_original}': {e}")
            return None


    def download_img_from_json(self, place_definition: dict) -> list[dict] | None:
        """
        Descarca o imagine pentru un singur obiectiv, dintr-un punct fix, pentru un landmark definit in place_definition, din json.
        """
        place_name_original = place_definition.get('name', f"place_id_{place_definition.get('place_id', 'unknown')}")
        place_name_clean = _clean_name(place_name_original)

        google_coords = place_definition.get('google_coords', [])
        google_center = place_definition.get('google_center')

        if not google_coords:
            print(f"EROARE: NU s-au gasit google_coods pentru: '{place_name_original}'")
            return None

        if not google_center or 'lat' not in google_center or 'long' not in google_center:
            print(f"EROARE: NU au fost gasite atributele lat, long pentru: '{place_name_original}'")
            return None

        target_lat = google_center['lat']
        target_lon = google_center['long']

        csv_entries_for_place: list[dict] = []

        for coord_info in google_coords:
            photo_lat = coord_info.get('lat')
            photo_lon = coord_info.get('long')
            coord_id = coord_info.get('id_coord', 'unk_coord')

            if photo_lat is None or photo_lon is None:
                print(f"EROARE: Coordonate invalide pentru id_coord: '{coord_info}', pentru: '{place_name_original}'")
                continue

            current_heading = _calc_heading(photo_lat, photo_lon, target_lat, target_lon)
            image_identifier = f"coord_{coord_id}_h{int(current_heading)}"

            entry = self._download_single_image(
                landmark_name_original=place_name_original,
                landmark_clean_name=place_name_clean,
                photo_location_lat=photo_lat,
                photo_location_lon=photo_lon,
                image_identifier=image_identifier,
                heading=current_heading,
                target_lat=target_lat,
                target_lon=target_lon
            )

            if entry is not None: csv_entries_for_place.append(entry)

        return csv_entries_for_place


    def download_images_for_landmark(self, landmark_data: dict[str, str | float]) -> list[dict]:
        """
        Descarca mai multe imagini in functie de heading si offset, pentru un landmark, in format obtinut de la Overpass API.
        """
        lm_nume = str(landmark_data['name'])
        lm_lat = float(landmark_data['lat'])
        lm_lon = float(landmark_data['lon'])
        lm_nume_curatat = _clean_name(lm_nume)

        csv_entries: list[dict] = []

        if self._num_headings_at_location > 0:
            headings = [i * (360.0 / self._num_headings_at_location) for i in range(self._num_headings_at_location)]
            for i, heading_val in enumerate(headings):
                identifier = f"loc_h{int(heading_val)}"
                entry = self._download_single_image(
                    landmark_name_original=lm_nume,
                    landmark_clean_name=lm_nume_curatat,
                    photo_location_lat=lm_lat,
                    photo_location_lon=lm_lon,
                    image_identifier=identifier,
                    heading=heading_val
                )
                if entry is not None: csv_entries.append(entry)

        if self._num_offset_locations > 0 and self._offset_distance_m > 0:
            offset_bearings = [i * (360.0 / self._num_offset_locations) for i in range(self._num_offset_locations)]

            for i, bearing_val in enumerate(offset_bearings):
                img_lat, img_lon = _calc_offset_coord(
                    lat=lm_lat,
                    lon=lm_lon,
                    distance_m=self._offset_distance_m,
                    bearing_deg=bearing_val
                )

                heading_to_lm = _calc_heading(
                    lat1=img_lat,
                    lon1=img_lon,
                    lat2=lm_lat,
                    lon2=lm_lon
                )
                
                identifier = f"offset_b{int(bearing_val)}_ht{int(heading_to_lm)}"
                entry = self._download_single_image(
                    landmark_name_original=lm_nume,
                    landmark_clean_name=lm_nume_curatat,
                    photo_location_lat=img_lat,
                    photo_location_lon=img_lon,
                    image_identifier=identifier,
                    heading=heading_to_lm,
                    target_lat=lm_lat,
                    target_lon=lm_lon
                )
                if entry is not None: csv_entries.append(entry)

        return csv_entries
