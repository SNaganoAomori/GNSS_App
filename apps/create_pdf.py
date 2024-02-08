import copy
from dataclasses import asdict
from dataclasses import dataclass
import datetime
import io
import math
from PIL import Image
from PIL import ImageColor
import re
from typing import Any
from typing import Dict
from typing import List
import unicodedata

import geopandas as gpd
import japanize_matplotlib
from matplotlib import pyplot as plt
import numpy as np
import pandas as pd
import shapely
from shapely.plotting import plot_polygon
import streamlit as st
from streamlit.runtime.uploaded_file_manager import UploadedFile
from streamlit.delta_generator import DeltaGenerator

from apps.disassembly import geom_disassembly
from apps.documents import Summary
from apps.exception import format_checker
from apps.exception import confirmation_existence_points
from apps.exception import confirmation_existence_poly
from apps.exception import count_poly_in_gdf
from apps.exception import vertex_matching
from apps.settings.configs import check_lang_jn_in_df
from apps.settings.configs import rename_en_to_jn_in_df
from apps.settings.configs import JnDataCols
from apps.sidebar import survey_area_confs
from apps.geometries import select_geom_rows
summary = Summary()



def uploder_row() -> List[UploadedFile]:
    st.markdown('<br>', True)
    st.markdown('### GeoJSONデータの読み込み')
    st.markdown('<hr style="margin: 0px; border: 3px solid #008899">', True)
    expander = st.expander('GeoJSONファイルを入力する', True)
    expander = summary.show_input_geoj1(expander)
    files = expander.file_uploader(
        label='ドラッグ&ドロップでも入ります。', 
        accept_multiple_files=True,
        help='GeoJSONのデータしか入力できません。',
        key='file_uploader' 
    )
    format_checker('.geojson', files)
    return files


