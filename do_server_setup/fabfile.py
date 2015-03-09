__author__ = 'Umut Karci'
__version__ = "0.1.0"
__version_tuple__ = __version__.split(".")
from fabric.api import *
from fabric.contrib import files
from fabric import colors as c
from contextlib import contextmanager
from fabtools import (nginx, deb, postgres, python, user, service,
                      files as files2)
from base58 import b58encode
from os import path
import os

USAGE = "\n".join([
    c.cyan("Usage:", bold=True),
    c.red("$", bold=True)+" "+c.blue("fab connect:ip=11.22.33.44 setup_server"),
    c.green("This will install nginx, uwsgi, postgresql, some python packages"),
    c.green("  also some settings will be optimised"),
    "",
    c.red("$", bold=True)+" "+c.blue("fab connect:ip=11.22.33.44 create_domain:user1,pass1,3"),
    c.green("This will create a user with username=user1 and pass=1"),
    c.green("  Also a python3 virtual environment at ~/venv that'll run when login"),
    c.green("  A postgresql user and database"),
    c.green("  Nginx and Uwsgi configurations"),
    c.green("  site-dir folder and staticfiles folder"),
    c.green("  Readme file with usernames and passwords and database name"),
    c.green("  It will also copy your ssh key to new user"),
    "",
    c.red("$", bold=True)+" "+c.blue("fab connect:ip=11.22.33.44 create_user:user2,pass2"),
    c.green("This will create a user with username=user2 and password=pass2"),
    c.green("  When no password is given, it'll generate a one"),
    "",
    c.red("$", bold=True)+" "+c.blue("fab connect:ip=11.22.33.44 create_pgsql_user:user2,pass2"),
    c.green("This will create a postgresql user and a database with generated name"),
    c.green("  When no password is given, it'll generate a one"),
    "",
    c.red("$", bold=True)+" "+c.blue("fab connect:ip=11.22.33.44:username=user1 create_venv:sanal,2"),
    c.green("This will create a python2 virtual environment at ~/sanal folder"),
    c.green("  This will also make the virtual environment run at login"),
    "",
    c.red("$", bold=True)+" "+c.blue("fab connect:ip=11.22.33.44:username=user1 pip_install:flask"),
    c.green("This will install flask to venv virtual environment"),
    "",
    c.red("$", bold=True)+" "+c.blue("fab connect:ip=11.22.33.44:username=user1 pip_install_requirements"),
    c.green("This will install all requirements in ~/site-dir/requirements.txt"),
    "",
    c.red("$", bold=True)+" "+c.blue("fab connect:ip=11.22.33.44:username=user1 push_key"),
    c.green("This will copy your ssh key to user1"),
    "",
    c.red("$", bold=True)+" "+c.blue("fab connect:ip=11.22.33.44 reload_services:nginx"),
    c.green("This will reload given services"),
    c.green("  When no argument is given it'll reload nginx and uwsgi-emperor"),
    "",
])

UWSGI_INI = "\n".join([
    "[uwsgi]",
    "plugins = {plugins}",
    "master = true",
    "uid = {domain}",
    "gid = www-data",
    "processes = 2",
    "venv = /home/{domain}/venv",
    "chdir = /home/{domain}/site-dir",
    "daemonize = /home/{domain}/uwsgi.log",
    "socket = /home/{domain}/uwsgi.sock",
    "wsgi-file = /home/{domain}/site-dir/wsgi.py"
])

NGINX_CONF = "\n".join([
    "upstream {domain} {{",
    "  server unix://home/{domain}/uwsgi.sock;",
    "}}",
    "server {{",
    "  listen 80;",
    "  server_name {domain};",
    "  charset utf-8;",
    "  client_max_body_size 75M;",
    "  access_log /home/{domain}/nginx_access.log;",
    "  error_log /home/{domain}/nginx_error.log;",
    "  location /static {{",
    "      alias /home/{domain}/site-dir/staticfiles;",
    "  }}",
    "  location / {{",
    "      uwsgi_pass {domain};",
    "  include uwsgi_params;",
    "  }}",
    "}}"
])

README_FILE = "\n".join([
    "UNIX:",
    "  Username= {user_unix}",
    "  Password= {pass_unix}",
    "POSTGRESQL:",
    "  Username= {user_pql}",
    "  Password= {pass_pql}",
    "  DB Name = {name_pql}",
    "",
    "Webserver needs a wsgi.py file in site-dir",
    "wsgi.py file must have a variable, named as \"application\"",
    "Django's wsgi.py is okay but for flask you should do this:",
    "  application = app",
    "",
    "staticfiles folder in site-dir is served by nginx as /static",
    "uwsgi.ini file is for uwsgi configuration and dynamic",
    "nginx configuration is at /etc/nginx/sites-enabled",
])

env.colorize_errors = True


def gen_pass(length=10):
    return b58encode(os.urandom(length))[:length]


@contextmanager
def source_virtualenv(name):
    with prefix('source ~/{name}/bin/activate'.format(name=name)):
        yield


@task
def connect(ip, username="root"):
    env.host_string = ip
    env.user = username
    prompt("password (leave empty for ssh key):", key="password")
    if not env.password:
        env.key_filename = path.expanduser("~/.ssh/id_rsa")


