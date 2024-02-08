from typing import Any
from typing import List
from typing import Tuple

import shapely


class GeomDisassembly(object):
    def type_checker(self, geom: Any):
        geom_id = shapely.get_type_id(geom)
        if geom_id == 0:
            return 'point'
        elif geom_id == 1:
            return 'linestring'
        elif geom_id == 3:
            return 'poly'
        elif geom_id == 4:
            return 'multi_point'
        elif geom_id == 5:
            return 'multi_linestring'
        elif geom_id == 6:
            return 'multi_poly'
        else:
            return None

    def pt_to_xyz(
        self, 
        point: shapely.geometry.Point
    ) -> Tuple[float, float]:
        return (point.x, point.y)
    
    def multi_pt_to_xyz(
        self, 
        geom: shapely.geometry.MultiPoint
    ) -> Tuple[Tuple[float, float]]:
        geo_dict = geom.__geo_interface__
        return geo_dict.get('coordinates')
    
    def multi_pt_to_points(
        self, 
        geom: shapely.geometry.MultiPoint
    ) -> List[shapely.geometry.Point]:
        return list(shapely.get_parts(geom))
    
    def line_to_xyz(
        self,
        geom: shapely.geometry.LineString
    ) -> List[Tuple[float, float]]:
        return list(geom.coords)
    
    def line_to_points(
        self,
        geom: shapely.geometry.LineString
    ) -> List[shapely.geometry.Point]:
        lst = []
        count = shapely.get_num_points(geom)
        for i in range(count):
            pt = shapely.get_point(geom, i)
            lst.append(pt)
        return lst
    
    def multi_line_to_xyzs(
        self,
        geom: shapely.geometry.MultiLineString
    ) -> List[List[Tuple[float, float]]]:
        lst = []
        for line in shapely.get_parts(geom):
            coords = list(line.coords)
            lst.append(coords)
        return lst
    
    def multi_line_to_points(
        self,
        geom: shapely.geometry.MultiLineString
    ) -> List[List[shapely.geometry.Point]]:
        lst = []
        for line in shapely.get_parts(geom):
            points = []
            count = shapely.get_num_points(line)
            for i in range(count):
                pt = shapely.get_point(line, i)
                points.append(pt)
            lst.append(points)
        return lst

    def poly_to_xyz(
        self,
        geom: shapely.geometry.Polygon
    ) -> List[Tuple[float, float]]:
        return list(geom.exterior.coords)
    
    def poly_to_points(
        self,
        geom: shapely.geometry.Polygon
    ) -> List[shapely.geometry.Point]:
        lst = []
        line = geom.exterior
        count = shapely.get_num_points(line)
        for i in range(count):
            pt = shapely.get_point(line, i)
            lst.append(pt)
        return lst

    def multi_poly_to_xyzs(
        self,
        geom: shapely.geometry.MultiPolygon
    ) -> List[List[Tuple[float, float]]]:
        lst = []
        for poly in shapely.get_parts(geom):
            coords = list(poly.exterior.coords)
            lst.append(coords)
        return lst

    def multi_poly_to_points(
        self,
        geom: shapely.geometry.MultiPolygon
    ) -> List[List[shapely.geometry.Point]]:
        lst = []
        for poly in shapely.get_parts(geom):
            points = []
            line = poly.exterior
            count = shapely.get_num_points(line)
            for i in range(count):
                pt = shapely.get_point(line, i)
                points.append(pt)
            lst.append(points)
        return lst

    def _points_to_x_y_z(
        self, 
        points: List[shapely.geometry.Point]
    ) -> List[List[float]]:
        xs = [c.x for c in points]
        ys = [c.y for c in points]
        zs = []
        for p in points:
            if shapely.has_z(p):
                zs.append(p.z)
            else:
                zs.append(None)
        return [xs, ys, zs]
    
    def _point_lst_to_x_y_z(
        self,
        point_lst: List[List[shapely.geometry.Point]]
    ) -> List[List[float]]:
        xs = []
        ys = []
        zs = []
        for points in point_lst:
            _xs, _ys, _zs = self._points_to_x_y_z(points)
            xs += _xs
            ys += _ys
            zs += _zs
        return [xs, ys, zs]
    

def _point_to(geom: Any, resps: str):
    disassembly = GeomDisassembly()
    if resps == 'point':
        return geom
    else:
        return disassembly.pt_to_xyz(geom)

def _multi_point_to(geom: Any, resps: str):
    disassembly = GeomDisassembly()
    if resps == 'point':
        return disassembly.multi_pt_to_points(geom)
    elif resps == 'xyz':
        return disassembly.multi_pt_to_xyz(geom)
    else:
        points = disassembly.multi_pt_to_points(geom)
        return disassembly._points_to_x_y_z(points)

def _line_to(geom: Any, resps: str):
    disassembly = GeomDisassembly()
    if resps == 'point':
        return disassembly.line_to_points(geom)
    elif resps == 'xyz':
        return disassembly.line_to_xyz(geom)
    else:
        points = disassembly.line_to_points(geom)
        return disassembly._points_to_x_y_z(points)

def _multi_line_to(geom: Any, resps: str):
    disassembly = GeomDisassembly()
    if resps == 'point':
        return disassembly.multi_line_to_points(geom)
    elif resps == 'xyz':
        return disassembly.multi_line_to_xyzs(geom)
    else:
        points = disassembly.multi_line_to_points(geom)
        return disassembly._point_lst_to_x_y_z(points)

def _poly_to(geom: Any, resps: str):
    disassembly = GeomDisassembly()
    if resps == 'point':
        return disassembly.poly_to_points(geom)
    elif resps == 'xyz':
        return disassembly.poly_to_xyz(geom)
    else:
        points = disassembly.poly_to_points(geom)
        return disassembly._points_to_x_y_z(points)

def _multi_poly_to(geom: Any, resps: str):
    disassembly = GeomDisassembly()
    if resps == 'point':
        return disassembly.multi_poly_to_points(geom)
    elif resps == 'xyz':
        return disassembly.multi_poly_to_xyzs(geom)
    else:
        points = disassembly.multi_poly_to_points(geom)
        return disassembly._point_lst_to_x_y_z(points)
    

def geom_disassembly(geom: Any, resps: str='point'):
    """
    Args:
        geom(Any): shapelyのgeometryオブジェクト
        response(str): 'point' | 'xyz' | 'x_y_z'
    returns:
        Any
    """
    disassembly = GeomDisassembly()
    t = disassembly.type_checker(geom)
    if t == 'point':
        return _point_to(geom, resps)
    elif t == 'multi_point':
        return _multi_point_to(geom, resps)
    elif t == 'linestring':
        return _line_to(geom, resps)
    elif t == 'multi_linestring':
        return _multi_line_to(geom, resps)
    elif t == 'poly':
        return _poly_to(geom, resps)
    elif t == 'multi_poly':
        return _multi_poly_to(geom, resps)
    else:
        return None