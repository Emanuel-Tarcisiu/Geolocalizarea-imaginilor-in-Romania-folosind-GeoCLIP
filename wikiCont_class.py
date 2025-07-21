import requests
import os
import time


class WikiCont_Interface:

    def __init__(self) -> None:
        self.__url = 'https://commons.wikimedia.org/w/api.php'
        self.__headers = { 'User-Agent': 'LandmarkDatasetCreator/1.0 (orsanemanuel@yahoo.com; Educational Project)' }


    def __get_images_info(self, landmark: str, num_img: int = 5) -> list | None:
        params = {
            'action': 'query',
            'list': 'search',
            'srsearch': landmark,
            'srnamespace': 6,
            'srlimit': num_img,
            'format': 'json'
        }

        try:
            response = requests.get(
                self.__url,
                params=params,
                headers=self.__headers
            )
            data = response.json()

            imgs = []
            if 'query' in data and 'search' in data['query']:
                for item in data['query']['search']:
                    imgs.append(item['title'])
        
            return imgs
        
        except Exception as e:
            print(f'Eroare la obtinerea imaginilor pentru landmark-ul: {landmark}')
            return None


    def __get_img_url(self, img_name: str):
        params = {
            'action': 'query',
            'titles': img_name,
            'prop': 'imageinfo',
            'iiprop': 'url|size|extmetadata',
            'format': 'json'
        }

        try:
            response = requests.get(
                self.__url,
                params=params,
                headers=self.__headers
            )
            data = response.json()

            pages = data.get('query', {}).get('pages', {})
            for page_id in pages:
                page = pages[page_id]
                if 'imageinfo' in page and len(page['imageinfo']) > 0:
                    return page['imageinfo'][0]['url']
                
            return None
        
        except Exception as e:
            print(f'Eroare la obtinerea URL-ului pentru imaginea: {img_name}')
            return None
        

    def __download_img(self, img_url: str, output: str) -> bool:
        try:
            response = requests.get(
                img_url,
                stream=True,
                headers=self.__headers
            )
            
            if response.status_code == 200:
                with open(output, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                return True
            
            else:
                print(f'Eroarea HTTP: {response.status_code}')
                return False
            
        except Exception as e:
            print(f'Eroare la descarcarea imgainii: {output}\nEroarea: {e}')
            return False
        

    def get_place_photos(self, landmark: dict[str, str | float], output_dir: str, num_img: int = 3) -> list[dict]:
        csv_entries: list[dict] = []

        try:
            img_names = self.__get_images_info(landmark['name'], num_img)

            if img_names is None or len(img_names) == 0:
                print(f'NU au fost gasite imagini pentru landmark-ul: {landmark["name"]}')
                return []

            for i, img_name in enumerate(img_names):
                img_url = self.__get_img_url(img_name)
                
                if img_url is None:
                    continue
                
                if '"' in landmark['name']:
                    clean_name = landmark['name'].replace('"', '')
                else:
                    clean_name = landmark['name']

                filename = f"{clean_name}_{i}.jpg"
                path = os.path.join(output_dir, filename)

                if self.__download_img(img_url, path):
                    csv_entries.append({
                        'IMG_FILE': filename,
                        'LAT': landmark['lat'],
                        'LON': landmark['lon']
                    })
                
                time.sleep(0.5)

        except Exception as e:
            print(f'Eroare la cautarea unei imagini pentru landmark: {landmark['name']} folosind wiki api\nEroarea: {e}')
            return []
        
        return csv_entries