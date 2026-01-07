import os
from pathlib import Path
from argparse import ArgumentParser
from platformdirs import user_config_dir
from zmq.auth import create_certificates


def get_config_paths():
    base_config = Path(user_config_dir("discos"))
    config_dir = base_config / "rpc" / "client"
    public = config_dir / "identity.key"
    secret = config_dir / "identity.key_secret"
    return config_dir, public, secret


def create_discos_keys(overwrite):
    config_dir, public, secret = get_config_paths()

    if secret.exists() and not overwrite:
        print("Kept previously created key pair. "
              "Use --overwrite to replace it.\n")
        return 0

    try:
        config_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        print(f"Error creating the configuration directory: {e}")
        return 1

    create_certificates(str(config_dir), "identity")

    if os.name == 'posix':
        public.chmod(0o644)
        secret.chmod(0o600)
    print(f"Key pair created in: '{config_dir}'.")
    return 0


def print_discos_keys():
    _, public, _ = get_config_paths()

    if not public.exists():
        print("No key was generated yet.")
        return 0

    with open(public, "r", encoding="utf-8") as f:
        print(f.read())

    print(f"\nPath of the public key file: {public}")
    print("Remember to never share the 'identity.key_secret' file with "
          "anyone.")
    print(
        "In order to be authorized to send command to any of the telescopes, "
        "remember to send a copy of the 'identity.key' file to the "
        "DISCOS team, asking for authorization. Your request will be taken "
        "into consideration and you will hear back from the team."
    )
    return 0


def keygen():
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
        return_code = create_discos_keys(args.overwrite)

        if return_code != 0:
            return return_code

    return print_discos_keys()
