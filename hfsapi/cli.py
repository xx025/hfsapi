"""
hfsapi CLI：认证一次保存到本地，有则用认证、无则无认证。
"""

from __future__ import annotations

import getpass
import json
import sys
from pathlib import Path
from typing import Annotated, Optional

import typer

from hfsapi import HFSClient, entry_created, entry_modified, entry_size
from hfsapi.cli_config import clear_config, load_config, save_config

app = typer.Typer(
    name="hfs",
    help="HFS API CLI. Auth once and save; use saved auth for all commands.",
)

# 可选参数：覆盖或补充 base_url（未登录时必填）
_base_url_option: type = Annotated[
    Optional[str],
    typer.Option("--base-url", "-b", help="Override saved base URL (or required if not logged in)"),
]


def _get_client(base_url: str | None) -> HFSClient | None:
    cfg = load_config()
    url = base_url or (cfg and cfg.get("base_url"))
    if not url:
        return None
    username = cfg.get("username") if cfg else None
    password = cfg.get("password") if cfg else None
    return HFSClient(base_url=url, username=username, password=password, timeout=30.0)


def _require_client(base_url: str | None) -> HFSClient:
    client = _get_client(base_url)
    if client is None:
        typer.echo("error: no saved credentials. run 'hfs login' or pass --base-url", err=True)
        raise typer.Exit(1)
    return client


# ------------------------- login / logout / auth -------------------------


@app.command("login", help="Save credentials to local config")
def login(
    base_url: Annotated[Optional[str], typer.Option("--base-url", "-b", help="HFS base URL")] = None,
    username: Annotated[Optional[str], typer.Option("--username", "-u", help="Username")] = None,
    password: Annotated[Optional[str], typer.Option("--password", "-p", help="Password (unsafe in shell)")] = None,
) -> None:
    base_url = base_url or input("Base URL (e.g. http://127.0.0.1:8280): ").strip()
    if not base_url:
        typer.echo("error: base URL required", err=True)
        raise typer.Exit(1)
    username = username or input("Username: ").strip() or None
    if username and password is None:
        password = getpass.getpass("Password: ")
    save_config(base_url, username, password)
    typer.echo("Saved.")


@app.command("logout", help="Clear saved credentials")
def logout() -> None:
    if clear_config():
        typer.echo("Cleared.")
    else:
        typer.echo("No saved credentials.")


auth_app = typer.Typer(help="Auth subcommands")
app.add_typer(auth_app, name="auth")


@auth_app.command("status", help="Show whether credentials are saved")
def auth_status() -> None:
    cfg = load_config()
    if not cfg:
        typer.echo("Not logged in.")
        return
    base = cfg.get("base_url", "")
    has_auth = bool(cfg.get("username") and cfg.get("password"))
    typer.echo(f"base_url: {base}")
    typer.echo(f"auth: {'yes' if has_auth else 'no'}")


# ------------------------- list / ls -------------------------


def _cmd_list_impl(
    uri: str,
    base_url: str | None,
) -> None:
    client = _require_client(base_url)
    # 前有无 / 均可：data、/data 都转为 /data
    uri = (uri or "/").strip("/")
    uri = f"/{uri}" if uri else "/"
    try:
        data = client.get_file_list(uri=uri, request_c_and_m=True)
    except Exception as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(1)
    finally:
        client.close()
    entries = data.get("list", [])
    for e in entries:
        name = e.get("n", "")
        size = entry_size(e)
        created = entry_created(e) or "-"
        modified = entry_modified(e) or "-"
        typer.echo(f"  {name}  {size} B  {created}  {modified}")


@app.command("list", help="List directory")
def list_cmd(
    uri: Annotated[str, typer.Argument(help="Directory URI (default: /)")] = "/",
    base_url: _base_url_option = None,
) -> None:
    _cmd_list_impl(uri, base_url)


@app.command("ls", help="Alias for list")
def ls_cmd(
    uri: Annotated[str, typer.Argument(help="Directory URI (default: /)")] = "/",
    base_url: _base_url_option = None,
) -> None:
    _cmd_list_impl(uri, base_url)


# ------------------------- upload -------------------------


@app.command("upload", help="Upload a file or a folder (file: upload one file; folder: upload recursively)")
def upload_cmd(
    path: Annotated[Path, typer.Argument(help="Local file or directory path")],
    folder: Annotated[str, typer.Option("--folder", "-f", help="Remote folder path")] = "",
    name: Annotated[Optional[str], typer.Option("--name", "-n", help="Remote filename (only for file; default: local name)")] = None,
    base_url: _base_url_option = None,
) -> None:
    if not path.exists():
        typer.echo(f"error: not found: {path}", err=True)
        raise typer.Exit(1)
    client = _require_client(base_url)
    try:
        if path.is_file():
            content = path.read_bytes()
            remote_name = name or path.name
            r = client.upload_file(
                folder,
                content,
                filename=remote_name,
                use_put=True,
                put_params={"resume": "0!"},
                use_session_for_put=True,
            )
            client.close()
            if r.status_code not in (200, 201):
                typer.echo(f"error: upload {r.status_code} {r.text}", err=True)
                raise typer.Exit(1)
            typer.echo("Uploaded.")
        elif path.is_dir():
            ok, failed = client.upload_folder((folder or "").strip("/"), path)
            client.close()
            typer.echo(f"Uploaded {ok} file(s).")
            if failed:
                for rel_path, msg in failed:
                    typer.echo(f"  failed: {rel_path} — {msg}", err=True)
                raise typer.Exit(1)
        else:
            client.close()
            typer.echo(f"error: not a file or directory: {path}", err=True)
            raise typer.Exit(1)
    except typer.Exit:
        raise
    except Exception as e:
        client.close()
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(1)


