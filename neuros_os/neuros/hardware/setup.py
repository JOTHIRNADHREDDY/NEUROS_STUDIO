from setuptools import setup, find_packages
setup(
    name="neuros-core",
    version="0.1.0",
    packages=find_packages(),
    install_requires=["pyserial>=3.5","rich>=13.0","click>=8.1"],
    entry_points={"console_scripts":["neuros=neuros.cli.main:cli"]},
)
