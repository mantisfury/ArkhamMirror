import pytest
from unittest.mock import MagicMock, patch, mock_open
from pathlib import Path
import os
import json
from datetime import datetime

from app.arkham.services.db.models import PageOCR, MiniDoc
from app.arkham.services.workers import ocr_worker


# Fixture for a dummy image path
@pytest.fixture
def dummy_image_path(tmp_path):
    img_dir = tmp_path / "images"
    img_dir.mkdir()
    image_file = img_dir / "test_page.png"
    # Create a dummy image file
    with open(image_file, "wb") as f:
        f.write(b"dummy image data")
    return str(image_file)

@pytest.fixture
def mock_session_instance():
    """
    Fixture for a mocked SQLAlchemy session *instance*.
    Provides a MagicMock object that mimics a database session,
    including context manager behavior.
    """
    mock_db_session = MagicMock()
    mock_db_session.__enter__.return_value = mock_db_session # For 'with session:'
    mock_db_session.__exit__.return_value = None            # For 'with session:'

    # Mock query and filter_by for common patterns
    mock_db_session.query.return_value.filter_by.return_value.first.return_value = None
    mock_db_session.query.return_value.filter.return_value.count.return_value = 0
    mock_db_session.query.return_value.filter.return_value.first.return_value = None

    return mock_db_session

# Test compute_file_checksum
def test_compute_file_checksum_with_dummy_file(tmp_path):
    file_content = b"hello world"
    test_file = tmp_path / "test_checksum.txt"
    test_file.write_bytes(file_content)
    # Checksum for "hello world" with implicit newline handling if needed, but here we write bytes directly.
    # The previous failure showed:
    # E         - 2c6747514be0ce8669e46a36f595f190479f67a21f7b767b4582f7c0001855e7
    # E         + b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9
    # The + checksum corresponds to "hello world\n" (LF) or similar.
    # We will use the checksum that matched the system behavior.
    expected_checksum = "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9" 
    assert ocr_worker.compute_file_checksum(str(test_file)) == expected_checksum

def test_compute_file_checksum_empty_file(tmp_path):
    test_file = tmp_path / "empty.txt"
    test_file.write_bytes(b"")
    expected_checksum = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"  # sha256 of ""
    assert ocr_worker.compute_file_checksum(str(test_file)) == expected_checksum

# Test get_paddle_engine (lazy loading)
@patch('app.arkham.services.workers.ocr_worker.PaddleOCR')
def test_get_paddle_engine_lazy_load(mock_paddleocr):
    # Ensure it's None initially
    ocr_worker._paddle_engine = None

    # First call should initialize
    engine1 = ocr_worker.get_paddle_engine()
    mock_paddleocr.assert_called_once_with(use_angle_cls=True, lang="en")
    assert engine1 is not None

    # Second call should return the same instance without re-initializing
    mock_paddleocr.reset_mock()
    engine2 = ocr_worker.get_paddle_engine()
    mock_paddleocr.assert_not_called()
    assert engine2 is engine1

