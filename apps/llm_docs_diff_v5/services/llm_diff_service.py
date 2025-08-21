"""
LLMベースの差分検出サービス for v5
ブロックレベルの差分をLLMで詳細に分析
"""
import openai
from typing import List, Dict, Any, Optional, Tuple
import json
import logging
from dataclasses import dataclass
import os

from ..models.block_models import Block, BlockDifference
from ..config.settings import settings

logger = logging.getLogger(__name__)


@dataclass
class LLMDiffAnalysis:
    """LLMによる差分分析結果"""
    semantic_similarity: float  # 意味的類似度（0-1）
    change_significance: str  # 変更の重要度（high/medium/low）
    change_category: str  # 変更カテゴリ（content/format/position/combined）
    explanation: str  # 変更内容の説明
    impact_assessment: str  # 影響評価


class LLMDiffService:
    """LLMベースの差分検出サービス"""
    
    def __init__(self):
        """初期化"""
        api_key = os.environ.get("OPENAI_API_KEY") or settings.OPENAI_API_KEY
        if not api_key:
            raise ValueError("OPENAI_API_KEY is not set")
        
        self.client = openai.OpenAI(api_key=api_key)
        self.model = "gpt-4o-mini"  # 高速で低コスト
        self.max_tokens = 2000
        self.temperature = 0.3  # より一貫性のある出力
    
    def analyze_block_differences(self, 
                                differences: List[BlockDifference],
                                doc_context: Optional[str] = None) -> Dict[str, Any]:
        """ブロックレベルの差分をLLMで分析
        
        Args:
            differences: ブロック差分のリスト
            doc_context: 文書全体のコンテキスト（オプション）
            
        Returns:
            LLM分析結果の辞書
        """
        if not differences:
            return {"analysis": "差分はありません"}
        
        # 差分を整理
        diff_summary = self._prepare_diff_summary(differences[:50])  # 最初の50件
        
        prompt = f"""
以下の文書の差分を分析してください。

{f'文書コンテキスト: {doc_context}' if doc_context else ''}

差分リスト:
{json.dumps(diff_summary, ensure_ascii=False, indent=2)}

以下の観点で分析してください：
1. 全体的な変更の傾向とパターン
2. 重要な変更点（内容的に意味のある変更）
3. 形式的な変更（日付、番号、書式など）
4. 変更の影響度評価

JSON形式で回答してください：
{{
    "overall_trend": "全体的な変更傾向の説明",
    "key_changes": ["重要な変更点1", "重要な変更点2", ...],
    "formatting_changes": ["形式的な変更1", "形式的な変更2", ...],
    "impact_assessment": "変更の影響度評価（high/medium/low）と理由",
    "summary": "変更内容の要約（100文字以内）"
}}
"""
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "あなたは文書差分分析の専門家です。"},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            return result
            
        except Exception as e:
            logger.error(f"LLM analysis failed: {e}")
            return {
                "overall_trend": "分析エラー",
                "key_changes": [],
                "formatting_changes": [],
                "impact_assessment": "unknown",
                "summary": "LLM分析に失敗しました"
            }
    
    def analyze_single_difference(self, 
                                block1: Optional[Block], 
                                block2: Optional[Block],
                                context_blocks: Optional[List[Block]] = None) -> LLMDiffAnalysis:
        """単一の差分を詳細に分析
        
        Args:
            block1: 文書1のブロック
            block2: 文書2のブロック
            context_blocks: 周辺のブロック（コンテキスト用）
            
        Returns:
            LLM差分分析結果
        """
        # ブロック情報を準備
        block1_info = self._block_to_dict(block1) if block1 else None
        block2_info = self._block_to_dict(block2) if block2 else None
        
        # コンテキストを準備
        context_text = ""
        if context_blocks:
            context_texts = [b.text for b in context_blocks[:5] if b and b.text]
            context_text = " ".join(context_texts)
        
        prompt = f"""
以下の2つのブロックの差分を詳細に分析してください。

ブロック1（元）:
{json.dumps(block1_info, ensure_ascii=False, indent=2) if block1_info else "なし"}

ブロック2（新）:
{json.dumps(block2_info, ensure_ascii=False, indent=2) if block2_info else "なし"}

{f'周辺コンテキスト: {context_text[:200]}' if context_text else ''}

以下を分析してください：
1. 意味的な類似度（0-1のスコア）
2. 変更の重要度（high/medium/low）
3. 変更カテゴリ（content/format/position/combined）
4. 変更内容の説明
5. 影響評価

JSON形式で回答してください：
{{
    "semantic_similarity": 0.0-1.0の数値,
    "change_significance": "high/medium/low",
    "change_category": "content/format/position/combined",
    "explanation": "変更内容の説明",
    "impact_assessment": "この変更の影響"
}}
"""
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "あなたは文書差分分析の専門家です。"},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=500,
                temperature=self.temperature,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            
            return LLMDiffAnalysis(
                semantic_similarity=float(result.get("semantic_similarity", 0.5)),
                change_significance=result.get("change_significance", "medium"),
                change_category=result.get("change_category", "content"),
                explanation=result.get("explanation", ""),
                impact_assessment=result.get("impact_assessment", "")
            )
            
        except Exception as e:
            logger.error(f"Single diff analysis failed: {e}")
            return LLMDiffAnalysis(
                semantic_similarity=0.5,
                change_significance="medium",
                change_category="unknown",
                explanation="分析エラー",
                impact_assessment="不明"
            )
    
    def generate_diff_summary(self, 
                            differences: List[BlockDifference],
                            max_items: int = 10) -> List[str]:
        """差分の要約を生成
        
        Args:
            differences: 差分リスト
            max_items: 要約項目の最大数
            
        Returns:
            要約文のリスト
        """
        if not differences:
            return ["変更はありません"]
        
        # 差分情報を準備
        diff_texts = []
        for diff in differences[:30]:  # 最初の30件
            if diff.change_type == "deleted":
                text = f"削除: {diff.block1.text[:50] if diff.block1 else ''}"
            elif diff.change_type == "added":
                text = f"追加: {diff.block2.text[:50] if diff.block2 else ''}"
            else:
                text1 = diff.block1.text[:50] if diff.block1 else ""
                text2 = diff.block2.text[:50] if diff.block2 else ""
                text = f"変更: '{text1}' → '{text2}'"
            diff_texts.append(text)
        
        prompt = f"""
以下の文書変更を要約してください。
最も重要な変更を{max_items}項目以内でまとめてください。

変更リスト:
{chr(10).join(diff_texts)}

JSON形式で回答してください：
{{"summary_items": ["要約1", "要約2", ...]}}
"""
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "あなたは文書変更の要約専門家です。"},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1000,
                temperature=self.temperature,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            return result.get("summary_items", ["要約の生成に失敗しました"])
            
        except Exception as e:
            logger.error(f"Summary generation failed: {e}")
            return ["差分要約の生成に失敗しました"]
    
    def _prepare_diff_summary(self, differences: List[BlockDifference]) -> List[Dict[str, Any]]:
        """差分情報を要約形式に変換"""
        summary = []
        for diff in differences:
            item = {
                "type": diff.change_type,
                "page": diff.block1.page if diff.block1 else (diff.block2.page if diff.block2 else 0)
            }
            
            if diff.block1:
                item["original"] = {
                    "text": diff.block1.text[:100],
                    "type": diff.block1.block_type.value
                }
            
            if diff.block2:
                item["modified"] = {
                    "text": diff.block2.text[:100],
                    "type": diff.block2.block_type.value
                }
            
            summary.append(item)
        
        return summary
    
    def _block_to_dict(self, block: Optional[Block]) -> Optional[Dict[str, Any]]:
        """ブロックを辞書形式に変換"""
        if not block:
            return None
        
        return {
            "text": block.text[:200],  # 最初の200文字
            "type": block.block_type.value,
            "page": block.page,
            "position": {
                "x": block.bbox.x,
                "y": block.bbox.y,
                "width": block.bbox.width,
                "height": block.bbox.height
            }
        }