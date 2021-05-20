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


def load_env(filepaths, target_vars, inject_env):
    env_content = inject_env
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


def convert_file(src_file, dst_file, env_vars):
    dst_dir = os.path.dirname(dst_file)
    if not os.path.isdir(dst_dir):
        os.makedirs(dst_dir)
    jinja_dst_file, ext = os.path.splitext(dst_file)
    if ext.lower() in dot_jinjas:
        content = open(src_file, 'r').read()
        output = jinja2.Template(content).render(env_vars)
        open(jinja_dst_file, 'w+').write(output)
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

    inject_env = ''
    for key, value in os.environ.items():
        if key.startswith("GJ_"):
            inject_env += "{key}={value}\n".format(key=key[3:], value=value)

    if os.path.isdir(env):
        for parent, dirnames, filenames in os.walk(env):
            filenames.sort()
            load_env(map(lambda f: os.path.join(
                parent, f), filenames), env_vars, inject_env)
    elif os.path.isfile(env):
        load_env([env], env_vars, inject_env)

    path_var_regex = re.compile(r'\$(\w+)')
    multiple_vars = {}
    for subdir, dirnames, filenames in os.walk(src):
        for filename in filenames:
            src_file = os.path.join(subdir, filename)
            for filename in filenames:
                jinja_filename, ext = os.path.splitext(filename)
                if ext.lower() in dot_jinjas:
                    if jinja_filename in dot_multiples:
                        with open(src_file, encoding='utf8') as f:
                            vars = yaml.load(jinja2.Template(
                                f.read()).render(env_vars), Loader=yaml.FullLoader)
                            multiple_vars[subdir] = vars
                        break
                elif filename in dot_multiples:
                    with open(src_file, encoding='utf8') as f:
                        jinja_content = f.read()
                        yaml_content = jinja2.Template(
                            jinja_content).render(env_vars)
                        vars = yaml.load(yaml_content, Loader=yaml.FullLoader)
                        multiple_vars[subdir] = vars
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
