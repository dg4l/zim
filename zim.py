#!/usr/bin/env python3
import argparse
import sys
import os
import subprocess
import zipfile
import urllib.request
import json
import platform
from pathlib import Path
import tarfile
import tempfile
import shutil
import hashlib

ZIM_ROOT = Path.home() / ".zim"
INSTALLS = ZIM_ROOT / "zig-installs"
CURRENT = ZIM_ROOT / "current"
INDEX = "https://ziglang.org/download/index.json"

def get_os_string():
    arch_list = {
        "x86_64": "x86_64",
        "amd64": "x86_64",
        "x64": "x86_64",
        "aarch64": "aarch64",
        "arm64": "aarch64",
        "aarch64_be": "aarch64",
        "arm": "arm",
        "armv6l": "arm",
        "armv7l": "arm",
        "armv7": "arm",
        "armv8l": "arm",
        "x86": "x86",
        "i386": "x86",
        "i486": "x86",
        "i586": "x86",
        "i686": "x86",
        "riscv64": "riscv64",
        "loongarch64": "loongarch64",
        "s390x": "s390x",
        "powerpc64le": "powerpc64le",
        "ppc64le": "powerpc64le",
        "powerpc64": "powerpc64",
        "ppc64": "powerpc64",
        "powerpc": "powerpc",
        "ppc": "powerpc",
    }
    os_list = {
        "linux": "linux",
        "darwin": "macos",
        "windows": "windows",
        "freebsd": "freebsd",
        "netbsd": "netbsd",
        "openbsd": "openbsd",
    }
    try:
        return f"{arch_list[platform.machine().lower()]}-{os_list[platform.system().lower()]}"
    except KeyError:
        return f"{platform.machine().lower()}-{platform.system().lower()}"

def get_current_version():
    target = CURRENT.resolve()
    return target.name if target.exists() else None

def get_version_path(version):
    root = INSTALLS.resolve()
    path = (INSTALLS / version).resolve()
    if path.parent != root or path.name.startswith("."):
        return None
    return path

def get_installed_path(version):
    path = get_version_path(version)
    return path if path is not None and path.is_dir() else None

def make_link(link, target):
    if os.name == "nt":
        subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)], check=True, capture_output=True)
    else:
        link.symlink_to(target)

def create_current_symlink(version_path):
    link = CURRENT
    old_target = link.readlink() if os.path.lexists(link) else None
    if old_target is not None:
        link.unlink()
    try:
        make_link(link, version_path)
    except (OSError, subprocess.CalledProcessError):
        if old_target is not None:
            make_link(link, old_target)
        raise

def fetch_index():
    with urllib.request.urlopen(INDEX) as r:
        return json.load(r)

def cmd_ls_remote(args):
    idx = fetch_index()
    versions = [i for i in idx if i != "master"]
    print(f'master ({idx["master"]["version"]})')
    for v in versions:
        print(v)

def cmd_ls(args):
    INSTALLS.mkdir(parents=True, exist_ok=True)
    current_version = get_current_version()
    for i in sorted(INSTALLS.iterdir()):
        if i.is_dir() and not i.name.startswith("."):
            if i.name == current_version:
                print("* ", end="")
            print(i.name)

def cmd_install(args):
    version = args.version
    idx = fetch_index()
    s = get_os_string()
    try:
        archive_url = idx[version][s]["tarball"]
        shasum = idx[version][s]["shasum"]
        actual_version = idx[version].get("version", version)
    except KeyError:
        print(f"version {version} not found", file=sys.stderr)
        return 1
    install_path = get_version_path(actual_version)
    if install_path is None:
        print(f"invalid version {actual_version}", file=sys.stderr)
        return 1
    if install_path.is_dir():
        print(f"version {actual_version} already installed")
        return
    print(f"installing {actual_version}")
    INSTALLS.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=INSTALLS, prefix=".stage-") as stage:
        with tempfile.TemporaryFile() as f:
            with urllib.request.urlopen(archive_url) as r:
                shutil.copyfileobj(r, f)
            f.seek(0)
            if hashlib.file_digest(f, "sha256").hexdigest() != shasum:
                print(f"hash mismatch for {archive_url}", file=sys.stderr)
                return 1
            f.seek(0)
            if archive_url.endswith(".zip"):
                with zipfile.ZipFile(f) as z:
                    z.extractall(stage)
            else:
                with tarfile.open(fileobj=f) as t:
                    t.extractall(path=stage, filter="data")
        (top_dir,) = Path(stage).iterdir()
        top_dir.rename(install_path)

def cmd_use(args):
    version = args.version
    install_path = get_installed_path(version)
    if install_path is None:
        print(f"version {version} not installed", file=sys.stderr)
        return 1
    create_current_symlink(install_path)

def cmd_rm(args):
    version = args.version
    install_path = get_installed_path(version)
    if install_path is None:
        print(f"version {version} not installed", file=sys.stderr)
        return 1
    if CURRENT.resolve() == install_path:
        CURRENT.unlink()
    shutil.rmtree(install_path)
    print(f"removed {version}")

def cmd_current(args):
    print(get_current_version())

class Parser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(1, f"{self.prog}: error: {message}\n")

def create_parser():
    parser = Parser(prog="zim")
    subparsers = parser.add_subparsers(dest="command", required=True)
    ls_remote_parser = subparsers.add_parser("ls-remote")
    ls_remote_parser.set_defaults(func=cmd_ls_remote)
    ls_parser = subparsers.add_parser("ls")
    ls_parser.set_defaults(func=cmd_ls)
    install_parser = subparsers.add_parser("install")
    install_parser.add_argument("version")
    install_parser.set_defaults(func=cmd_install)
    use_parser = subparsers.add_parser("use")
    use_parser.add_argument("version")
    use_parser.set_defaults(func=cmd_use)
    rm_parser = subparsers.add_parser("rm")
    rm_parser.add_argument("version")
    rm_parser.set_defaults(func=cmd_rm)
    current_parser = subparsers.add_parser("current")
    current_parser.set_defaults(func=cmd_current)
    return parser

def main():
    if sys.version_info < (3, 11, 4):
        sys.exit("zim requires python 3.11.4+")
    args = create_parser().parse_args()
    sys.exit(args.func(args))

if __name__ == "__main__":
    main()
