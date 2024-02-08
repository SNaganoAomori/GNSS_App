from dataclasses import dataclass
import datetime
import json
import time
from typing import Any, Dict, List

import arcgis
from arcgis.gis import GIS
from arcgis.gis import Item
from arcgis.features import FeatureLayer
from arcgis.features.feature import FeatureSet
import folium
import geopandas as gpd
import streamlit as st
from streamlit.delta_generator import DeltaGenerator
from streamlit.runtime.uploaded_file_manager import UploadedFile
from streamlit_folium import st_folium
from streamlit_folium import folium_static
import pandas as pd

from apps.documents import Summary
from apps.exception import count_data_rows
from apps.exception import format_checker
from apps.settings.configs import check_lang_jn_in_df
from apps.settings.configs import rename_en_to_jn_in_df
summary = Summary()


class SignIn(object):
    def __init__(self):
        self._url = 'https://www.arcgis.com'

    @property
    def _input_account(self) -> Dict[str, str]:
        st.markdown('<br>', True)
        st.markdown('### サインイン')
        st.markdown('<hr style="margin: 0px; border: 3px solid #008899">', True)
        expander = st.expander('アカウント情報の入力')
        expander.markdown("""データをアップロードする為にはArcGIS Onlineのアカウントが必要です。普段自分でFieldMapsを使用する際に使っているアカウントの名前とパスワードを入力して下さい。""")
        user_name = expander.text_input('アカウント名')
        passward = expander.text_input('パスワード')
        return {'user_name': user_name, 'passward': passward, 'expander': expander}
            
    def _check_user_name(self, user_name: str) -> bool:
        request = True
        if st.session_state.get('user_name') is None:
            if user_name != '':
                request = True
        elif st.session_state.get('user_name') == user_name:
            if st.session_state.get('gis') is None:
                request = True
            elif st.session_state.get('gis') != arcgis.gis.GIS:
                request = True
        if request:
            st.session_state['user_name'] = user_name
        return request
    
    def _check_passward(self, passward: str) -> bool:
        request = True
        if st.session_state.get('passward') is None:
            if passward != '':
                request = True
        elif st.session_state.get('passward') == passward:
            if st.session_state.get('gis') is None:
                request = True
            elif st.session_state.get('gis') != arcgis.gis.GIS:
                request = True
        if request:
            st.session_state['passward'] = passward
        return request

    @property
    def _sign_in(self) -> arcgis.gis.GIS:
        try:
            user_name = st.session_state.get('user_name')
            passward = st.session_state.get('passward')
            gis = arcgis.GIS(self._url, user_name, passward)
        except Exception as e:
            return e
        else:
            return gis
    
    @property
    def sign_in_arcgis_online(self):
        inputs = self._input_account
        success = False
        error = False
        user_name = inputs.get('user_name')
        passward = inputs.get('passward')
        expander = inputs.get('expander')
        if expander.button('サインインする', type='primary'):
            if self._check_user_name(user_name) & self._check_passward(passward):
                placeholder = expander.empty()
                placeholder.warning('サインインしています。10～20秒程掛かります。')
                st.session_state['gis'] = self._sign_in
                placeholder.empty()
                if isinstance(st.session_state.get('gis'), GIS):
                    success = True
                else:
                    error = True
            elif isinstance(st.session_state.get('gis'), GIS):
                success = True
            else:
                error = True
        elif isinstance(st.session_state.get('gis'), GIS):
            success = True
        if st.session_state.get('gis'):
            if success:
                st.success('サインインに成功しました。', icon='😀')
            if error:
                st.error(
                    f"""
                    Error Message:  
                    サインインに失敗しました。  
                    失敗が複数回続くと暫くサインイン出来なくなります。
                    >>> user name: {user_name}, passward: {passward}  
                    >>> {st.session_state.get('gis')}  
                    """,
                    icon='😢'
                )

@dataclass
class Datasets:
    gis: arcgis.gis.GIS = None
    db_item: arcgis.gis.Item = None
    db_layer: arcgis.features.layer.FeatureLayer = None
    db_feat_set: arcgis.features.feature.FeatureSet = None
    db_sdf: pd.DataFrame = None


