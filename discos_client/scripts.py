import os
import shutil
from pathlib import Path
from argparse import ArgumentParser
from platformdirs import user_config_dir
from zmq.auth import create_certificates, load_certificate


def get_config_paths(identity: str):
    base_config = Path(user_config_dir("discos"))
    config_dir = base_config / "rpc" / "client"
    public = config_dir / f"{identity}.key"
    secret = config_dir / f"{identity}.key_secret"
    return config_dir, public, secret


def set_permissions(public_path, secret_path):
    if os.name == "posix":
        try:
            public_path.chmod(0o644)
            secret_path.chmod(0o600)
        except OSError as e:
            print(f"Warning: Could not set permissions: {e}")


def import_discos_keys(secret_src, identity, overwrite):
    config_dir, public_dst, secret_dst = get_config_paths(identity)

    if not secret_src.exists():
        print(f"Error: Secret key file not found: {secret_src}")
        return 1

    try:
        user_pub, _ = load_certificate(str(secret_src))
        user_pub = user_pub.decode("utf-8")
    except (OSError, ValueError) as e:
        print(f"Error reading secret key file: {e}")
        print("Ensure if is a valid ZMQ secret certificate.")
        return 1

    if (secret_dst.exists() or public_dst.exists()) and not overwrite:
        print(f"Kept previously created key pair '{identity}'. "
              "Use --overwrite to replace it.\n")
        return 0

    try:
        config_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        print(f"Error creating the configuration directory: {e}")
        return 1

    create_certificates(str(config_dir), identity)
    generated_pub, _ = load_certificate(str(public_dst))
    generated_pub = generated_pub.decode("utf-8")

    shutil.copy2(secret_src, secret_dst)

    with open(secret_src, "r", encoding="utf-8") as f:
        creation_date = f.readline()

    lines = []
    with open(public_dst, "r", encoding="utf-8") as f:
        lines = f.readlines()

    lines[0] = creation_date

    with open(public_dst, "w", encoding="utf-8") as f:
        for line in lines:
            if generated_pub in line:
                line = line.replace(generated_pub, user_pub)
            f.write(line)

    set_permissions(public_dst, secret_dst)
    print(f"Keys '{identity}' imported successfully to : '{config_dir}'.")
    return 0


def create_discos_keys(identity, overwrite):
    config_dir, public, secret = get_config_paths(identity)

    if secret.exists() and not overwrite:
        print(f"Kept previously created key pair '{identity}'. "
              "Use --overwrite to replace it.\n")
        return 0

    try:
        config_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        print(f"Error creating the configuration directory: {e}")
        return 1

    create_certificates(str(config_dir), identity)
    set_permissions(public, secret)

    print(f"Key pair '{identity}' created in: '{config_dir}'.")
    return 0


def print_discos_keys(identity):
    _, public, _ = get_config_paths(identity)

    if not public.exists():
        print(f"No key named '{identity}' was found.")
        return 0

    with open(public, "r", encoding="utf-8") as f:
        print(f.read())

    print(f"\nPath of the public key file: {public}")
    print(f"Remember to never share the '{identity}.key_secret' file with "
          "anyone.")
    print(
        "In order to be authorized to send command to any of the telescopes, "
        f"remember to send a copy of the '{identity}.key' file to the "
        "DISCOS team, asking for authorization. Your request will be taken "
        "into consideration and you will hear back from the team."
    )
    return 0


def keygen():
    parser = ArgumentParser(
        description="DISCOS CURVE key pairs generator."
    )
    parser.add_argument(
        "identity",
        type=str,
        help="The identity of the application that will use the DISCOSClient "
             "to send remote commands."
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
    parser.add_argument(
        "--import-pair",
        type=Path,
        help="Path to an existing secret key file to import "
             "The public key will be automatically derived from it."
    )
    args = parser.parse_args()

    if args.show_only:
        return print_discos_keys(args.identity)

    if args.import_pair:
        return_code = import_discos_keys(
            args.import_pair,
            args.identity,
            args.overwrite
        )
    else:
        return_code = create_discos_keys(args.identity, args.overwrite)

    if return_code != 0:
        return return_code

    return print_discos_keys(args.identity)
