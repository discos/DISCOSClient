import unittest
import sys
import shutil
import tempfile
from io import StringIO
from pathlib import Path
from unittest.mock import patch, MagicMock
from platformdirs import user_config_dir
from zmq.auth import create_certificates, load_certificate
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
        config_dir, public, secret = scripts.get_config_paths("identity")
        expected_config_dir = \
            Path(user_config_dir("discos")) / "rpc" / "client"
        expected_public = expected_config_dir / "identity.key"
        expected_secret = expected_config_dir / "identity.key_secret"
        self.assertEqual(config_dir, expected_config_dir)
        self.assertEqual(public, expected_public)
        self.assertEqual(secret, expected_secret)

    @patch("discos_client.scripts.get_config_paths")
    @patch("sys.stdout", new_callable=StringIO)
    @patch.object(sys, "argv", ["discos-keygen", "identity"])
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
        self.assertIn("Key pair 'identity' created in", output)

    @patch("discos_client.scripts.get_config_paths")
    @patch("sys.stdout", new_callable=StringIO)
    @patch.object(sys, "argv", ["discos-keygen", "identity"])
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
        self.assertIn("Key pair 'identity' created in", output)
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
        scripts.print_discos_keys("identity")
        output = mock_stdout.getvalue()
        self.assertIn("No key named 'identity' was found.", output)

    @patch("discos_client.scripts.get_config_paths")
    @patch("sys.stdout", new_callable=StringIO)
    def test_mkdir_error(self, mock_stdout, mock_paths):
        mock_target_dir = MagicMock()
        mock_target_dir.mkdir.side_effect = OSError("Test error")

        mock_paths.return_value = (
            mock_target_dir,
            self.mock_public,
            self.mock_secret
        )

        with patch.object(sys, "argv", ["discos-keygen", "identity"]):
            rc = scripts.keygen()
            self.assertEqual(rc, 1)
            output = mock_stdout.getvalue()
            self.assertIn("Error creating the configuration directory", output)

        mock_stdout.truncate(0)
        mock_stdout.seek(0)

        source_dir = Path(tempfile.mkdtemp())
        create_certificates(str(source_dir), "identity")
        source_secret = source_dir / "identity.key_secret"

        with patch.object(
            sys,
            "argv",
            ["discos-keygen", "--import-pair", str(source_secret), "identity"]
        ):
            rc = scripts.keygen()
            self.assertEqual(rc, 1)
            output = mock_stdout.getvalue()
            self.assertIn("Error creating the configuration directory", output)

        shutil.rmtree(source_dir)

    @patch("discos_client.scripts.get_config_paths")
    @patch("sys.stdout", new_callable=StringIO)
    @patch.object(sys, "argv", ["discos-keygen", "--show-only", "identity"])
    def test_keygen_show_only(self, mock_stdout, mock_paths):
        self.mock_target_dir.mkdir(parents=True, exist_ok=True)
        create_certificates(str(self.mock_target_dir), "identity")

        mock_paths.return_value = (
            self.mock_target_dir,
            self.mock_public,
            self.mock_secret
        )

        rc = scripts.keygen()

        self.assertEqual(rc, 0)
        output = mock_stdout.getvalue()
        self.assertIn("public-key =", output)
        self.assertIn(
            f"Path of the public key file: {self.mock_public}", output
        )

    @patch("discos_client.scripts.get_config_paths")
    @patch("sys.stdout", new_callable=StringIO)
    def test_keygen_import_success(self, mock_stdout, mock_paths):
        source_dir = Path(tempfile.mkdtemp())
        create_certificates(str(source_dir), "identity")
        source_secret = source_dir / "identity.key_secret"

        src_pub, src_sec = load_certificate(str(source_secret))

        mock_paths.return_value = (
            self.mock_target_dir,
            self.mock_public,
            self.mock_secret
        )

        with patch.object(
            sys,
            "argv",
            ["discos-keygen", "--import-pair", str(source_secret), "identity"]
        ):
            rc = scripts.keygen()

        self.assertEqual(rc, 0)
        self.assertTrue(self.mock_public.exists())
        self.assertTrue(self.mock_secret.exists())

        dst_pub, dst_sec = load_certificate(str(self.mock_secret))
        self.assertEqual(src_sec, dst_sec)
        self.assertEqual(src_pub, dst_pub)

        output = mock_stdout.getvalue()
        self.assertIn("Keys 'identity' imported successfully to", output)

        shutil.rmtree(source_dir)

    @patch("discos_client.scripts.get_config_paths")
    @patch("sys.stdout", new_callable=StringIO)
    def test_keygen_import_file_not_found(self, mock_stdout, mock_paths):
        non_existent = self.test_path / "non_existent.key_secret"

        mock_paths.return_value = (
            self.mock_target_dir,
            self.mock_public,
            self.mock_secret
        )

        with patch.object(
            sys,
            "argv",
            ["discos-keygen", "--import-pair", str(non_existent), "identity"]
        ):
            rc = scripts.keygen()

        self.assertEqual(rc, 1)
        output = mock_stdout.getvalue()
        self.assertIn("Error: Secret key file not found", output)

    @patch("discos_client.scripts.get_config_paths")
    @patch("sys.stdout", new_callable=StringIO)
    def test_keygen_import_invalid_file(self, mock_stdout, mock_paths):
        source_dir = Path(tempfile.mkdtemp())
        invalid_file = source_dir / "invalid.key"
        with open(invalid_file, "w", encoding="utf-8") as f:
            f.write("This is not a ZMQ key file")

        mock_paths.return_value = (
            self.mock_target_dir,
            self.mock_public,
            self.mock_secret
        )

        with patch.object(
            sys,
            "argv",
            ["discos-keygen", "--import-pair", str(invalid_file), "identity"]
        ):
            rc = scripts.keygen()

        self.assertEqual(rc, 1)
        output = mock_stdout.getvalue()
        self.assertIn("Error reading secret key file", output)

        shutil.rmtree(source_dir)

    @patch("discos_client.scripts.get_config_paths")
    @patch("sys.stdout", new_callable=StringIO)
    def test_keygen_import_no_overwrite(self, mock_stdout, mock_paths):
        self.mock_target_dir.mkdir(parents=True, exist_ok=True)
        create_certificates(str(self.mock_target_dir), "identity")

        orig_pub, orig_sec = load_certificate(str(self.mock_secret))

        source_dir = Path(tempfile.mkdtemp())
        create_certificates(str(source_dir), "identity")
        source_secret = source_dir / "identity.key_secret"

        mock_paths.return_value = (
            self.mock_target_dir,
            self.mock_public,
            self.mock_secret
        )

        with patch.object(
            sys,
            "argv",
            ["discos-keygen", "--import-pair", str(source_secret), "identity"]
        ):
            rc = scripts.keygen()

        self.assertEqual(rc, 0)
        output = mock_stdout.getvalue()
        self.assertIn("Kept previously created key pair", output)

        current_pub, current_sec = load_certificate(str(self.mock_secret))
        self.assertEqual(current_pub, orig_pub)
        self.assertEqual(current_sec, orig_sec)

        shutil.rmtree(source_dir)

    @patch("sys.stdout", new_callable=StringIO)
    def test_set_permissions_oserror(self, mock_stdout):
        mock_pub = MagicMock()
        mock_sec = MagicMock()

        error = OSError("Permission denied")
        mock_pub.chmod.side_effect = error

        with patch("os.name", "posix"):
            scripts.set_permissions(mock_pub, mock_sec)

        output = mock_stdout.getvalue()
        self.assertIn("Warning: Could not set permissions", output)
        self.assertIn("Permission denied", output)


if __name__ == "__main__":
    unittest.main()
