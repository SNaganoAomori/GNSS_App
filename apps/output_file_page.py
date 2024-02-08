import re
import requests
import string
from typing import List

import polars as pl
import streamlit as st
import shapely

from apps.chiriin_api import semidynamic_exe
from apps.dta import write_csv_sentence
from apps.dta import write_dta_sentence
from apps.documents import Summary
from apps.exception import collection_checker
from apps.geometries import GeoJ
from apps.geometries import edit_line_kml
from apps.geometries import edit_points_kml
from apps.geometries import edit_poly_kml
from apps.geometries import edit_single_geom_datasets
from apps.sidebar import SideBarResponse
from apps.projective_transformer import transformer_project
from apps.settings.configs import JnDataCols
from apps.xls import write_dataframe_to_xls_bytes
summary = Summary()



def check_internet_connection(url='http://www.google.com', timeout=10):
    """InterNet接続の確認"""
    try:
        r = requests.head(url, timeout=timeout)
        return True
    except requests.ConnectionError as ex:
        print(ex)
        return False


def select_projective_technique(local_epsg):
    st.markdown('<br>', unsafe_allow_html=True)
    st.markdown('##### 出力する座標系を選択する')
    st.markdown('<hr style="margin: 0px; border: 3px solid #008899">', True)
    epsg_codes = {
        '経緯度（WGS84）': 4326,
        f'平面直角座標系（EPSG:{local_epsg}）': local_epsg,
        'Webメルカトル': 3857,
    }
    captions = [
        '経緯度はGNSSなどで使用される座標系です。',
        '平面直角座標系はサイドバーで選択した座標系が使用されます。',
        'Web地図で使用される座標系です。'
    ]
    expander = st.expander('出力座標系を変更したい')
    cols = expander.columns((3.5, 6.5))

    with cols[0]:
        # 出力座標系を選択する為のラジオボタン
        selected = st.radio(
            '出力座標系の選択', options=list(epsg_codes.keys()),
            captions=captions
        )
        selected_epsg = epsg_codes.get(selected)

    with cols[1]:
        # 出力座標系の説明
        if selected_epsg == 4326:
            summary.show_wgs84_summary
        elif selected_epsg == local_epsg:
            summary.show_local_mercator_summary
        elif selected_epsg == 3857:
            summary.show_web_mercator_summary
    return selected_epsg


def select_language() -> bool:
    expander = summary.show_select_language_summary
    language = expander.toggle('列名を英語で出力する')
    return language


def correction_coords(df: pl.DataFrame, epsg: int) -> pl.DataFrame:
    # セミダイナミック補正してDataFrameに入力する
    jn_confs = JnDataCols()
    lons = df[jn_confs.lon_col].to_list()
    lats = df[jn_confs.lat_col].to_list()
    years = df[jn_confs.datetime_col].dt.year().to_list()

    # セミダイナミック補正の実行とProgressBarの表示
    txt = 'セミダイナミック補正を実行しています。しばらくお待ち下さい。'
    pbar = st.progress(0., text=txt)
    step = 1 / len(lons)
    progress = 0
    cd_lons = []
    cd_lats = []
    for lon, lat, year in zip(lons, lats, years):
        coords = semidynamic_exe(lon, lat, year)
        cd_lons.append(coords.lon)
        cd_lats.append(coords.lat)
        progress += step
        pbar.progress(progress, text=txt)
    pbar.empty()
    # 投影変換
    coords = transformer_project(cd_lons, cd_lats, 4326, epsg)
    df = (
        df
        .with_columns([
            pl.lit(epsg).alias(jn_confs.epsg_col),
            # 緯度がX
            pl.Series(name=jn_confs.x_col, values=coords.lats),
            # 経度がY
            pl.Series(name=jn_confs.y_col, values=coords.lons)
        ])
    )
    return df
    