def set_language(langcode="en_US.UTF-8"):
    files.append(filename="/etc/default/locale",
                 text=["LANGUAGE=\"{lang}\"".format(lang=langcode),
                       "LC_ALL=\"{lang}\"".format(lang=langcode)],
                 use_sudo=True)


@task
def setup_server():
    set_language()
    files.sed(
        "/etc/ssh/sshd_config",
        "StrictModes yes",
        "StrictModes no",
        use_sudo=True)
    service.restart("ssh")

    deb.upgrade()
    deb.install(["nginx", "uwsgi", "uwsgi-emperor", "uwsgi-plugin-python",
                 "uwsgi-plugin-python3", "libpq-dev", "postgresql",
                 "postgresql-contrib", "python-virtualenv", "python-dev",
                 "python3-dev"], update=True)

    # Increase domain name limit
    files.sed(
        "/etc/nginx/nginx.conf",
        "# server_names_hash_bucket_size 64;",
        "server_names_hash_bucket_size 96;",
        use_sudo=True)
    nginx.disable("default")


@task
def pip_install(*packages):
    venv = prompt("Env name:", default="venv")
    with source_virtualenv(venv):
        run("pip install -U {}".format(" ".join(packages)))


@task
def pip_install_requirements():
    with source_virtualenv("venv"):
        run("pip install -U -r {}".format("~/site-dir/requirements.txt"))


@task
def create_user(username, password=None):
    if user.exists(username):
        raise KeyError("Username {} is taken".format(username))

    if password is None:
        password = gen_pass(10)

    # Create user
    user.create(name=username,
                group="www-data",
                extra_groups=["sudo"],
                shell="/bin/bash",
                create_home=True,
                password=password)

    print c.blue("Username=", bold=True),\
        c.green(username, bold=True)
    print c.blue("Password=", bold=True),\
        c.green(password, bold=True)
    return username, password


@task
def create_pgsql_user(username, password=None):
    if postgres.user_exists(username):
        raise KeyError("Username {} is taken".format(username))

    if password is None:
        password = gen_pass(10)
    postgres.create_user(username, password=password, createdb=True)

    db_not_created = True
    db_name = ""
    while db_not_created:
        db_name = gen_pass(12)+"_DB"
        if not postgres.database_exists(db_name):
            postgres.create_database(db_name, owner=username)
            db_not_created = False

    print c.blue("Username=", bold=True),\
        c.green(username, bold=True)
    print c.blue("Password=", bold=True),\
        c.green(password, bold=True)
    print c.blue("DB Name =", bold=True),\
        c.green(db_name, bold=True)
    return username, password, db_name


@task
def create_domain(domain, password=None, version="3"):
    unix_u, unix_p = create_user(domain, password)
    with settings(user=unix_u, password=unix_p):
        # Push ssh key
        push_key()

        # Create virtual env
        create_venv("venv", version)

        run("chmod 775 ~/")
        files.append(filename=".bashrc", text="umask 002")

        # Create site folder
        run("mkdir site-dir")
        run("mkdir site-dir/staticfiles")

        # Create nginx log files
        run("touch ~/nginx_access.log")
        sudo("chgrp root nginx_access.log")
        run("touch ~/nginx_error.log")
        sudo("chgrp root nginx_error.log")

        # Create uwsgi ini file and move to vassal directory
        uwsgi_plugins = []
        if version == "3":
            uwsgi_plugins.append("python3")
        if version == "2":
            uwsgi_plugins.append("python2")

        files.append("uwsgi.ini", UWSGI_INI.format(
            domain=env.user, plugins=", ".join(uwsgi_plugins)))
        files2.symlink("/home/{user}/uwsgi.ini".format(user=env.user),
                       "/etc/uwsgi-emperor/vassals/{user}.ini".format(
                           user=env.user), use_sudo=True)

        # Create nginx config file and enable
        files.append(
            "/etc/nginx/sites-available/{user}".format(user=env.user),
            NGINX_CONF.format(domain=env.user), use_sudo=True)
        nginx.enable(env.user)

        if unix_p == password:
            psql_u, psql_p, psql_n = create_pgsql_user(username=env.user,
                                                       password=password)
        else:
            psql_u, psql_p, psql_n = create_pgsql_user(username=env.user)

        files.append("README.txt", README_FILE.format(
            user_unix=unix_u,
            pass_unix=unix_p,
            user_pql=psql_u,
            pass_pql=psql_p,
            name_pql=psql_n,
        ))


@task
def push_key(key_file=path.expanduser('~/.ssh/id_rsa.pub')):
    user.add_ssh_public_key(env.user, key_file)


@task
def reload_services(*apps):
    if len(apps) == 0:
        apps = ["nginx", "uwsgi-emperor"]
    map(service.reload, apps)


@task
def create_venv(name, version):
    if not python.virtualenv_exists(name):
        if version == "2":
            run("python -m virtualenv ~/{name} --no-pip ".format(name=name))
        elif version == "3":
            run("python3 -m venv ~/{name} --symlinks --without-pip".format(
                name=name))
        else:
            raise KeyError("Version must be a string ('2', '3')")
        files.append(
            filename=".bashrc",
            text="source ~/{name}/bin/activate".format(name=name))
    with source_virtualenv(name):
        run("curl --silent https://bootstrap.pypa.io/get-pip.py | python")


@task(alias="help")
def fabric_help():
    print USAGE