import os
import paramiko
from tqdm import tqdm


def _get_remote_home_dir(ssh: paramiko.SSHClient) -> str:
    # Works on Linux/macOS shells
    stdin, stdout, stderr = ssh.exec_command("printf %s $HOME")
    home = stdout.read().decode("utf-8").strip()
    if not home:
        raise RuntimeError("Could not determine remote $HOME")
    return home


def _expand_remote_path(ssh: paramiko.SSHClient, remote_path: str) -> str:
    # Expand "~" or "~/" into absolute remote home path
    if remote_path == "~":
        return _get_remote_home_dir(ssh)
    if remote_path.startswith("~/"):
        return _get_remote_home_dir(ssh).rstrip("/") + remote_path[1:]  # replace leading "~"
    return remote_path


def _mkdir_p_sftp(sftp: paramiko.SFTPClient, remote_dir: str) -> None:
    if remote_dir in ("", "/"):
        return

    try:
        sftp.stat(remote_dir)
    except FileNotFoundError:
        parent = os.path.dirname(remote_dir)
        _mkdir_p_sftp(sftp, parent)
        sftp.mkdir(remote_dir)


def upload_file(
        host: str,
        username: str,
        port: int,
        remote_path: str,
        local_path: str,
        key_path: str | None = None,
        password: str | None = None,
        timeout: int = 30,
) -> None:
    if not os.path.isfile(local_path):
        raise FileNotFoundError(f"Local file does not exist: {local_path}")

    file_size = os.path.getsize(local_path)

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        connect_kwargs = {
            "hostname": host,
            "username": username,
            "port": port,
            "timeout": timeout,
        }
        if key_path:
            connect_kwargs["key_filename"] = key_path
        if password:
            connect_kwargs["password"] = password

        ssh.connect(**connect_kwargs)

        # Expand "~" BEFORE using SFTP
        remote_path_expanded = _expand_remote_path(ssh, remote_path)

        sftp = ssh.open_sftp()

        # Ensure remote directory exists
        remote_dir = os.path.dirname(remote_path_expanded)
        _mkdir_p_sftp(sftp, remote_dir)

        with tqdm(
                total=file_size,
                unit="B",
                unit_scale=True,
                unit_divisor=1024,
                desc=f"Uploading {os.path.basename(local_path)}",
        ) as pbar:

            def progress_callback(transferred, total):
                pbar.total = total
                pbar.update(transferred - pbar.n)

            sftp.put(local_path, remote_path_expanded, callback=progress_callback)

        sftp.close()

    finally:
        ssh.close()
