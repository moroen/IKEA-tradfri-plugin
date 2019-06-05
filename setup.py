from setuptools import setup

setup(
    name='IKEA-Tradfri-plugin',
    version='0.0.1',
    url='https://github.com/moroen/IKEA-Tradfri-plugin',
    author='moroen',
    author_email='moroen@gmail.com',
    description='Controlling IKEA-Tradfri from Domoticz',
    packages=[],
    dependency_links=['http://github.com/moroen/ikea-tradfri/tarball/development#egg=ikeatradfri-0.0.1'],
    include_package_data=True,
    setup_requires=['Cython'],
    install_requires=['ikeatradfri==0.0.1'],
    scripts=[],
)
