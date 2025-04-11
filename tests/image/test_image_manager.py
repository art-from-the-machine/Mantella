from src.image.image_manager import ImageManager
import pytest
import numpy as np
import cv2
from pathlib import Path
import os
import base64
from unittest.mock import MagicMock, patch
from src.config.config_loader import ConfigLoader
from src.config.definitions.game_definitions import GameEnum

@pytest.fixture
def image_manager(default_config: ConfigLoader, tmp_path: Path):
    """Provides a default ImageManager instance for testing"""
    # Ensure save_folder uses tmp_path for isolation
    default_config.save_folder = str(tmp_path) + os.sep
    # Disable saving screenshots by default in tests unless specified
    default_config.save_screenshot = False
    # Set a known game path for testing game screenshot logic
    default_config.game_path = str(tmp_path / "FakeGameDir")
    os.makedirs(default_config.game_path, exist_ok=True)

    # Mock ctypes call during init
    with patch('ctypes.windll.user32.SetProcessDPIAware', return_value=None):
         manager = ImageManager(
            game=default_config.game,
            save_folder=default_config.save_folder,
            save_screenshot=default_config.save_screenshot,
            image_quality=default_config.image_quality,
            low_resolution_mode=default_config.low_resolution_mode,
            resize_method=default_config.resize_method,
            capture_offset=default_config.capture_offset,
            use_game_screenshots=default_config.use_game_screenshots,
            game_image_path=default_config.game_path
        )
    return manager

@pytest.fixture
def mock_win32gui(mocker):
    """Mocks win32gui functions needed for capture param calculation"""
    mocker.patch('win32gui.FindWindow', return_value=123) # Simulate window found
    mocker.patch('win32gui.GetWindowRect', return_value=(100, 100, 1100, 700)) # Left, Top, Right, Bottom (1000x600 window)
    mocker.patch('win32gui.GetClientRect', return_value=(0, 0, 980, 580)) # Width, Height (Simulate 10px borders)
    mocker.patch('win32gui.ClientToScreen', return_value=(110, 110)) # Simulate client area starts 10px in
    return mocker

@pytest.fixture
def mock_mss(mocker):
    """Mocks the mss screenshot library"""
    mock_sct = MagicMock()
    # Simulate a captured image (eg 100x100 pixels, 3 channels)
    mock_img = np.zeros((100, 100, 3), dtype=np.uint8)
    mock_sct.grab.return_value = MagicMock(width=100, height=100, __array__=lambda: mock_img)

    # Need to mock the context manager `mss.mss()`
    mock_mss_instance = MagicMock()
    mock_mss_instance.__enter__.return_value = mock_sct
    mock_mss_instance.__exit__.return_value = None
    mocker.patch('mss.mss', return_value=mock_mss_instance)
    return mock_sct


def test_init_sets_window_title(default_config: ConfigLoader, tmp_path: Path):
    """Tests if the correct window title is selected based on the game"""
    default_config.save_folder = str(tmp_path) + os.sep
    with patch('ctypes.windll.user32.SetProcessDPIAware', return_value=None):
        # Skyrim Test
        default_config.game = GameEnum.SKYRIM
        im_skyrim = ImageManager(default_config.game, default_config.save_folder, False, 80, False, 'Nearest', {}, False, None)
        assert im_skyrim._ImageManager__window_title == 'Skyrim Special Edition'

        # Fallout VR Test
        default_config.game = GameEnum.FALLOUT4_VR
        im_f4vr = ImageManager(default_config.game, default_config.save_folder, False, 80, False, 'Nearest', {}, False, None)
        assert im_f4vr._ImageManager__window_title == 'Fallout4VR'


def test_init_sets_resize_method(default_config: ConfigLoader, image_manager: ImageManager):
    """Tests if the resize method string maps correctly to a cv2 constant"""
    assert image_manager._ImageManager__resize_method == cv2.INTER_NEAREST # Default config value
    # Test another resize method
    default_config.resize_method = 'Cubic'
    with patch('ctypes.windll.user32.SetProcessDPIAware', return_value=None):
        manager_cubic = ImageManager(default_config.game, default_config.save_folder, False, 80, False, 'Cubic', {}, False, None)
    assert manager_cubic._ImageManager__resize_method == cv2.INTER_CUBIC


def test_init_cleans_old_game_screenshot(default_config: ConfigLoader, tmp_path: Path):
    """Tests if an existing game screenshot is removed on init if configured"""
    default_config.save_folder = str(tmp_path) + os.sep
    default_config.game_path = str(tmp_path / "FakeGameDir")
    os.makedirs(default_config.game_path, exist_ok=True)
    game_screenshot_path = Path(default_config.game_path) / "Mantella_Vision.jpg"

    # Create a dummy screenshot file
    game_screenshot_path.touch()
    assert game_screenshot_path.exists()

    # Init with use_game_screenshots = True
    default_config.use_game_screenshots = True
    with patch('ctypes.windll.user32.SetProcessDPIAware', return_value=None):
         ImageManager(default_config.game, default_config.save_folder, False, 80, False, 'Nearest', {}, True, default_config.game_path)

    # Check if the file was removed
    assert not game_screenshot_path.exists()


