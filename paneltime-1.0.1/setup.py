"""A setuptools based setup module.
See:
https://packaging.python.org/en/latest/distributing.html
https://github.com/pypa/sampleproject
"""

# Always prefer setuptools over distutils
import numpy as np
from setuptools import setup, find_packages,Extension
# To use a consistent encoding
from codecs import open
from os import path

here = path.abspath(path.dirname(__file__))

# Get the long description from the README file
with open(path.join(here, 'README.rst'), encoding='utf-8') as f:
	long_description = f.read()
print (find_packages(exclude=['contrib', 'docs', 'tests']))

cfunctions = Extension('cfunctions',
#        define_macros=[('FOO', '1')],
include_dirs=[np.get_include()],
library_dirs=[],
libraries=[],
sources=['paneltime/cfunctions.cpp'])

setup(
    name='paneltime',

    # Versions should comply with PEP440.  For a discussion on single-sourcing
    # the version across setup.py and the project code, see
    # https://packaging.python.org/en/latest/single_source_version.html
    version='1.0.1',

    description='An efficient integrated panel and GARCH estimator',
    long_description=long_description,

    # The project's main homepage.
    url='https://github.com/espensirnes/paneltime',

    # Author details
    author='Espen Sirnes',
    author_email='espen.sirnes@uit.no',

    # Choose your license
    license='GPL-3.0',

    # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        # How mature is this project? Common values are
        #   3 - Alpha
        #   4 - Beta
        #   5 - Production/Stable
        'Development Status :: 4 - Beta',

        # Indicate who your project is intended for
        'Intended Audience :: Researchers',
        'Topic :: Statistical Software :: time series estimation',

        # Pick your license as you wish (should match "license" above)
        'License :: OSI Approved :: GPL-3.0 License',

        # Specify the Python versions you support here. In particular, ensure
        # that you indicate whether you support Python 2, Python 3 or both.
        'Programming Language :: Python :: 3.5',
        ],

    # What does your project relate to?
    keywords='econometrics',

    # You can just specify the packages manually here if your project is
    # simple. Or you can use find_packages().
    packages=find_packages(exclude=['contrib', 'docs', 'tests']),
    
    # Alternatively, if you want to distribute just a my_module.py, uncomment
    # this:
    #   py_modules=["my_module"],

    # List run-time dependencies here.  These will be installed by pip when
    # your project is installed. For an analysis of "install_requires" vs pip's
    # requirements files see:
    # https://packaging.python.org/en/latest/requirements.html
    #**************************************************************************REMOVED>
    install_requires=['numpy >= 1.11','scipy','matplotlib',],
    #**************************************************************************<REMOVED

    # List additional groups of dependencies here (e.g. development
    # dependencies). You can install these using the following syntax,
    # for example:
    # $ pip install -e .[dev,test]
    #**************************************************************************REMOVED>
    # extras_require={
    #     'dev': ['check-manifest'],
    #     'test': ['coverage'],
    #     },
    #**************************************************************************<REMOVED 
    #
    # If there are data files included in your packages that need to be
    # installed, specify them here.  If using Python 2.6 or less, then these
    # have to be included in MANIFEST.in as well.
    #**************************************************************************REMOVED>
    #package_data={
    #    'sample': ['package_data.dat'],
    #    },
    #**************************************************************************<REMOVED
    #
    # Although 'package_data' is the preferred approach, in some case you may
    # need to place data files outside of your packages. See:
    # http://docs.python.org/3.4/distutils/setupscript.html#installing-additional-files # noqa
    # In this case, 'data_file' will be installed into '<sys.prefix>/my_data'
    #**************************************************************************REMOVED>
    #data_files=[('my_data', ['data/data_file'])],
    #**************************************************************************<REMOVED
    # To provide executable scripts, use entry points in preference to the
    # "scripts" keyword. Entry points provide cross-platform support and allow
    # pip to create the appropriate form of executable for the target platform.
    ext_modules=[cfunctions],
    entry_points={
        'console_scripts': [
            'paneltime=paneltime:main',
            ],
        },
)