class GeoDataFrames(object):
    def __init__(self, files: List[UploadedFile]):
        self._files = files
        if 1 < len(files):
            gdf = pd.concat([gpd.read_file(file) for file in files])
        else:
            gdf = gpd.read_file(files[0])
        points, poly = self.check_geoms(gdf)
        points, poly = self.rename(points), self.rename(poly)
        self.points: gpd.GeoDataFrame = points.dropna(how='all', axis=1)
        self.poly: gpd.GeoDataFrame = poly.dropna(how='all', axis=1)

    def check_geoms(self, gdf) -> List[gpd.GeoDataFrame]:
        poly_gdf = select_geom_rows(gdf)
        points_gdf = select_geom_rows(gdf, False)
        a = count_poly_in_gdf(poly_gdf)
        b = confirmation_existence_poly(poly_gdf)
        c = confirmation_existence_points(points_gdf)
        if a & b & c:
            poly = poly_gdf.geometry.iloc[0]
            points = points_gdf.geometry.to_list()
            match = vertex_matching(poly, points)
        return points_gdf, poly_gdf

    def rename(self, gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        # 列名を日本語にする
        if check_lang_jn_in_df == False:
            gdf = rename_en_to_jn_in_df(gdf)
        return gdf



def read_file(files: List[UploadedFile]) -> GeoDataFrames:
    return GeoDataFrames(files)


def select_epsg_row():
    st.markdown('<br>', True)
    st.markdown('### 平面直角座標系の選択')
    st.markdown('<hr style="margin: 0px; border: 3px solid #008899">', True)
    expander = st.expander('必ず選択して下さい', True)
    expander.markdown("""
        図面を正しい形で描画する為に、平面直角座標系を指定します。
        地域を選択すればEPSGが勝手に変わります。"""
    )
    response = survey_area_confs(2, expander)
    return response.get('epsg')
    

def localize_crs(geo_dfs: GeoDataFrames, epsg: int) -> GeoDataFrames:
    # 投影変換
    if geo_dfs.points.crs.to_epsg() != epsg:
        geo_dfs.points = geo_dfs.points.to_crs(crs=f'EPSG:{epsg}')
    if geo_dfs.poly.crs.to_epsg() != epsg:
        geo_dfs.poly = geo_dfs.poly.to_crs(crs=f'EPSG:{epsg}')
    return geo_dfs


class PdfSize(object):
    """
    PDFを印刷する為にmatplotlibのFigureオブジェクトのSizeを設定する
    """
    def _calc_size(self, w: float, h: float):
        inches_per_cm = 1 / 2.54
        fig_width = w * inches_per_cm
        fig_height = h * inches_per_cm
        return [fig_width, fig_height]

    @property
    def portrait_a4_size(self, cm_w: float=21.0, cm_h: float=29.7) -> List[float]:
        return self._calc_size(cm_w, cm_h)
    
    @property
    def landscape_a4_size(self, cm_w: float=29.7, cm_h: float=21.0) -> List[float]:
        return self._calc_size(cm_w, cm_h)
    
    @property
    def portrait_a3_size(self, cm_w: float=29.7, cm_h: float=42.0) -> List[float]:
        return self._calc_size(cm_w, cm_h)

    @property
    def landscape_a3_size(self, cm_w: float=42.0, cm_h: float=29.7) -> List[float]:
        return self._calc_size(cm_w, cm_h)



class Title(object):
    def __init__(self, gdf: gpd.GeoDataFrame):
        jn_confs = JnDataCols()
        self.office = gdf[jn_confs.office_col][0]
        self.local_area = gdf[jn_confs.lcoal_area_col][0]
        self.address = gdf[jn_confs.address_col][0]
        self.big_addrs, self.small_addrs = self._split_address(self.address)
        self.jn_year = None
        self.title_font_size = 14
    
    def _update(self):
        expander = st.expander('タイトル設定')
        self.office = expander.text_input('森林管理署名', value=self.office)
        self.local_area = expander.text_input('国有林名', value=self.local_area)
        self.big_addrs = expander.text_input('林班', self.big_addrs)
        self.small_addrs = expander.text_input('小班', self.small_addrs)
        if expander.toggle('収穫予定年度の追加', True):
            y = datetime.datetime.now().year - 2017
            self.jn_year = expander.number_input('収穫予定年度（令和）', value=y)
        self.title_font_size = expander.number_input('フォントサイズ', 6, 17, 14)
        self.title_coords_txt = self._ttc_jn_to_en(expander)
        
    def _split_address(self, address: str) -> List[str]:
        pattern = r'[あ-ん]' 
        jn = ''
        for _jn in re.findall(pattern, address):
            jn += _jn
        lst = re.split(pattern, address)
        big_addr = lst[0]
        small_addr = jn + lst[-1]
        if big_addr == small_addr:
            return [big_addr, '']
        return [big_addr, small_addr]

    def create_title_sentence(self) -> str:
        fmt = 'NFKC'
        title = f"{unicodedata.normalize(fmt, self.office)} 森林管理署"
        title += f"\n{unicodedata.normalize(fmt, self.local_area)} 国有林  "
        title += f"{unicodedata.normalize(fmt, self.big_addrs)} 林班 "
        title += f"{unicodedata.normalize(fmt, self.small_addrs)} 小班"
        if self.jn_year:
            title += f"\n令和 {self.jn_year} 年度  収穫予定箇所"
        title += "\n実測原図"
        return title
    
    def _ttc_jn_to_en(self, expander) -> Dict[str, str]:
        horizontals = {
            '右側': 'right',
            '中央': 'center',
            '左側': 'left'
        }
        verticals = {
            '上側': 'top',
            '下側': 'bottom'
        }
        select_ha = expander.selectbox('水平位置', list(horizontals.keys()), 1)
        select_va = expander.selectbox('垂直位置', list(verticals.keys()), 0)
        return {'ha': horizontals.get(select_ha), 'va': verticals.get(select_va)}



class FindLabels(object):
    def select_label_rows(self, points_gdf: gpd.GeoDataFrame) -> List[Dict[str, Any]]:
        gdf = points_gdf.dropna(subset=['label']).copy()
        return gdf[['label', 'color', 'geometry']]
    
    def rewrite_label(self, label: str) -> str:
        find = '.'
        if '.' in label:
            if label[label.find('.'): ] == '.0':
                return label[: label.find('.')]
        return label

    def create_label_dict(
        self, 
        points_gdf: gpd.GeoDataFrame, 
        poly_geom: shapely.geometry.Polygon | shapely.geometry.MultiPolygon,
        grouping_color: bool, 
        buffer: float,
        distance: float,
        poly_color_rgba: tuple=None
    ) -> List[Dict[str, Any]]:
        selected_points_gdf = self.select_label_rows(points_gdf)
        zipper = zip(
            selected_points_gdf['label'], 
            selected_points_gdf['color'], 
            selected_points_gdf.geometry
        )
        label_lst = []
        for label, color, geom in zipper:
            # 色設定
            if grouping_color == False:
                if poly_color_rgba:
                    color = poly_color_rgba[: -1]
                else:
                    color = 'black'
            # ラベルの座標を再計算
            geom = self.recalc_label_coords(geom, poly_geom, buffer, distance)
            kwargs = {
                'x': geom.x,
                'y': geom.y,
                's': self.rewrite_label(label),
                'fontsize': 5,
                'color': color
            }
            label_lst.append(kwargs)
        return label_lst

    def calc_new_point(
        self, 
        point: shapely.geometry.Point, 
        distance: float, 
        angle :float
    ) -> shapely.geometry.Point:
        angle_rad = math.radians(angle)
        x = point.x + distance * math.sin(angle_rad)
        y = point.y + distance * math.cos(angle_rad)
        destination = (x, y)
        return shapely.geometry.Point(destination)

    def calc_angle(
        self,
        point: shapely.geometry.Point, 
        base_point: shapely.geometry.Point
    ) -> float:
        dy = point.y - base_point.y
        dx = point.x - base_point.x
        angle = math.degrees(math.atan2(dx, dy))
        if angle < 0:
            angle += 360
        return angle
    
    def get_center_pt(
        self, 
        point: shapely.geometry.Point, 
        poly_geom: shapely.geometry.Polygon | shapely.geometry.MultiPolygon,
        buffer: float
    ) -> shapely.geometry.Point:
        buff = point.buffer(buffer)
        intersection = buff.intersection(poly_geom)
        center = intersection.centroid
        return center
        
    def recalc_label_coords(
        self, 
        point: shapely.geometry.Point, 
        poly_geom: shapely.geometry.Polygon | shapely.geometry.MultiPolygon,
        buffer: float=100, 
        distance: float=20
    ) -> shapely.geometry.Point:
        center_point = self.get_center_pt(point, poly_geom, buffer)
        angle = self.calc_angle(point, center_point)
        new_point = self.calc_new_point(point, distance, angle)
        return new_point



class MapDetails(object):
    def __init__(self, poly_gdf: gpd.GeoDataFrame, points_gdf: gpd.GeoDataFrame):
        st.markdown('<br>', True)
        st.markdown('### 図面の設定')
        st.markdown('<hr style="margin: 0px; border: 3px solid #008899">', True)
        expander = st.expander('ON / OFF')
        self.title = None
        self.title_font_size = None
        self.title_coords_ = None
        if expander.toggle('図面にタイトルを追加する'):
            self.set_pdf_title(poly_gdf)
        self.excluded = None
        if expander.toggle('除地を計算する'):
            self.excluded = self.set_excluded_area()
        pdf_type = self.set_pdf_size()
        self.pdf_name = pdf_type.get('name')
        self.pdf_size = pdf_type.get('size')
        self.map_scale = self.set_map_scale()
        self.other = self.set_other()
        self.poly_geom = poly_gdf.iloc[0].geometry
        self.points = points_gdf
        if self.other.get('label'):
            self.label_lst = self.calc_labels

    def set_pdf_title(self, poly_gdf: gpd.GeoDataFrame) -> str:
        title = Title(poly_gdf)
        title._update()
        self.title = title.create_title_sentence()
        self.title_font_size = title.title_font_size
        self.title_coords_txt = title.title_coords_txt

    def set_excluded_area(self):
        expander = st.expander('除地の詳細設定')
        count = expander.number_input('除地の数を選択', 1, 7, 1)
        excluded = {}
        for i in range(count):
            left, right = expander.columns(2)
            key = left.text_input(f'{i+1} 除地の名称', max_chars=8)
            val = right.number_input(
                f'{i+1} 除地の面積（ha）', 0.0, 100.0, 0.2, 
                step=0.01, format="%.4f")
            excluded[key] = round(val, 4)
        return excluded

    def set_pdf_size(self):
        pdf_size = PdfSize()
        pattern = {
            'A4 縦': {'name': 'portrait_a4', 'size': pdf_size.portrait_a4_size},
            'A4 横': {'name': 'landscape_a4', 'size': pdf_size.landscape_a4_size},
            'A3 縦': {'name': 'portrait_a3', 'size': pdf_size.portrait_a3_size},
            'A3 横': {'name': 'landscape_a3', 'size': pdf_size.landscape_a3_size},
        }
        with st.container(border=True):
            select = st.selectbox('PDFのサイズを選択する', list(pattern.keys()))
        return pattern.get(select)

    def set_map_scale(self):
        scales = [5000, 10000, 7000, 2000, 1000]
        with st.container(border=True):
            scale = st.selectbox('地図の縮尺を選択', scales)
        return scale

    def set_other(self):
        expander = st.expander('その他の細かな設定')
        label = expander.toggle('5点ごとに測点ラベルを追加する', True)
        if label:
            font_size = expander.number_input('フォントサイズ', 3, 15, 5, 1)
            left, right = expander.columns(2)
            buff = left.number_input('中心距離計算バッファー（m）', 5, 200, 50, 20)
            distance = right.number_input('ラベルを離す距離（m）', 5, 200, 20, 5)
        other = {
            'label': label,
            'grouping_color': expander.toggle('班別に測点の色を変える', True),
            'legend': expander.toggle('凡例を追加する', True),
            'poly_color_rgba': (0., 0., 0., 0.05),
            'grid': False,
            'estimate_area': False,
            'summary': expander.toggle('計測概要を追加する', True)
        }
        if label:
            other['font_size'] = font_size
            other['label_buff'] = buff
            other['label_distance'] = distance
        if expander.toggle('区域の色を変更', help='デフォルトは黒'):
            other['poly_color_rgba'] = self._color_picker(expander)
        if expander.toggle('グリッドの追加', True, help='背景にグリッドを追加する'):
            other['grid'] = self._grid_picker(expander)
        if expander.toggle('調査指定面積の追加', False):
            other['estimate_area'] = (
                expander
                .number_input(
                '面積（ha）', 0., 500., 5., step=1., format="%.4f")
            )

        return other
               
    def _color_picker(self, expander):
        left, right = expander.columns(2)
        c = left.color_picker('色選択', '#000000')
        rgb = [v / 255 for v in ImageColor.getcolor(c, 'RGB')]
        alpha = right.number_input(
            '区域内の塗りつぶし透明度', 0., 1., 0.05, step=0.05, format="%.2f",
            help='小さい程透明度が高い')
        rgba = (list(rgb) + [alpha])
        return rgba
    
    def _grid_picker(self, expander):
        help_txt = '小さい程透明度が高い'
        left, right = expander.columns(2)
        major_lw = left.number_input(
            '100mグリッドの線の太さ', 0., 3., 0.5, step=0.1, format="%.1f")
        major_alpha = right.number_input(
            '100mグリッドの透明度', 0., 1., 0.15, step=0.01, format="%.2f",
            help=help_txt)
        left, right = expander.columns(2)
        minor_lw = left.number_input(
            '20mグリッドの線の太さ', 0., 3., 0.5, step=0.1, format="%.1f")
        minor_alpha = right.number_input(
            '20mグリッドの透明度', 0., 1., 0.17, step=0.01, format="%.2f",
            help=help_txt)
        c = '#7d7d7d'
        return {
            'major': dict(lw=major_lw, c=c, alpha=major_alpha, ls='solid'),
            'minor': dict(lw=minor_lw, c=c, alpha=minor_alpha, ls='dotted')
        }
    
    def get_title_txt_coords(
        self, 
        xmin: float, 
        xmax: float, 
        ymin: float, 
        ymax: float, 
        horizontalalignment: str, 
        verticalalignment: str
    ) -> Dict[str, float]:
        h_tick = (xmax - xmin) / 8
        ha = {
            'right': xmax - h_tick * 2.5,
            'center': xmin + (xmax - xmin) / 2,
            'left': xmin + h_tick * 2.5
        }
        va = {
            'top': ymax - (ymax - ymin) / 10,
            'bottom': ymin + (ymax - ymin) / 8
        }
        coords = {
            'x': ha.get(horizontalalignment),
            'y': va.get(verticalalignment)
        }
        return coords
    
    @property
    def title_config(self):
        font_dict = {
            'size': self.title_font_size, 
            'ha': 'center', 
            'va': 'center',
            'linespacing': 1.5,
            'bbox': {'facecolor': 'none', 'edgecolor': 'black', 'pad': 7}
        }
        return font_dict

    @property
    def calc_labels(self) -> List[Dict[str, Any]]:
        findlabels = FindLabels()
        labels = (
            findlabels
            .create_label_dict(
                points_gdf=self.points, 
                poly_geom=self.poly_geom,
                grouping_color=self.other.get('grouping_color'),
                buffer=self.other.get('label_buff'),
                distance=self.other.get('label_distance'),
                poly_color_rgba=self.other.get('poly_color_rgba')
            )
        )
        font_size = self.other.get('font_size')
        expander = st.expander('測点ラベル設定')
        new_labels = []
        for i, label_dict in enumerate(labels):
            left, center, right = expander.columns(3)
            label = left.text_input(f'{i+1} 測点名', label_dict.get('s'))
            delta_x = right.number_input(f'{i+1} 左右移動（m）', -200, 200, 0, 10)
            delta_y = center.number_input(f'{i+1} 上下移動（m）', -200, 200, 0, 10)
            label_dict['s'] = label
            label_dict['x'] = label_dict['x'] + delta_x
            label_dict['y'] = label_dict['y'] + delta_y
            label_dict['fontsize'] = font_size
            new_labels.append(label_dict)
        return new_labels
        


class Report(object):
    def coords(
        self, 
        xmin: float, 
        xmax: float, 
        ymin: float, 
        ymax: float,
        portrait: bool=True
    ) -> Dict[str, float]:
        coef = 3 if portrait else 2
        x = xmax - (xmax - xmin) / 10 * coef
        y = (ymax - ymin) / 10 * 0.6 + ymin
        return {'x': x, 'y': y}

    def report_text(
        self, 
        polygon: shapely.geometry.Polygon | shapely.geometry.MultiPolygon, 
        scale: int, 
        estimate_area: float | bool=False
    ) -> str:
        sentence = f"縮尺　　　　　    ：  1/{scale}\n"
        if estimate_area:
            sentence += f"指定面積（ha）　：  {estimate_area}\n"
        sentence += f"実測面積（ha）　：  {round(polygon.area / 10_000, 4)}\n"
        sentence += f"周囲長（m） 　　：  {round(polygon.length, 3)}\n\n"
        return sentence
    
    def _calc_space(self, txt) -> str:
        return (8 - len(txt)) * '　'

    def details_exclution(
        self, 
        poly_area: float, 
        exclution_dict: Dict[str, float]
    ) -> str:
        poly_area = poly_area / 10000
        sentence = "林地面積計算（ha）\n"
        for key, val in exclution_dict.items():
            sentence += f"{key}{self._calc_space(key)}：  {val}\n"
            poly_area -= val
        sentence += f"林地面積{self._calc_space('    ')}：  {round(poly_area, 4)}"
        return sentence
    

@dataclass
class MinMax:
    xmin: float
    xmax: float
    ymin: float
    ymax: float
    dict = asdict



class PlottingPdf(object):
    def __init__(
        self, 
        geo_gdfs: GeoDataFrames, 
        map_details: MapDetails, 
        base_map: np.ndarray=None
    ):
        self.poly_geom = geo_gdfs.poly.geometry.to_list()[0]
        self.points = geo_gdfs.points
        self.base_point = self.points.geometry.to_list()[0]
        self.map_details = map_details
        self.fig, self.ax = plt.subplots(figsize=map_details.pdf_size, dpi=300)
        self.fig.tight_layout(pad=0)
        self.minmax = self.set_lims
        if base_map is None:
            self.poly_plot
            self.points_plot
            self.set_report
            self.set_title
            self.set_labels
        self.set_lims
        self.set_spines
        self.set_ticks_base_point
        if not base_map is None:
            self.ax.imshow(
                base_map, cmap='gray', vmin=0, vmax=255, 
                extent=[self.ax.get_xlim()[0], 
                        self.ax.get_xlim()[1], 
                        self.ax.get_ylim()[0], 
                        self.ax.get_ylim()[1]
                ]
            )

    @property
    def poly_plot(self):
        rgba = self.map_details.other.get('poly_color_rgba')
        res = plot_polygon(
            self.poly_geom, self.ax, add_points=False,
            edgecolor=rgba[:-1], facecolor=rgba,
            linewidth=0.5
        )
        res

    @property
    def points_plot(self):
        jn_confs = JnDataCols()
        points = self.points.sort_values(['group', jn_confs.pt_number_col]).copy()
        colored = self.map_details.other.get('grouping_color')
        for group in points['group'].unique():
            rows = points[points['group'] == group].copy()
            if colored:
                self._color_points_plot(rows, group)
            else:
                self._simple_points_plot(rows)
        self.ax.set_axisbelow(True)

    def _color_points_plot(self, rows: gpd.GeoDataFrame, group: str):
        x, y = rows.geometry.x, rows.geometry.y
        color = rows['color']
        size = rows['size']
        self.ax.scatter(x=x, y=y, c=color, s=size * 0.7, label=group)
        self.ax.scatter(x=x, y=y, facecolor='none', edgecolor=color, 
                        s=size.apply(self._adjustment_size), linewidths=0.2)
    
    def _simple_points_plot(self, rows: gpd.GeoDataFrame):
        x, y = rows.geometry.x, rows.geometry.y
        size = rows['size']
        c = self.map_details.other.get('poly_color_rgba')[: -1]
        self.ax.scatter(x=x, y=y, s=size * 0.7, c=c)
        self.ax.scatter(x=x, y=y, facecolor='none', edgecolor=c, 
                        s=size.apply(self._adjustment_size), linewidths=0.2)
        
    def _adjustment_size(self, size):
        if size == 1:
            return size
        elif size == 2:
            return size * 9
        else:
            return size * 12
        
    @property
    def select_coef(self) -> int:
        # 縮尺に合わせてaxisの拡大係数を選択する
        map_scales = {
            10000: 10,
            7000: 7,
            5000: 5,
            2000: 2,
            1000: 1
        }
        return map_scales.get(self.map_details.map_scale)
    
    @property
    def expansions(self) -> List[float]:
        # PDFサイズと縮尺に合わせて、軸の拡大範囲を計算する
        pdf_size = self.map_details.pdf_name
        if pdf_size == 'portrait_a4':
            # A4縦の場合のlim拡張に使用する
            expansion_x = 105 * self.select_coef
            expansion_y = 148.5 * self.select_coef
        elif pdf_size == 'landscape_a4':
            # A4横の場合のlim拡張に使用する
            expansion_x = 148.5 * self.select_coef
            expansion_y = 105 * self.select_coef
        elif pdf_size == 'portrait_a3':
            # A3縦の場合のlim拡張に使用する
            expansion_x = 148.5 * self.select_coef
            expansion_y = 210 * self.select_coef
        elif pdf_size == 'landscape_a3':
            # A3横の場合のlim拡張に使用する
            expansion_x = 210 * self.select_coef
            expansion_y = 148.5 * self.select_coef
        else:
            return None
        return expansion_x, expansion_y

    @property
    def delta(self) -> float:
        # 縮尺に合わせたDeltaパラメーター
        base = 54.3 / 10
        coef = self.map_details.map_scale / 1000
        return base * coef
    
    @property
    def xlim(self) -> List[float]:
        # xlimの値を計算する
        reversed_x = False
        center_x = self.poly_geom.centroid.x
        if center_x < 0:
            center_x = center_x * -1
            reversed_x = True
        expansion_x, _ = self.expansions
        xmin = center_x  - expansion_x + self.delta
        xmax = center_x + expansion_x - self.delta
        if reversed_x:
            xmin = xmin * -1
            xmax = xmax * -1
        return list(sorted([xmin, xmax]))
    
    @property
    def ylim(self) -> List[float]:
        # ylimの値を計算する
        reversed_y = False
        center_y = self.poly_geom.centroid.y
        if center_y < 0:
            center_y = center_y * -1
            reversed_y = True
        _, expansion_y = self.expansions
        ymin = center_y  - expansion_y + self.delta
        ymax = center_y + expansion_y - self.delta
        if reversed_y:
            ymin = ymin * -1
            ymax = ymax * -1
        return list(sorted([ymin, ymax]))
    
    @property
    def set_lims(self) -> MinMax:
        xmin, xmax = self.xlim
        ymin, ymax = self.ylim
        self.ax.set_xlim([xmin, xmax])
        self.ax.set_ylim([ymin, ymax])
        self.ax.set_aspect('equal')
        return MinMax(xmin, xmax, ymin, ymax)

    @property
    def set_spines(self):
        # XYの軸の位置と色を設定する
        delta = self.map_details.map_scale / 100
        self.ax.spines['left'].set_position(('data', self.minmax.xmin + delta))
        self.ax.spines['left'].set_color('#7d7d7d')
        self.ax.spines['right'].set_color('none')
        self.ax.spines['bottom'].set_position(('data', self.minmax.ymin + delta))
        self.ax.spines['bottom'].set_color('#7d7d7d')
        self.ax.spines['top'].set_color('none')
    
    def get_grid_ticks_base_point(
        self, base_x_or_y: float, 
        min_val: float, 
        max_val: float
    ) -> List[float]:
        # 最初の測点をベースにGridのTicksListを作成する。
        lefter = base_x_or_y
        ticks = []
        while True:
            if lefter < 0:
                lefter += -100
                ticks.append(lefter)
                if lefter + (-100) < min_val:
                    break
            else:
                lefter -= 100
                ticks.append(lefter)
                if lefter - 100 < min_val:
                    break
        ticks.append(base_x_or_y)
        righter = base_x_or_y
        while True:
            righter += 100
            ticks.append(righter)
            if max_val <= righter + 100:
                break
        return list(sorted(ticks))

    def _create_minor_ticks(self, major_ticks: List[float]) -> List:
        ticks = [round(v, 3) for v in np.arange(major_ticks[0], major_ticks[-1], 20)]
        ticks.append(major_ticks[-1])
        return ticks

    @property
    def set_ticks_base_point(self):
        xticks = self.get_grid_ticks_base_point(
            self.base_point.x, self.minmax.xmin, self.minmax.xmax)
        yticks = self.get_grid_ticks_base_point(
            self.base_point.y, self.minmax.ymin, self.minmax.ymax)
        minor_xticks = self._create_minor_ticks(xticks)
        minor_yticks = self._create_minor_ticks(yticks)
        self.ax.set_xticks(xticks[1 : -1])
        self.ax.set_yticks(yticks[1 : -1])
        self.ax.set_xticks(minor_xticks, minor=True)
        self.ax.set_yticks(minor_yticks, minor=True)
        self.ax.minorticks_on()
        grid = self.map_details.other.get('grid')
        if grid:
            self.ax.grid(which="major", **grid.get('major'), axis='both')
            self.ax.grid(which="minor", **grid.get('minor'), axis='both')
        c = '#7d7d7d'
        self.ax.xaxis.set_tick_params(labelcolor=c, labelsize=7, color=c)
        self.ax.yaxis.set_tick_params(rotation=90, labelcolor=c, labelsize=7, color=c)

    @property
    def set_title(self):
        if not self.map_details.title is None:
            coords_txt = self.map_details.title_coords_txt
            tc = self.map_details.get_title_txt_coords(
                xmin=self.minmax.xmin,
                xmax=self.minmax.xmax,
                ymin=self.minmax.ymin,
                ymax=self.minmax.ymax,
                horizontalalignment=coords_txt.get('ha'),
                verticalalignment=coords_txt.get('va')
            )
            tc['s'] = self.map_details.title
            txt = self.ax.text(**tc, fontdict=self.map_details.title_config)
            txt.set_bbox(dict(facecolor='white', alpha=0.9, edgecolor='black'))

    @property
    def set_report(self):
        if 'portrait' in self.map_details.pdf_name:
            portrait = True
        else:
            portrait = False
        report = Report()
        coords = report.coords(
            self.minmax.xmin, self.minmax.xmax, 
            self.minmax.ymin, self.minmax.ymax,
            portrait
        )
        sentence = report.report_text(
            polygon=self.poly_geom,
            scale=self.map_details.map_scale, 
            estimate_area=self.map_details.other.get('estimate_area')
        )
        excluded_dict = self.map_details.excluded
        if excluded_dict:
            sentence += report.details_exclution(
                poly_area=self.poly_geom.area, 
                exclution_dict=self.map_details.excluded
            )
        coords['s'] = sentence
        txt = self.ax.text(**coords)
        txt.set_bbox(dict(facecolor='white', alpha=0.9, edgecolor='black'))

    @property
    def set_labels(self):
        if self.map_details.other.get('label'):
            labels = self.map_details.label_lst
            for label in labels:
                self.ax.text(**label, label=label.get('s'))
        if self.map_details.other.get('legend'):
            self.ax.legend(fontsize=12, markerscale=5, bbox_to_anchor=(0.05, 0.05), loc='lower left')


class PdfEvent(object):
    def __init__(self, geo_dfs: GeoDataFrames, map_details: MapDetails):
        self.id = 0
        self.pdf = PlottingPdf(geo_dfs, map_details)
    
    @property
    def show_pdf(self):
        st.pyplot(self.pdf.fig)

    @property
    def save_pdf(self):
        txt = st.text_input('出力ファイル名', 'Map')
        buffer = io.BytesIO()
        self.pdf.fig.savefig(buffer, format='pdf')
        pdf_bytes = buffer.getvalue()
        st.download_button(
            label="PDFのダウンロード",
            data=pdf_bytes,
            file_name=f"{txt}.pdf",
            mime="application/pdf",
        )


def create_pdf(geo_gdfs: GeoDataFrames, map_details: MapDetails):
    st.markdown('<br>', True)
    st.markdown('## 📌 実測原図の作成')
    st.markdown('<hr style="margin: 0px; border: 3px solid #696969">', True)
    help_txt = 'ONにしておくと、パラメーターを変化させる度に図面に変更を加える'
    help_txt += 'ので、計算に時間が掛かります。スペックの低いPCを使用している'
    help_txt += '場合はこのトグルボタンをOFFにしておき、パラメーターの調整が'
    help_txt += '終わってから「図面の作成」ボタンを押す方がいいかもしれません。'
    show = st.toggle('常に最新の図面を作成する', help=help_txt)
    event = None
    if show:
        event = PdfEvent(geo_gdfs, map_details)
        event.show_pdf
    else:
        if st.button('図面の作成'):
            event = PdfEvent(geo_gdfs, map_details)
        if event:
            event.show_pdf
    if event:
        event.save_pdf


class CalcImageSize(PdfSize):
    def __init__(self, fp: str, out_img_size: str):
        super().__init__()
        self.img = Image.open(fp).convert('L')
        self.img_ary = np.array(self.img)
        self.out_img_size = self.select_size(out_img_size)
        if self.out_img_size is None:
            raise ValueError('画像サイズを正しく選択して')
    
    @property
    def img_dpi_w(self) -> int:
        return int(self.img.info['dpi'][0])
    
    @property
    def img_dpi_h(self) -> int:
        return int(self.img.info['dpi'][1])

    @property
    def img_fig_w(self) -> float:
        return self.size_w / self.dpi_w
    
    @property
    def img_fig_h(self) -> float:
        return self.size_h / self.dpi_h

    @property
    def img_cols(self) -> int:
        return self.img_ary.shape[1]
    
    @property
    def img_rows(self) -> int:
        return self.img_ary.shape[0]
    
    def select_size(self, out_img_size: str) -> List[int]:
        sizes = {
            'portrait_a4': self.portrait_a4_size,
            'portrait_a3': self.portrait_a3_size,
            'landscape_a4': self.landscape_a4_size,
            'landscape_a3': self.landscape_a3_size,
        }
        return sizes.get(out_img_size)

    @property
    def img_add_cols_num(self) -> float:
        # ImgArrayから追加または削除する行数を取得する
        fig_w = self.out_img_size[0]
        trg_cols = round(fig_w * self.img_dpi_w, 0)
        coef = (trg_cols -  self.img_cols) / self.img_cols
        add_cols = self.img_cols * coef
        return int(round(add_cols, 0))

    @property
    def img_add_rows_num(self) -> float:
        # ImgArrayから追加または削除する行数を取得する
        fig_h = self.out_img_size[1]
        trg_rows = round(fig_h * self.img_dpi_h, 0)
        coef = (trg_rows -  self.img_rows) / self.img_rows
        add_rows = self.img_rows * coef
        return int(round(add_rows, 0))
    
    def add_rows_ary(self, img_cols: int) -> np.ndarray:
        return np.zeros((self.img_add_rows_num, img_cols)) + 255
    
    def add_cols_ary(self, img_rows) -> np.ndarray:
        return np.zeros((img_rows, self.img_add_cols_num)) + 255

    def trimming_of_margins(
        self, 
        img_ary: np.ndarray, 
        pdf_width: int=2970,
        pdf_height: int=2100,
        tb_margin_mm: float=106.5, 
        lr_margin_mm: float=103.5
    ) -> np.ndarray:
        rows, cols = img_ary.shape
        cols_coef = cols / pdf_width
        rows_coef = rows / pdf_height
        lr_margin = int(round(lr_margin_mm / cols_coef, 0))
        tb_margin = int(round(tb_margin_mm / rows_coef, 0))
        return img_ary[: -lr_margin, : -tb_margin]

    @property
    def resized_image(self):
        # 画像サイズを指定の用紙サイズに調整します。
        # 行の調整
        if self.img_add_rows_num < 0:
            img_ary = self.img_ary[: self.img_add_rows_num, :]
        elif 0 < self.img_add_rows_num:
            add_rows = self.add_rows_ary(self.img_cols)
            img_ary = np.vstack([self.img_ary, add_rows])
        else:
            img_ary = self.img_ary
        # 列の調整
        if self.img_add_cols_num < 0:
            img_ary = img_ary[:, : self.img_add_cols_num]
        elif 0 < self.img_add_cols_num:
            add_cols = self.add_cols_ary(img_ary.shape[0])
            img_ary = np.hstack([img_ary, add_cols])
        return img_ary


@dataclass
class Delta:
    x: float
    y: float
    angle: float


class LocationMap(object):
    def __init__(self, geo_dfs: GeoDataFrames, map_details: MapDetails):
        self.geo_dfs = geo_dfs
        self.map_details = map_details
        self.file = self.uploder_img
        self.ppf = None
        if self.file:
            self.delta, col2 = self.move_it
            self.img_ary = self.fit_img(self.map_details.pdf_name)
            self.ppf = PlottingPdf(self.geo_dfs, self.map_details, self.img_ary)
            self.move_poly
            self.move_points
            self.move_labels
            self.ppf.poly_plot
            self.ppf.points_plot
            self.ppf.set_labels
            self.enlarged_view_plot(col2)
            if st.toggle('常に最新の位置図を作成する'):
                self.re_title
                self.ppf.set_title
                self.set_summary
                self.ppf
                self.ppf.ax.set_xticks([])
                self.ppf.ax.set_yticks([])
                self.ppf.ax.spines['left'].set_visible(False)
                self.ppf.ax.spines['bottom'].set_visible(False)
                st.pyplot(self.ppf.fig)
                self.save_fig
                
    @property
    def uploder_img(self) -> UploadedFile:
        # 画像ファイルの入力
        st.markdown('<br>', True)
        st.markdown('### 基本図の読み込み')
        st.markdown('<hr style="margin: 0px; border: 3px solid #008899">', True)
        expander = st.expander('基本図画像を入力する（.jpg, .png, .tif）', True)
        with open('././views/document_grayscale_map.html', mode='r', encoding='utf-8') as f:
            html_string = f.read()
        expander.markdown(html_string, unsafe_allow_html=True)
        files = expander.file_uploader(
            label='ドラッグ&ドロップでも入ります。',
            type=['png', 'jpg', 'tif'], 
        )
        return files

    @property
    def move_it(self) -> Delta:
        expander = st.expander('区域の移動')
        col1, col2 = expander.columns([0.3, 0.7])
        help_x = 'x軸方向の移動距離を指定して下さい'
        help_y = 'y軸方向の移動距離を指定して下さい'
        help_r = '回転する角度を指定して下さい。原点は1号点です。'
        x = col1.number_input('横軸の移動（m）', -1000.0, 1000.0, 0., 5.0, help=help_x)
        y = col1.number_input('縦軸の移動（m）', -1000.0, 1000.0, 0., 5.0, help=help_y)
        angle = col1.number_input('回転（°）', -180., 180., 0., 1.0, help=help_r)
        angle = 360 - angle
        return Delta(x, y, angle), col2

    def enlarged_view_plot(self, column: DeltaGenerator):
        # 区域を移動する際に拡大図を表示する
        fig = copy.deepcopy(self.ppf.fig)
        fig.set_size_inches(5, 5)
        ax = fig.get_axes()[0]
        # 表示範囲をpolygon周辺に絞り込む
        xmin, ymin, xmax, ymax = self.ppf.poly_geom.bounds
        xmin += -50
        ymin += -50
        xmax += 50
        ymax += 50
        ax.set_ylim([ymin, ymax])
        ax.set_xlim([xmin, xmax])
        ax.spines['left'].set_visible(False)
        ax.spines['bottom'].set_visible(False)
        ax.set_xticks([])
        ax.set_yticks([])
        for text in ax.texts:
            if 10 < len(text.get_text()):
                text.set_visible(False)
        ax.legend().remove()
        column.pyplot(fig)


    def fit_img(
        self,
        out_img_size: str, 
        tb_margin_mm: float=154, 
        lr_margin_mm: float=150
    ) -> np.array:
        cis = CalcImageSize(self.file, out_img_size)
        resized = cis.resized_image
        sizes = {
            'portrait_a4': {'w': 2100, 'h': 2970},
            'landscape_a4': {'w': 2970, 'h': 2100},
            'portrait_a3': {'w': 2970, 'h': 4200},
            'landscape_a3': {'w': 4200, 'h': 2970},
        }
        size = sizes.get(out_img_size)
        pdf_w, pdf_h = size.get('w'), size.get('h')
        trimmed = cis.trimming_of_margins(
            resized, pdf_w, pdf_h, tb_margin_mm, lr_margin_mm)
        return trimmed

    @property
    def get_base_point(self) -> shapely.geometry.Point:
        return self.ppf.points.geometry.to_list()[0]
    
    @property
    def move_poly(self):
        # Polygonの回転
        poly_geom = (
            shapely
            .affinity
            .rotate(
                self.ppf.poly_geom, 
                self.delta.angle, 
                origin=self.get_base_point
            )
        )
        # Polygonの移動
        self.ppf.poly_geom = (
            shapely
            .affinity
            .translate(
                poly_geom, 
                xoff=self.delta.x, 
                yoff=self.delta.y
            )
        )
    
    @property
    def move_points(self):
        self.ppf.points['geometry'] = (
            self
            .ppf
            .points
            .geometry
            .rotate(self.delta.angle, origin=self.get_base_point)
        )
        self.ppf.points['geometry'] = (
            self
            .ppf
            .points
            .geometry
            .translate(xoff=self.delta.x, yoff=self.delta.y)
        )

    @property
    def move_labels(self):
        geoms = [ 
            shapely.geometry.Point(d.get('x'), d.get('y'))
            for d in self.map_details.label_lst
        ]
        new_labels = []
        for geom, label in zip(geoms, self.map_details.label_lst):
            geom = shapely.affinity.translate(geom, xoff=self.delta.x, yoff=self.delta.y)
            geom = shapely.affinity.rotate(geom, self.delta.angle, origin=self.get_base_point)
            label['x'] = geom.x
            label['y'] = geom.y
            new_labels.append(label)
        self.map_details.label_lst = new_labels

    @property
    def re_title(self):
        txt = self.map_details.title
        if isinstance(txt, str):
            if '原図' in txt:
                txt = txt.replace('原図', '位置図\n')
                e_area = self.map_details.other.get('estimate_area')
                if e_area:
                    txt += f"調査指定面積： {round(e_area, 2)}ha\n"
                txt += f"実測面積： {round(self.ppf.poly_geom.area / 10_000, 2)} ha"
            
        self.map_details.title = txt

    @property
    def set_summary(self):
        if self.map_details.other.get('summary'):
            self.ppf.set_report
        
    @property
    def save_fig(self):
        if st.toggle('実測位置図のPDFを作成する'):
            jn = JnDataCols()
            row = self.ppf.points.iloc[0]
            office = row[jn.office_col]
            address = row[jn.address_col]
            name = f"実測位置図_{office}_{address}"
            name = st.text_input('保存する名前を入力する', name)
            buffer = io.BytesIO()
            self.ppf.fig.savefig(buffer, format='pdf')
            pdf_bytes = buffer.getvalue()
            st.download_button(
                label="実測位置図のダウンロード",
                data=pdf_bytes,
                file_name=f"{name}.pdf",
                mime="application/pdf",
            )


def page_of_mapping_pdf():
    summary.show_mapping_pdf_summary
    files = uploder_row()
    show = False
    # ファイルをGeoDataFrameにする
    if files:
        geo_dfs = read_file(files)
        if geo_dfs:
            show = True
    else:
        show = False
    if show:
        # 実測原図の作成
        geo_dfs = localize_crs(geo_dfs, select_epsg_row())
        map_details = MapDetails(geo_dfs.poly, geo_dfs.points)
        create_pdf(geo_dfs, map_details)
        # 実測位置図の作成
        st.markdown('## 📌 実測位置図の作成')
        st.markdown('<hr style="margin: 0px; border: 3px solid #696969">', True)
        LocationMap(geo_dfs, map_details)
        
        