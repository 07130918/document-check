"""
LLMプロンプトテンプレート管理
"""
from typing import Dict, Any, List
import json


class PromptTemplateManager:
    """プロンプトテンプレート管理クラス"""

    # 読み順序推定用テンプレート
    READING_ORDER_TEMPLATE = """
あなたは文書レイアウト解析の専門家です。
以下の文書要素の読み順序を推定してください。

【要素リスト】
{elements}

【レイアウト情報】
{layout_info}

【指示】
1. 一般的な読書順序（左上から右下へ）を基本とする
2. カラムレイアウトの場合は、左カラムから右カラムへ
3. 表やボックス内のテキストは、その構造内で完結させる
4. ヘッダー・フッターは最後に読む

【出力形式】
{{"reading_order": [要素のインデックス番号のリスト]}}
"""


    @classmethod
    def format_reading_order_prompt(cls, elements: List[Dict[str, Any]],
                                  layout_info: str = "") -> str:
        """読み順序推定用プロンプトをフォーマット"""
        elements_json = json.dumps(elements, ensure_ascii=False, indent=2)
        return cls.READING_ORDER_TEMPLATE.format(
            elements=elements_json,
            layout_info=layout_info or "標準的な文書レイアウト"
        )
