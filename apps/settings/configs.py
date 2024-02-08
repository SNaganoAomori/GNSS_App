from dataclasses import dataclass
import datetime
from typing import Any
from typing import Dict
from typing import List
from typing import Union
from typing import overload

import pandas as pd
import polars as pl
import yaml


conf_file_path = r'apps\settings\configs.yaml'

global CONF_FILE

with open(conf_file_path, mode='r', encoding='utf-8') as f:
    CONF_FILE = yaml.safe_load(f)


class JnDataCols(object):
    def __init__(self):
        self.confs =CONF_FILE['on_drogger']
    
    @property
    def start_datetime_col(self) -> str:
        return self.confs['use_cols']['start']

    @property
    def datetime_col(self) -> str:
        return self.confs['use_cols']['end']
    
    @property
    def pt_number_col(self) -> str:
        return self.confs['use_cols']['pt_num']
    
    @property
    def pt_name_col(self) -> str:
        return self.confs['use_cols']['pt_name']

    @property
    def lon_col(self) -> str:
        return self.confs['use_cols']['longitude']

    @property
    def lat_col(self) -> str:
        return self.confs['use_cols']['latitude']

    @property
    def epochs_col(self) -> str:
        return self.confs['use_cols']['epochs']
    
    @property
    def pdop_col(self) -> str:
        return self.confs['use_cols']['pdop']
    
    @property
    def satellites_col(self) -> str:
        return self.confs['use_cols']['satellites']
    
    @property
    def signal_frec_col(self) -> str:
        return self.confs['use_cols']['signal_frecuencies']
    
    @property
    def hstd_col(self) -> str:
        return self.confs['use_cols']['std_h']
    
    @property
    def vstd_col(self) -> str:
        return self.confs['use_cols']['std_v']
    
    @property
    def epsg_col(self) -> str:
        return self.confs['use_cols']['projective_technique_epsg']

    @property
    def y_col(self) -> str:
        return self.confs['use_cols']['transformed_y(lon)']

    @property
    def x_col(self) -> str:
        return self.confs['use_cols']['transformed_x(lat)']
    
    @property
    def office_col(self) -> str:
        return '森林管理署'
    
    @property
    def branch_office_col(self) -> str:
        return '森林事務所'
    
    @property
    def lcoal_area_col(self) -> str:
        return '国有林名'
    
    @property
    def address_col(self) -> str:
        return '林小班'
    
    @property
    def person_col(self) -> str:
        return '測量者名'
    
    @property
    def reciver_col(self) -> str:
        return '測定機器'



