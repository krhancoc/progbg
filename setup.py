"""Setup"""

import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
        name="progbg",
        version="0.0.1",
        author="Ryan Hancock",
        author_email="krhancoc@uwaterloo.ca",
        license='MIT',
        description="A programmable way help quickly run and produce benchmarks and create graphs",
        long_description_content_type="text/markdown",
        url="https://github.com/krhancoc/progbg",
        packages=setuptools.find_packages(),
        include_package_data=True,
        keywords=['benchmark', 'graph'],
        classifiers=[
            "Programming Language :: Python :: 3",
            "Topic :: System :: Benchmark",
            "Operating System :: OS Independent",
        ],
        install_requires=['numpy','matplotlib','flask'],
        python_requires='>=3.8',
        entry_points={
            'console_scripts': [
                'progbg=progbg.__main__:main'
            ],
        }
)