class MapParts(object):
    def cmap(self, idx: int) -> str:
        cmap = [
            '#c9171e', # 赤
            '#1e50a2', # 青
            '#316745', # 緑
            '#674196', # 紫
            '#ea5506', # 橙
            '#0095d9', # 薄青
            '#69b076', # 薄緑
            '#8a3b00', # 茶
            '#e95295', # 桃
            '#008899', # 納戸
            '#b8d200', # 黄緑
            '#426579', # 灰色
            '#e6b422', # 黄色
            '#16160e', # 黒
        ]
        if len(cmap) < idx:
            return '#16160e'
        return cmap[idx]
    
    def alhpabet_idx(self, alhpabet: str) -> int:
        # グループ名であるアルファベットの位置を取得
        return list(string.ascii_uppercase).index(alhpabet)
    
    def select_color(self, group_name: str) -> str:
        if group_name in list(string.ascii_uppercase):
            return self.cmap(self.alhpabet_idx(group_name))
        else:
            return '#16160e'

    def find_label(self, labels: List[str | int | float]) -> List[str]:
        # 5点ごとにラベルを表示させる
        new_labels = []
        for i, label in enumerate(labels):
            idx = i + 1
            if idx == 1:
                new_labels.append(label)
            elif idx % 5 == 0:
                new_labels.append(label)
            elif idx == len(labels):
                new_labels.append(label)
            else:
                new_labels.append(None)
        return new_labels
    
    def get_point_size(self, labels: List[str | int | float]) -> List[str]:
        # Point別のMarkerSizeを取得
        sizes = []
        for i, _ in enumerate(labels):
            idx = i + 1
            if idx == 1:
                sizes.append(3)
            elif idx % 5 == 0:
                sizes.append(2)
            else:
                sizes.append(1)
        return sizes

    def get_colors(self, group_names: List[str]) -> List[str]:
        colors = [self.select_color(g) for g in group_names]
        return colors
            
    def find_number(self, point_names: List[str]) -> List[float]:
        result = []
        for name in point_names:
            numbers = re.findall(r'\d+\.\d*|\d+', name)
            result.append(float(numbers[0]))
        return result


def add_mapping_parts(df: pl.DataFrame) -> pl.DataFrame:
    """Map作成時に便利なように、Group別にLabelなどを作成する"""
    parts = MapParts()
    confs = JnDataCols()
    df = df.with_columns([
        # 念のためIndexを振り直す
        pl.int_range(0, pl.count()).cast(pl.Int64).alias('idx'),
        # 一時的な並び替えの数字
        pl.Series('_num', parts.find_number(df[confs.pt_name_col].to_list()))
    ])
    dfs = []
    for group in df['group'].unique():
        rows = df.filter(pl.col('group') == group).sort('_num')
        _labels = rows[confs.pt_name_col].to_list()
        labels = parts.find_label(_labels)
        sizes = parts.get_point_size(_labels)
        colors = parts.get_colors(rows['group'].to_list())
        rows = rows.with_columns([
            pl.Series('color', colors),
            pl.Series('label', labels),
            pl.Series('size', sizes),
        ])
        dfs.append(rows)
    
    return pl.concat(dfs).sort('idx').drop('_num')


def download_excel(
    df: pl.DataFrame, 
    file_base: str, 
    positioning_correction: bool, 
):
    jn_confs = JnDataCols()
    expander = summary.show_download_xls_summary
    edit = expander.toggle('測量野帳を作成する', False)
    if positioning_correction & edit:
        xs = df[jn_confs.y_col].to_list()
        ys = df[jn_confs.x_col].to_list()
        poly = shapely.geometry.Polygon([(x, y) for x, y in zip(xs, ys)])
        area = round(poly.area / 10_000, 4)
        length = round(poly.length, 2)
        xls_bytes = write_dataframe_to_xls_bytes(df, area, length)
        expander.download_button(
            label='.xlsx のダウンロード',
            data=xls_bytes,
            file_name=f'{file_base}_測量野帳.xlsx',
            mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            type='primary'
        )
        

