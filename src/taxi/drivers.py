import shlex
import os
import tempfile
import stat
from .utils import get_config, get_command, register, get_command2, TaskError


@register
def venv(_, *, venv, cmd, python=None):
    yield "uv"
    yield "run"
    yield "--no-project"
    if python:
        yield "--python"
        yield python
    pkgs = [i for i in venv.splitlines() if i]
    for pkg in pkgs:
        yield "--with"
        yield pkg
    yield "--"
    yield from shlex.split(cmd)


@register
def script(_, *, script):
    with tempfile.NamedTemporaryFile(mode="w", delete=False) as temp_file:
        temp_file.write(script)
    os.chmod(temp_file.name, stat.S_IXUSR | stat.S_IRUSR | stat.S_IWUSR)
    yield temp_file.name


@register
def cmd(_, *, cmd):
    yield from shlex.split(cmd)


def _docker(*, version="latest", image, image_port, user_port, envs):
    yield "docker"
    yield "run"
    if version is None:
        version = "latest"
    if user_port is None:
        user_port = image_port

    yield "-p"
    yield f"{image_port}:{user_port}"

    for env, env_val in envs.items():
        if env_val is not None:
            yield "-e"
            yield f"{env.upper()}={env_val}"

    yield f"{image}:{version}"


@register
def postgres(_, *, postgres, port=None, user=None, password=None, db=None, lang=None):
    return _docker(
        version=postgres,
        user_port=port,
        image="postgres",
        image_port=5432,
        envs={
            "POSTGRES_PASSWORD": password,
            "POSTGRES_USER": user,
            "POSTGRES_DB": db,
            "LANG": lang,
        },
    )


@register
def mysql(_, *, mysql, port=None, user=None, password=None, db=None, lang=None):
    return _docker(
        version=mysql,
        user_port=port,
        image="mysql",
        image_port=3306,
        envs={
            "MYSQL_PASSWORD": password,
            "MYSQL_USER": user,
            "MYSQL_DATABASE": db,
        },
    )


@register
def redis(_, *, redis, port=None):
    return _docker(
        version=redis,
        user_port=port,
        image="redis",
        image_port=6379,
        envs={},
    )


@register
def nix(_, *, nix, cmd):
    yield "nix-shell"
    yield "--packages"
    yield from [i for i in nix.splitlines() if i]
    yield "--run"
    yield cmd


@register
def raw(_, **kw):
    yield kw


@register
def noop(_, noop):
    yield "true"


@register
def use(section_name, *, use, **kw):
    try:
        use = dict(get_config()[use])
    except KeyError:
        raise TaskError(f"use: no such task: {use}")
    return get_command2(section_name, dict(use, **kw))


@register
def assert_(section_name, **kw):
    assert_ = kw.pop("assert")
    cmd = get_command2(section_name, kw)
    cmd_str = shlex.join(cmd)
    if cmd_str != assert_:
        raise TaskError(
            f"assert failed at {section_name}:\nexpected: {assert_}\nactual:   {cmd_str}"
        )
    yield "true"


@register
def list(_, *, list=None):
    if list is None:
        list = [
            section for section in get_config() if section not in ("list", "DEFAULT")
        ]
    else:
        list = [i for i in list.splitlines() if i]
    help = []
    for task in list:
        cmd = shlex.join(get_command(task))
        help.append(f"{task:16}{cmd}")
    yield "printf"
    yield "\n".join(help)


@register
def services(_, *, services):
    import json

    services = [i for i in services.splitlines() if i]
    config = {"version": "0.5", "processes": {}}
    for service in services:
        cmd = get_command(service)
        config["processes"][service] = {"command": shlex.join(cmd)}
    source = json.dumps(config)
    with tempfile.NamedTemporaryFile(mode="w", delete=False) as temp_file:
        temp_file.write(source)
    yield "process-compose"
    yield "--config"
    yield temp_file.name
