import requests
from threading import Thread, Lock
from time import sleep


OVERPASS_URL = 'http://overpass-api.de/api/interpreter'


def __get_osm_city_data(city: str) -> list[dict[str, str | float]]:
    """
    Functie ajutatoare pentru a obtine date despre obiectivele turistice dintr-un oras
    """

    overpass_query = f"""
    [out:json];
    area["name"="{city}"]->.searchArea;
    (
      way["historic"="monument"](area.searchArea);
      way["building"="church"](area.searchArea);
      way["government"](area.searchArea);
      way["tourism"="museum"](area.searchArea);
      way["amenity"="theatre"](area.searchArea);
      way["tourism"="attraction"](area.searchArea);

  	  node["historic"="monument"](area.searchArea);
      node["building"="church"](area.searchArea);
      node["government"](area.searchArea);
      node["tourism"="museum"](area.searchArea);
      node["amenity"="theatre"](area.searchArea);
      node["tourism"="attraction"](area.searchArea);
    );
    out body;
    >;
    out skel qt;
    """
    
    landmarks: list[dict[str, str | float]] = []
    retries = 3

    while retries:
        try:
            response = requests.post(OVERPASS_URL, data={'data': overpass_query})

            if response.status_code != 200:
                retries -= 1
                sleep(0.5)
                continue
            
            data = response.json()

            for element in data['elements']:
                if 'lat' in element and 'lon' in element:
                    landmark = {
                        'name': element.get('tags', {}).get('name', 'Unknown'),
                        'type': element.get('tags', {}).get('historic') or 
                            element.get('tags', {}).get('tourism') or 
                            element.get('tags', {}).get('amenity'),
                        'lat': element['lat'],
                        'lon': element['lon']
                    }

                    landmarks.append(landmark)

            break

        except Exception as e:
            print(f"Eroare pentru obtinerea datelor despre orasul: {city}\nEroarea: {e}")

    landmarks.sort(key=lambda x: x['name'] == 'Unknown')

    return landmarks


def __read_orase(filename: str = 'orase.txt') -> list[str]:
    try:
        with open(filename, encoding='utf-8') as f_orase:
            orase = f_orase.readlines()
            orase = [oras.strip() for oras in orase]

    except Exception as e:
        print(f"Error reading orase.txt: {e}")
        return []

    return orase


def get_osm_data() -> list[dict[str, str | float]]:
    """
    Returneaza o lista cu obiectivele turistice/punctele cheie pentru orasele citite din fisierul orase.txt

    Forma:
    [
        {
            'name': 'Nume obiectiv',
            'type': 'Tip obiectiv',
            'lat': 12.3456,
            'lon': 12.3456
        }
    ]
    """
    
    orase = __read_orase()
    mutex_orase = Lock()
    mutex_landmarks = Lock()
    landmarks: list[dict[str, str|float]] = []


    def __thread_func() -> None:
        local_landmarks: list[dict[str, str|float]] = []

        while True:
            with mutex_orase:
                if len(orase) == 0:
                    break
                oras = orase.pop()
            
            local_landmarks.extend(__get_osm_city_data(oras)[:3])
            # local_landmarks.extend(__get_osm_city_data(oras))
            sleep(0.25)

        with mutex_landmarks:
            landmarks.extend(local_landmarks)


    threads = [Thread(target=__thread_func) for _ in range(2)]
    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join()

    return landmarks

def get_city_based_landmarks() -> dict[str, list[dict[str, str | float]]]:
    """
    Returneaza un dictionar care contine ca cheie numele unui oras, iar ca valoare o lista cu informatii despre punctele cheie/obiectivele turistice

    { nume_oras : [{
        'name': 'Nume obiectiv',
        'type': 'Tip obiectiv',
        'lat': 12.3456,
        'lon': 12.3456
    }, {}...], ...}
    """

    orase = __read_orase()
    mutex_orase = Lock()
    mutex_landmarks = Lock()
    city_landmarks: dict[str, list[dict[str, str | float]]] = {}


    def _thread_func() -> None:
        while True:
            with mutex_orase:
                if len(orase) == 0:
                    break

                oras = orase.pop()
            
            landmarks = __get_osm_city_data(oras)[:15]

            with mutex_landmarks:
                city_landmarks[oras] = landmarks


    threads = [Thread(target=_thread_func) for _ in range(2)]
    for t in threads:
        t.start()

    for t in threads:
        t.join()

    return city_landmarks


if __name__ == '__main__':
    lm = get_city_based_landmarks()

    key, v = lm.popitem()

    print(key)
    for i in v:
        print(i)
