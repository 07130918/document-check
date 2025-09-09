# coding: utf-8
"""
PyMuPDF "bad quads entry" エラー修正のテストファイル
"""

import sys
import logging
from pathlib import Path

# プロジェクトルートをPATHに追加
sys.path.append(str(Path(__file__).parent.parent.parent))

# ログ設定
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def test_coordinate_validation():
    """座標検証機能のテスト"""
    from handlers.enhanced_output_handler_v3_4 import EnhancedOutputHandlerV34
    
    handler = EnhancedOutputHandlerV34()
    
    # テストケース1: 正常な座標
    valid_coords = {
        'left': 1.0764,
        'top': 5.0382,
        'right': 7.9888,
        'bottom': 11.4585,
        'width': 6.9124,
        'height': 6.4203
    }
    
    result = handler._validate_coordinates(valid_coords)
    print(f"✅ 正常な座標のテスト: {result}")
    assert result == True, "正常な座標が無効と判定されました"
    
    # テストケース2: width/heightから計算
    coords_with_wh = {
        'left': 1.0,
        'top': 2.0,
        'width': 3.0,
        'height': 4.0
    }
    
    result = handler._validate_coordinates(coords_with_wh)
    print(f"✅ width/height座標のテスト: {result}")
    assert result == True, "width/height座標が無効と判定されました"
    
    # テストケース3: 無効な座標（負の値）
    invalid_coords = {
        'left': -1.0,
        'top': 5.0,
        'right': 7.0,
        'bottom': 11.0
    }
    
    result = handler._validate_coordinates(invalid_coords)
    print(f"✅ 無効な座標（負の値）のテスト: {result}")
    assert result == False, "無効な座標が正常と判定されました"
    
    # テストケース4: 異常に大きな座標
    oversized_coords = {
        'left': 1.0,
        'top': 2.0,
        'right': 50.0,  # 異常に大きな値
        'bottom': 60.0
    }
    
    result = handler._validate_coordinates(oversized_coords)
    print(f"✅ 異常に大きな座標のテスト: {result}")
    assert result == False, "異常に大きな座標が正常と判定されました"
    
    print("✅ 座標検証テスト：全て成功")

def test_coordinate_conversion():
    """座標変換機能のテスト"""
    from handlers.enhanced_output_handler_v3_4 import EnhancedOutputHandlerV34
    import fitz
    
    handler = EnhancedOutputHandlerV34()
    
    # 模擬PDFページ作成
    doc = fitz.open()
    page = doc.new_page(width=595.276, height=841.890)  # A4サイズ（ポイント）
    
    # テスト座標（インチ単位）
    test_coords = {
        'left': 1.0,
        'top': 1.0, 
        'right': 2.0,
        'bottom': 2.0
    }
    
    rect = handler._create_valid_rect(test_coords, page)
    
    print(f"✅ 座標変換テスト:")
    print(f"  元座標: {test_coords}")
    if rect:
        print(f"  変換後: ({rect.x0:.1f}, {rect.y0:.1f}, {rect.x1:.1f}, {rect.y1:.1f})")
        print(f"  期待値: (72.0, 72.0, 144.0, 144.0)")  # 1inch * 72DPI
        
        # 検証
        expected_scale = 72.0
        assert abs(rect.x0 - test_coords['left'] * expected_scale) < 0.1, "X座標の変換が不正確"
        assert abs(rect.y0 - test_coords['top'] * expected_scale) < 0.1, "Y座標の変換が不正確"
        assert rect.is_valid, "変換後の矩形が無効"
        
        print("✅ 座標変換：成功")
    else:
        print("❌ 座標変換：失敗")
        assert False, "座標変換に失敗しました"
    
    doc.close()

def test_annotation_color_determination():
    """注釈色決定のテスト"""
    from handlers.enhanced_output_handler_v3_4 import EnhancedOutputHandlerV34
    
    handler = EnhancedOutputHandlerV34()
    
    # テストケース
    test_cases = [
        ('DELETION', True, (1, 0, 0)),     # 削除 + 文書1 = 赤
        ('ADDITION', False, (0, 1, 0)),    # 追加 + 文書2 = 緑
        ('MODIFICATION', True, (1, 0.8, 0)), # 変更 = オレンジ
        ('MODIFICATION', False, (1, 0.8, 0)), # 変更 = オレンジ
        ('REPLACEMENT', True, (1, 1, 0)),  # 置換 = 黄色
        ('UNKNOWN', True, None),           # 不明 = None
    ]
    
    for change_type, is_doc1, expected in test_cases:
        result = handler._determine_annotation_color(change_type, is_doc1)
        print(f"✅ 色決定テスト: {change_type} + {'文書1' if is_doc1 else '文書2'} → {result}")
        assert result == expected, f"色決定が不正確: {change_type}, {is_doc1}, 期待値: {expected}, 実際: {result}"
    
    print("✅ 注釈色決定テスト：全て成功")

def test_safe_annotation():
    """安全な注釈追加のテスト"""
    from handlers.enhanced_output_handler_v3_4 import EnhancedOutputHandlerV34
    import fitz
    
    handler = EnhancedOutputHandlerV34()
    
    # 模擬PDFページ作成
    doc = fitz.open()
    page = doc.new_page(width=595.276, height=841.890)  # A4サイズ
    
    # テスト用矩形
    rect = fitz.Rect(100, 100, 200, 150)
    color = (1, 0, 0)  # 赤
    
    # 注釈追加テスト
    success = handler._add_safe_annotation(page, rect, color, "TEST", 1)
    
    print(f"✅ 安全な注釈追加テスト: {success}")
    assert success == True, "注釈追加に失敗しました"
    
    doc.close()
    print("✅ 安全な注釈追加テスト：成功")

def main():
    """メイン関数"""
    print("🔧 PyMuPDF修正内容の検証テストを開始")
    print("=" * 50)
    
    try:
        # テスト実行
        test_coordinate_validation()
        print()
        
        test_coordinate_conversion()
        print()
        
        test_annotation_color_determination()
        print()
        
        test_safe_annotation()
        print()
        
        print("=" * 50)
        print("🎉 全てのテストが成功しました！")
        print("✅ PyMuPDF 'bad quads entry' エラーの修正が完了")
        
        # 修正内容のサマリー
        print("\n📋 修正内容サマリー:")
        print("1. ✅ 座標検証機能の強化 (_validate_coordinates)")
        print("2. ✅ 座標変換ロジックの改良 (_create_valid_rect)")
        print("3. ✅ 安全な注釈追加メソッドの実装 (_add_safe_annotation)")
        print("4. ✅ エラーハンドリングの詳細化")
        print("5. ✅ デバッグログの充実")
        
    except Exception as e:
        print(f"❌ テスト失敗: {e}")
        logger.exception("テスト実行中にエラーが発生しました")
        return False
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)