class DrgGpxConfs(object):
    """configs.yamlファイルで設定している情報を取得"""
    def __init__(self):
        self.conf = CONF_FILE['on_drogger']
    
    @property
    def pt_datetime_col(self) -> str: 
        return CONF_FILE['point_datetime_col']

    @property
    def pt_number_col(self) -> str: 
        return CONF_FILE['point_number_col']

    @property
    def pt_name_col(self) -> str: 
        return CONF_FILE['point_name_col']
    
    @property
    def pt_datetime_col_jn(self) -> str: 
        return CONF_FILE['point_datetime_col_jn']

    @property
    def pt_number_col_jn(self) -> str: 
        return CONF_FILE['point_number_col_jn']

    @property
    def pt_name_col_jn(self) -> str: 
        return CONF_FILE['point_name_col_jn']
    
    @property
    def start_time_col(self) -> str:
        return self.conf['start_col']
    
    @property
    def end_time_col(self) -> str:
        return self.conf['end_col']
    
    @property
    def signals_col(self) -> str:
        return self.conf['signals_name_col']
    
    @property
    def frecuencies_col(self) -> str:
        return self.conf['signal_frec_col']

    

    @property
    def original_cols_lst(self) -> List[str]:
        """.gpxファイルのオリジナルタグ名を取得"""
        return list(self.conf['original_cols'].keys())
    
    @property
    def rename_cols_lst_from_original(self) -> List[str]:
        """.gpxファイルのオリジナルタグ名から変更したい名称を取得"""
        return list(self.conf['original_cols'].values())
    
    @property
    def rename_original2use_dict(self) -> Dict[str, str]:
        """.gpxファイルのオリジナルタグ名と変更したい名称の辞書を取得"""
        return self.conf['original_cols']
    
    @property
    def use_cols_lst(self) -> List[str]:
        """
        .gpxファイルのオリジナルタグ名から変更後の名称で、使用したい名称のみの
        Listを取得
        """
        return list(self.conf['use_cols'].keys())

    @property
    def use_cols_jn_lst(self) -> List[str]:
        """
        .gpxファイルのオリジナルタグ名から変更後の名称で、使用したい名称のみの
        日本語Listを取得
        """
        return list(self.conf['use_cols'].values())
    
    @property
    def use_cols_dict(self) -> Dict[str, str]:
        """
        .gpxファイルのオリジナルタグ名から変更後の名称で、使用したい名称のみの
        英語と日本語の辞書を取得
        """
        return self.conf['use_cols']

    def convert_str2epsg(
        self, 
        coord_genaration: str, 
        projective_technique: str
    ) -> int:
        """
        GPXファイルに書かれているこの部分からEPSGコードを作成する。
        地殻変動補正されていない場合は、平面直角座標系で記録されて
        いても強制的にNoneを返す。
        <b:coordGenaration>JGD2011_R</b:coordGenaration>
			<b:coordinate_transform>
				<b:type>JPN10</b:type>
				<b:x>92432.8488</b:x>
				<b:y>-8801.0286</b:y>
			</b:coordinate_transform>
        """
        generations = self.conf['re_projective_name']
        if coord_genaration in generations:
            projects = generations.get(coord_genaration)
            if projective_technique in projects:
                return projects[projective_technique]
        else:
            return None

    @property    
    def coordinate_generation_col(self):
        return self.conf['generation_tags']['coord_genaration']
    
    @property    
    def projective_col(self):
        return self.conf['generation_tags']['projective_technique']
    
    @property    
    def transformed_x_col(self):
        return self.conf['generation_tags']['x']
    
    @property    
    def transformed_y_col(self):
        return self.conf['generation_tags']['y']
    
    @property
    def l1(self):
        return self.conf['signals']['L1']
    
    @property
    def l2(self):
        return self.conf['signals']['L2']
    
    @property
    def l5(self):
        return self.conf['signals']['L5']
    
    @property
    def datetime_fmt(self):
        return self.conf['datetime_fmt']



class ChiriinConfs(object):
    def __init__(self):
        self.conf = CONF_FILE['chiriin_param_files']
    
    @overload
    def date_to_semidyna_file_name(self, date: datetime.date) -> str: ...
    @overload
    def date_to_semidyna_file_name(self, date: datetime.datetime) -> str: ...
    @overload
    def date_to_semidyna_file_name(self, date: str) -> str: ...

    def date_to_semidyna_file_name(
        self, 
        date: Union[datetime.date, datetime.datetime, str]
    ) -> str:
        """
        データの日付からSemiDynamic補正に使用するParametaFileNameを作成する
        Args:
            date(datetime.date, datetime.datetime, str): fmt = '%Y-%m-%d'
        Returns:
            (str): パラメータファイル名
        """
        # 文字列でもdatetimeObjectでも受け付けられる様に
        if isinstance(date, str):
            try:
                # 文字列を日付として解析
                if 10 < len(date):
                    # datetimeの文字列を渡された場合
                    parsed_date = \
                        datetime.datetime.strptime(date[: 10], "%Y-%m-%d").date()
                else:
                    # dateの文字列を渡された場合
                    parsed_date = \
                        datetime.datetime.strptime(date, "%Y-%m-%d").date()
            except ValueError:
                raise ValueError("無効な日付形式です。有効な日付文字列（YYYY-MM-DD）を指定してください。")
        elif isinstance(date, datetime.datetime):
            parsed_date = date.date()
        elif isinstance(date, datetime.date):
            parsed_date = date
        else:
            raise ValueError("無効な日付形式です。")
        
        # 適用するパラメータファイルの年を選択
        if parsed_date.month <= 3:
            year = parsed_date.year - 1
        else:
            year = parsed_date.year
        # parametaファイルの文字列を作成
        param = self.conf['semidayna']['param_file_base']
        return param.replace('{YEAR}', str(year))
        

