"""
Report Generator - 実行レポート生成
"""
from typing import Dict, List, Any
from pathlib import Path
from datetime import datetime
import json
import time
from ..models import DiffResult, ChangeType


class ReportGenerator:
    """実行レポートの生成"""
    
    def __init__(self):
        self.start_time = None
        self.end_time = None
        self.phase_times = {}
        self.current_phase = None
        self.phase_start = None
    
    def start_timer(self):
        """全体タイマー開始"""
        self.start_time = time.time()
        self.phase_times = {}
    
    def start_phase(self, phase_name: str):
        """フェーズタイマー開始"""
        self.current_phase = phase_name
        self.phase_start = time.time()
    
    def end_phase(self):
        """フェーズタイマー終了"""
        if self.current_phase and self.phase_start:
            elapsed = time.time() - self.phase_start
            self.phase_times[self.current_phase] = elapsed
            self.current_phase = None
            self.phase_start = None
    
    def end_timer(self):
        """全体タイマー終了"""
        self.end_time = time.time()
    
    def generate_report(self,
                       doc1_info: Dict[str, Any],
                       doc2_info: Dict[str, Any],
                       differences: List[DiffResult],
                       layout_changes: List[Dict] = None,
                       output_dir: Path = None) -> Dict[str, Any]:
        """
        詳細な実行レポートを生成
        
        Args:
            doc1_info: 文書1の情報
            doc2_info: 文書2の情報
            differences: 差分リスト
            layout_changes: レイアウト変更リスト
            output_dir: 出力ディレクトリ
            
        Returns:
            レポートデータ
        """
        # 実行時間の計算
        total_time = self.end_time - self.start_time if self.end_time and self.start_time else 0
        
        # 差分の分析
        diff_analysis = self._analyze_differences(differences)
        
        # レポートデータの構築
        report = {
            "execution_info": {
                "timestamp": datetime.now().isoformat(),
                "total_execution_time": f"{total_time:.2f} seconds",
                "phase_times": {
                    phase: f"{time_val:.2f} seconds" 
                    for phase, time_val in self.phase_times.items()
                }
            },
            "document_info": {
                "document1": {
                    "total_words": doc1_info.get('word_count', 0),
                    "total_pages": doc1_info.get('page_count', 0),
                    "words_per_page": self._calculate_words_per_page(doc1_info)
                },
                "document2": {
                    "total_words": doc2_info.get('word_count', 0),
                    "total_pages": doc2_info.get('page_count', 0),
                    "words_per_page": self._calculate_words_per_page(doc2_info)
                }
            },
            "diff_summary": {
                "total_differences": len(differences),
                "by_type": diff_analysis['by_type'],
                "by_page": diff_analysis['by_page'],
                "success_rate": self._calculate_success_rate(differences)
            },
            "detailed_differences": self._format_detailed_differences(differences),
            "layout_changes": self._format_layout_changes(layout_changes) if layout_changes else [],
            "quality_metrics": self._calculate_quality_metrics(differences, layout_changes),
            "examples": self._extract_success_failure_examples(differences)
        }
        
        # レポートをファイルに保存
        if output_dir:
            report_path = output_dir / "execution_report.json"
            with open(report_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
            
            # 人間が読みやすいマークダウンレポートも生成
            md_report_path = output_dir / "execution_report.md"
            self._generate_markdown_report(report, md_report_path)
        
        return report
    
    def _analyze_differences(self, differences: List[DiffResult]) -> Dict[str, Any]:
        """差分の詳細分析"""
        by_type = {
            'additions': 0,
            'deletions': 0,
            'modifications': 0
        }
        
        by_page = {}
        
        for diff in differences:
            # タイプ別集計
            if diff.change_type == ChangeType.ADDITION:
                by_type['additions'] += 1
            elif diff.change_type == ChangeType.DELETION:
                by_type['deletions'] += 1
            elif diff.change_type == ChangeType.MODIFICATION:
                by_type['modifications'] += 1
            
            # ページ別集計
            page = diff.page
            if page not in by_page:
                by_page[page] = {'additions': 0, 'deletions': 0, 'modifications': 0}
            
            if diff.change_type == ChangeType.ADDITION:
                by_page[page]['additions'] += 1
            elif diff.change_type == ChangeType.DELETION:
                by_page[page]['deletions'] += 1
            elif diff.change_type == ChangeType.MODIFICATION:
                by_page[page]['modifications'] += 1
        
        return {
            'by_type': by_type,
            'by_page': by_page
        }
    
    def _calculate_words_per_page(self, doc_info: Dict[str, Any]) -> Dict[int, int]:
        """ページごとの単語数を計算"""
        words_per_page = {}
        if 'bbox_list' in doc_info:
            for bbox in doc_info['bbox_list']:
                page = bbox.get('page', 0)
                words_per_page[page] = words_per_page.get(page, 0) + 1
        return words_per_page
    
    def _calculate_success_rate(self, differences: List[DiffResult]) -> float:
        """差分検出の成功率を推定（信頼度ベース）"""
        if not differences:
            return 100.0
        
        total_confidence = sum(diff.confidence for diff in differences)
        avg_confidence = total_confidence / len(differences)
        return round(avg_confidence * 100, 2)
    
    def _format_detailed_differences(self, differences: List[DiffResult]) -> List[Dict[str, Any]]:
        """差分の詳細情報をフォーマット"""
        detailed = []
        
        for i, diff in enumerate(differences[:50]):  # 最初の50件のみ
            detail = {
                'index': i + 1,
                'type': diff.change_type.value,
                'page': diff.page + 1,  # 1-indexed
                'confidence': diff.confidence
            }
            
            if diff.original_bbox:
                detail['original_text'] = diff.original_bbox.get('text', '')
                detail['original_position'] = {
                    'x': diff.original_bbox['bbox'][0],
                    'y': diff.original_bbox['bbox'][1]
                }
            
            if diff.modified_bbox:
                detail['modified_text'] = diff.modified_bbox.get('text', '')
                detail['modified_position'] = {
                    'x': diff.modified_bbox['bbox'][0],
                    'y': diff.modified_bbox['bbox'][1]
                }
            
            detailed.append(detail)
        
        return detailed
    
    def _extract_success_failure_examples(self, differences: List[DiffResult]) -> Dict[str, List[Dict]]:
        """成功例と失敗例を抽出"""
        success_examples = []
        failure_examples = []
        
        for diff in differences:
            example = {
                'type': diff.change_type.value,
                'confidence': diff.confidence,
                'page': diff.page + 1
            }
            
            if diff.original_bbox:
                example['text1'] = diff.original_bbox.get('text', '')
            if diff.modified_bbox:
                example['text2'] = diff.modified_bbox.get('text', '')
            
            # 高信頼度（成功例）
            if diff.confidence >= 0.95 and len(success_examples) < 5:
                success_examples.append(example)
            # 低信頼度（失敗例・要確認）
            elif diff.confidence < 0.7 and len(failure_examples) < 5:
                failure_examples.append(example)
        
        return {
            'success': success_examples,
            'failure': failure_examples
        }
    
    def _format_layout_changes(self, layout_changes: List[Dict]) -> List[Dict[str, Any]]:
        """レイアウト変更情報をフォーマット"""
        formatted = []
        
        for change in layout_changes[:30]:  # 最初の30件のみ
            formatted.append({
                'text': change['text'],
                'old_page': change['old_position']['page'] + 1,
                'new_page': change['new_position']['page'] + 1,
                'movement_distance': round(change['distance'], 2)
            })
        
        return formatted
    
    def _calculate_quality_metrics(self, differences: List[DiffResult], layout_changes: List[Dict] = None) -> Dict[str, Any]:
        """品質メトリクスの計算"""
        metrics = {
            'avg_confidence': 0,
            'high_confidence_ratio': 0,
            'layout_change_detected': len(layout_changes) if layout_changes else 0,
            'potential_false_positives': 0
        }
        
        if differences:
            confidences = [diff.confidence for diff in differences]
            metrics['avg_confidence'] = sum(confidences) / len(confidences)
            metrics['high_confidence_ratio'] = len([c for c in confidences if c > 0.8]) / len(confidences)
            
            # 潜在的な誤検出の推定
            for diff in differences:
                if diff.confidence < 0.5:
                    metrics['potential_false_positives'] += 1
        
        return metrics
    
    def _generate_markdown_report(self, report: Dict[str, Any], output_path: Path):
        """人間が読みやすいマークダウンレポートを生成"""
        md_content = f"""# 文書差分検出 実行レポート

## 実行情報
- 実行日時: {report['execution_info']['timestamp']}
- 総実行時間: {report['execution_info']['total_execution_time']}

### フェーズ別実行時間
"""
        
        for phase, time_str in report['execution_info']['phase_times'].items():
            md_content += f"- {phase}: {time_str}\n"
        
        md_content += f"""
## 文書情報

### 文書1
- 総単語数: {report['document_info']['document1']['total_words']}
- 総ページ数: {report['document_info']['document1']['total_pages']}

### 文書2
- 総単語数: {report['document_info']['document2']['total_words']}
- 総ページ数: {report['document_info']['document2']['total_pages']}

## 差分検出結果

### サマリー
- 総差分数: {report['diff_summary']['total_differences']}
- 追加: {report['diff_summary']['by_type']['additions']}
- 削除: {report['diff_summary']['by_type']['deletions']}
- 変更: {report['diff_summary']['by_type']['modifications']}
- 検出成功率（推定）: {report['diff_summary']['success_rate']}%

### 品質メトリクス
- 平均信頼度: {report['quality_metrics']['avg_confidence']:.2f}
- 高信頼度の割合: {report['quality_metrics']['high_confidence_ratio']:.2%}
- レイアウト変更検出数: {report['quality_metrics']['layout_change_detected']}
- 潜在的な誤検出: {report['quality_metrics']['potential_false_positives']}

## 詳細な差分（最初の10件）
"""
        
        for diff in report['detailed_differences'][:10]:
            md_content += f"\n### {diff['index']}. {diff['type']} (ページ {diff['page']})\n"
            if 'original_text' in diff:
                md_content += f"- 元のテキスト: 「{diff['original_text']}」\n"
            if 'modified_text' in diff:
                md_content += f"- 変更後のテキスト: 「{diff['modified_text']}」\n"
            md_content += f"- 信頼度: {diff['confidence']:.2f}\n"
        
        if report['layout_changes']:
            md_content += "\n## レイアウト変更（最初の10件）\n"
            for i, change in enumerate(report['layout_changes'][:10]):
                md_content += f"\n{i+1}. 「{change['text']}」\n"
                md_content += f"   - ページ {change['old_page']} → ページ {change['new_page']}\n"
                md_content += f"   - 移動距離: {change['movement_distance']}px\n"
        
        # 成功例・失敗例セクション
        if 'examples' in report:
            md_content += "\n## 検出例\n"
            
            if report['examples']['success']:
                md_content += "\n### 高信頼度の検出例（成功例）\n"
                for i, example in enumerate(report['examples']['success']):
                    md_content += f"\n{i+1}. {example['type']} (ページ {example['page']}, 信頼度: {example['confidence']:.2f})\n"
                    if 'text1' in example:
                        md_content += f"   - 文書1: 「{example['text1']}」\n"
                    if 'text2' in example:
                        md_content += f"   - 文書2: 「{example['text2']}」\n"
            
            if report['examples']['failure']:
                md_content += "\n### 低信頼度の検出例（要確認）\n"
                for i, example in enumerate(report['examples']['failure']):
                    md_content += f"\n{i+1}. {example['type']} (ページ {example['page']}, 信頼度: {example['confidence']:.2f})\n"
                    if 'text1' in example:
                        md_content += f"   - 文書1: 「{example['text1']}」\n"
                    if 'text2' in example:
                        md_content += f"   - 文書2: 「{example['text2']}」\n"
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(md_content)