"""
// アプリ画面のサイドバーに関するモジュールを纏めたもの
"""
import copy
from dataclasses import dataclass
import datetime
import os
import string
from typing import Dict, List, Any

import geopandas as gpd
import pandas as pd
import shapely
import streamlit as st
from streamlit.runtime.uploaded_file_manager import UploadedFile

from apps.exception import format_checker
from apps.read_files import parse_zen2han
from apps.settings.configs import DrgGpxConfs
from apps.settings.configs import JnDataCols
from apps.settings.configs import WebAppConfs

@dataclass
class SideBarResponse:
    """SideBarでの入力結 果を返す"""
    uploaded_file: UploadedFile
    file_name: str
    file_idx: int
    group_name: str
    sort_col: str
    sort_type: bool
    office: str
    branch_office: str
    local_area: str
    address: str
    year: int
    project_name: str
    person: str
    epsg: int
    thres_epochs: int
    thres_pdop: float
    thres_sats: int
    poly_close: bool


def the_current_fiscal_year() -> int:
    """事業年度を計算"""
    now = datetime.datetime.now().date()
    if 4 <= now.month:
        return now.year
    return int(now.year - 1)


def select_unique_file(file_obj_lst: List[UploadedFile]) -> List[List[Any]]:
    """同じ名前のファイルがない様にする"""
    selected_names = []
    selected_objs = []
    for file_obj in file_obj_lst:
        if len(selected_objs) == 0:
            selected_names.append(file_obj.name)
            selected_objs.append(file_obj)
        else:
            if not file_obj.name in selected_names:
                selected_names.append(file_obj.name)
                selected_objs.append(file_obj)
    if len(file_obj_lst) != len(selected_objs):
        selected = True
    else:
        selected = False
    return selected_objs, selected


def alhpabet_lst() -> List[str]:
    return [''] + list(string.ascii_uppercase)


def _help_input_files() -> str:
    message = """
    Help message:  
    ここにはGNSS測量してきたデータを入力します。  
    xxx_way-point.gpx フォーマットのデータを入れましょう。  
    ・Browse files を使用してフォルダから  
    ・ドラッグ＆ドロップで  
    """
    return message

def input_files() -> Dict[str, List[Any]]:
    """LocalPCからファイルを読み込みメモリに保存"""
    sort_col = DrgGpxConfs().pt_datetime_col_jn
    # ファイルの読み込み.
    st.markdown('## 測量データを読み込む')
    files = st.file_uploader(
        label='xxx_way-point.gpxのファイルを入力', 
        accept_multiple_files=True,
        help=_help_input_files()
    )
    format_checker('.gpx', files)
    # ファイル名が一意かの確認
    files, selected = select_unique_file(files)
    if selected:
        st.markdown('同名のファイルがあります。削除して下さい')
    if 2 <= len(files):
        # 複数ファイルの場合
        prepro_confs = []
        for i, file in enumerate(files):
            prepro_conf = input_prepro_confs(file, i)
            prepro_confs.append(prepro_conf)
    elif files:
        # 単一ファイルの場合
        prepro_confs = [
            input_prepro_confs(files[0], 0)
        ]
    else:
        prepro_confs = [
            dict(
                file_name='',
                file_idx=1,
                group_name='',
                sort_col=sort_col,
                sort_type=False
            )
        ] 
    return dict(files=files, prepro_confs=prepro_confs)


def input_prepro_confs(file: UploadedFile, idx: int) -> List[Dict[str, Any]]:
    """ファイル別のカテゴリー値を入力するフォームを作成（ファイル毎）"""
    # streamlitでは同じlabelのObjectを作成出来ないのでspaceで長くする
    add = ' ' * idx
    file_name = file.name.replace('_way-point.gpx', '')
    expander = st.expander(file_name + add)
    # ファイル番号を入力させる
    file_idx = expander.number_input('ファイル番号' + add, value=idx + 1)
    # グループ名をアルファベットで入力させる
    group_name = expander.selectbox('班名' + add, alhpabet_lst(), index=idx + 1)
    # 並び替えに使用する要素を選択させる
    sort_cols = ['測定終了日時', '測点番号', '測点名']
    sort_col = (
        expander
        .selectbox(
            '並び替え列' + add, 
            sort_cols, 
            index=2
        )
    )
    # 並び替えの方法を選択させる
    sort_types = ['昇順', '降順']
    sort_type = expander.selectbox('並び替え' + add, sort_types, index=0)
    if sort_type == '昇順':
        sort_type = False
    else:
        sort_type = True
    return dict(
        file_name=file_name,
        file_idx=file_idx,
        group_name=group_name,
        sort_col=sort_col,
        sort_type=sort_type
    )
   

