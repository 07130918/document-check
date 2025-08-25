"""
セル内テキストの詳細解析モジュール
MeCabを使用して形態素解析を行い、細かい粒度での差分検出を実現
"""
from typing import List, Dict, Tuple, Optional
import MeCab
import difflib
import re


class CellTextAnalyzer:
    """セル内テキストの詳細解析器"""
    
    def __init__(self):
        """初期化"""
        # MeCabの初期化（システム辞書を使用）
        try:
            # 標準的な初期化を試行
            self.mecab = MeCab.Tagger()
        except RuntimeError:
            try:
                # 設定ファイルパスを明示的に指定
                self.mecab = MeCab.Tagger('-r /etc/mecabrc')
            except RuntimeError:
                try:
                    # 辞書パスも明示的に指定
                    self.mecab = MeCab.Tagger('-r /etc/mecabrc -d /var/lib/mecab/dic/debian')
                except RuntimeError:
                    # MeCabが使用できない場合は簡易的な解析にフォールバック
                    self.mecab = None
                    import logging
                    logging.warning("MeCab initialization failed. Using simple text analysis.")
        
    def analyze_cell_diff(self, text1: str, text2: str) -> Dict[str, any]:
        """セル内テキストの詳細な差分を解析
        
        Args:
            text1: 元のテキスト
            text2: 変更後のテキスト
            
        Returns:
            差分情報の辞書
        """
        # テキストが同じ場合は差分なし
        if text1 == text2:
            return {
                'has_diff': False,
                'diff_type': 'none',
                'segments': []
            }
        
        # 文単位に分割
        sentences1 = self._split_sentences(text1)
        sentences2 = self._split_sentences(text2)
        
        # 文単位での差分を検出
        sentence_diff = self._compare_sentences(sentences1, sentences2)
        
        # 変更があった文について、形態素単位で詳細解析
        detailed_segments = []
        for seg in sentence_diff:
            if seg['type'] == 'modified':
                # 形態素解析して詳細な差分を取得
                morpheme_diff = self._analyze_morpheme_diff(
                    seg['old_text'], 
                    seg['new_text']
                )
                seg['morpheme_diff'] = morpheme_diff
            detailed_segments.append(seg)
        
        return {
            'has_diff': True,
            'diff_type': self._determine_diff_type(detailed_segments),
            'segments': detailed_segments
        }
    
    def _split_sentences(self, text: str) -> List[str]:
        """テキストを文単位に分割
        
        Args:
            text: 分割するテキスト
            
        Returns:
            文のリスト
        """
        # 句読点で分割（ただし、数値や英文の小数点は除外）
        # 改行も文の区切りとして扱う
        sentences = re.split(r'(?<![0-9])(?<![a-zA-Z])[。！？\n]+', text)
        # 空文字列を除去し、句読点を戻す
        result = []
        parts = re.split(r'([。！？\n]+)', text)
        
        current = ""
        for i, part in enumerate(parts):
            if re.match(r'^[。！？\n]+$', part):
                if current:
                    current += part
                    result.append(current.strip())
                    current = ""
            else:
                current += part
        
        if current.strip():
            result.append(current.strip())
        
        return [s for s in result if s]
    
    def _compare_sentences(self, sentences1: List[str], sentences2: List[str]) -> List[Dict]:
        """文単位で比較
        
        Args:
            sentences1: 元の文リスト
            sentences2: 変更後の文リスト
            
        Returns:
            差分セグメントのリスト
        """
        segments = []
        
        # difflibを使用して文単位の差分を取得
        matcher = difflib.SequenceMatcher(None, sentences1, sentences2)
        
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == 'equal':
                # 変更なし
                for i in range(i1, i2):
                    segments.append({
                        'type': 'unchanged',
                        'text': sentences1[i]
                    })
            elif tag == 'delete':
                # 削除
                for i in range(i1, i2):
                    segments.append({
                        'type': 'deleted',
                        'old_text': sentences1[i],
                        'new_text': None
                    })
            elif tag == 'insert':
                # 追加
                for j in range(j1, j2):
                    segments.append({
                        'type': 'added',
                        'old_text': None,
                        'new_text': sentences2[j]
                    })
            elif tag == 'replace':
                # 変更
                old_texts = sentences1[i1:i2]
                new_texts = sentences2[j1:j2]
                
                # 1対1の変更の場合
                if len(old_texts) == 1 and len(new_texts) == 1:
                    segments.append({
                        'type': 'modified',
                        'old_text': old_texts[0],
                        'new_text': new_texts[0]
                    })
                else:
                    # 複数の文が関係する場合は削除と追加として扱う
                    for old in old_texts:
                        segments.append({
                            'type': 'deleted',
                            'old_text': old,
                            'new_text': None
                        })
                    for new in new_texts:
                        segments.append({
                            'type': 'added',
                            'old_text': None,
                            'new_text': new
                        })
        
        return segments
    
    def _analyze_morpheme_diff(self, text1: str, text2: str) -> List[Dict]:
        """形態素単位での差分解析
        
        Args:
            text1: 元のテキスト
            text2: 変更後のテキスト
            
        Returns:
            形態素レベルの差分情報
        """
        # 形態素解析
        morphemes1 = self._parse_morphemes(text1)
        morphemes2 = self._parse_morphemes(text2)
        
        # 形態素単位で差分を検出
        diff_morphemes = []
        matcher = difflib.SequenceMatcher(
            None, 
            [m['surface'] for m in morphemes1],
            [m['surface'] for m in morphemes2]
        )
        
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == 'equal':
                continue  # 変更なしは記録しない
            elif tag == 'delete':
                for i in range(i1, i2):
                    diff_morphemes.append({
                        'type': 'deleted',
                        'morpheme': morphemes1[i]
                    })
            elif tag == 'insert':
                for j in range(j1, j2):
                    diff_morphemes.append({
                        'type': 'added',
                        'morpheme': morphemes2[j]
                    })
            elif tag == 'replace':
                # 置換された形態素
                for i in range(i1, i2):
                    diff_morphemes.append({
                        'type': 'deleted',
                        'morpheme': morphemes1[i]
                    })
                for j in range(j1, j2):
                    diff_morphemes.append({
                        'type': 'added',
                        'morpheme': morphemes2[j]
                    })
        
        return diff_morphemes
    
    def _parse_morphemes(self, text: str) -> List[Dict]:
        """MeCabで形態素解析
        
        Args:
            text: 解析するテキスト
            
        Returns:
            形態素情報のリスト
        """
        morphemes = []
        
        if self.mecab is None:
            # MeCabが使用できない場合は簡易的な単語分割
            # スペース、句読点、記号で分割
            import re
            words = re.findall(r'[^\s\W]+|[。、！？]', text)
            for word in words:
                if word:
                    morphemes.append({
                        'surface': word,
                        'pos': 'unknown',
                        'pos_detail': [],
                        'base_form': word,
                    })
            return morphemes
        
        # MeCabで解析
        node = self.mecab.parseToNode(text)
        
        while node:
            if node.surface:  # 空文字でない場合
                features = node.feature.split(',')
                morphemes.append({
                    'surface': node.surface,
                    'pos': features[0],  # 品詞
                    'pos_detail': features[1:4] if len(features) > 3 else [],  # 品詞細分類
                    'base_form': features[6] if len(features) > 6 else node.surface,  # 原形
                })
            node = node.next
        
        return morphemes
    
    def _determine_diff_type(self, segments: List[Dict]) -> str:
        """差分タイプを判定
        
        Args:
            segments: 差分セグメント
            
        Returns:
            差分タイプ（minor_change, major_change, etc.）
        """
        # 変更された文の数をカウント
        modified_count = sum(1 for s in segments if s['type'] in ['modified', 'added', 'deleted'])
        total_count = len(segments)
        
        if modified_count == 0:
            return 'none'
        elif modified_count == 1 and total_count > 3:
            # 1文だけの変更で、全体が4文以上ある場合は軽微な変更
            return 'minor_change'
        elif modified_count / total_count < 0.3:
            # 30%未満の変更は部分的変更
            return 'partial_change'
        else:
            # それ以外は大幅な変更
            return 'major_change'