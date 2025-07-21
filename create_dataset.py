from pandas import DataFrame, concat, read_csv
import os, psutil, json
from threading import Thread, Lock
from osm import get_city_based_landmarks
from gmaps_class import GoogleMaps_Interface
from mapillary_class import Mapillary_Interface
from copy import deepcopy
from streetView_class import StreetView


csv_df: DataFrame = DataFrame()
LOG_PATH = 'data_gathering.log'
# JSON_FILE_PATH = 'dataset_request_directview.json'
JSON_FILE_PATH = 'dataset_coords_meu.json'


def extend_csv_df(df: DataFrame, images_dir: str) -> None:
    """
    Extinde csv-ul global, csv_df, cu un DataFrame df
    """
    global csv_df
    df['IMG_FILE'] = df['IMG_FILE'].apply(lambda x: os.path.join(images_dir, x))
    csv_df = concat([csv_df, df], ignore_index=True)


def save_to_csv(df: DataFrame, path: str = 'landmarks.csv', increment_old_csv: bool = False) -> None:
    """
    Salveaza df ca csv la locatia path.
    Daca increment_old_csv e True, citeste csv-ul de la locatia path si il extinde cu df, dupa care il salveaza.
    """
    if increment_old_csv:
        old_csv = read_csv(path)
        old_csv = old_csv.append(df)
        old_csv.to_csv(path, index=False)
    else:
        df.to_csv(path, index=False)


def read_api_key(path: str) -> str | None:
    try:
        with open(path) as f:
            return f.read().strip()
    except Exception as e:
        print(f'Eroare la citirea unui API KEY: {path}\nEroarea: {e}')
        return None


def verifica_dir(path: str) -> None:
    if not os.path.exists(path) or not os.path.isdir(path):
        os.makedirs(path)


def get_landmarks() -> tuple[dict[str, list[dict[str, str | float]]], dict[str, list[dict[str, str | float]]], dict[str, list[dict[str, str | float]]]]:
    landmarks_gPlaces = get_city_based_landmarks()
    if len(landmarks_gPlaces) == 0:
        write_log('Eroare la obtinerea obiectivelor turistice de la Overpass_API!\n')
        exit(1)

    landmarks_mapillary = deepcopy(landmarks_gPlaces)
    landmarks_wiki = deepcopy(landmarks_gPlaces)
    return landmarks_gPlaces, landmarks_mapillary, landmarks_wiki


def verifica_landmarks_list(city_landmarks: dict[str, list[dict]]) -> dict[str, list[dict]] | None:
    if city_landmarks is not None and len(city_landmarks) != 0: return city_landmarks
    city_landmarks = get_city_based_landmarks()
    if city_landmarks is None or len(city_landmarks) == 0: return None
    return city_landmarks


def write_log(log_msg: str) -> None:
    with open(LOG_PATH, 'a') as f:
        f.write(log_msg + '\n')


