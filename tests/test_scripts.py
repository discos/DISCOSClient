import unittest
import sys
import shutil
import tempfile
from io import StringIO
from pathlib import Path
from unittest.mock import patch, MagicMock
from platformdirs import user_config_dir
from discos_client import scripts


class TestKeygen(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.test_path = Path(self.test_dir)
        self.mock_target_dir = self.test_path / "rpc" / "client"
        self.mock_public = self.mock_target_dir / "identity.key"
        self.mock_secret = self.mock_target_dir / "identity.key_secret"

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_correct_paths(self):
        config_dir, public, secret = scripts.get_config_paths()
        expected_config_dir = \
            Path(user_config_dir("discos")) / "rpc" / "client"
        expected_public = expected_config_dir / "identity.key"
        expected_secret = expected_config_dir / "identity.key_secret"
        self.assertEqual(config_dir, expected_config_dir)
        self.assertEqual(public, expected_public)
        self.assertEqual(secret, expected_secret)

    @patch("discos_client.scripts.get_config_paths")
    @patch("sys.stdout", new_callable=StringIO)
    @patch.object(sys, "argv", ["discos-keygen"])
    def test_keygen(self, mock_stdout, mock_paths):
        mock_paths.return_value = (
            self.mock_target_dir,
            self.mock_public,
            self.mock_secret
        )
        rc = scripts.keygen()
        self.assertEqual(rc, 0)
        self.assertTrue(self.mock_public.exists())
        self.assertTrue(self.mock_secret.exists())
        output = mock_stdout.getvalue()
        self.assertIn("Key pair created in", output)

    @patch("discos_client.scripts.get_config_paths")
    @patch("sys.stdout", new_callable=StringIO)
    @patch.object(sys, "argv", ["discos-keygen"])
    def test_keygen_no_overwrite(self, mock_stdout, mock_paths):
        mock_paths.return_value = (
            self.mock_target_dir,
            self.mock_public,
            self.mock_secret
        )
        self.assertEqual(scripts.keygen(), 0)
        self.assertTrue(self.mock_public.exists())
        self.assertTrue(self.mock_secret.exists())
        output = mock_stdout.getvalue()
        self.assertIn("Key pair created in", output)
        self.assertEqual(scripts.keygen(), 0)
        output = mock_stdout.getvalue()
        self.assertIn("Kept previously created key pair", output)

    @patch("discos_client.scripts.get_config_paths")
    @patch("sys.stdout", new_callable=StringIO)
    def test_print_keys(self, mock_stdout, mock_paths):
        mock_paths.return_value = (
            self.mock_target_dir,
            self.mock_public,
            self.mock_secret
        )
        scripts.print_discos_keys()
        output = mock_stdout.getvalue()
        self.assertIn("No key was generated yet.", output)

    @patch("discos_client.scripts.get_config_paths")
    @patch("sys.stdout", new_callable=StringIO)
    @patch.object(sys, "argv", ["discos-keygen"])
    def test_mkdir_error(self, mock_stdout, mock_paths):
        mock_target_dir = MagicMock()
        mock_target_dir.mkdir.side_effect = OSError("Test error")
        mock_paths.return_value = (
            mock_target_dir,
            self.mock_public,
            self.mock_secret
        )
        rc = scripts.keygen()
        self.assertEqual(rc, 1)
        output = mock_stdout.getvalue()
        self.assertIn("Error creating the configuration directory", output)


if __name__ == "__main__":
    unittest.main()