class RequestsItems(Datasets):
    def __init__(self):
        super().__init__()
        if isinstance(st.session_state.get('gis'), GIS):
            self.gis: arcgis.gis.GIS = st.session_state.get('gis')
        else:
            self.gis = None
    

    def _search_item_name(self, search: str) -> List[arcgis.gis.Item]:
        # 複数のアイテムを検索します
        items = self.gis.content.search(search)
        if items:
            return items
        else:
            e = f"{search} を検索しましたが見つかりませんでした。"
            st.warning(e)
            return None
    
    def __timedelta(self, series: pd.Series):
        ts = pd.to_datetime(series) + datetime.timedelta(hours=9)
        strings = ts.dt.strftime("%Y-%m-%d %H:%M")
        return ts

    def _show_table(self, item: Item, office: str, expander: DeltaGenerator):
        where_clause = f"office = '{office}'"
        sdf = None

        if (office != '') & (not office is None):
            lyr = item.layers[0]
            feature = lyr.query(where_clause)
            sdf = feature.sdf
        if not sdf is None:
            if 1 <= sdf.shape[0]:
                # 日本語に直す為の辞書を作成
                fields = {}
                for field in feature.fields:
                    fields[field.get('name')] = field.get('alias')
                # geometryを文字列で見れる様に
                sdf['SHAPE'] = sdf['SHAPE'].astype('string')
                sdf['CreationDate'] = self.__timedelta(sdf['CreationDate'])
                sdf['EditDate'] = self.__timedelta(sdf['EditDate'])
                expander.dataframe(sdf.rename(columns=fields))
            else:
                expander.warning('データがありません。')
        elif (office == '') | (office is None):
            expander.warning('森林管理署名を入力して下さい。')
        else:
            expander.warning('データがありません。')



    def _show_summary(self, item: Item):
        url_base = 'https://jff-aomori.maps.arcgis.com/home/item.html?id='
        expander = st.expander(f"{item.title}の詳細確認", True)
        expander.markdown("#### アイテムのURL")
        expander.markdown(f"{url_base}{item.id}")

        expander.markdown("#### データの概要")
        expander.markdown(item.snippet)
        expander.markdown("#### データの説明")
        expander.markdown(item.description, True)
        expander.markdown("#### ID")
        expander.markdown(item.id)
        expander.markdown("#### テーブルデータ")
        if expander.toggle('テーブルデータの表示'):
            office = expander.text_input('森林管理署名で絞り込み', placeholder="青森")
            self._show_table(item, office, expander)

    def select_search_items(self, search: str) -> arcgis.gis.Item:
        if search == '':
            return None
        items = [
            item
            for item in self._search_item_name(search)
            if item.type == 'Feature Service'
        ]
        if items:
            checks = []
            expander = st.expander('ファイルを追加したいアイテムを選んで下さい。')
            expander.markdown("""
            <p>ポリゴンデータ = GNSS Polygon</p>
            <p>ラインデータ = GNSS Line</p>
            """, True)
            for i, item in enumerate(items):
                check = expander.checkbox(f"{i+1}: {item.title}")
                checks.append(check)
            if sum([1 for check in checks if check]) == 1:
                item = [data for check, data in zip(checks, items) if check][0]
                self.db_item = item
                st.success(f'{item.title}を選択しています。')
                self._show_summary(item)
            else:
                e = f"チェックは1つだけに入れて下さい。"
                st.warning(e)
        else:
            e = f"検索に引っ掛かりませんでした。ArcGIS Onlineのコンテンツを調べて下さい。"
            st.warning(e)
                   
    def search_item_id(self, item_id: str) -> arcgis.gis.Item:
        if item_id:
            item = self.gis.content.get(item_id)
            if item:
                self.db_item = item
                st.success(f'{item.title}を選択しています。')
            else:
                e = f"検索に引っ掛かりませんでした。ArcGIS Onlineのコンテンツを調べて下さい。"
                st.warning(e)

    def update_db_item(func):
        def wrapper(self):
            if isinstance(self.db_item, Item):
                in_session = st.session_state.get('db_item')
                if (in_session is None):
                    st.session_state['db_item'] = self.db_item
                elif isinstance(in_session, Item):
                    if self.db_item.title != in_session.title:
                        st.session_state['db_item'] = self.db_item
            func(self)
        return wrapper

    @property
    @update_db_item
    def get_db_layer(self):
        layer = self.db_item.layers[0]
        self.db_layer = layer
        st.session_state['db_layer'] = layer

    @property
    def update_datasets(self):
        session = st.session_state
        if self.db_item:
            calc = False
            if session.get('db_item') is None:
                calc = True
            elif self.db_item.title != session.get('db_item').title:
                calc = True
            if calc:
                self.get_db_layer
                session['db_layer'] = self.db_layer
                feats = self.db_layer.query()
                session['db_feat_set'] = feats
                session['db_sdf'] = feats.sdf

        