def read_json(json_file_path: str) -> list:
    with open(json_file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        all_place_definitions = data.get('placedefinitions', [])
    return all_place_definitions


def main_places(city_landmarks: dict[str, list[dict]]) -> None:
    city_landmarks = verifica_landmarks_list(city_landmarks)
    if city_landmarks is None:
        write_log('Eroare la obtinerea oraselor si obiectivelor turistice de la Overpass_API!(in main_places)\n')
        exit(1)

    mutex_csv = Lock()
    mutex_orase = Lock()
    csv_entries: list[dict] = []

    GOOGLE_API_KEY = read_api_key('googleAPI_key.txt')
    if GOOGLE_API_KEY is None: exit(1)

    OUTPUT_DIR = 'imagini_places'
    verifica_dir(OUTPUT_DIR)

    num_cores = psutil.cpu_count()
    if not num_cores: num_cores = 4

    places_api = GoogleMaps_Interface(GOOGLE_API_KEY)

    def _thread_func(gmaps: GoogleMaps_Interface, output_dir: str, num_img: int = 3) -> None:
        local_csv_entries: list[dict] = []

        while True:
            with mutex_orase:
                if len(city_landmarks) == 0: break
                _, landmarks = city_landmarks.popitem()

            for landmark in landmarks:
                local_csv_entries.extend(gmaps.get_place_photos(
                    landmark=landmark,
                    output_dir=output_dir,
                    num_img=num_img
                ))

        with mutex_csv:
            csv_entries.extend(local_csv_entries)

    write_log('Incepe procesul de descarcare a imaginilor, pentru places api')

    threads = [Thread(target=_thread_func, args=(places_api, OUTPUT_DIR, 25)) for _ in range(num_cores)]
    for t in threads: t.start()
    for t in threads: t.join()

    df = DataFrame(csv_entries)
    save_to_csv(df, 'landmarks_places.csv')
    extend_csv_df(csv_df, OUTPUT_DIR)

    write_log('Done, places api!')


def main_places_2() -> None:
    place_definitions = read_json(JSON_FILE_PATH)
    if len(place_definitions) == 0:
        write_log("Eroare la citirea place_definitions\n")
        exit(1)

    GOOGLE_API_KEY = read_api_key('googleAPI_key.txt')
    if GOOGLE_API_KEY is None: exit(1)

    OUTPUT_DIR = 'imagini_places_json'
    verifica_dir(OUTPUT_DIR)

    places_api = GoogleMaps_Interface(GOOGLE_API_KEY)

    csv_entries: list[dict] = []

    for place in place_definitions:
        entry = places_api.get_place_imgs_from_json(place, OUTPUT_DIR, 50)
        csv_entries.extend(entry)
        if entry is not None: csv_entries.extend(entry)

    df = DataFrame(csv_entries)
    save_to_csv(df, 'landmarks_streetview_json.csv')
    # extend_csv_df(csv_df, OUTPUT_DIR)

    write_log('Done, palces api + json!')


def main_mapillary(city_landmarks: dict[str, list[dict]]) -> None:
    city_landmarks = verifica_landmarks_list(city_landmarks)
    if city_landmarks is None:
        write_log('Eroare la obtinerea oraselor si obiectivelor turistice de la Overpass_API!(in main_mapillary)\n')
        exit(1)

    mutex_csv = Lock()
    mutex_orase = Lock()
    csv_entries: list[dict] = []

    MAPILLARY_API_KEY = read_api_key('mapillary_token.txt')
    if MAPILLARY_API_KEY is None: exit(1)

    OUTPUT_DIR = 'imagini_streetview'
    verifica_dir(OUTPUT_DIR)

    num_cores = psutil.cpu_count()
    if num_cores is None: num_cores = 4

    mapillary_api = Mapillary_Interface(MAPILLARY_API_KEY)

    def _thread_func(mapi: Mapillary_Interface, output_dir: str, num_img: int = 3) -> None:
        local_csv_entries: list[dict] = []
        while True:
            with mutex_orase:
                if len(city_landmarks) == 0: break
                _, landmarks = city_landmarks.popitem()

                for landmark in landmarks:
                    result = mapi.get_place_imgs(
                        landmark,
                        output_dir,
                        num_img
                        )
                    if result is not None: local_csv_entries.extend(result)

        with mutex_csv:
            csv_entries.extend(local_csv_entries)

    write_log('Incepe procesul de descarcare a imaginilor, pentru mapillry api')

    threads = [Thread(target=_thread_func, args=(mapillary_api, OUTPUT_DIR, 50)) for _ in range(num_cores)]
    for t in threads: t.start()
    for t in threads: t.join()

    df = DataFrame(csv_entries)
    save_to_csv(df, 'landmarks_mapillary.csv')
    extend_csv_df(csv_df, OUTPUT_DIR)

    write_log('Done, mapillary api!')


def main_mapillary_2() -> None:
    MAPILLARY_API_KEY = read_api_key('mapillary_token.txt')
    if MAPILLARY_API_KEY is None: exit(1)

    OUTPUT_DIR = 'imagini_mapillary_json'
    verifica_dir(OUTPUT_DIR)

    mapillary_api = Mapillary_Interface(
        access_token=MAPILLARY_API_KEY,
        json_file=OUTPUT_DIR
    )

    csv_entries = mapillary_api.get_json_imgs(
        output_dir=OUTPUT_DIR,
        num_img=25
    )

    df = DataFrame(csv_entries)
    save_to_csv(df, 'landmarks_mapillary_json.csv')

    write_log('Done, mapillary api + json!')


def main_streetview() -> None:
    place_definitions = read_json(JSON_FILE_PATH)
    if len(place_definitions) == 0:
        write_log("Eroare la citirea place_definitions\n")
        exit(1)

    GOOGLE_API_KEY = read_api_key('googleAPI_key.txt')
    if GOOGLE_API_KEY is None: exit(1)

    OUTPUT_DIR = 'imagini_street_view_meu'
    verifica_dir(OUTPUT_DIR)

    streetview_api = StreetView(
        api_key=GOOGLE_API_KEY,
        fov=100,
        pitch=0,
        req_delay=1,
        img_size='1280x720',
        output_dir=OUTPUT_DIR,
        imgs_per_heading=10,
        num_offset_loc=20,
        offset_dist=10.0
    )

    csv_entries: list[dict] = []

    for place in place_definitions:
        entry = streetview_api.download_img_from_json(place)
        if entry is not None: csv_entries.extend(entry)

    df = DataFrame(csv_entries)
    save_to_csv(df, 'landmarks_streetview_meu.csv')
    # extend_csv_df(csv_df, OUTPUT_DIR)

    write_log('Done, street view api!')


if __name__ == '__main__':
    # places_landmarks, mapillary_landmarks, wiki_landmarks = get_landmarks()
    # places_landmarks = get_city_based_landmarks()
    # main_mapillary(places_landmarks)
    # save_to_csv(csv_df, 'landmarks.csv', True)
    main_streetview()
    main_mapillary_2()

    write_log(f'Done!\nNumarul de intrari in csv: {csv_df.shape[0]}\n')
