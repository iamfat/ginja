import os
import click
import jinja2
import shutil

from dotenv import dotenv_values

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
    env_vars = dotenv_values(env)
    for subdir, dirs, files in os.walk(src):
        for filename in files:
            src_file = os.path.join(subdir, filename)
            dst_file = os.path.join(dst, os.path.relpath(subdir, src), filename)
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

if __name__ == "__main__":
    cli()