def add_project_confs(being_sought: dict) -> List[Dict[str, Any]]:
    """追加情報の入力フォーム作成"""
    # 現在の年度を計算する
    st.markdown("""---""")
    st.markdown('## 追加情報の入力 ')
    if not being_sought is None:
        first = dict(
        office=parse_zen2han(
            st.text_input('森林管理署:', value=being_sought.get('office'))
        ),
        branch_office=parse_zen2han(
            st.text_input('森林事務所:', value=being_sought.get('branch_office'))
        ),
        local_area=parse_zen2han(
            st.text_input('国有林:', value=being_sought.get('local_area'))
            )
        )
    else:
        first = dict(
        office=parse_zen2han(
            st.text_input('森林管理署:', placeholder='青森')
        ),
        branch_office=parse_zen2han(
            st.text_input('森林事務所:', placeholder='三厩')
        ),
        local_area=parse_zen2han(
            st.text_input('国有林:', placeholder='増川山')
            )
        )
    second = dict(
        address=parse_zen2han(
            st.text_input('林小班:', placeholder='871い1')
        ),
        year=st.number_input('事業年度:', value=the_current_fiscal_year()),
        project_name=parse_zen2han(
            st.text_input('事業名:', placeholder='青森1-1')
        ),
        person=parse_zen2han(
            st.text_input('測量者:', placeholder='〇〇 〇〇')
        ),
    )
    return dict(**first, **second)


def survey_area_confs(add_key: int=None, expander: st.expander=None):
    """平面直角座標系に変換する為にEPSGコードを入力させるフォームの作成"""
    confs = WebAppConfs()
    if not add_key is None:
        add_key = add_key * ' '
    epsg_codes = confs.epsg_code_dict
    epsg_codes['EPSGを入力'] = None
    if expander:
        selected = expander.selectbox(f'測量場所{add_key}', options=list(epsg_codes.keys()))
        if selected == 'EPSGを入力':
            epsg = expander.number_input(f'EPSG code{add_key}', value=6678)
        else:
            code = epsg_codes.get(selected)
            epsg = expander.number_input(
                f'EPSG code{add_key}', value=code, min_value=code, max_value=code
            )
    else:
        st.markdown("""---""")
        st.markdown('## 測量地域を選択', help=confs.help_txt_epsg)
        selected = st.selectbox(f'測量場所{add_key}', options=list(epsg_codes.keys()))
        if selected == 'EPSGを入力':
            epsg = st.number_input(f'EPSG code{add_key}', value=6678)
        else:
            code = epsg_codes.get(selected)
            epsg = st.number_input(
                f'EPSG code{add_key}', value=code, min_value=code, max_value=code
            )
    return dict(epsg=epsg)


def threshold_confs():
    """精度を保証する為の閾値パラメータを設定する"""
    txt = WebAppConfs().help_txt_acc_thres
    st.markdown("""---""")
    st.markdown('## 精度保証の閾値パラメーター', help=txt)
    expander = st.expander('詳細設定')
    results = dict(
        thres_epochs=expander.number_input('平均化測点数: n点以上ならOK', value=10),
        thres_pdop=expander.number_input('PDOP: n以下ならOK', value=4.0, step=0.1),
        thres_sats=expander.number_input('衛星数: n以上ならOK', value=4)
    )
    return results 


def spatial_search(file: UploadedFile):
    jn_confs = JnDataCols()
    df = pd.read_xml(copy.deepcopy(file))
    mu_x = df['lon'].mean()
    mu_y = df['lat'].mean()
    point = shapely.geometry.Point(mu_x, mu_y)
    if st.session_state.get('spatial_index') is None:
        fp = r'apps/settings/local_area.geoparquet'
        st.session_state['spatial_index'] = gpd.read_parquet(fp)
    
    gdf = st.session_state.get('spatial_index')
    row = gdf[point.intersects(gdf.geometry)].copy()
    series = row.iloc[0]
    if 1 <= row.shape[0]:
        return {
            'office': series[jn_confs.office_col], 
            'branch_office': series[jn_confs.branch_office_col], 
            'local_area': series[jn_confs.lcoal_area_col]
        }
    else:
        return None



def run_sidebar():
    # SideBarの作成
    with st.sidebar:
        # ファイルアップローダー
        res = input_files()
        files = res.get('files')
        prepro_confs = res.get('prepro_confs')
        if files:
            try:
                being_sought = spatial_search(files[0])
            except Exception as _:
                being_sought = None
            # 追加情報の入力
            project_confs = add_project_confs(being_sought)
            # 測量結果を閉合するか
            st.markdown("""---""")
            
            idx = st.session_state.get('spatial_index')
            st.markdown(f"Type: {type(idx)}, Size: {idx}")
            _gdf = gpd.read_parquet(r'apps/settings/local_area.geoparquet')
            st.markdown(type(_gdf))
            st.markdown(_gdf.shape)

            st.markdown("## 測量結果の閉合", help='このチェックボックスを外す事で閉合しないデータを出力します。')
            expander = st.expander('設定')
            close = expander.checkbox('閉合する', True)
            # EPSGコードの入力
            epsg_conf = survey_area_confs()
            # 精度保証の閾値パラメーター設定
            thres_confs = threshold_confs()
            # ファイルが入力されたら
            resps = []
            for file, prepro_conf in zip(files, prepro_confs):
                d = dict(uploaded_file=file)
                data = dict(
                    d, **prepro_conf, **project_confs,
                    **epsg_conf, **thres_confs
                )
                data['poly_close'] = close
                res = SideBarResponse(**data)
                resps.append(res)
            return resps
        
