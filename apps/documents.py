from bs4 import BeautifulSoup
import os

from matplotlib import pyplot as plt
import streamlit as st
from streamlit.delta_generator import DeltaGenerator


class Documents(object):
    def __init__(self):
        self.soup_html = self._html_parser
    
    @property
    def _html_parser(self) -> BeautifulSoup:
        fp = r'././views/documents.html'
        with open(fp, mode='r', encoding='utf-8') as f:
            html = f.read()
            soup = BeautifulSoup(html, 'html.parser')
        return soup
    
    def select_short_html(self, _id: str) -> str:
        return self.soup_html.find('div', id=_id)
    
    @property
    def show_simple_surveying_doc(self):
        html = self.select_short_html('simple_surveying_doc')
        st.markdown(html, unsafe_allow_html=True)
    
    @property
    def show_multiple_surveying_doc(self):
        html = self.select_short_html('multiple_surveying_doc')
        st.markdown(html, unsafe_allow_html=True)
        img_file = r'././views/images/sort_img.jpg'
        img = plt.imread(img_file)
        fig, ax = plt.subplots(figsize=(6, 5), dpi=400)
        ax.imshow(img)
        ax.set_axis_off()
        st.pyplot(fig)

    @property
    def show_revision_doc(self):
        html = self.select_short_html('revision_doc')
        st.markdown(html, unsafe_allow_html=True)

    @property
    def show_create_map_doc(self):
        html = self.select_short_html('create_map_doc')
        st.markdown(html, unsafe_allow_html=True)
    
    @property
    def show_marge_doc(self):
        html = self.select_short_html('marge_doc')
        st.markdown(html, unsafe_allow_html=True)
    
    @property
    def show_warning_dta(self):
        html = self.select_short_html('warning_dta')
        st.markdown(html, unsafe_allow_html=True)

    @property
    def show_warning_kml(self):
        html = self.select_short_html('warning_kml')
        st.markdown(html, unsafe_allow_html=True)

    @property
    def show_output_data_doc(self):
        html = self.select_short_html('output_data_doc')
        st.markdown(html, unsafe_allow_html=True)
    
    @property
    def show_sync_doc(self):
        html = self.select_short_html('sync_doc')
        st.markdown(html, unsafe_allow_html=True)
    
    @property
    def show_semidyna_doc(self):
        html = self.select_short_html('semidyna_doc')
        st.markdown(html, unsafe_allow_html=True)