def download_dta(
    df: pl.DataFrame, 
    file_base: str
):
    """
    DTAファイルをダウンロードする為の行を作成する
    """
    jn_confs = JnDataCols()
    expander = summary.show_download_dta_summary
    if expander.toggle('ONにするとDTAファイルが作成されダウンロード可能になります'):
        # 座標データからコンパス測量の成果を求め、DTAファイルと同じフォーマットの文字列を作成する        
        dta_sentence = write_dta_sentence(
            pt_names=df[jn_confs.pt_name_col].to_list(),
            lons=df[jn_confs.lon_col].to_list(),
            lats=df[jn_confs.lat_col].to_list(),
            epsg=4326
        )
        expander.download_button(
            label=".DTA ファイルのダウンロード",
            data=dta_sentence,
            file_name=f"{file_base}.DTA",
            mime='text/plain',
            type='primary'
        )
        csv_sentence = write_csv_sentence(
            pt_names=df[jn_confs.pt_name_col].to_list(),
            lons=df[jn_confs.lon_col].to_list(),
            lats=df[jn_confs.lat_col].to_list(),
            epsg=4326
        )
        expander.download_button(
            label=".CSV ファイルのダウンロード",
            data=csv_sentence,
            file_name=f"{file_base}.csv",
            mime='text/plain',
            type='primary'
        )


def download_geojson(
    df: pl.DataFrame, 
    file_base: str, 
    positioning_correction: bool, 
    out_epsg: int,
    sidebar_response: SideBarResponse,
    is_en: bool
):
    expander = summary.show_download_geojson_summary
    if expander.toggle('ONにするとGeoJSONファイルが作成されダウンロード可能になります'):
        geometries = edit_single_geom_datasets(
            df=df, 
            out_epsg=out_epsg,
            close=sidebar_response.poly_close,
            positioning_correction=positioning_correction,
            local_epsg=sidebar_response.epsg,
        )
        # geojsonオブジェクトの作成
        if geometries.poly:
            geoj = GeoJ(df, geometries, is_en)
            gjsons = geoj.collections(True)
            labels = geoj._labels(True)
            jsons = [gjsons.pnp_geojson, gjsons.point_geojson, gjsons.poly_geojson]
            file_names = [
                f"{file_base}_PnP.geojson", f"{file_base}_Point.geojson",
                f"{file_base}_Poly.geojson",
            ]
        else:
            geoj = GeoJ(df, geometries, is_en)
            gjsons = geoj.collections(False)
            labels = geoj._labels(False)
            jsons = [gjsons.pnl_geojson, gjsons.point_geojson, gjsons.line_geojson]
            file_names = [
                f"{file_base}_PnL.geojson", f"{file_base}_Point.geojson",
                f"{file_base}_Line.geojson",
            ]
        # GeoJSONのダウンロード
        for label, js, file in zip(labels, jsons, file_names):
            expander.download_button(
                label=label,
                data=js,
                file_name=file,
                mime='application/json',
                type='primary'
            )

        ##############


def download_kml(
    df: pl.DataFrame, 
    file_base: str, 
    positioning_correction: bool, 
    sidebar_response: SideBarResponse,
    is_en: bool
):
    expander = summary.show_download_kml_summary  
    if expander.toggle('ONにするとKMLファイルが作成されダウンロード可能になります'):
        geometries = edit_single_geom_datasets(
            df=df, 
            out_epsg=4326,# kmlは強制的に4326にしておく
            close=sidebar_response.poly_close,
            positioning_correction=positioning_correction,
            local_epsg=sidebar_response.epsg
        )

        kml_pt = edit_points_kml(df, geometries, is_en)
        expander.download_button(
            label="ポイント.kml ファイルのダウンロード",
            data=kml_pt.kml(),
            file_name=f"{file_base}_points.kml",
            mime='application/octet-stream',
            type='primary'
        )
        if sidebar_response.poly_close:
            kml_poly = edit_poly_kml(df, geometries, is_en)
            expander.download_button(
                label="ポリゴン.kml ファイルのダウンロード",
                data=kml_poly.kml(),
                file_name=f"{file_base}_polygon.kml",
                mime='application/octet-stream',
                type='primary'
            )
        else:
            kml_line = edit_line_kml(df, geometries, is_en)
            expander.download_button(
                label="ライン.kml ファイルのダウンロード",
                data=kml_line.kml(),
                file_name=f"{file_base}_line.kml",
                mime='application/octet-stream',
                type='primary'
            )

    
