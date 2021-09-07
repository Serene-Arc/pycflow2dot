"""Installation script."""
from setuptools import setup
from pkg_resources import parse_version


NAME = 'pycflow2dot'
DESCRIPTION = (
    'Create C call graphs from multiple source files '
    'using Cflow, producing linked PDF.')
with open('README.md') as f:
    long_description = f.read()
url = f'https://github.com/johnyf/{NAME}'
PROJECT_URLS = {
    'Bug Tracker': 'https://github.com/johnyf/pycflow2dot/issues',
    'Examples': 'https://github.com/johnyf/pycflow2dot/tree/main/examples'}
VERSION_FILE = f'{NAME}/_version.py'
MAJOR = 0
MINOR = 2
MICRO = 4
VERSION = f'{MAJOR}.{MINOR}.{MICRO}'
VERSION_TEXT = (
    '# This file was generated from setup.py\n'
    "version = '{version}'\n")
PYTHON_REQUIRES = '>= 3.9'
INSTALL_REQUIRES = [
    'networkx >= 2.0',
    'pydot >= 1.2.3']
TESTS_REQUIRE = ['pytest >= 6.2.5']
CLASSIFIERS = [
    'Development Status :: 2 - Pre-Alpha',
    'Intended Audience :: Developers',
    ('License :: OSI Approved :: '
     'GNU General Public License v3 or later (GPLv3+)'),
    'Operating System :: OS Independent',
    'Programming Language :: Python',
    'Programming Language :: Python :: 3 :: Only',
    'Programming Language :: Python :: 3.9',
    'Programming Language :: Python :: 3.10',
    'Topic :: Software Development']
KEYWORDS = [
    'c', 'call graph', 'control flow', 'dot',
    'latex', 'cflow']


def git_version(version):
    """Return version with local version identifier."""
    import git
    repo = git.Repo('.git')
    repo.git.status()
    # assert versions are increasing
    latest_tag = repo.git.describe(
        match='v[0-9]*', tags=True, abbrev=0)
    assert parse_version(latest_tag) <= parse_version(version), (
        latest_tag, version)
    sha = repo.head.commit.hexsha
    if repo.is_dirty():
        return f'{version}.dev0+{sha}.dirty'
    # commit is clean
    # is it release of `version` ?
    try:
        tag = repo.git.describe(
            match='v[0-9]*', exact_match=True,
            tags=True, dirty=True)
    except git.GitCommandError:
        return f'{version}.dev0+{sha}'
    assert tag == 'v' + version, (tag, version)
    return version


def run_setup():
    # version
    try:
        version = git_version(VERSION)
    except:
        print('No git info: Assume release.')
        version = VERSION
    s = VERSION_TEXT.format(version=version)
    with open(VERSION_FILE, 'w') as f:
        f.write(s)
    setup(
        name=NAME,
        version=version,
        description=DESCRIPTION,
        long_description=long_description,
        long_description_content_type='text/markdown',
        author='Ioannis Filippidis',
        author_email='jfilippidis@gmail.com',
        url=url,
        project_urls=PROJECT_URLS,
        license='GPLv3',
        python_requires=PYTHON_REQUIRES,
        install_requires=INSTALL_REQUIRES,
        tests_require=TESTS_REQUIRE,
        packages=[NAME],
        package_dir={NAME: NAME},
        entry_points={
            'console_scripts': ['cflow2dot = pycflow2dot.pycflow2dot:main']},
        classifiers=CLASSIFIERS,
        keywords=KEYWORDS)


if __name__ == '__main__':
    run_setup()
