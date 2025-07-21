import os
import time
import googlemaps


def _clean_name(name: str) -> str:
    name = name.replace('"', '').replace('/', '_').replace('\\', '_').replace(' ', '_')
    return "".join(c for c in name if c.isalnum() or c in ('_', '-')).strip()


class GoogleMaps_Interface:

    def __init__(self, api_key: str) -> None:
        self.__client = googlemaps.Client(key=api_key)


    def get_place_photos(self, landmark: dict[str, str | float], output_dir: str, num_img: int = 3) -> list[dict]:
        """ 
        Cauta si descarca imagini cu un landmark folosind Google Places API.
        Returneaza o lista cu intrari pentru csv:
        {
            'IMG_FILE': filename,
            'LAT': landmark['lat'],
            'LON': landmark['lon']
        }
        """

        try:
            csv_entries: list[dict] = []

            location = (landmark['lat'], landmark['lon'])
            places_result = self.__client.places_nearby(
                location=location,
                radius=100,
                keyword=landmark['name']
            )
            
            if places_result.get('results'):
                place = places_result['results'][0]
                place_details = self.__client.place(place['place_id'], fields=['photo'])

                if 'photos' in place_details['result']:
                    imgs = place_details['result']['photos'][:num_img]

                    for i, img in enumerate(imgs):
                        try:
                            img_ref = img['photo_reference']

                            img_data = self.__client.places_photo(
                                photo_reference=img_ref,
                                max_width=1600
                            )
                            
                            if '"' in landmark['name']:
                                landmark['name'] = landmark['name'].replace('"', '')

                            filename = f"{landmark['name']}_{i}.jpg"
                            path = os.path.join(output_dir, filename)

                            self.__save_img(img_data, path)

                            csv_entries.append({
                                'IMG_FILE': filename,
                                'LAT': landmark['lat'],
                                'LON': landmark['lon']
                            })

                            time.sleep(0.5)

                        except Exception as e:
                            print(f"Eroare la descarcarea imaginii: {landmark['name']}\nEroarea: {e}\n")
                            continue
                        
        except Exception as e:
            print(f"Eroare la cautarea unei imaginilor pentru landmark: {landmark['name']} folosing google places api\nEroarea: {e}")
            return []
        
        return csv_entries

    def get_place_imgs_from_json(self, place_definition: dict,  output_dir: str, num_img: int = 10) -> list[dict] | None:
        place_name_original = place_definition.get('name', f"place_id_{place_definition.get('place_id', 'unknown')}")
        place_name_clean = _clean_name(place_name_original)
        google_center = place_definition.get('google_center')

        if not google_center or 'lat' not in google_center or 'long' not in google_center:
            print(f"EROARE: NU au fost gasite atributele lat, long pentru: '{place_name_original}'")
            return None

        try:
            csv_entries: list[dict] = []

            latitude = google_center['lat']
            longitude = google_center['long']

            location = (latitude, longitude)
            places_result = self.__client.places_nearby(
                location=location,
                radius=100,
                keyword=place_name_clean
            )

            if places_result.get('results'):
                place = places_result['results'][0]
                place_details = self.__client.place(place['place_id'], fields=['photo'])

                if 'photos' in place_details['result']:
                    imgs = place_details['result']['photos'][:num_img]

                    for i, img in enumerate(imgs):
                        try:
                            img_ref = img['photo_reference']

                            img_data = self.__client.places_photo(
                                photo_reference=img_ref,
                                max_width=1600
                            )

                            filename = f"{place_name_clean}_{i}.jpg"
                            path = os.path.join(output_dir, filename)

                            self.__save_img(img_data, path)

                            csv_entries.append({
                                'IMG_FILE': filename,
                                'LAT': latitude,
                                'LON': longitude
                            })

                            time.sleep(0.5)

                        except Exception as e:
                            print(f"Eroare la descarcarea imaginii: {place_name_clean}\nEroarea: {e}\n")
                            continue

        except Exception as e:
            print(f"Eroare la cautarea unei imaginilor pentru landmark: {place_name_original} folosing google places api\nEroarea: {e}")
            return None

        return csv_entries


    def __save_img(self, img_data: bytes, path: str) -> None:
        with open(path, 'wb') as f:
            for chunk in img_data:
                if chunk:
                    f.write(chunk)
