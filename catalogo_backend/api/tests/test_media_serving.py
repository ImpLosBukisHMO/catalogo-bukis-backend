from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import SimpleTestCase, override_settings


class MediaServingProductionTest(SimpleTestCase):
    @override_settings(DEBUG=False, MEDIA_URL="/media/")
    def test_media_url_serves_uploaded_file_when_debug_is_false(self):
        expected_content = b"bukis-media-regression"
        relative_path = Path("img/products/test-media-serving.txt")

        with TemporaryDirectory() as media_root:
            absolute_path = Path(media_root) / relative_path
            absolute_path.parent.mkdir(parents=True, exist_ok=True)
            absolute_path.write_bytes(expected_content)

            with override_settings(MEDIA_ROOT=media_root):
                response = self.client.get(f"/media/{relative_path.as_posix()}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(b"".join(response.streaming_content), expected_content)