# ------------------------- download -------------------------


@app.command("download", help="Download a file")
def download_cmd(
    remote_path: Annotated[str, typer.Argument(help="Remote path (e.g. data/foo.txt)")],
    output: Annotated[Optional[Path], typer.Option("--output", "-o", help="Local path (default: same name)")] = None,
    base_url: _base_url_option = None,
) -> None:
    client = _require_client(base_url)
    # 前有无 / 均可
    remote = (remote_path or "").strip("/")
    out = str(output) if output is not None else Path(remote).name
    try:
        client.download_file(remote, save_to=out)
    except Exception as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(1)
    finally:
        client.close()
    typer.echo(f"Saved to {out}.")


# ------------------------- mkdir -------------------------


@app.command("mkdir", help="Create a folder (path: e.g. data/myfolder or /data/myfolder)")
def mkdir_cmd(
    path: Annotated[str, typer.Argument(help="Full path (leading / optional)")],
    base_url: _base_url_option = None,
) -> None:
    path = (path or "").strip("/")
    if "/" in path:
        parent, new_name = path.rsplit("/", 1)
        parent = parent.strip("/")
        new_name = new_name.strip("/")
    else:
        parent = ""
        new_name = path
    client = _require_client(base_url)
    try:
        r = client.create_folder(parent, new_name)
    except Exception as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(1)
    finally:
        client.close()
    if r.status_code not in (200, 201):
        typer.echo(f"error: create_folder {r.status_code} {r.text}", err=True)
        raise typer.Exit(1)
    typer.echo("Created.")


# ------------------------- delete -------------------------


@app.command("delete", help="Delete a file (path: e.g. data/foo.txt or /data/foo.txt)")
def delete_cmd(
    path: Annotated[str, typer.Argument(help="Full path (leading / optional)")],
    base_url: _base_url_option = None,
) -> None:
    path = (path or "").strip("/")
    if "/" in path:
        folder, filename = path.rsplit("/", 1)
        folder = folder.strip("/")
    else:
        folder = ""
        filename = path
    client = _require_client(base_url)
    try:
        r = client.delete_file(folder, filename)
    except Exception as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(1)
    finally:
        client.close()
    if r.status_code not in (200, 201, 204):
        typer.echo(f"error: delete {r.status_code} {r.text}", err=True)
        raise typer.Exit(1)
    typer.echo("Deleted.")


# ------------------------- config -------------------------


config_app = typer.Typer(help="Config subcommands")
app.add_typer(config_app, name="config")


@config_app.command("get", help="Get HFS config")
def config_get(
    only: Annotated[Optional[str], typer.Option("--only", help="Comma-separated keys to return")] = None,
    omit: Annotated[Optional[str], typer.Option("--omit", help="Comma-separated keys to omit")] = None,
    base_url: _base_url_option = None,
) -> None:
    client = _require_client(base_url)
    only_list = [k.strip() for k in only.split(",") if k.strip()] if only else None
    omit_list = [k.strip() for k in omit.split(",") if k.strip()] if omit else None
    try:
        data = client.get_config(only=only_list, omit=omit_list)
    except Exception as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(1)
    finally:
        client.close()
    typer.echo(json.dumps(data, ensure_ascii=False, indent=2))


@config_app.command("set", help="Set HFS config (admin)")
def config_set(
    key_value: Annotated[list[str], typer.Argument(help="KEY=VALUE pairs")],
    base_url: _base_url_option = None,
) -> None:
    values = {}
    for pair in key_value:
        if "=" not in pair:
            typer.echo(f"error: expected KEY=VALUE: {pair}", err=True)
            raise typer.Exit(1)
        k, v = pair.split("=", 1)
        values[k.strip()] = v.strip()
    if not values:
        typer.echo("error: at least one KEY=VALUE required", err=True)
        raise typer.Exit(1)
    client = _require_client(base_url)
    try:
        r = client.set_config(values)
    except Exception as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(1)
    finally:
        client.close()
    if not r.is_success:
        typer.echo(f"error: set_config {r.status_code} {r.text}", err=True)
        raise typer.Exit(1)
    typer.echo("OK.")


# ------------------------- vfs -------------------------


@app.command("vfs", help="Print VFS tree (JSON)")
def vfs_cmd(base_url: _base_url_option = None) -> None:
    client = _require_client(base_url)
    try:
        data = client.get_vfs()
    except Exception as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(1)
    finally:
        client.close()
    typer.echo(json.dumps(data, ensure_ascii=False, indent=2))


# ------------------------- info -------------------------


@app.command("info", help="Show saved base_url and auth status")
def info_cmd() -> None:
    cfg = load_config()
    if not cfg:
        typer.echo("Not logged in. Run 'hfs login' or pass --base-url for commands.")
        return
    typer.echo(f"base_url: {cfg.get('base_url')}")
    typer.echo(f"auth: {'yes' if (cfg.get('username') and cfg.get('password')) else 'no'}")


# ------------------------- main -------------------------


def main() -> None:
    app()


if __name__ == "__main__":
    main()
