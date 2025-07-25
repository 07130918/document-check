"""
LLM-based Reading Order Estimator
Azure Document Intelligenceの全特徴量を使用した高度な読み取り順序推定
"""
import json
from typing import List, Dict, Any, Optional
import logging
from openai import OpenAI
import os

from apps.llm_docs_diff_v4.config.settings import settings

logger = logging.getLogger(__name__)


class LLMReadingOrderEstimator:
    """LLMを使用した読み取り順序推定器"""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4-turbo-preview"):
        """
        Args:
            api_key: OpenAI APIキー
            model: 使用するモデル名
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model
        
        if self.api_key:
            self.client = OpenAI(api_key=self.api_key)
        else:
            logger.warning("OpenAI API key not provided. LLM features will be disabled.")
            self.client = None
    
    def estimate_reading_order_with_llm(self, 
                                      bbox_list: List[Dict[str, Any]],
                                      azure_result: Any,
                                      page_num: int = 0) -> List[Dict[str, Any]]:
        """LLMを使用して読み取り順序を推定
        
        Args:
            bbox_list: テキスト要素のリスト
            azure_result: Azure Document Intelligenceの完全な結果
            page_num: 処理するページ番号
            
        Returns:
            並び替えられたテキスト要素のリスト
        """
        if not self.client:
            logger.warning("LLM client not available. Returning original order.")
            return bbox_list
        
        # Azure結果から特徴量を抽出
        features = self._extract_all_features(azure_result, page_num)
        
        # プロンプトを構築
        prompt = self._build_prompt(bbox_list, features)
        
        try:
            # LLMに問い合わせ
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self._get_system_prompt()},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,  # 一貫性のため低温度
                max_tokens=4000
            )
            
            # レスポンスを解析
            result = response.choices[0].message.content
            ordered_indices = self._parse_llm_response(result)
            
            # インデックスに基づいて並び替え
            if ordered_indices:
                ordered_list = []
                for idx in ordered_indices:
                    if 0 <= idx < len(bbox_list):
                        ordered_list.append(bbox_list[idx])
                
                # 漏れがあれば元の順序で追加
                if len(ordered_list) < len(bbox_list):
                    for i, item in enumerate(bbox_list):
                        if item not in ordered_list:
                            ordered_list.append(item)
                
                return ordered_list
            
        except Exception as e:
            logger.error(f"LLM processing failed: {e}")
        
        return bbox_list
    
    def _extract_all_features(self, azure_result: Any, page_num: int) -> Dict[str, Any]:
        """Azure結果から全特徴量を抽出"""
        features = {
            "paragraphs": [],
            "tables": [],
            "figures": [],
            "sections": [],
            "lists": [],
            "annotations": [],
            "styles": [],
            "reading_order": []
        }
        
        # 段落情報
        if hasattr(azure_result, 'paragraphs'):
            for para in azure_result.paragraphs:
                if para.bounding_regions and para.bounding_regions[0].page_number - 1 == page_num:
                    features["paragraphs"].append({
                        "content": para.content[:100] + "..." if len(para.content) > 100 else para.content,
                        "role": getattr(para, 'role', 'unknown'),
                        "bounds": self._get_bounds(para.bounding_regions[0])
                    })
        
        # テーブル情報
        if hasattr(azure_result, 'tables'):
            for table in azure_result.tables:
                if table.bounding_regions and table.bounding_regions[0].page_number - 1 == page_num:
                    features["tables"].append({
                        "row_count": table.row_count,
                        "column_count": table.column_count,
                        "bounds": self._get_bounds(table.bounding_regions[0])
                    })
        
        # 図形情報
        if hasattr(azure_result, 'figures'):
            for figure in azure_result.figures:
                if figure.bounding_regions and figure.bounding_regions[0].page_number - 1 == page_num:
                    features["figures"].append({
                        "caption": getattr(figure, 'caption', {}).get('content', 'No caption'),
                        "bounds": self._get_bounds(figure.bounding_regions[0])
                    })
        
        # セクション情報
        if hasattr(azure_result, 'sections'):
            for section in azure_result.sections:
                features["sections"].append({
                    "title": getattr(section, 'title', 'Untitled'),
                    "elements": len(getattr(section, 'elements', []))
                })
        
        # リスト情報
        if hasattr(azure_result, 'lists'):
            for lst in azure_result.lists:
                if lst.bounding_regions and lst.bounding_regions[0].page_number - 1 == page_num:
                    features["lists"].append({
                        "items": len(lst.items),
                        "bounds": self._get_bounds(lst.bounding_regions[0])
                    })
        
        # 注釈情報（矢印など）
        if hasattr(azure_result, 'annotations'):
            for annot in azure_result.annotations:
                if annot.bounding_regions and annot.bounding_regions[0].page_number - 1 == page_num:
                    features["annotations"].append({
                        "type": getattr(annot, 'type', 'unknown'),
                        "bounds": self._get_bounds(annot.bounding_regions[0])
                    })
        
        # スタイル情報
        if hasattr(azure_result, 'styles'):
            for style in azure_result.styles:
                features["styles"].append({
                    "style_type": getattr(style, 'style_type', 'unknown'),
                    "confidence": getattr(style, 'confidence', 0)
                })
        
        # Azure自身の読み取り順序（もしあれば）
        if hasattr(azure_result, 'reading_order'):
            for item in azure_result.reading_order:
                if item.page_number - 1 == page_num:
                    features["reading_order"].append({
                        "index": item.index,
                        "content_snippet": item.content[:50] + "..." if len(item.content) > 50 else item.content
                    })
        
        return features
    
    def _get_bounds(self, bounding_region) -> Dict[str, float]:
        """バウンディングリージョンから座標を取得"""
        if hasattr(bounding_region, 'polygon') and bounding_region.polygon:
            points = bounding_region.polygon
            if len(points) >= 8:
                return {
                    "x": points[0],
                    "y": points[1],
                    "width": points[2] - points[0],
                    "height": points[5] - points[1]
                }
        return {"x": 0, "y": 0, "width": 0, "height": 0}
    
    def _get_system_prompt(self) -> str:
        """システムプロンプト"""
        return """あなたは文書解析の専門家です。与えられた文書要素と視覚的特徴から、
