import datetime
import re
from typing import Dict, List, Any
import unicodedata
import xml.etree.ElementTree as ET
from xml.etree.ElementTree import Element

from apps.settings.configs import DrgGpxConfs


def parse_zen2han(sentence: str) -> str:
    """全角文字列を半角文字列に変換"""
    return unicodedata.normalize('NFKC', sentence).replace('．', '.')

def parse_sentence_in_numeric(sentence: str) -> float:
    """文字列を浮動小数点数に変換"""
    sentence = parse_zen2han(sentence)
    numeric = re.sub(r'[^0-9\.]', '', sentence)
    if numeric == '':
        return 0.
    else:
        return float(numeric)
    
def parse_sats_signals_frecuencies(signals: str, separate: str=' ') -> str:
    """衛星信号名から周波数の名称を計算する（n周波など）"""
    confs = DrgGpxConfs()
    signal_codes = [confs.l1, confs.l2, confs.l5]
    frecuency = 0
    for signal in signals.split(separate):
        if signal in signal_codes:
            frecuency += 1
    return frecuency

def convert_datetimestr2datetime(sentence: str):
    confs = DrgGpxConfs()
    return datetime.datetime.strptime(sentence, confs.datetime_fmt)


#---GPXファイルの処理------------------------------------------------

class GPX2(object):
    def __init__(self, fp: str):
        super().__init__()
        self.trees = [tree for tree in ET.parse(fp).getroot()]
      
    def __loop(self, tree):
        results = []
        try:
            for node in tree:
                results.append(node)
        except:
            results.append(tree)
            pass
        return results
    
    def __convert_float(self, value):
        try:
            val = float(value)
        except:
            return value
        else:
            return val
    
    def _read_coors(self, sentence: str) -> Dict:
        coors = dict()
        for sent in sentence.split(' '):
            if 'lon' in sent:
                coors['lon'] = float(sent.replace('lon=', ''))
            elif 'lat' in sent:
                coors['lat'] = float(sent.replace('lat=', ''))
            elif 'ellipsoidHeight' in sent:
                coors['ellipsoidHeight'] = float(sent.replace('ellipsoidHeight=', ''))
        return coors

    
    def read_items(self):
        '''全てのタグを読み込む'''
        results = []
        for tree in self.trees:
            rows = []
            exts = None
            for node in tree:
                resps = self.__loop(node)
                if len(resps) == 0:
                    # mainのタグ
                    rows.append(node)
                else:
                    exts = resps
            for node in exts:
                resps = self.__loop(node)
                if len(resps) == 0:
                    # extensionsのタグ
                    rows.append(node)
                else:
                    # さらに深いタグ
                    rows += resps
            # まとめて辞書化
            items = dict()
            for row in rows:
                tag = str(row.tag)
                key = tag[tag.find('}') + 1:]
                items[key] = self.__convert_float(row.text)
            # cmtから座標を取り出しitemsに追加
            coors = self._read_coors(items.get('cmt'))
            del items['cmt']
            items.update(coors)
            results.append(items)
        return results

    

def read_drggpx_original(
    fp: str
) -> List[Dict[str, Any]]:
    """
    .gpxから読み込んだデータを変更せずに返す
    """
    gpx2 = GPX2(fp)
    item_lst = gpx2.read_items()
    return item_lst


def read_drggpx_useing(fp: str) -> List[Dict[str, Any]]:
    """
    .gpxから読み込んだデータを名称変更し、必要なデータに絞って返す
    """
    # データの読み込み
    item_lst = read_drggpx_original(fp)
    # 設定クラス読み込み、名
    confs = DrgGpxConfs()
    # 称変更用の設定辞書
    rename_dict = confs.rename_original2use_dict
    # 使用する列名のlist
    use_cols = confs.use_cols_lst
    results = []
    for item in item_lst:
        # 名称変更
        renamed = dict()
        for ori_key, ori_val in item.items():
            if ori_key in rename_dict:
                renamed[rename_dict[ori_key]] = ori_val
            else:
                print(f"Key is not found: {ori_key}. Must be newly registered.")
        # 地殻変動補正されているかの確認
        coord_genaration = renamed.get(confs.coordinate_generation_col)
        projective_technique = renamed.get(confs.projective_col)
        epsg = confs.convert_str2epsg(coord_genaration, projective_technique)
        if epsg is None:
            # 補正がないならばNoneを代入
            renamed[confs.projective_col] = None
            renamed[confs.transformed_x_col] = None
            renamed[confs.transformed_y_col] = None
        # APIで標高を取得して”transformed_z”に
        else:
            renamed[confs.projective_col] = epsg
        # 必要な列のみに絞り込む
        converted = dict()
        for col in use_cols:
            if col in renamed.keys():
                converted[col] = renamed[col]
            else:
                converted[col] = None
        # 時刻をdatetimeObjectに
        start = converted.get(confs.start_time_col)
        converted[confs.start_time_col] = convert_datetimestr2datetime(start)
        end = converted.get(confs.end_time_col)
        converted[confs.end_time_col] = convert_datetimestr2datetime(end)
        # 測点名をFloatに型変換
        name = confs.pt_name_col
        converted[name] = parse_sentence_in_numeric(str(converted.get(name)))
        # 信号解析
        signals = converted.get(confs.signals_col)
        frecuencies = parse_sats_signals_frecuencies(signals)
        converted[confs.frecuencies_col] = frecuencies
        results.append(converted)
    return results
        

def read_drggpx_useing_jn(fp) -> List[Dict[str, Any]]:
    """
    .gpxから読み込んだデータを名称変更し、必要なデータに絞って返す
    Dictのkeyは日本語に変換しています
    """
    confs = DrgGpxConfs()
    use_cols_dict = confs.use_cols_dict
    us_results = read_drggpx_useing(fp)
    jn_results = []
    for row in us_results:
        new_row = dict()
        for us_key, val in row.items():
            jn_key = use_cols_dict.get(us_key)
            new_row[jn_key] = val
        jn_results.append(new_row)
    return jn_results
