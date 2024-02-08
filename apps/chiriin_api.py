""""
国土地理院の提供しているAPIで情報を取得する為のモジュール
https://vldb.gsi.go.jp/sokuchi/surveycalc/api_help.html
地理院の用意しているAPIでは秒1回のリクエストに制限されている為
一度取得するたびに1秒休ませている
Example:
    セミダイナミック補正の方法
    地理院APIでは取得制限があるので秒一回の取得に制限を掛けています。
    from chiriin_api import semidynamic_exe
    # 測量結果の経度
    lon = 140.08785504166664 
    # 測量結果の緯度
    lat = 36.103774791666666 
    # 測量時の年度(yyyy/4/1 ~ yyyy+1/3/31)
    year = 2022
    print(semidynamic_exe())
    # 標高も国土地理院のAPIで取得
    >>> NewCoords(lon=140.087850903, lat=36.103776483, alti=24.9)

"""
from dataclasses import dataclass
import requests
import time

import numpy as np



def get_public_altitude(lon: float, lat: float) -> float:
    """国土地理院のAPIを用いて経緯度から標高を取得する。
    https://maps.gsi.go.jp/development/elevation_s.html
    Args:
        lon(flaot): 経度
        lat(float): 緯度
    Returns:
        alti(float): 標高
    """
    dummy = 'Mozilla/5.0 (Windows NT 6.1; Win64; x64; rv:47.0) Gecko/20100101 Firefox/47.0'
    url = 'https://cyberjapandata2.gsi.go.jp/general/dem/scripts/getelevation.php?'
    param = f'lon={lon}&lat={lat}&outtype=JSON'
    loop = True
    while loop:
        resps = requests.get(url + param, 
                             headers={'User-Agent': dummy},
                             timeout=10)
        resps = resps.json()
        if resps.get('ErrMsg') is None:
            print(url + param)
            return resps
        else:
            print('サーバーが混みあっています。')
            time.sleep(1)


class SemiDynamicCorrection(object):
    def __init__(self):
        """
        init:
            URL: セミダイナミック補正の指定URL
            OUTPUT_TYPE: json or xml
            SOCUCHI: 0 = [元期 -> 今期], 1 = [今期 -> 元期]
            PLACE: 0 = [経緯度], 1 = [平面直角座標系]
            HOSEI_J: 2 = [2次元補正], 3 = [3次元補正]
        """
        # 地理院セミダイナミック補正用URL
        self.URL = "http://vldb.gsi.go.jp/sokuchi/surveycalc/semidyna/web/semidyna_r.php?"
        self.SOKUCHI = 1 
        self.PLACE = 0
        self.HOSEI_J = 2

    def get_param_file_name(self, input_data_year):
        """セミダイナミック補正のパラメータファイル名を取得
        https://www.gsi.go.jp/sokuchikijun/semidyna_download.html
        """
        return f"SemiDyna{input_data_year}.par"
    
    def get_original_coordinate_json(self, lon, lat, input_data_year):
        url = self.URL
        url += f'outputType=json&'
        url += f'chiiki={self.get_param_file_name(input_data_year)}&'
        url += f'sokuchi={self.SOKUCHI}&'
        url += f'Place={self.PLACE}&'
        url += f'Hosei_J={self.HOSEI_J}&'
        url += f'latitude={lat}&'
        url += f'longitude={lon}&'
        url += f'altitude={0}'
        return requests.get(url, verify=False).json()
    

@dataclass
class NewCoor:
    lon: float
    lat: float


def semidynamic_exe(lon, lat, input_data_year) -> NewCoor:
    """
    国土地理院の用意しているAPIでセミダイナミック補正を行い \n
    経緯度を今期から元期に変換します
    Args:
        lon(float): 経度.
        lat(float): 緯度.
        input_data_year(int): 測量時の年度(yyyy/4/1 ~ yyyy+1/3/31)
    Returns:
        NewCoor(dataclass):
            lon(float): 補正後の経度
            lat(float): 補正後の緯度
    Example:
        セミダイナミック補正の方法 \n
        地理院APIでは取得制限があるので秒一回の取得に制限を掛けています。 \n
        >>> from chiriin_api import semidynamic_exe \n
        # 測量結果の経度 \n
        >>> lon = 140.08785504166664  \n
        # 測量結果の緯度 \n
        >>> lat = 36.103774791666666  \n
        # 測量時の年度(yyyy/4/1 ~ yyyy+1/3/31) \n
        >>> year = 2022 \n
        >>> print(semidynamic_exe(lon, lat, year)) \n
        NewCoords(lon=140.087850903, lat=36.103776483) \n
    """
    semidyna = SemiDynamicCorrection()
    roop = True
    while roop:
        resps = semidyna.get_original_coordinate_json(lon, lat, input_data_year)
        if resps.get('ErrMsg') == None:
            data = resps.get('OutputData')
            new_lon = float(data.get('longitude'))
            new_lat = float(data.get('latitude'))
            print(f"""#################################################################
            INPUT  = lon: {lon}, lat: {lat}
            RESULT = lon: {new_lon}, lat: {new_lat}
            DIFF   = lon: {new_lon - lon}, lat: {new_lat - lat}""")
            roop = False
        else:
            print('サーバーが混雑しています。')
            time.sleep(2)
        time.sleep(1)
        if roop == False:
            return NewCoor(lon=new_lon, lat=new_lat)
    else:
        err = -9999
        return NewCoor(lon=err, lat=err)






if __name__ == '__main__':
    lat = 41.142745499
    lon = 141.307135647
    semidynamic_exe(lon, lat, 2023)