人間が自然に読む順序を推定してください。

以下の点を考慮してください：
1. 視覚的な流れ（矢印、線、図形による接続）
2. レイアウト構造（カラム、セクション、段落）
3. 意味的な関連性（タイトル、本文、キャプション）
4. 日本語文書の一般的な読み方（左から右、上から下）
5. 特殊な要素（図表、リスト、注釈）の扱い

出力は要素のインデックス番号のリストとして、読むべき順序で返してください。"""
    
    def _build_prompt(self, bbox_list: List[Dict[str, Any]], features: Dict[str, Any]) -> str:
        """LLM用のプロンプトを構築"""
        # テキスト要素の情報
        elements = []
        for i, item in enumerate(bbox_list):
            elements.append({
                "index": i,
                "text": item.get('text', '')[:50] + "..." if len(item.get('text', '')) > 50 else item.get('text', ''),
                "x": item.get('x', 0),
                "y": item.get('y', 0),
                "width": item.get('width', 0),
                "height": item.get('height', 0)
            })
        
        # ブロック検出（X座標でグループ化）
        blocks = self._detect_text_blocks(bbox_list)
        block_info = "## 検出されたテキストブロック\n"
        for block_id, indices in blocks.items():
            block_info += f"ブロック{block_id}: インデックス {indices}\n"
        
        prompt = f"""以下の文書要素の読み取り順序を決定してください。

## テキスト要素
{json.dumps(elements, ensure_ascii=False, indent=2)}

{block_info}

## Azure Document Intelligence特徴量
### 段落情報
{json.dumps(features['paragraphs'], ensure_ascii=False, indent=2)}

### テーブル情報
{json.dumps(features['tables'], ensure_ascii=False, indent=2)}

### 図形情報
{json.dumps(features['figures'], ensure_ascii=False, indent=2)}