def search_item():
    st.markdown('<br>', True)
    st.markdown('### アイテム検索')
    st.markdown('<hr style="margin: 0px; border: 3px solid #008899">', True)
    req_items = RequestsItems()
    expander = st.expander('アイテムを検索します。')
    search_is_name = expander.toggle('名前で検索', True)
    if search_is_name:
        select = expander.selectbox('デフォルトの候補から選ぶ', ['', 'GNSS_Polygon', 'GNSS_Line'])
        if select == '':
            search = expander.text_input('検索名を入力する', placeholder='GNSS_Polygon などで検索')
        else:
            search = expander.text_input('検索名を入力する', value=select)
        req_items.select_search_items(search)
    else:
        item_id = expander.text_input('アイテムIDを入力する')
        req_items.search_item_id(item_id)
    req_items.update_datasets
        
        
def uploder() -> UploadedFile:
    st.markdown('<br>', True)
    st.markdown('### GeoJSONデータの入力')
    st.markdown('<hr style="margin: 0px; border: 3px solid #008899">', True)
    expander = st.expander(
        ' GeoJSONファイルのアップロード',
        expanded=True
    )
    file = expander.file_uploader(
        label='"ポリゴン"か"ライン"のファイルを入れて下さい。', 
        accept_multiple_files=False,
        help='GeoJSONファイルを入力して下さい。'
    )
    if not file is None:
        format_checker('.geojson', file)
    return file, expander


def select_geom_rows(gdf: gpd.GeoDataFrame, poly=True) -> gpd.GeoDataFrame:
    """
    列名を日本語に変更してから
    GeoDataFrameからMultiPolygonとPolygonの行のみ取り出す
    Args:
        gdf(GeoDataFrame): 
    Returns:
        gdf(GeoDataFrame): 
    """
    # 列名の変更
    is_jn = check_lang_jn_in_df(gdf)
    if is_jn == False:
        gdf = rename_en_to_jn_in_df(gdf)
    # Polygonの取り出し
    if poly:
        select = ['MultiPolygon', 'Polygon']
    else:
        select = ['LineString', 'MutiLineString']
    is_poly = []
    for gtype in gdf.geometry.type.to_list():
        if gtype in select:
            is_poly.append(True)
        else:
            is_poly.append(False)
    return gdf.loc[is_poly]