@dataclass
class CoordsCell:
    row: int
    column: int 


class ExcelTemplate(object):
    def __init__(self):
        self._confs = CONF_FILE['excel_templates']
        self.template_file = self._confs['file_path']


class XlsSummaryConfs(ExcelTemplate):
    def __init__(self):
        super().__init__()
        self._sheet = self._confs['main_sheet']
        self.cells = self._sheet['summary_cells']
    
    @property
    def sheet_name(self):
        """概要を入力するシート名の取得"""
        return self._sheet['sheet_name']
    
    @property
    def coords_office(self) -> CoordsCell:
        return CoordsCell(**self.cells['office'])
    
    @property
    def coords_branch_office(self) -> CoordsCell:
        return CoordsCell(**self.cells['branch_office'])
    
    @property
    def coords_local_area(self) -> CoordsCell:
        return CoordsCell(**self.cells['local_area'])
    
    @property
    def coords_address(self) -> CoordsCell:
        return CoordsCell(**self.cells['address'])
    
    @property
    def coords_person(self) -> CoordsCell:
        return CoordsCell(**self.cells['person'])
    
    @property
    def coords_reciver(self) -> CoordsCell:
        return CoordsCell(**self.cells['reciver'])
    
    @property
    def coords_projective_name(self) -> CoordsCell:
        return CoordsCell(**self.cells['projective_name'])
    
    @property
    def coords_start(self) -> CoordsCell:
        return CoordsCell(**self.cells['start'])
    
    @property
    def coords_end(self) -> CoordsCell:
        return CoordsCell(**self.cells['end'])
    
    @property
    def coords_pt_count(self) -> CoordsCell:
        return CoordsCell(**self.cells['pt_count'])
    
    @property
    def coords_signal_frec(self) -> CoordsCell:
        return CoordsCell(**self.cells['signal_frec'])
    
    @property
    def coords_area(self) -> CoordsCell:
        return CoordsCell(**self.cells['area'])
    
    @property
    def coords_outline_length(self) -> CoordsCell:
        return CoordsCell(**self.cells['outline_length'])
    
    @property
    def coords_min_epochs(self) -> CoordsCell:
        return CoordsCell(**self.cells['min_epochs'])
    
    @property
    def coords_max_pdop(self) -> CoordsCell:
        return CoordsCell(**self.cells['max_pdop'])
    
    @property
    def coords_min_satellites(self) -> CoordsCell:
        return CoordsCell(**self.cells['min_satellites'])
    
    @property
    def coords_work_days(self) -> CoordsCell:
        return CoordsCell(**self.cells['work_days'])
    
    @property
    def coords_work_time(self) -> CoordsCell:
        return CoordsCell(**self.cells['work_time'])
    


class XlsResultConfs(ExcelTemplate):
    def __init__(self):
        super().__init__()
        self._sheet = self._confs['main_sheet']
        self.cells = self._sheet['result_cells']

    @property
    def coords_pt_num_first(self) -> CoordsCell:
        return CoordsCell(**self.cells['pt_num_first'])
    
    @property
    def coords_pt_name_first(self) -> CoordsCell:
        return CoordsCell(**self.cells['pt_name_first'])
    
    @property
    def coords_lon_first(self) -> CoordsCell:
        return CoordsCell(**self.cells['lon_first'])
    
    @property
    def coords_lat_first(self) -> CoordsCell:
        return CoordsCell(**self.cells['lat_first'])
    
    @property
    def coords_epochs_first(self) -> CoordsCell:
        return CoordsCell(**self.cells['epochs_first'])
    
    @property
    def coords_pdop_first(self) -> CoordsCell:
        return CoordsCell(**self.cells['pdop_first'])
    
    @property
    def coords_satellites_first(self) -> CoordsCell:
        return CoordsCell(**self.cells['satellites_first'])
    
    @property
    def coords_y_first(self) -> CoordsCell:
        return CoordsCell(**self.cells['y_first'])
    
    @property
    def coords_x_first(self) -> CoordsCell:
        return CoordsCell(**self.cells['x_first'])
    