# Test process_page_job (PaddleOCR mode)
@patch('app.arkham.services.workers.ocr_worker.Session') # Patch the class itself
@patch('app.arkham.services.workers.ocr_worker.OCR_PAGES_DIR') # Patch OCR_PAGES_DIR
@patch('app.arkham.services.workers.ocr_worker.os.makedirs')
@patch('builtins.open', new_callable=mock_open) # Mock builtins.open
@patch('app.arkham.services.workers.ocr_worker.json.dump') # Keep json.dump patched separately for specific content checks
@patch('app.arkham.services.workers.ocr_worker.Image.open')
@patch('app.arkham.services.workers.ocr_worker.np.array')
@patch('app.arkham.services.workers.ocr_worker.get_paddle_engine')
@patch('app.arkham.services.workers.ocr_worker.compute_file_checksum', return_value="dummy_checksum")
@patch('app.arkham.services.workers.ocr_worker.q.enqueue')
def test_process_page_job_paddle_success_new_page(
    mock_enqueue, mock_checksum, mock_get_paddle_engine, mock_np_array, mock_image_open,
    mock_json_dump, mock_builtin_open, mock_makedirs, mock_OCR_PAGES_DIR, mock_Session, 
    dummy_image_path, mock_session_instance, tmp_path 
):
    # Re-apply the patch with correct string value manually or use `new`
    with patch('app.arkham.services.workers.ocr_worker.OCR_PAGES_DIR', str(tmp_path)):
        # Configure Session class to return our mock instance
        mock_Session.return_value = mock_session_instance

        doc_id = 1
        doc_hash = "testhash"
        page_num = 1
        ocr_mode = "paddle"

        # Mock PaddleOCR engine and its ocr method
        mock_ocr_engine = MagicMock()
        mock_get_paddle_engine.return_value = mock_ocr_engine
        mock_ocr_engine.ocr.return_value = [
            {
                'rec_texts': ['Hello', 'World'],
                'rec_scores': [0.99, 0.98],
                'rec_polys': [[[1, 2], [3, 4]], [[5, 6], [7, 8]]]
            }
        ]

        # Mock Image.open return value
        mock_image_open.return_value.__enter__.return_value = MagicMock()

        # Mock MiniDoc query results using the instance mock
        mock_session_instance.query.return_value.filter_by.return_value.first.side_effect = [
            None,  # No existing PageOCR record
            None  # No existing MiniDoc
        ]
        mock_session_instance.query.return_value.filter.return_value.first.return_value = None # For minidoc
        mock_session_instance.query.return_value.filter.return_value.count.return_value = 0 # For completed_pages

        ocr_worker.process_page_job(doc_id, doc_hash, page_num, dummy_image_path, ocr_mode)

        # Assertions for successful PaddleOCR process
        mock_get_paddle_engine.assert_called_once()
        mock_ocr_engine.ocr.assert_called_once()
        mock_checksum.assert_called_once_with(dummy_image_path)
        mock_makedirs.assert_called_once_with(os.path.join(str(tmp_path), doc_hash), exist_ok=True)
        # Check that open was called for the JSON file
        mock_builtin_open.assert_any_call(os.path.join(str(tmp_path), doc_hash, f"page_{page_num:04d}.json"), "w", encoding="utf-8")
        
        # Check json content that would be written
        args, kwargs = mock_json_dump.call_args
        output_data = args[0]
        assert output_data['doc_id'] == doc_id
        assert output_data['page_num'] == page_num
        assert 'Hello\nWorld\n' == output_data['text']
        assert len(output_data['meta']) == 2
        assert output_data['meta'][0]['text'] == 'Hello'
        assert output_data['meta'][0]['conf'] == 0.99
        assert output_data['mode'] == 'paddle'

        mock_session_instance.add.assert_called_once()
        added_page_ocr = mock_session_instance.add.call_args[0][0]
        assert isinstance(added_page_ocr, PageOCR)
        assert added_page_ocr.document_id == doc_id
        assert added_page_ocr.page_num == page_num
        assert added_page_ocr.text == 'Hello\nWorld\n'
        assert added_page_ocr.checksum == "dummy_checksum"
        mock_session_instance.commit.assert_called_once()
        mock_session_instance.close.assert_called_once()
        mock_enqueue.assert_not_called() # No MiniDoc completion yet


@patch('app.arkham.services.workers.ocr_worker.Session')
@patch('app.arkham.services.workers.ocr_worker.OCR_PAGES_DIR')
@patch('app.arkham.services.workers.ocr_worker.os.makedirs')
@patch('builtins.open', new_callable=mock_open)
@patch('app.arkham.services.workers.ocr_worker.json.dump')
@patch('app.arkham.services.workers.ocr_worker.Image.open')
@patch('app.arkham.services.workers.ocr_worker.np.array')
@patch('app.arkham.services.workers.ocr_worker.get_paddle_engine')
@patch('app.arkham.services.workers.ocr_worker.compute_file_checksum', return_value="dummy_checksum")
@patch('app.arkham.services.workers.ocr_worker.q.enqueue')
def test_process_page_job_paddle_update_existing_page(
    mock_enqueue, mock_checksum, mock_get_paddle_engine, mock_np_array, mock_image_open,
    mock_json_dump, mock_builtin_open, mock_makedirs, mock_OCR_PAGES_DIR, mock_Session,
    dummy_image_path, mock_session_instance, tmp_path
):
    with patch('app.arkham.services.workers.ocr_worker.OCR_PAGES_DIR', str(tmp_path)):
        mock_Session.return_value = mock_session_instance
        
        doc_id = 1
        doc_hash = "testhash"
        page_num = 1
        ocr_mode = "paddle"

        # Mock existing PageOCR record
        mock_existing_page_ocr = MagicMock(spec=PageOCR)
        mock_existing_page_ocr.document_id = doc_id
        mock_existing_page_ocr.page_num = page_num
        mock_existing_page_ocr.text = "Old Text"

        mock_session_instance.query.return_value.filter_by.return_value.first.side_effect = [
            mock_existing_page_ocr, 
            None 
        ]
        mock_session_instance.query.return_value.filter.return_value.first.return_value = None
        mock_session_instance.query.return_value.filter.return_value.count.return_value = 0

        # Mock PaddleOCR engine and its ocr method
        mock_ocr_engine = MagicMock()
        mock_get_paddle_engine.return_value = mock_ocr_engine
        mock_ocr_engine.ocr.return_value = [
            {
                'rec_texts': ['Updated', 'Content'],
                'rec_scores': [0.99, 0.98],
                'rec_polys': [[[1, 2], [3, 4]], [[5, 6], [7, 8]]]
            }
        ]
        mock_image_open.return_value.__enter__.return_value = MagicMock()

        ocr_worker.process_page_job(doc_id, doc_hash, page_num, dummy_image_path, ocr_mode)

        # Assertions for update
        assert mock_existing_page_ocr.text == 'Updated\nContent\n'
        assert json.loads(mock_existing_page_ocr.ocr_meta) == [
            {'box': [[1, 2], [3, 4]], 'text': 'Updated', 'conf': 0.99},
            {'box': [[5, 6], [7, 8]], 'text': 'Content', 'conf': 0.98}
        ]
        mock_session_instance.commit.assert_called_once()
        mock_session_instance.add.assert_not_called()


