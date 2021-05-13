import os
import io
import click
import jinja2
import shutil
import yaml
import toml

from dotenv import dotenv_values


def load_env(filepaths, target_vars):
    env_content = ''
    structed_vars = {}
    for filepath in filepaths:
        ext = os.path.splitext(filepath)[1]
        if ext == '.env':
            with open(filepath, encoding='utf8') as f:
                env_content += f.read()
        elif ext == '.toml':
            with open(filepath, encoding='utf8') as f:
                toml_vars = toml.load(f)
                structed_vars.update(toml_vars)
        elif ext == '.yml' or ext == '.yaml':
            with open(filepath, encoding='utf8') as f:
                yaml_vars = yaml.load(f, Loader=yaml.FullLoader)
                structed_vars.update(yaml_vars)
    env_vars = dict(dotenv_values(
        stream=io.StringIO(env_content), encoding='utf8'))
    target_vars.update(env_vars)
    target_vars.update(structed_vars)
    return target_vars


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
        for parent, dirnames, filenames in os.walk(env):
            filenames.sort()
            load_env(map(lambda f: os.path.join(
                parent, f), filenames), env_vars)
    elif os.path.isfile(env):
        load_env([env], env_vars)

    for subdir, dirnames, filenames in os.walk(src):
        for filename in filenames:
            src_file = os.path.join(subdir, filename)
            dst_file = os.path.join(
                dst, os.path.relpath(subdir, src), filename)
            dst_dir = os.path.dirname(dst_file)
            if not os.path.isdir(dst_dir):
                os.makedirs(dst_dir)
            jinja_dst_file, ext = os.path.splitext(dst_file)
            if ext.lower() in ('.jinja', '.jinja2', '.j2'):
                content = open(src_file, 'r').read()
                output = jinja2.Template(content).render(env_vars)
                open(jinja_dst_file, 'w+').write(output)
                click.echo('[J] ' + jinja_dst_file)
            else:
                shutil.copyfile(src_file, dst_file)
                click.echo('[ ] ' + dst_file)
