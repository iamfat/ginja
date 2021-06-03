import os
import io
import click
import jinja2
import shutil
import yaml
import toml
import re

from dotenv import dotenv_values

dot_jinjas = ('.jinja', '.jinja2', '.j2')
dot_multiples = ('.multiple.yml', '.multiple.yaml')


def jinja_convert(filepath: str, os_env: dict):
    converted = ''
    with open(filepath, encoding='utf8') as f:
        converted = jinja2.Template(f.read()).render(os_env)
    return converted


def load_env(filepaths, os_env):
    target_vars = os_env.copy()

    content = ''
    for filepath in filepaths:
        filename, ext = os.path.splitext(filepath)
        if ext in dot_jinjas:
            ext = os.path.splitext(filename)[1]
            if ext != '.env':
                continue
            content += '\n' + jinja_convert(filepath, os_env)
        elif ext == '.env':
            with open(filepath, encoding='utf8') as f:
                content += '\n' + f.read()
        else:
            continue

    vars = dict(dotenv_values(io.StringIO(content), encoding='utf8'))
    target_vars.update(vars)

    for filepath in filepaths:
        filename, ext = os.path.splitext(filepath)
        content = ''
        if ext in dot_jinjas:
            content = jinja_convert(filepath, os_env)
            ext = os.path.splitext(filename)[1]
        else:
            with open(filepath, encoding='utf8') as f:
                content = f.read()

        vars = {}
        if ext == '.toml':
            vars = toml.load(io.StringIO(content))
        elif ext == '.yml' or ext == '.yaml':
            vars = yaml.load(content, Loader=yaml.FullLoader)
        target_vars.update(vars)

    return target_vars


def convert_file(src_file, dst_file, env_vars):
    dst_dir = os.path.dirname(dst_file)
    if not os.path.isdir(dst_dir):
        os.makedirs(dst_dir)
    jinja_dst_file, ext = os.path.splitext(dst_file)
    if ext.lower() in dot_jinjas:
        output = jinja_convert(src_file, env_vars)
        with open(jinja_dst_file, 'w+') as f:
            f.write(output)
        click.echo('[J] ' + jinja_dst_file)
    else:
        shutil.copyfile(src_file, dst_file)
        click.echo('[ ] ' + dst_file)


@click.command()
@click.version_option()
@click.option(
    '-e',
    '--env',
    required=True,
    type=click.Path(exists=True),
    help='Load system environment variables before local ones.')
@click.argument('src', nargs=1, required=True)
@click.argument('dst', nargs=1, required=True)
def cli(env, src, dst):
    env_vars = {}
    if os.path.isdir(env):
        filepaths = []
        for parent, dirnames, filenames in os.walk(env):
            filepaths.extend(map(lambda f: os.path.join(
                parent, f), filenames))
        filepaths.sort()
        env_vars = load_env(filepaths, os.environ)
    elif os.path.isfile(env):
        env_vars = load_env([env], os.environ)

    path_var_regex = re.compile(r'\$(\w+)')
    multiple_vars = {}
    for subdir, dirnames, filenames in os.walk(src):
        for filename in filenames:
            src_file = os.path.join(subdir, filename)
            for filename in filenames:
                jinja_filename, ext = os.path.splitext(filename)
                if ext.lower() in dot_jinjas:
                    if jinja_filename in dot_multiples:
                        multiple_vars[subdir] = yaml.load(jinja_convert(
                            src_file, env_vars), Loader=yaml.FullLoader) or {}
                        break
                elif filename in dot_multiples:
                    with open(src_file, encoding='utf8') as f:
                        multiple_vars[subdir] = yaml.load(
                            f, Loader=yaml.FullLoader) or {}
                    break

    for subdir, dirnames, filenames in os.walk(src):
        for filename in filenames:
            if filename[0:1] == '.':
                continue
            src_file = os.path.join(subdir, filename)
            subdir_multiples = []
            for basedir, vars in multiple_vars.items():
                if subdir.startswith(basedir):
                    subdir_multiples.append(vars)
            if len(subdir_multiples) > 0:
                def _convert(vars):
                    n_subdir = path_var_regex.sub(
                        lambda m: vars[m.group(1)], subdir)
                    n_filename = path_var_regex.sub(
                        lambda m: vars[m.group(1)], filename)
                    dst_file = os.path.join(
                        dst, os.path.relpath(n_subdir, os.path.dirname(src)), n_filename)
                    n_env_vars = env_vars.copy()
                    n_env_vars.update(vars)
                    convert_file(src_file, dst_file, n_env_vars)

                def _walk(idx, vars):
                    if idx >= len(subdir_multiples):
                        _convert(vars)
                        return
                    for v in subdir_multiples[idx]:
                        n_vars = vars.copy()
                        n_vars.update(v)
                        _walk(idx+1, n_vars)

                _walk(0, {})
            else:
                dst_file = os.path.join(
                    dst, os.path.relpath(subdir, os.path.dirname(src)), filename)
                convert_file(src_file, dst_file, env_vars)
