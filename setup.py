"""Setup"""

import setuptools

with open("README.md", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="progbg",
    version="0.3",
    author="Kenneth R Hancock",
    author_email="krhancoc@uwaterloo.ca",
    license="MIT",
    description="A programmable way help quickly run and produce benchmarks and create graphs",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/krhancoc/progbg",
    packages=setuptools.find_packages(),
    include_package_data=True,
    keywords=["benchmark", "graph"],
    classifiers=[
        "Programming Language :: Python :: 3",
        "Topic :: System :: Benchmark",
        "Operating System :: OS Independent",
    ],
    install_requires=["numpy", "matplotlib", "flask", "pandas"],
    python_requires=">=3.8",
    entry_points={
        "console_scripts": ["progbg=progbg.__main__:main"],
    },
)