class SyncData(object):
    def __init__(self):
        self.session = st.session_state
        self.db_layer = self.session.get('db_layer')
        self.db_feat_set = self.session.get('db_feat_set')
        self.db_sdf = self.session.get('db_sdf')
    
    @property
    def db_feat_epsg(self) -> int:
        if self.db_feat_set:
            return self.db_feat_set.spatial_reference.get('latestWkid')
        else:
            return None

    def reprojection_input_gdf(self, gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        original_epsg = self.db_feat_epsg
        if gdf.crs.to_epsg() != original_epsg:
            gdf = gdf.to_crs(crs=f'EPSG:{original_epsg}')
        return gdf

    def disassembly_fields(self, key: str='name', value: str='alias') -> Dict[str, str]:
        """
        FeatureSetオブジェクトから取得出来るfieldsの中から必要なデータを辞書として
        取り出す。key, value 両方とも以下の辞書のkeyから選ぶ。
        {
            'name': 'OBJECTID',
            'type': 'esriFieldTypeOID',
            'alias': 'OBJECTID',
            'sqlType': 'sqlTypeOther',
            'domain': None,
            'defaultValue': None
        }
        """
        # Dict[FieldName, AliasName]
        if self.db_feat_set is None:
            return None
        fields = {}
        for field in self.db_feat_set.fields:
            fields[field.get(key)] = field.get(value)
        return fields

    def _check_df_columns(self, in_sdf: pd.DataFrame) -> Dict[str, List[str]]:
        db_columns = self.db_sdf.columns
        in_columns = in_sdf.columns
        not_included_db = []
        not_included_in = []
        for col in in_columns:
            if not col in db_columns:
                not_included_db.append(col)
        for col in db_columns:
            if not col in in_columns:
                not_included_in.append(col)
        exclude_lst = ['OBJECTID', 'Shape__Area', 'Shape__Length']
        for exclude in exclude_lst:
            if exclude in not_included_db:
                not_included_db.remove(exclude)
            if exclude in not_included_in:
                not_included_in.remove(exclude)
        return {
            'not_included_db': not_included_db, 
            'not_included_in': not_included_in
        }

    def cast_in_dataframe(self, in_sdf: pd.DataFrame) -> pd.DataFrame:
        # in_sdfからdb_sdfにない列を削除する
        not_ins = self._check_df_columns(in_sdf)
        if not_ins.get('not_included_db'):
            # 入力したデータにあるが、DBに無い列を消すか決める
            expander = st.expander('元データに存在しない列があります。')
            expander.markdown(f"列名: {not_ins.get('not_included_db')}")
            if expander.toggle('削除しますか？'):
                in_sdf = in_sdf.drop(not_ins.get('not_included_db'), axis=1)
            else:
                e = '❌ アップロードしたい場合はArcGIS Onlineにある元データにFieldを追加して下さい'
                raise UserWarning(e)
        # 列ごとにCloudのデータと同じ型に変換する
        sdf = in_sdf.copy()
        columns = sdf.columns
        for key, val in self.db_sdf.dtypes.to_dict().items():
            if key in columns:
                sdf[key] = sdf[key].astype(val)
        return sdf

    def query_same_address(
        self, 
        in_sdf: pd.DataFrame, 
        office: str='office', 
        address: str='address'
    ) -> pd.DataFrame:
        office_lst = in_sdf[office].unique()
        address_lst = in_sdf[address].unique()
        db_sdf = self.db_sdf[self.db_sdf[office].isin(office_lst)].copy()
        db_sdf = db_sdf[db_sdf[address].isin(address_lst)].copy()
        if 1 <= db_sdf.shape[0]:
            return db_sdf
        return None
    
    def _en_to_jn_sdf(self, sdf: pd.DataFrame) -> pd.DataFrame:
        rename_dict = self.disassembly_fields('name', 'alias')
        return sdf.rename(columns=rename_dict)

    def _jn_to_en_sdf(self, sdf: pd.DataFrame) -> pd.DataFrame:
        rename_dict = self.disassembly_fields('alias', 'name')
        return sdf.rename(columns=rename_dict)



def read_geojson(file: UploadedFile, expander):
    # GeoJSONを読み込み投影変換とデータ型変換を行い、列名を合わせる
    if file is None:
        return None
    gdf = gpd.read_file(file)
    poly_gdf = select_geom_rows(gdf, poly=True)
    line_gdf = select_geom_rows(gdf, poly=False)
    if (1 <= poly_gdf.shape[0]) & (1 <= line_gdf.shape[0]):
        expander.markdown('ポリゴンとラインの両方があります。')
        if expander.toggle('ポリゴンを選択する', True):
            gdf = poly_gdf
        else:
            gdf = line_gdf
    elif 1 <= poly_gdf.shape[0]:
        gdf = poly_gdf
        st.success('ポリゴンのデータが読み込まれています。')
    elif 1 <= line_gdf.shape[0]:
        gdf = line_gdf
        st.success('ラインのデータが読み込まれています。')
    else:
        gdf = None
    if not gdf is None:
        count_data_rows(gdf)
        sync_data = SyncData()
        rename_dict = sync_data.disassembly_fields('alias', 'name')
        gdf = (
            gdf
            .rename(columns=rename_dict)
            .dropna(axis=1)
        )
        in_sdf = pd.DataFrame.spatial.from_geodataframe(gdf)
        in_sdf = sync_data.cast_in_dataframe(in_sdf)
        return in_sdf
    else:
        message = """
        Error message:  
        データの中にポリゴンもラインも存在しません。
        """
        st.error(message)


class PlotLayers(object):
    def __init__(self):
        pass

    def cmaps(self, idx) -> str:
        colors = [
            '#ff0000', # 赤
            '#0000cc', # 青
            '#00cc00', # 緑
            '#cc00ff', # 紫
            '#00947a', # ターコイズ
            '#cc6600', # 茶
            '#ff0099', # ピンク
            '#00a1e9', # シアン
            '#5f6527', # オリーブ
        ] 
        return colors[idx]

    def _check(self, db_sdf: pd.DataFrame):
        save = False
        if st.session_state.get('plot_db_sdf') is None:
            save = True
        elif st.session_state.get('plot_db_sdf').iloc[:, : -1].equals(db_sdf.iloc[:, : -1]) == False:
            save = True
        if save:
            st.session_state['plot_db_sdf'] = db_sdf
        return True

    def select_columns_db_sdf(self, db_sdf: pd.DataFrame):
        if self._check(db_sdf):
            epsg = (
                st
                .session_state
                .get('db_feat_set')
                .spatial_reference
                .get('latestWkid')
            )
            selects = [
                'OBJECTID', 'end_datetime', 'CreationDate', 
                'points', 'area_ha', 'SHAPE'
            ]
            gdf = (
                gpd
                .GeoDataFrame(db_sdf)
                .set_geometry('SHAPE')
                .set_crs(crs=f"EPSG:{epsg}")
                .to_crs(crs='EPSG:4326')
                [selects]
            )
            gdf['end_datetime'] = pd.to_datetime(gdf['end_datetime']).dt.strftime('%Y-%m-%d %H:%M')
            gdf['CreationDate'] = (
                (gdf['CreationDate'] + datetime.timedelta(hours=9))
                .dt.strftime('%Y-%m-%d %H:%M')
                .astype('string')
            )
            st.session_state['plot_db_gdf'] = gdf
            return gdf
        else:
            return st.session_state.get('plot_db_gdf')
    
    def get_details(self, db_gdf):
        df = db_gdf.T.iloc[: -1].copy()
        idx = ['ID', '測定終了日時', 'アップロード日', '測点数', '面積(ha)']
        df.index = idx
        data = df.to_dict()
        sentence = "データの詳細"
        for key, val in data.items():
            sentence += f"<br>{key}: {val}"
        return sentence

    def add_plot_in_sdf(self, in_sdf: pd.DataFrame, _map: folium.Map):
        geom = (
            gpd
            .GeoDataFrame(in_sdf)
            .set_geometry('SHAPE')
            .geometry
            .__geo_interface__
        )
        geojson = folium.GeoJson(
            data=geom,
            name='追加予定のデータ',
            fill_color='black',
            color='black',
            weight=3,
        )
        geojson.add_to(_map)

    def plotter(self, db_sdf: pd.DataFrame, in_sdf: pd.DataFrame=None) -> DeltaGenerator:
        db_gdf = self.select_columns_db_sdf(db_sdf)
        m = folium.Map(
            location=[
                db_gdf.centroid.y.mean(), 
                db_gdf.centroid.x.mean()
            ], 
            zoom_start=13
        )
        self.add_plot_in_sdf(in_sdf, m)
        # GeoDataFrameの各行に対して、foliumのGeoJsonオブジェクトを作成する
        for i, row in db_gdf.iterrows():
            layer_name = f"ID: {row['OBJECTID']}"
            layer_name += f"<br>測定終了　　　: {row['end_datetime']}"
            layer_name += f"<br>アップロード日: {row['CreationDate']}"
            geojson = folium.GeoJson(
                row['SHAPE'].__geo_interface__, 
                name=layer_name,
                tooltip=self.get_details(row),
                fill_color=self.cmaps(i),
                color='black',
                weight=1,
                fill_opacity=0.7,
                legend_name='I'

            )
            geojson.add_to(m)
        # # レイヤーコントロールを追加する
        layer_control = (
            folium
            .LayerControl(
                position='topleft',
                collapsed=False
            )
            .add_to(m)
        )
        placeholder = st.empty()
        with placeholder.container():
            st_data = st_folium(m, height=500, width=800)
        return placeholder



class SyncExcution(object):
    def __init__(self, same_db_sdf: pd.DataFrame, in_sdf: pd.DataFrame):
        out_placeholder = st.empty()
        out_placeholder.warning('クラウドに同じ林小班のデータがあります。')
        plot_layers = PlotLayers()
        map_container = plot_layers.plotter(same_db_sdf, in_sdf)
        self.same_db_sdf = same_db_sdf
        self.in_sdf = in_sdf
        self.del_sdf = None
        self.del_excution = False
        self.add_excution = False
        self.close = False
        self.expander = (
            out_placeholder
            .expander(
                'クラウド内のデータを削除するか、そのまま追加するかを選択して下さい。', 
                True
            )
        )
        if self.expander.toggle('削除するデータのIDを選択する'):
            self.select_delete_rows
        else:
            self.select_adds
        self.response_expander = st.expander('通信結果')
        if self.del_excution:
            self.delete_excution_func
        if self.add_excution:
            self.add_excution_func
        if self.close:
            out_placeholder.empty()
            map_container.empty()
            st.success('データの追加が完了しました。')

    @property
    def select_delete_rows(self):
        del_ids = self.expander.multiselect(
            'マップを確認して削除するデータのIDを決めて下さい',
            options=self.same_db_sdf['OBJECTID'].to_list()
        )
        self.del_sdf = self.same_db_sdf[
            self.same_db_sdf['OBJECTID'].isin(del_ids)
        ].copy()
        if self.expander.toggle('削除データを確認します'):
            self.expander.dataframe(self.del_sdf.drop('SHAPE', axis=1))
            if self.expander.toggle('本当に削除しますか？'):
                self.del_excution = self.expander.button('削除', type='primary')

    @property
    def select_adds(self):
        self.expander.warning('クラウド内のデータを削除せずに、新たなデータを追加します。')
        if self.expander.toggle('追加しますが問題ありませんか？'):
            self.add_excution = self.expander.button('追加', type='primary')

    @property
    def delete_excution_func(self):
        placeholder = self.expander.empty()
        placeholder.warning('データを削除中です')
        resps = (
            st
            .session_state
            .get('db_layer')
            .edit_features(deletes=self.del_sdf)
        )
        self.response_expander.write(resps)
        placeholder.empty()
        self.add_excution = True

    @property
    def add_excution_func(self):
        placeholder = self.expander.empty()
        placeholder.warning('データを追加中です')
        resps = (
            st
            .session_state
            .get('db_layer')
            .edit_features(adds=self.in_sdf)
        )
        placeholder.empty()
        self.response_expander.write(resps)
        self.close = True


def simple_add_data(in_sdf: pd.DataFrame):
    close = False
    resps_expander = st.expander('通信結果')
    placeholder = st.empty()
    expander = placeholder.expander('問題ないのでこのままデータを追加できます。')
    if expander.toggle('データを追加しますか？'):
        if expander.button('データ追加'):
            expander.warning('データを追加しています。')
            resps = st.session_state.get('db_layer').edit_features(adds=in_sdf)
            close = True
    if close:
        st.success('データを追加しました。')
        placeholder.empty()
        resps_expander.write(resps)


def sync_cloud_page():
    summary.show_sync_summary
    sign_in = SignIn()
    sign_in.sign_in_arcgis_online
    if isinstance(st.session_state.get('gis'), GIS):
        search_item()
    if isinstance(st.session_state.get('db_feat_set'), FeatureSet):
        sync_data = SyncData()
        file, expander = uploder()
        in_sdf = read_geojson(file, expander)
        if not in_sdf is None:
            same_db_sdf = sync_data.query_same_address(in_sdf)
            if not same_db_sdf is None:
                sync_exe = SyncExcution(same_db_sdf, in_sdf)
            if same_db_sdf is None:
                st.success('クラウドには同じ林小班のデータがありません。')
                simple_add_data(in_sdf)
                
        
        
