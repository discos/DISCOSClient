import os
import sys
from pathlib import Path
from argparse import ArgumentParser
from platformdirs import user_config_dir
from zmq.auth import create_certificates

base_config = Path(user_config_dir("discos"))
target_dir = base_config / "rpc" / "client"
KEY_FILENAME = "identity"
full_path_public = target_dir / f"{KEY_FILENAME}.key"
full_path_secret = target_dir / f"{KEY_FILENAME}.key_secret"


def create_discos_keys(overwrite):

    if full_path_secret.exists() and not overwrite:
        print("Kept previously created key pair. "
              "Use --overwrite to replace it.\n")
        return

    try:
        target_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        print(f"Error creating the configuration directory: {e}")
        sys.exit(1)

    create_certificates(str(target_dir), KEY_FILENAME)

    if os.name == 'posix':
        full_path_secret.chmod(0o600)
        (target_dir / f"{KEY_FILENAME}.key").chmod(0o644)
    print(f"Key pair created in: '{target_dir}'.")


def print_discos_keys():
    if not full_path_public.exists():
        print("No key was generated yet.")
        return

    with open(full_path_public, "r", encoding="utf-8") as f:
        print(f.read())
    print(f"\nPath of the public key file: {full_path_public}")
    print(f"Remember to never share the '{KEY_FILENAME}.key_secret' file with "
          "anyone.")
    print(
        "In order to be authorized to send command to any of the telescopes, "
        f"remember to send a copy of the '{KEY_FILENAME}.key' file to the "
        "DISCOS team, asking for authorization. Your request will be taken "
        "into consideration and you will hear back from the team."
    )


def main():
    parser = ArgumentParser(
        "DISCOS CURVE key pairs generator."
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing keys. Dafaults to False."
    )
    parser.add_argument(
        "--show-only",
        action="store_true",
        help="Only prints the public key and its path without \
             generating a new pair."
    )
    args = parser.parse_args()

    if not args.show_only:
        create_discos_keys(args.overwrite)
    print_discos_keys()