### 注釈情報（矢印など）
{json.dumps(features['annotations'], ensure_ascii=False, indent=2)}

### その他の特徴
- セクション数: {len(features['sections'])}
- リスト数: {len(features['lists'])}
- スタイル種類: {len(features['styles'])}

## 重要な考慮事項
1. 「入社→結婚→出産→住宅購入→子供独立→退職」のような矢印でつながった要素は、その順序を保持してください。
2. 図形とそのキャプションは連続して読まれるべきです。
3. テーブルは一つのまとまりとして扱ってください。
4. **X座標が近い（差が50ピクセル以内）でY座標が連続している要素は、同じブロックとして連続して読んでください。**
5. **特に左カラム（X座標が100-200程度）の要素は、右カラムに移る前にすべて読み終えてください。**

## 出力形式
読むべき順序でインデックス番号をカンマ区切りで出力してください。
例: 0,3,1,2,4,5..."""
        
        return prompt
    
    def _parse_llm_response(self, response: str) -> List[int]:
        """LLMのレスポンスを解析してインデックスリストを取得"""
        try:
            # カンマ区切りの数字を抽出
            import re
            numbers = re.findall(r'\d+', response)
            return [int(n) for n in numbers]
        except Exception as e:
            logger.error(f"Failed to parse LLM response: {e}")
            return []
    
    def process_with_azure_features(self, 
                                  bbox_list: List[Dict[str, Any]],
                                  azure_hierarchy: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Azure階層データを使用して処理（簡易版）"""
        # LLMが利用できない場合の代替処理
        if not self.client:
            logger.info("Using rule-based ordering with Azure features")
            return self._rule_based_ordering(bbox_list, azure_hierarchy)
        
        # LLMを使用した処理
        # azure_hierarchyをazure_result形式に変換（簡易実装）
        class MockResult:
            pass
        
        mock_result = MockResult()
        mock_result.paragraphs = azure_hierarchy.get('paragraphs', [])
        mock_result.lines = azure_hierarchy.get('lines', [])
        mock_result.words = azure_hierarchy.get('words', [])
        
        return self.estimate_reading_order_with_llm(bbox_list, mock_result)
    
    def _rule_based_ordering(self, bbox_list: List[Dict[str, Any]], 
                           azure_hierarchy: Dict[str, Any]) -> List[Dict[str, Any]]:
        """ルールベースの順序付け（LLMなしの代替）"""
        # 段落情報があれば、段落の順序に従う
        if 'paragraphs' in azure_hierarchy and azure_hierarchy['paragraphs']:
            # 段落のコンテンツとbbox_listのテキストをマッチング
            ordered = []
            for para in azure_hierarchy['paragraphs']:
                para_content = para.get('content', '')
                for item in bbox_list:
                    if item.get('text', '') in para_content and item not in ordered:
                        ordered.append(item)
            
            # マッチしなかった要素を追加
            for item in bbox_list:
                if item not in ordered:
                    ordered.append(item)
            
            return ordered
        
        # 段落情報がない場合は元の順序を返す
        return bbox_list
    
    def _detect_text_blocks(self, bbox_list: List[Dict[str, Any]]) -> Dict[int, List[int]]:
        """X座標の近さに基づいてテキストブロックを検出"""
        blocks = {}
        block_id = 0
        x_threshold = 50  # X座標の差の閾値
        
        # X座標でソート
        indexed_items = [(i, item) for i, item in enumerate(bbox_list)]
        indexed_items.sort(key=lambda x: x[1].get('x', 0))
        
        current_block = []
        current_x = None
        
        for idx, item in indexed_items:
            x = item.get('x', 0)
            
            if current_x is None or abs(x - current_x) <= x_threshold:
                current_block.append(idx)
                current_x = x
            else:
                # 新しいブロック
                if current_block:
                    blocks[block_id] = sorted(current_block)  # インデックス順にソート
                    block_id += 1
                current_block = [idx]
                current_x = x
        
        # 最後のブロック
        if current_block:
            blocks[block_id] = sorted(current_block)
        
        return blocks