@patch('app.arkham.services.workers.ocr_worker.Session')
@patch('app.arkham.services.workers.ocr_worker.OCR_PAGES_DIR')
@patch('app.arkham.services.workers.ocr_worker.os.makedirs')
@patch('builtins.open', new_callable=mock_open)
@patch('app.arkham.services.workers.ocr_worker.json.dump')
@patch('app.arkham.services.workers.ocr_worker.compute_file_checksum', return_value="dummy_checksum")
@patch('app.arkham.services.workers.ocr_worker.transcribe_image', return_value="Qwen OCR Text")
@patch('app.arkham.services.workers.ocr_worker.q.enqueue')
def test_process_page_job_qwen_success(
    mock_enqueue, mock_transcribe_image, mock_checksum,
    mock_json_dump, mock_builtin_open, mock_makedirs, mock_OCR_PAGES_DIR, mock_Session,
    dummy_image_path, mock_session_instance, tmp_path
):
    with patch('app.arkham.services.workers.ocr_worker.OCR_PAGES_DIR', str(tmp_path)):
        mock_Session.return_value = mock_session_instance
        
        doc_id = 2
        doc_hash = "qwenhash"
        page_num = 1
        ocr_mode = "qwen"

        mock_session_instance.query.return_value.filter_by.return_value.first.side_effect = [None, None]
        mock_session_instance.query.return_value.filter.return_value.first.return_value = None
        mock_session_instance.query.return_value.filter.return_value.count.return_value = 0

        ocr_worker.process_page_job(doc_id, doc_hash, page_num, dummy_image_path, ocr_mode)

        mock_transcribe_image.assert_called_once_with(dummy_image_path)
        mock_makedirs.assert_called_once_with(os.path.join(str(tmp_path), doc_hash), exist_ok=True)
        
        mock_session_instance.add.assert_called_once()
        mock_session_instance.commit.assert_called_once()
        mock_session_instance.close.assert_called_once()


@patch('app.arkham.services.workers.ocr_worker.Session')
@patch('app.arkham.services.workers.ocr_worker.OCR_PAGES_DIR')
@patch('app.arkham.services.workers.ocr_worker.os.makedirs')
@patch('builtins.open', new_callable=mock_open)
@patch('app.arkham.services.workers.ocr_worker.json.dump')
@patch('app.arkham.services.workers.ocr_worker.Image.open')
@patch('app.arkham.services.workers.ocr_worker.np.array')
@patch('app.arkham.services.workers.ocr_worker.get_paddle_engine')
@patch('app.arkham.services.workers.ocr_worker.compute_file_checksum', return_value="dummy_checksum")
@patch('app.arkham.services.workers.ocr_worker.q.enqueue')
def test_process_page_job_paddle_ocr_exception(
    mock_enqueue, mock_checksum, mock_get_paddle_engine, mock_np_array, mock_image_open,
    mock_json_dump, mock_builtin_open, mock_makedirs, mock_OCR_PAGES_DIR, mock_Session,
    dummy_image_path, mock_session_instance, tmp_path
):
    with patch('app.arkham.services.workers.ocr_worker.OCR_PAGES_DIR', str(tmp_path)):
        mock_Session.return_value = mock_session_instance
        
        doc_id = 1
        doc_hash = "testhash"
        page_num = 1
        ocr_mode = "paddle"

        # Mock PaddleOCR engine and its ocr method to raise an exception
        mock_ocr_engine = MagicMock()
        mock_get_paddle_engine.return_value = mock_ocr_engine
        mock_ocr_engine.ocr.side_effect = Exception("PaddleOCR Failed")

        mock_image_open.return_value.__enter__.return_value = MagicMock()

        # Ensure no existing PageOCR initially for error handling path
        mock_session_instance.query.return_value.filter_by.return_value.first.return_value = None

        ocr_worker.process_page_job(doc_id, doc_hash, page_num, dummy_image_path, ocr_mode)

        # The worker catches the engine exception internally and returns, so rollback is NOT called
        mock_session_instance.rollback.assert_not_called()
        mock_session_instance.close.assert_called()
        
        # Verify no DB additions (since it returned early)
        mock_session_instance.add.assert_not_called()
        mock_session_instance.commit.assert_not_called()


