import argparse
import contextlib
import hashlib
import os
import subprocess
import sys


def cache_dir() -> str:
    venv_dir = os.environ.get('VIRTUAL_ENV')

    if venv_dir is None:
        raise RuntimeError('Script must be run from virtualenv')

    return os.path.abspath(os.path.join(venv_dir, os.pardir))


def venv_cache_dir(reqs_hash: str) -> str:
    return os.path.join(cache_dir(), 'pylint_venvs', reqs_hash)


# Borrowed from https://github.com/pre-commit/pre-commit
def bin_dir(venv: str) -> str:
    """On windows there's a different directory for the virtualenv"""
    bin_part = 'Scripts' if os.name == 'nt' else 'bin'
    return os.path.join(venv, bin_part)


@contextlib.contextmanager
def venv_context(venv: str):
    env = os.environ
    to_restore = dict(env)

    env.pop('PYTHON_HOME', None)
    env['PIP_DISABLE_PIP_VERSION_CHECK'] = '1'
    env['VIRTUAL_ENV'] = venv
    env['PATH'] = ''.join((bin_dir(venv), os.pathsep, env.get('PATH', '')))

    try:
        yield
    finally:
        env.clear()
        env.update(to_restore)


def read_requirements(path):
    with open(path) as f:
        return f.readlines()


def call(*command, capture_output=True, check=True, **kwargs):
    subprocess.run(
        command, capture_output=capture_output,
        check=check, **kwargs,
    )


def process_error_to_str(e: subprocess.CalledProcessError) -> str:
    return b''.join((
        b'command:\n\n', e.cmd, b'\n',
        b'stdout:\n\n', e.stdout, b'\n',
        b'stderr:\n\n', e.stderr, b'\n',
    )).decode()


def install_virtualenv(venv_dir: str, requirements) -> int:
    try:
        call(sys.executable, '-mvirtualenv', venv_dir)

        with venv_context(venv_dir):
            call('pip', 'install', *requirements)
    except subprocess.CalledProcessError as e:
        print(process_error_to_str(e), file=sys.stderr)
        return e.returncode

    return 0


def parse_arguments(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--requirements',
        help='Location of requirements.txt file',
        default='requirements.txt',
    )
    parser.add_argument('files', nargs='*')
    return parser.parse_args(argv)


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    args = parse_arguments(argv)

    reqs = read_requirements(args.requirements)
    reqs_hash = hashlib.sha1('\n'.join(reqs).encode()).hexdigest()
    venv_dir = venv_cache_dir(reqs_hash)

    if not os.path.exists(venv_dir):
        install_virtualenv(venv_dir, args.requirements)

    try:
        with venv_context(venv_dir):
            call('pylint', *args.files, capture_output=False)
    except subprocess.CalledProcessError as e:
        return e.returncode

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