def test_calculate_capture_params_success(image_manager: ImageManager, mock_win32gui):
    """Tests successful calculation of capture parameters"""
    params = image_manager._calculate_capture_params()
    assert params is not None
    # Based on mock values:
    # Window: 100, 100, 1100, 700
    # Client Rect: 0, 0, 980, 580
    # ClientToScreen: 110, 110 (implies 10px border left/top)
    # Expected Capture: Left=110, Top=110, Width=980, Height=580 (without offsets)
    assert params['left'] == 110
    assert params['top'] == 110
    assert params['width'] == 980
    assert params['height'] == 580


def test_calculate_capture_params_with_offset(mock_win32gui, default_config: ConfigLoader):
    """Tests capture parameters with offsets applied"""
    default_config.capture_offset = {'left': 5, 'top': 10, 'right': -15, 'bottom': -20}
    # Re-init manager with new config
    with patch('ctypes.windll.user32.SetProcessDPIAware', return_value=None):
        manager_offset = ImageManager(
            default_config.game, default_config.save_folder, False, 80, False, 'Nearest',
            default_config.capture_offset, False, default_config.game_path
        )
    params = manager_offset._calculate_capture_params()
    assert params is not None
    # Expected Capture: Left=110+5, Top=110+10, Width=980-15, Height=580-20
    assert params['left'] == 115
    assert params['top'] == 120
    assert params['width'] == 965
    assert params['height'] == 560


def test_calculate_capture_params_window_not_found(image_manager: ImageManager, mock_win32gui):
    """Tests behavior when the target window is not found"""
    mock_win32gui.patch('win32gui.FindWindow', return_value=0) # Simulate window not found
    params = image_manager._calculate_capture_params()
    assert params is None
    assert image_manager.capture_params is None


def test_capture_params_caching_and_reset(image_manager: ImageManager, mock_win32gui):
    """Tests that capture parameters are cached and can be reset"""
    find_window_mock = mock_win32gui.patch('win32gui.FindWindow', return_value=123)

    # First call calculates
    params1 = image_manager.capture_params
    assert params1 is not None
    assert find_window_mock.call_count == 1

    # Second call should use cache
    params2 = image_manager.capture_params
    assert params2 is params1 # Should be the same object
    assert find_window_mock.call_count == 1 # Should not have called FindWindow again

    # Reset params
    image_manager.reset_capture_params()
    assert image_manager._ImageManager__capture_params is None

    # Third call recalculates
    params3 = image_manager.capture_params
    assert params3 is not None
    assert params3 is not params1 # Should be a new calculation result
    assert find_window_mock.call_count == 2 # FindWindow called again


@pytest.mark.parametrize("low_res_mode, input_w, input_h, expected_w, expected_h", [
    # Low Res Mode Tests
    (True, 1920, 1080, 512, 512), # Scale down wide
    (True, 1080, 1920, 512, 512), # Scale down tall
    (True, 500, 500, 512, 512),   # Scale up square (crop won't happen here as it fits)
    (True, 600, 400, 512, 512),   # Scale up wide, then crop
    # High Res Mode Tests (Max short=768, Max long=2000)
    (False, 1920, 1080, 1365, 768), # Scale down wide (1080 * (768/1080) = 768 short, 1920 * (768/1080) = 1365 long)
    (False, 1080, 1920, 768, 1365), # Scale down tall (1080 * (768/1080) = 768 short, 1920 * (768/1080) = 1365 long)
    (False, 700, 500, 700, 500),     # Fits, no change
    (False, 2100, 600, 2000, 571),   # Scale down by long side (600 * (2000/2100) = 571)
    (False, 700, 800, 700, 800),     # Scale down by short side
    (False, 800, 1000, int(800*(768/800)), int(1000*(768/800))), # Scale down by short side
])
def test_resize_image(image_manager: ImageManager, low_res_mode, input_w, input_h, expected_w, expected_h):
    """Tests the _resize_image logic for various scenarios"""
    image_manager._ImageManager__low_resolution_mode = low_res_mode
    dummy_image = np.zeros((input_h, input_w, 3), dtype=np.uint8)
    resized = image_manager._resize_image(dummy_image, input_w, input_h)
    assert isinstance(resized, np.ndarray)
    assert resized.shape == (expected_h, expected_w, 3)