class Summary(object):
    def __init__(self):
        self.dir_name = '././views/'
        self.soup_html = self._html_parser
    
    @property
    def _html_parser(self) -> BeautifulSoup:
        fp = r'././views/summary.html'
        with open(fp, mode='r', encoding='utf-8') as f:
            html = f.read()
            soup = BeautifulSoup(html, 'html.parser')
        return soup

    def select_short_html(self, _id: str) -> str:
        return self.soup_html.find('div', id=_id)

    @property
    def show_main_page_summary(self):
        html = self.select_short_html('main_page_summary')
        st.markdown(html, unsafe_allow_html=True)

    @property
    def show_unsuccessful_connect_internet(self):
        # インターネット接続失敗の際に表示させる
        html = self.select_short_html('unsuccessful_connect_internet')
        st.markdown(html, unsafe_allow_html=True)

    @property
    def show_edit_table_summary(self):
        html = self.select_short_html('edit_table_summary')
        st.markdown(html, unsafe_allow_html=True)

    @property
    def show_wgs84_summary(self):
        # WGS84の座標系に関する概要を表示させる
        html = self.select_short_html('wgs84_summary')
        st.markdown(html, unsafe_allow_html=True)
    
    @property
    def show_local_mercator_summary(self):
        # 平面直角座標系に関する概要を表示させる
        html = self.select_short_html('local_mercator_summary')
        st.markdown(html, unsafe_allow_html=True)
    
    @property
    def show_web_mercator_summary(self):
        # Webメルカトルに関する概要を表示させる
        html = self.select_short_html('web_mercator_summary')
        st.markdown(html, unsafe_allow_html=True)
    
    @property
    def show_marge_geojson_summary(self):
        html = self.select_short_html('marge_geojson_summary')
        st.markdown(html, unsafe_allow_html=True)
    
    @property
    def show_select_language_summary(self):
        st.markdown('<br>', unsafe_allow_html=True)
        st.markdown('##### 出力するGISデータの列名を英語にする')
        st.markdown('<hr style="margin: 0px; border: 3px solid #008899">', True)
        expander = st.expander('なぜ英語で出力する選択肢が必要なのか')
        html = self.select_short_html('select_language_summary')
        expander.markdown(html, unsafe_allow_html=True)
        return expander

    @property
    def show_download_xls_summary(self) -> DeltaGenerator:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('### 📝 測量野帳のダウンロード')
        st.markdown('<hr style="margin: 0px; border: 3px solid #008899">', True)
        expander = st.expander('測量野帳はどんなデータ？')
        html = self.select_short_html('download_excel_summary')
        expander.markdown(html, unsafe_allow_html=True)
        return expander
    
    @property
    def show_download_dta_summary(self) -> DeltaGenerator:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('### 📝 DTAファイルのダウンロード')
        st.markdown('<hr style="margin: 0px; border: 3px solid #008899">', True)
        expander = st.expander('DTAってどんなデータ？')
        html = self.select_short_html('download_dta_summary')
        expander.markdown(html, unsafe_allow_html=True)
        return expander
    
    @property
    def show_download_geojson_summary(self) -> DeltaGenerator:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('### 📝 GeoJSONファイルのダウンロード')
        st.markdown('<hr style="margin: 0px; border: 3px solid #008899">', True)
        expander = st.expander('GeoJSONってどんなデータ？')
        html = self.select_short_html('download_geojson_summary')
        expander.markdown(html, unsafe_allow_html=True)
        return expander
    
    @property
    def show_download_kml_summary(self) -> DeltaGenerator:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('### 📝 KMLファイルのダウンロード')
        st.markdown('<hr style="margin: 0px; border: 3px solid #008899">', True)
        expander = st.expander('KMLってどんなデータ？')
        html = self.select_short_html('download_kml_summary')
        expander.markdown(html, unsafe_allow_html=True)
        return expander

    @property
    def show_marge_dta_summary(self):
        html = self.select_short_html('marge_dta_summary')
        st.markdown(html, unsafe_allow_html=True)

    @property
    def show_mapping_pdf_summary(self):
        html = self.select_short_html('mapping_pdf_summary')
        st.markdown(html, unsafe_allow_html=True)

    @property
    def show_sync_summary(self):
        html = self.select_short_html('sync_summary')
        st.markdown(html, unsafe_allow_html=True)

    def show_input_geoj1(self, expander: DeltaGenerator) -> DeltaGenerator:
        html = self.select_short_html('upload_geoj1')
        expander.markdown(html, unsafe_allow_html=True)
        return expander

    def show_input_geoj2(self, expander: DeltaGenerator) -> DeltaGenerator:
        html = self.select_short_html('upload_geoj2')
        expander.markdown(html, unsafe_allow_html=True)
        return expander


class CheatSheet(object):
    def __init__(self):
        documents = Documents()
        page = st.selectbox('表示する説明を選択して下さい', self.page_list)
        if page == '1つのファイルから一筆書きのデータを作成する':
            documents.show_simple_surveying_doc
        elif page == '複数のファイルから一筆書きのデータを作成する':
            documents.show_multiple_surveying_doc
        elif page == '出力データの概要':
            documents.show_output_data_doc
        elif page == '測点名の命名規則と測点の修正':
            documents.show_revision_doc
        elif page == '実測図の作成':
            documents.show_create_map_doc
        elif page == '複数のGeoJSONファイルを結合する':
            documents.show_marge_doc
        elif page == 'DTAファイルの注意点':
            documents.show_warning_dta
        elif page == 'KMLファイルの注意点':
            documents.show_warning_kml
        elif page == '実測データの共有':
            documents.show_sync_doc
        elif page == 'セミダイナミック補正とは':
            documents.show_semidyna_doc

    @property
    def page_list(self):
        lst = [
            'Droggerでの測量方法',
            '1つのファイルから一筆書きのデータを作成する',
            '複数のファイルから一筆書きのデータを作成する',
            '出力データの概要',
            '測点名の命名規則と測点の修正',
            '実測図の作成',
            '複数のGeoJSONファイルを結合する',
            'DTAファイルの注意点',
            'KMLファイルの注意点',
            '実測データの共有',
            'セミダイナミック補正とは'
        ]
        return lst