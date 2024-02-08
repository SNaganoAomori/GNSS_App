"""
投影変換のモジュールを纏めたpythonファイル
"""
from dataclasses import dataclass, asdict
from typing import List

import pyproj


@dataclass
class Coords:
    lon: float=None
    lat: float=None
    lons: List[float]=None
    lats: List[float]=None
    dict=asdict


def create_tramsformer(
    in_epsg: int, 
    out_epsg: int
) -> pyproj.Transformer:
    # 投影変換器の作成
    transformer = pyproj.Transformer.from_crs(
        f'epsg:{in_epsg}', f'epsg:{out_epsg}', always_xy=True
    )
    return transformer


def transformer_project(
    lon: float | List[float], 
    lat: float | List[float], 
    in_epsg: int=None, 
    out_epsg: int=None,
    transformer: pyproj.Transformer=None,
):
    """
    経緯度を投影変換して返す
    """
    if transformer is None:
        transformer = create_tramsformer(in_epsg, out_epsg)
    x, y = transformer.transform(lon, lat)
    if isinstance(x, float):
        return Coords(lon=x, lat=y)
    else:
        return Coords(lons=x, lats=y)
        


if __name__ == '__main__':
    lon = 39773.1479
    lat = 126992.7959
    print(transformer_project(lon, lat, 6678, 4326))
    lons = [39773.1479, 39773.147955]
    lats = [126992.7959, 126992.795955]
    print(transformer_project(lons, lats, 6678, 4326))