def test_encode_image_to_jpeg(image_manager: ImageManager):
    """Tests encoding a dummy image to JPEG format"""
    dummy_image = np.zeros((100, 100, 3), dtype=np.uint8)
    buffer = image_manager._encode_image_to_jpeg(dummy_image)
    assert isinstance(buffer, np.ndarray)
    # Check if it looks like JPEG data (starts with FF D8)
    assert buffer.tobytes().startswith(b'\xff\xd8')


def test_save_screenshot_to_file(image_manager: ImageManager, tmp_path: Path):
    """Tests saving the screenshot data to a file"""
    image_manager._ImageManager__save_screenshot = True
    image_manager._ImageManager__window_title = "TestWindow"
    # Ensure the specific image path directory exists within tmp_path
    image_path_dir = tmp_path / 'data' / 'tmp' / 'images'
    image_manager._ImageManager__image_path = str(image_path_dir)
    os.makedirs(image_path_dir, exist_ok=True)

    dummy_bytes = b'\xff\xd8\xff\xe0\x00\x10JFIF' # Minimal valid JPEG start
    image_manager._save_screenshot_to_file(dummy_bytes)

    # Check if a file was created in the expected directory
    saved_files = list(image_path_dir.glob("TestWindow_*.jpg"))
    assert len(saved_files) == 1
    # Check content
    with open(saved_files[0], 'rb') as f:
        content = f.read()
    assert content == dummy_bytes


def test_get_image_success_takes_screenshot(image_manager: ImageManager, mock_win32gui, mock_mss):
    """Tests the successful flow of get_image using mss"""
    image_manager._ImageManager__use_game_screenshots = False # Ensure mss is used
    img_str = image_manager.get_image()
    assert isinstance(img_str, str)
    # Check if it looks like base64
    try:
        import base64
        base64.b64decode(img_str)
    except Exception:
        pytest.fail("Output is not valid base64")

    # Check if mss grab was called (via the mock)
    mock_mss.grab.assert_called_once()


def test_get_image_success_uses_game_screenshot(image_manager: ImageManager, mocker):
    """Tests the successful flow of get_image using a game screenshot file"""
    image_manager._ImageManager__use_game_screenshots = True
    game_screenshot_path = Path(image_manager._ImageManager__game_image_file_path)

    # Mock os.path.exists to return True
    mock_exists = mocker.patch('os.path.exists', return_value=True)
    # Mock cv2.imread to return a dummy image
    dummy_image = np.zeros((200, 300, 3), dtype=np.uint8) # Different size
    mock_imread = mocker.patch('cv2.imread', return_value=dummy_image)
    # Mock os.remove
    mock_remove = mocker.patch('os.remove')

    # Mock capture params so it doesn't fail early
    image_manager._ImageManager__capture_params = {"left": 0, "top": 0, "width": 100, "height": 100}

    img_str = image_manager.get_image()
    assert isinstance(img_str, str)

    # Verify mocks were called correctly
    mock_exists.assert_called_once_with(str(game_screenshot_path))
    mock_imread.assert_called_once_with(str(game_screenshot_path))
    mock_remove.assert_called_once_with(str(game_screenshot_path))

    # Verify the image processed was the one from imread
    try:
        base64.b64decode(img_str)
    except Exception:
        pytest.fail("Output is not valid base64")


def test_get_image_returns_none_if_window_not_found(image_manager: ImageManager, mock_win32gui):
    """Tests get_image returning None when the window isn't found"""
    mock_win32gui.patch('win32gui.FindWindow', return_value=0)
    img_str = image_manager.get_image()
    assert img_str is None


def test_get_image_returns_none_if_game_screenshot_missing(image_manager: ImageManager, mocker):
    """Tests get_image returning None when game screenshot file is expected but missing"""
    image_manager._ImageManager__use_game_screenshots = True
    mock_exists = mocker.patch('os.path.exists', return_value=False) # File doesn't exist
    # Mock capture params so it doesn't fail early
    image_manager._ImageManager__capture_params = {"left": 0, "top": 0, "width": 100, "height": 100}

    img_str = image_manager.get_image()
    assert img_str is None
    mock_exists.assert_called_once()


def test_get_image_handles_exception_and_resets_params(image_manager: ImageManager, mock_win32gui, mocker):
    """Tests error handling within get_image and resetting capture params"""
    image_manager._ImageManager__use_game_screenshots = False # Use mss path

    # Make one of the internal steps raise an error (e.g., resizing)
    mocker.patch.object(image_manager, '_resize_image', side_effect=Exception("Test Resize Error"))
    # Spy on reset_capture_params
    reset_spy = mocker.spy(image_manager, 'reset_capture_params')
    # Mock error sound
    mocker.patch('src.utils.play_error_sound')

    # Pre-calculate params so they exist to be reset
    assert image_manager.capture_params is not None

    img_str = image_manager.get_image()
    assert img_str is None # Should return None on error
    reset_spy.assert_called_once() # Should have reset params