def output_page(df: pl.DataFrame, sidebar_resps: SideBarResponse):
    """
    ファイル出力用のページ作成
    """
    jn_confs = JnDataCols()
    #----------------- Sidebarに入力した値 -----------------#
    add = sidebar_resps[0]
    file_base = f"{add.office}-{add.branch_office}-{add.local_area}-{add.address}"

    st.title('💾 ファイル出力')
    st.markdown('<hr style="margin-top: 5px; margin-bottom: 10px; border: 3px solid #dcdddd;">', True)
    st.markdown('このページではGNSS測量データを、任意のファイルフォーマットで出力します。')
    # --------------- Mapping用の情報を入力する(color, label, size) --------------- #
    df = add_mapping_parts(df)
    #----------------- セミダイナミック補正 -----------------#
    if not jn_confs.epsg_col in df.columns:
        df = df.with_columns([
            pl.lit(None).alias(col)
            for col in [jn_confs.epsg_col, jn_confs.x_col, jn_confs.y_col]
        ])
    # セミダイナミック補正の確認
    positioning_correction = collection_checker(df)
    if (positioning_correction == False) & ('positioning_correction' not in st.session_state):
        placeholder = st.empty()
        correction = placeholder.button('セミダイナミック補正の実行!!', type='primary')
        if check_internet_connection():
            # インターネット接続を確認する
            if 'correction' not in st.session_state:
                st.session_state['correction'] = correction
            
            if 'dataframe' not in st.session_state:
                st.session_state['dataframe'] = df

            if correction:
                # 補正の実行
                st.session_state.dataframe = correction_coords(
                    df=df, epsg=add.epsg
                )
                if 'positioning_correction' not in st.session_state:
                    st.session_state['positioning_correction'] = True
                    st.success("""補正が終わりました""", icon='😀')
                    placeholder.empty()
                del correction
        else:
            with open('././views/connect_internet.html', mode='r', encoding='utf-8') as f:
                html_string = f.read()
            st.markdown(html_string, unsafe_allow_html=True)
    
    if (positioning_correction) | ('positioning_correction' in st.session_state):
        table_expander =st.expander('実際に出力されるデータを見てみる')
        table_expander.dataframe(st.session_state.dataframe)

    if 'positioning_correction' in st.session_state:
        # 補正後にはsession_stateに保存されているdataframeを削除するボタンを表示する
        delete = st.button('Delete')
        if delete == True:
            if 'collection' in st.session_state:
                del st.session_state.collection
            if 'dataframe' in st.session_state:
                del st.session_state.dataframe
            del st.session_state.positioning_correction
    #----------------- 出力するデータのEPSGコードを選択させる -----------------#
    selected_epsg = select_projective_technique(add.epsg)
    #----------------- 出力するGISデータのFieldNameを選択させる ---------------#
    is_en = select_language()
    #----------------- Excelファイルの出力 -----------------#
    if 'positioning_correction' in st.session_state:
        # Sessionにセミダイナミック補正の実行が追加されていれば
        positioning_correction = st.session_state['positioning_correction']
    if positioning_correction:
        # セミダイナミック補正済みの場合の処理
        download_excel(
            st.session_state.dataframe, 
            file_base, 
            positioning_correction,
        )
        #----------------- DTAファイルの出力 -----------------#
        download_dta(st.session_state.dataframe, file_base)
        #----------------- GeoJSONファイルの出力 -----------------#
        download_geojson(
            df=st.session_state.dataframe, 
            file_base=file_base, 
            positioning_correction=positioning_correction, 
            out_epsg=selected_epsg, 
            sidebar_response=add,
            is_en=is_en
            
        )
        #----------------- KMLファイルの出力 -----------------#
        download_kml(
            df=st.session_state.dataframe, 
            file_base=file_base, 
            positioning_correction=positioning_correction, 
            sidebar_response=add,
            is_en=is_en
        )

    else:
        # セミダイナミック補正していない場合の処理
        #----------------- DTAファイルの出力 -----------------#
        download_dta(df, file_base)
        #----------------- GeoJSONファイルの出力 -----------------#
        download_geojson(
            df=df, 
            file_base=file_base, 
            positioning_correction=positioning_correction, 
            out_epsg=selected_epsg, 
            sidebar_response=add,
            is_en=is_en
        )
        
        #----------------- KMLファイルの出力 -----------------#
        download_kml(
            df=df, 
            file_base=file_base, 
            positioning_correction=positioning_correction,  
            sidebar_response=add,
            is_en=is_en
        )


    
    