class XlsDetailConfs(ExcelTemplate):
    def __init__(self):
        super().__init__()
        self._sheet = self._confs['detail_sheet']

    @property
    def sheet_name(self):
        """概要を入力するシート名の取得"""
        return self._sheet['sheet_name']
    
    @property
    def coords_cells_start(self) -> CoordsCell:
        return CoordsCell(**self._confs['detail_sheet']['cells_start'])


        
class WebAppConfs(object):
    def __init__(self):
        self._confs = CONF_FILE['web_app']
    
    @property
    def add_details_list(self):
        dic = self._confs['add_details']
        return list(dic.keys())
    
    @property
    def add_details_dict(self):
        return self._confs['add_details']
    
    @property
    def help_txt_in_files(self):
        return self._confs['help_input_file']
    
    @property
    def help_txt_semidyna(self):
        return self._confs['help_semi_dyna']
    
    @property
    def help_txt_epsg(self):
        return self._confs['help_epsg']
    
    @property
    def help_txt_acc_thres(self):
        return self._confs['help_accuracy_thres']
    
    @property
    def show_cols_in_table(self):
        return self._confs['show_columns_in_table']
    
    @property
    def epsg_code_dict(self):
        return CONF_FILE['epsg_codes']
    
    @property
    def threshold_col_pdop(self):
        return CONF_FILE['point_pdop_col_jn']
    
    @property
    def threshold_col_epochs(self):
        return CONF_FILE['point_epochs_col_jn']
    
    @property
    def threshold_col_nsats(self):
        return CONF_FILE['point_nsats_col_jn']
    
    @property
    def threshold_col_signal_frec(self):
        return CONF_FILE['point_signal_frec_col_jn']



def rename_properties_dict(
    properties: Dict[str, Any], 
    is_en: bool,
) -> Dict[str, Any]:
    """
    propertiesに格納されたkeyを日本語にするか英語にするか
    """
    jns = DrgGpxConfs().use_cols_dict
    ens = WebAppConfs().add_details_dict
    en_to_jn_dict = jns
    for key, val in ens.items():
        if not key in en_to_jn_dict:
            en_to_jn_dict[key] = val
    jn_to_en_dict = {val: key for key, val in en_to_jn_dict.items()}

    new_properties = dict()
    for key, val in properties.items():
        if is_en:
            # 英語に変換する場合
            if key in jn_to_en_dict:
                new_properties[jn_to_en_dict.get(key)] = val
            else:
                new_properties[key] = val
        else:
            # 日本語に変換する場合
            if key in en_to_jn_dict:
                new_properties[jn_to_en_dict.get(key)] = val
            else:
                new_properties[key] = val
    return new_properties


def rename_jn_to_en_in_df(
        df: [pl.DataFrame | pd.DataFrame]
) -> pl.DataFrame | pd.DataFrame:
    # DataFrameの列名を日本語から英語に変える
    use_cols = DrgGpxConfs().use_cols_dict
    add_cols = WebAppConfs().add_details_dict
    use_cols.update(**add_cols)
    renames = {val: key for key, val in use_cols.items()}
    if type(df) == pl.DataFrame:
        return df.rename(renames)
    else:
        return df.rename(columns=renames)


def rename_en_to_jn_in_df(df: [pl.DataFrame | pd.DataFrame]):
    # DataFrameの列名を英語から日本語に変える
    use_cols = DrgGpxConfs().use_cols_dict
    add_cols = WebAppConfs().add_details_dict
    use_cols.update(**add_cols)
    if type(df) == pl.DataFrame:
        return df.rename(use_cols)
    else:
        return df.rename(columns=use_cols)

    
def check_lang_jn_in_df(df: [pl.DataFrame | pd.DataFrame]) -> bool:
    """DataFrameの列名が日本語かを判断する"""
    confs = JnDataCols()
    if confs.pt_name_col in df.columns:
        return True
    else:
        return False
    



if __name__ == '__main__':
    xsconf = XlsSummaryConfs()
    