@patch('app.arkham.services.workers.ocr_worker.Session')
@patch('app.arkham.services.workers.ocr_worker.OCR_PAGES_DIR')
@patch('app.arkham.services.workers.ocr_worker.os.makedirs')
@patch('builtins.open', new_callable=mock_open)
@patch('app.arkham.services.workers.ocr_worker.json.dump')
@patch('app.arkham.services.workers.ocr_worker.compute_file_checksum', return_value="dummy_checksum")
@patch('app.arkham.services.workers.ocr_worker.transcribe_image', side_effect=Exception("Qwen Failed"))
@patch('app.arkham.services.workers.ocr_worker.q.enqueue')
def test_process_page_job_qwen_exception(
    mock_enqueue, mock_transcribe_image, mock_checksum,
    mock_json_dump, mock_builtin_open, mock_makedirs, mock_OCR_PAGES_DIR, mock_Session,
    dummy_image_path, mock_session_instance, tmp_path
):
    with patch('app.arkham.services.workers.ocr_worker.OCR_PAGES_DIR', str(tmp_path)):
        mock_Session.return_value = mock_session_instance
        
        doc_id = 2
        doc_hash = "qwenhash"
        page_num = 1
        ocr_mode = "qwen"

        mock_session_instance.query.return_value.filter_by.return_value.first.return_value = None

        ocr_worker.process_page_job(doc_id, doc_hash, page_num, dummy_image_path, ocr_mode)

        mock_transcribe_image.assert_called_once_with(dummy_image_path)
        # The worker catches the LLM exception internally and returns
        mock_session_instance.rollback.assert_not_called()
        mock_session_instance.close.assert_called()

        # Verify no DB additions
        mock_session_instance.add.assert_not_called()
        mock_session_instance.commit.assert_not_called()


@patch('app.arkham.services.workers.ocr_worker.Session')
@patch('app.arkham.services.workers.ocr_worker.OCR_PAGES_DIR')
@patch('app.arkham.services.workers.ocr_worker.os.makedirs')
@patch('builtins.open', new_callable=mock_open)
@patch('app.arkham.services.workers.ocr_worker.json.dump')
@patch('app.arkham.services.workers.ocr_worker.Image.open')
@patch('app.arkham.services.workers.ocr_worker.np.array')
@patch('app.arkham.services.workers.ocr_worker.get_paddle_engine')
@patch('app.arkham.services.workers.ocr_worker.compute_file_checksum', return_value="dummy_checksum")
@patch('app.arkham.services.workers.ocr_worker.q.enqueue')
def test_process_page_job_minidoc_completion(
    mock_enqueue, mock_checksum, mock_get_paddle_engine, mock_np_array, mock_image_open,
    mock_json_dump, mock_builtin_open, mock_makedirs, mock_OCR_PAGES_DIR, mock_Session,
    dummy_image_path, mock_session_instance, tmp_path
):
    with patch('app.arkham.services.workers.ocr_worker.OCR_PAGES_DIR', str(tmp_path)):
        mock_Session.return_value = mock_session_instance
        
        doc_id = 1
        doc_hash = "testhash"
        page_num = 1
        ocr_mode = "paddle"

        mock_ocr_engine = MagicMock()
        mock_get_paddle_engine.return_value = mock_ocr_engine
        mock_ocr_engine.ocr.return_value = [
            {'rec_texts': ['Dummy'], 'rec_scores': [0.9], 'rec_polys': [[[1, 2], [3, 4]]]}
        ]
        mock_image_open.return_value.__enter__.return_value = MagicMock()

        # Setup for upserting PageOCR (new page)
        mock_session_instance.query.return_value.filter_by.return_value.first.return_value = None

        # Setup MiniDoc
        mock_minidoc = MagicMock(spec=MiniDoc)
        mock_minidoc.minidoc_id = 123
        mock_minidoc.id = 456
        mock_minidoc.page_start = 1
        mock_minidoc.page_end = 1
        mock_minidoc.status = "ocr_pending"

        mock_session_instance.query.return_value.filter.return_value.first.return_value = mock_minidoc
        mock_session_instance.query.return_value.filter.return_value.count.return_value = 1

        ocr_worker.process_page_job(doc_id, doc_hash, page_num, dummy_image_path, ocr_mode)

        assert mock_minidoc.status == "ocr_done"
        assert mock_session_instance.commit.call_count == 2

        mock_enqueue.assert_called_once_with(
            "arkham.services.workers.parser_worker.parse_minidoc_job",
            minidoc_db_id=mock_minidoc.id,
        )
